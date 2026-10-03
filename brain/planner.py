"""
Action Planner
Converts structured NLU response dictionaries into strongly-typed PlannedAction sequences
and orchestrates execution against the TaskExecutor.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from config import config

logger = logging.getLogger("VoiceAgent.Planner")


def max_risk(table_risk: str, llm_risk: str) -> str:
    """The LLM can raise risk but never lower it below the table baseline."""
    order = {"low": 1, "medium": 2, "high": 3}
    t_val = order.get(table_risk.lower(), 2)
    l_val = order.get(llm_risk.lower(), 1)
    rev_order = {1: "low", 2: "medium", 3: "high"}
    return rev_order[max(t_val, l_val)]


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
                if step_action not in getattr(config, "ACTION_RISK", {}):
                    actions.append(
                        PlannedAction(
                            action_type="unhandled",
                            parameters=step.get("parameters", {}),
                            description=f"Step {i+1}: Unsupported action '{step_action}'",
                            risk_level="high",
                            requires_permission=False,
                            confirmation_message=f"Step {i+1} action '{step_action}' is not supported."
                        )
                    )
                    continue

                step_params = step.get("parameters", {})
                desc = step.get("description", f"Step {i+1}: {step_action}")
                step_llm_risk = step.get("risk_level", "medium").lower()
                step_table_risk = config.ACTION_RISK.get(step_action, "high")
                step_risk = max_risk(step_table_risk, step_llm_risk)
                needs_perm = step_risk in ("low", "medium", "high")
                confirm_msg = step.get("confirmation_message", f"Proceed with step {i+1}: {desc}?")
                actions.append(
                    PlannedAction(
                        action_type=step_action,
                        parameters=step_params,
                        description=desc,
                        risk_level=step_risk,
                        requires_permission=needs_perm,
                        confirmation_message=confirm_msg
                    )
                )
            return actions

        # Reject unknown action types as unhandled
        if action_type not in getattr(config, "ACTION_RISK", {}):
            return [
                PlannedAction(
                    action_type="unhandled",
                    parameters=nlu_response.get("parameters", {}),
                    description=f"Unsupported action: '{action_type}'",
                    risk_level="high",
                    requires_permission=False,
                    confirmation_message=f"Action '{action_type}' is not recognized."
                )
            ]

        # Single action: enforce baseline table risk
        table_risk = config.ACTION_RISK.get(action_type, "high")
        computed_risk = max_risk(table_risk, raw_risk)
        needs_perm = computed_risk in ("low", "medium", "high")

        return [
            PlannedAction(
                action_type=action_type,
                parameters=nlu_response.get("parameters", {}),
                description=nlu_response.get("description", action_type),
                risk_level=computed_risk,
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
