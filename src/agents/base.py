"""Base agent class and shared patterns for VGAC agents."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActionScope(str, Enum):
    """Determines what actions an agent can take based on calibration."""

    AUTONOMOUS = "autonomous"  # Act without human approval
    NOTIFY = "notify"  # Act and notify human
    ESCALATE = "escalate"  # Don't act, ask human


class CalibrationState(BaseModel):
    """Current calibration state for an environment."""

    cluster_id: str
    score: float = Field(ge=0.0, le=1.0, description="Calibration score (0-1, higher is better)")
    sample_count: int = Field(ge=0, description="Number of samples used for calibration")
    last_updated: datetime
    is_learning_mode: bool = Field(
        default=False, description="True if sample_count < 50 (new environment)"
    )
    recalibration_needed: bool = False


class ToolResult(BaseModel):
    """Result from a tool invocation."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


def determine_action_scope(calibration: CalibrationState) -> ActionScope:
    """
    Determine what actions an agent can take based on calibration.

    This implements the confidence-gating pattern that differentiates VGAC
    from other AI agents. Thresholds align with existing VGAC policy generator
    (0.6 confidence threshold).

    Args:
        calibration: Current calibration state for the environment

    Returns:
        ActionScope indicating what level of autonomy is appropriate
    """
    # New environment - still learning
    if calibration.sample_count < 50 or calibration.is_learning_mode:
        return ActionScope.ESCALATE

    # Well-calibrated - full autonomy
    if calibration.score > 0.85:
        return ActionScope.AUTONOMOUS

    # Moderate calibration - act but notify
    if calibration.score > 0.60:
        return ActionScope.NOTIFY

    # Poor calibration - escalate
    return ActionScope.ESCALATE


class BaseAgent(ABC):
    """
    Base class for all VGAC agents.

    Agents wrap existing VGAC functionality and add calibration-aware
    decision making. They do not replace VGAC's core prediction/policy
    logic - they orchestrate it with confidence gating.
    """

    def __init__(self, name: str, description: str) -> None:
        """
        Initialize the agent.

        Args:
            name: Agent name (e.g., "PredictorAgent")
            description: What this agent does
        """
        self.name = name
        self.description = description

    @property
    @abstractmethod
    def tools(self) -> list[dict[str, Any]]:
        """
        Define the tools this agent can use.

        Returns:
            List of tool definitions in Bedrock AgentCore format
        """
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """
        System prompt that defines this agent's behavior.

        Returns:
            System prompt string
        """
        ...

    @abstractmethod
    async def invoke_tool(self, tool_name: str, parameters: dict[str, Any]) -> ToolResult:
        """
        Invoke a tool by name with given parameters.

        Args:
            tool_name: Name of the tool to invoke
            parameters: Parameters to pass to the tool

        Returns:
            ToolResult with success status and data or error
        """
        ...

    async def check_action_scope(self, cluster_id: str) -> ActionScope:
        """
        Check what actions are allowed for a given cluster.

        Args:
            cluster_id: The cluster to check

        Returns:
            ActionScope indicating allowed autonomy level
        """
        # This will be implemented by subclasses or via dependency injection
        # For now, return a conservative default
        from .calibrator import get_calibration_state

        calibration = await get_calibration_state(cluster_id)
        return determine_action_scope(calibration)


class AgentResponse(BaseModel):
    """Response from an agent invocation."""

    agent_name: str
    success: bool
    message: str
    action_taken: str | None = None
    action_scope: ActionScope
    calibration_score: float | None = None
    data: dict[str, Any] | None = None
    error: str | None = None
