"""
Action Planner
Converts structured NLU response dictionaries into strongly-typed PlannedAction sequences
and orchestrates execution against the TaskExecutor.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel, Field, conint, ValidationError
from config import config

logger = logging.getLogger("VoiceAgent.Planner")


# === Parameter Validation Models ===

class SystemInfoParams(BaseModel):
    type: str = "battery"

class ScreenshotParams(BaseModel):
    pass

class ListAppsParams(BaseModel):
    pass

class OpenAppParams(BaseModel):
    app_name: str = Field(..., min_length=1)

class CloseAppParams(BaseModel):
    process_name: str = Field(..., min_length=1)

class OpenUrlParams(BaseModel):
    url: str = Field(..., min_length=1)

class WebSearchParams(BaseModel):
    query: str = Field(..., min_length=1)

class VolumeParams(BaseModel):
    level: conint(ge=0, le=100)

class TypeTextParams(BaseModel):
    text: str = Field(..., min_length=1)

class KeyboardShortcutParams(BaseModel):
    keys: List[str] = Field(..., min_length=1)

class MouseClickParams(BaseModel):
    x: int = 0
    y: int = 0
    button: str = "left"

class FileCreateParams(BaseModel):
    path: str = Field(..., min_length=1)
    content: str = ""

class FileDeleteParams(BaseModel):
    path: str = Field(..., min_length=1)

class FileMoveParams(BaseModel):
    source: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)

class FileCopyParams(BaseModel):
    source: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)

class FileSearchParams(BaseModel):
    directory: str = "Desktop"
    pattern: str = "*"

class FileReadParams(BaseModel):
    path: str = Field(..., min_length=1)

class RunCommandParams(BaseModel):
    command: str = Field(..., min_length=1)

class ShutdownParams(BaseModel):
    mode: str = "lock"


ACTION_PARAM_MODELS: Dict[str, Type[BaseModel]] = {
    "system_info": SystemInfoParams,
    "screenshot": ScreenshotParams,
    "list_apps": ListAppsParams,
    "open_app": OpenAppParams,
    "close_app": CloseAppParams,
    "open_url": OpenUrlParams,
    "web_search": WebSearchParams,
    "volume_set": VolumeParams,
    "type_text": TypeTextParams,
    "keyboard_shortcut": KeyboardShortcutParams,
    "mouse_click": MouseClickParams,
    "file_create": FileCreateParams,
    "file_delete": FileDeleteParams,
    "file_move": FileMoveParams,
    "file_copy": FileCopyParams,
    "file_search": FileSearchParams,
    "file_read": FileReadParams,
    "run_command": RunCommandParams,
    "shutdown": ShutdownParams,
}


def validate_action_params(action_type: str, raw_params: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Validate parameters using Pydantic model. Returns (validated_dict, error_string)."""
    model_cls = ACTION_PARAM_MODELS.get(action_type)
    if not model_cls:
        return raw_params, None
    try:
        instance = model_cls(**(raw_params or {}))
        return instance.model_dump(), None
    except ValidationError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


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


