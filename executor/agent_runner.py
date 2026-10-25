"""Shared local/remote task runner with bounded planning, approvals and cancellation."""

import asyncio
import copy
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from config import config
from brain.planner import PlannedAction, describe_action, compute_action_id


@dataclass
class TaskRun:
    goal: str
    source: str
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cancelled: threading.Event = field(default_factory=threading.Event)
    observations: list = field(default_factory=list)
    started: float = field(default_factory=time.monotonic)


class TaskCoordinator:
    """One desktop owner across asyncio loops and local/server threads."""
    def __init__(self):
        self._lock = threading.Lock()
        self.active = None

    def begin(self, run):
        with self._lock:
            if self.active is not None:
                return False
            self.active = run
            return True

    def stop(self, source=None):
        with self._lock:
            if self.active and (source is None or self.active.source == source):
                self.active.cancelled.set()

    def finish(self, run):
        with self._lock:
            if self.active is run:
                self.active = None


coordinator = TaskCoordinator()


class AgentRunner:
    def __init__(self, brain, permissions, source, approve, emit):
        self.brain, self.permissions = brain, permissions
        self.source, self.approve, self.emit = source, approve, emit

    async def run(self, goal, actions=None, agent_mode=False):
        run = TaskRun(goal, self.source)
        if not coordinator.begin(run):
            await self.emit({"type": "response", "message": "ZENO is busy with another task. Stop it or wait for completion."})
            return
        terminal_status = "failed"
        terminal_message = "Task failed."
        async def event(status, message, **extra):
            if agent_mode:
                await self.emit({"type": "task_progress", "task_id": run.task_id, "status": status,
                                 "message": message, "completed": len(run.observations), **extra})

        async def guarded(awaitable):
            """Cancel planning/permission waits promptly without blocking socket input."""
            pending = asyncio.ensure_future(awaitable)
            try:
                while not pending.done():
                    if run.cancelled.is_set():
                        raise asyncio.CancelledError
                    if time.monotonic() - run.started > config.AGENT_TIMEOUT:
                        raise TimeoutError("Task time limit reached.")
                    await asyncio.wait({pending}, timeout=0.05)
                if run.cancelled.is_set():
                    raise asyncio.CancelledError
                return await pending
            finally:
                if not pending.done():
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)

        try:
            seen = set()
            rounds = config.AGENT_MAX_ROUNDS if agent_mode else 1
            for round_index in range(rounds):
                if run.cancelled.is_set():
                    raise asyncio.CancelledError
                if agent_mode:
                    await event("planning", "Planning the next steps from actual results…")
                    decision = await guarded(self.brain.goal_planner.decide(goal, run.observations))
                    if decision.status != "plan":
                        terminal_status = {"done": "completed", "clarify": "needs_input", "blocked": "blocked"}[decision.status]
                        terminal_message = decision.message
                        break
                    actions = self.brain.goal_planner.actions(decision)
                actions = copy.deepcopy(actions or [])
                # Preflight the ENTIRE phase before any side effect.
                if not actions or any(a.action_type in ("unknown", "unhandled") for a in actions):
                    terminal_message = next((a.confirmation_message for a in actions if a.action_type == "unhandled"), "The task has no executable steps.")
                    await self.emit({"type": "response", "message": terminal_message})
                    break
                if len(run.observations) + len(actions) > config.AGENT_MAX_STEPS:
                    terminal_message = "Task step limit reached. No further actions were run."
                    break
                if agent_mode and any(a.action_id in seen for a in actions):
                    terminal_message = "The planner repeated an attempted step. Stopped to avoid duplicate actions."
                    break
                await event("planned", "Task plan ready.", steps=[describe_action(a) for a in actions])

                def automatic(a):
                    allowed = config.AGENT_AUTO_ACTIONS if agent_mode else config.AUTO_APPROVE_ACTIONS
                    return a.risk_level == "low" and a.action_type in allowed

                # Approve a concrete phase once. High-risk operations retain double confirmation.
                batch_ids = set()
                batch = [a for a in actions if not automatic(a) and a.risk_level != "high"]
                if agent_mode and batch:
                    request = PlannedAction("task_plan", {"steps": [
                        {"action": a.action_type, "parameters": a.parameters} for a in batch
                    ]}, description="Approve the planned task steps", risk_level="medium")
                    await event("awaiting_approval", "Review the exact steps before ZENO continues.")
                    if not await guarded(self.approve(request)):
                        terminal_status, terminal_message = "cancelled", "Task cancelled: plan was denied or timed out."
                        break
                    batch_ids = {a.action_id for a in batch}
                failed = False
                for action in actions:
                    if run.cancelled.is_set():
                        raise asyncio.CancelledError
                    if time.monotonic() - run.started > config.AGENT_TIMEOUT:
                        raise TimeoutError("Task time limit reached.")
                    # Never trust a mutable or stale approval fingerprint.
                    if action.action_id != compute_action_id(action.action_type, action.parameters):
                        raise ValueError("Action parameters changed after planning.")
                    if automatic(action) or action.action_id in batch_ids:
                        self.permissions.log_decision(action, True, source=self.source,
                                                      reason="Task plan approved" if action.action_id in batch_ids else "Allowed by action policy")
                    elif action.requires_permission:
                        if not await guarded(self.approve(action)):
                            terminal_status, terminal_message = "cancelled", "Task cancelled: action was denied or timed out."
                            await self.emit({"type": "response", "message": terminal_message, "kind": "cancelled"})
                            return
                    if run.cancelled.is_set():
                        raise asyncio.CancelledError
                    await event("running", describe_action(action), step=len(run.observations) + 1)
                    seen.add(action.action_id)
                    # A thread cannot be force-killed. Retain desktop ownership until it returns,
                    # and never start the next action after cancellation.
                    worker = asyncio.create_task(asyncio.to_thread(self.brain.planner.execute_action, action))
                    try:
                        result = await asyncio.shield(worker)
                    except asyncio.CancelledError:
                        run.cancelled.set()
                        while not worker.done():
                            try:
                                await asyncio.shield(worker)
                            except asyncio.CancelledError:
                                continue
                        self.permissions.log_result(action, worker.result(), source=self.source)
                        raise
                    self.permissions.log_result(action, result, source=self.source)
                    output = result.output
                    if action.action_type == "screenshot":
                        output = {"captured": result.success}  # No image/base64 in model history.
                    serialized = json.dumps(output, default=str, ensure_ascii=False)
                    run.observations.append({"action": action.action_type, "parameters": action.parameters,
                                             "success": result.success, "message": result.message,
                                             "output": serialized[:12000], "output_truncated": len(serialized) > 12000})
                    if run.cancelled.is_set():
                        raise asyncio.CancelledError
                    if action.action_type == "screenshot" and result.success and isinstance(result.output, dict):
                        await self.emit({"type": "screenshot", "data": result.output.get("base64"), "message": result.message})
                    else:
                        await self.emit({"type": "response", "message": ("✅ " if result.success else "❌ ") + result.message})
                    if not result.success:
                        failed = True
                        terminal_message = result.message
                        break  # Replan from failure; do not execute dependent steps.
                if not agent_mode:
                    terminal_status = "failed" if failed else "completed"
                    terminal_message = "Task stopped at a failed step." if failed else "All planned steps completed."
                    break
            else:
                terminal_status, terminal_message = "blocked", "Task planning limit reached. Completed steps are listed above."
        except asyncio.CancelledError:
            terminal_status, terminal_message = "cancelled", "Task stopped. No further steps will run."
        except (TimeoutError, ValueError) as exc:
            terminal_status, terminal_message = "blocked", str(exc)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Agent task failed")
            terminal_status, terminal_message = "failed", "Task failed unexpectedly. No further steps will run."
            await self.emit({"type": "response", "message": terminal_message})
        finally:
            coordinator.finish(run)
            if agent_mode:
                self.brain.memory.add_turn("user", goal)
                self.brain.memory.add_turn("zeno", terminal_message)
            await event(terminal_status, terminal_message)
