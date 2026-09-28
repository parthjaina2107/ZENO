"""
Action Planner
Converts structured NLU response dictionaries into strongly-typed PlannedAction sequences
and orchestrates execution against the TaskExecutor.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger("VoiceAgent.Planner")


@dataclass
class PlannedAction:
    action_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    risk_level: str = "medium"  # "low", "medium", "high"
    requires_permission: bool = True  # Always requires user approval
    confirmation_message: str = ""


@dataclass
class ActionResult:
    success: bool
    message: str
    output: Any = None  # e.g., base64 screenshot, file content, process list
    error: Optional[str] = None


class ActionPlanner:
    def __init__(self, executor=None):
        self.executor = executor

    def plan(self, nlu_response: Dict[str, Any]) -> List[PlannedAction]:
        """Convert NLU JSON into one or more PlannedAction instances."""
        if not nlu_response.get("understood", False):
            return [
                PlannedAction(
                    action_type="unhandled",
                    parameters=nlu_response.get("parameters", {}),
                    description=nlu_response.get("description", "Command could not be understood."),
                    risk_level="low",
                    requires_permission=False,
                    confirmation_message=nlu_response.get("confirmation_message", "I didn't understand that command.")
                )
            ]

        action_type = nlu_response.get("action", "unknown")
        raw_risk = nlu_response.get("risk_level", "medium").lower()

        # Multi-step action decomposition
        if action_type == "multi_step":
            steps = nlu_response.get("parameters", {}).get("steps", [])
            actions = []
            for i, step in enumerate(steps):
                step_action = step.get("action", "unknown")
                step_params = step.get("parameters", {})
                desc = step.get("description", f"Step {i+1}: {step_action}")
                risk = step.get("risk_level", "medium").lower()
                needs_perm = risk in ("medium", "high")
                confirm_msg = step.get("confirmation_message", f"Proceed with step {i+1}: {desc}?")
                actions.append(
                    PlannedAction(
                        action_type=step_action,
                        parameters=step_params,
                        description=desc,
                        risk_level=risk,
                        requires_permission=needs_perm,
                        confirmation_message=confirm_msg
                    )
                )
            return actions

        # Single action
        needs_perm = raw_risk in ("medium", "high")
        return [
            PlannedAction(
                action_type=action_type,
                parameters=nlu_response.get("parameters", {}),
                description=nlu_response.get("description", action_type),
                risk_level=raw_risk,
                requires_permission=needs_perm,
                confirmation_message=nlu_response.get("confirmation_message", f"Execute {action_type}?")
            )
        ]

    def execute_action(self, action: PlannedAction) -> ActionResult:
        """Dispatch a single action to the executor."""
        if not self.executor:
            return ActionResult(success=False, message="No executor configured.", error="MISSING_EXECUTOR")

        return self.executor.execute(action)

    def execute_plan(self, plan: List[PlannedAction]) -> List[ActionResult]:
        """Execute a list of planned actions sequentially."""
        results = []
        for action in plan:
            res = self.execute_action(action)
            results.append(res)
            # If an intermediate step fails, stop sequential multi-step execution
            if not res.success:
                logger.warning(f"Stopping multi-step execution due to failure in '{action.action_type}': {res.error}")
                break
        return results