def describe_action(action: PlannedAction) -> str:
    """Build a deterministic, human-readable description from the action's real parameters."""
    act_type = action.action_type
    params = action.parameters or {}

    if act_type == "run_command":
        cmd = params.get("command", "")
        return f'Run command: "{cmd}"'
    elif act_type == "file_delete":
        path = params.get("path", "")
        return f'Delete file: "{path}"'
    elif act_type == "file_create":
        path = params.get("path", "")
        return f'Create file: "{path}"'
    elif act_type == "file_move":
        src = params.get("source", "")
        dst = params.get("destination", "")
        return f'Move file: from "{src}" to "{dst}"'
    elif act_type == "file_copy":
        src = params.get("source", "")
        dst = params.get("destination", "")
        return f'Copy file: from "{src}" to "{dst}"'
    elif act_type == "file_read":
        path = params.get("path", "")
        return f'Read file: "{path}"'
    elif act_type == "file_search":
        directory = params.get("directory", "Desktop")
        pattern = params.get("pattern", "*")
        return f'Search files in "{directory}" matching "{pattern}"'
    elif act_type == "type_text":
        txt = params.get("text", "")
        return f'Type text: "{txt}"'
    elif act_type == "keyboard_shortcut":
        keys = params.get("keys", [])
        return f'Press shortcut: {", ".join(keys)}'
    elif act_type == "mouse_click":
        x = params.get("x", 0)
        y = params.get("y", 0)
        btn = params.get("button", "left")
        return f'Click {btn} mouse button at ({x}, {y})'
    elif act_type == "open_app":
        app = params.get("app_name", "")
        return f'Open application: "{app}"'
    elif act_type == "close_app":
        proc = params.get("process_name", "")
        return f'Close application: "{proc}"'
    elif act_type == "open_url":
        url = params.get("url", "")
        return f'Open URL: "{url}"'
    elif act_type == "web_search":
        query = params.get("query", "")
        return f'Search web for: "{query}"'
    elif act_type == "volume_set":
        lvl = params.get("level", 50)
        return f'Set volume to {lvl}%'
    elif act_type == "system_info":
        info_type = params.get("type", "battery")
        return f'Get system info: {info_type}'
    elif act_type == "screenshot":
        return "Take screenshot"
    elif act_type == "list_apps":
        return "List running applications"
    elif act_type == "shutdown":
        mode = params.get("mode", "lock")
        return f'System {mode}'
    elif act_type == "unhandled":
        return action.description or "Unhandled action"
    else:
        return f'{act_type.replace("_", " ").capitalize()}: {params}'


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
                validated_params, val_err = validate_action_params(step_action, step_params)
                if val_err:
                    actions.append(
                        PlannedAction(
                            action_type="unhandled",
                            parameters=step_params,
                            description=f"Step {i+1}: Invalid parameters for '{step_action}': {val_err}",
                            risk_level="high",
                            requires_permission=False,
                            confirmation_message=f"Step {i+1} action '{step_action}' has invalid parameters."
                        )
                    )
                    continue

                desc = step.get("description", f"Step {i+1}: {step_action}")
                step_llm_risk = step.get("risk_level", "medium").lower()
                step_table_risk = config.ACTION_RISK.get(step_action, "high")
                step_risk = max_risk(step_table_risk, step_llm_risk)
                needs_perm = step_risk in ("low", "medium", "high")
                confirm_msg = step.get("confirmation_message", f"Proceed with step {i+1}: {desc}?")
                step_obj = PlannedAction(
                    action_type=step_action,
                    parameters=validated_params,
                    description=desc,
                    risk_level=step_risk,
                    requires_permission=needs_perm,
                    confirmation_message=confirm_msg
                )
                if step_risk in ("medium", "high"):
                    step_obj.confirmation_message = describe_action(step_obj)
                actions.append(step_obj)
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

        raw_params = nlu_response.get("parameters", {})
        validated_params, val_err = validate_action_params(action_type, raw_params)
        if val_err:
            return [
                PlannedAction(
                    action_type="unhandled",
                    parameters=raw_params,
                    description=f"Invalid parameters for '{action_type}': {val_err}",
                    risk_level="high",
                    requires_permission=False,
                    confirmation_message=f"Invalid parameters for action '{action_type}'."
                )
            ]

        # Single action: enforce baseline table risk
        table_risk = config.ACTION_RISK.get(action_type, "high")
        computed_risk = max_risk(table_risk, raw_risk)
        needs_perm = computed_risk in ("low", "medium", "high")

        act_obj = PlannedAction(
            action_type=action_type,
            parameters=validated_params,
            description=nlu_response.get("description", action_type),
            risk_level=computed_risk,
            requires_permission=needs_perm,
            confirmation_message=nlu_response.get("confirmation_message", f"Execute {action_type}?")
        )
        if computed_risk in ("medium", "high"):
            act_obj.confirmation_message = describe_action(act_obj)

        return [act_obj]

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
