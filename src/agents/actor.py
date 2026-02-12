"""Actor Agent - Takes actions based on predictions and calibration."""

from typing import Any

from .base import ActionScope, BaseAgent, ToolResult, determine_action_scope


class ActorAgent(BaseAgent):
    """
    Actor Agent for VGAC GPU infrastructure.

    Responsibilities:
    - Take actions based on predictions (notify users, adjust queues)
    - Gate actions based on calibration confidence
    - Escalate to humans when confidence is low
    """

    def __init__(self) -> None:
        super().__init__(
            name="ActorAgent",
            description="Takes calibration-gated actions based on predictions",
        )

    @property
    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "tool_send_slack_notification",
                "description": "Send a notification to a Slack channel or user",
                "parameters": {
                    "channel": {"type": "string", "description": "Slack channel or user ID"},
                    "message": {"type": "string", "description": "Notification message"},
                },
            },
            {
                "name": "tool_requeue_job",
                "description": "Move a job to a different queue or cluster",
                "parameters": {
                    "job_id": {"type": "string", "description": "Job identifier"},
                    "target_queue": {"type": "string", "description": "Target queue name"},
                },
            },
            {
                "name": "tool_adjust_priority",
                "description": "Change the priority of a job",
                "parameters": {
                    "job_id": {"type": "string", "description": "Job identifier"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "critical"],
                    },
                },
            },
            {
                "name": "tool_create_alert",
                "description": "Create an operational alert",
                "parameters": {
                    "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
                    "message": {"type": "string", "description": "Alert message"},
                },
            },
            {
                "name": "tool_escalate_to_human",
                "description": "Flag a situation for human review",
                "parameters": {
                    "reason": {"type": "string", "description": "Why escalation is needed"},
                    "context": {"type": "object", "description": "Relevant context data"},
                },
            },
        ]

    @property
    def system_prompt(self) -> str:
        return """You are the Actor Agent for VGAC GPU infrastructure.

Your role:
- Take actions based on predictions (notify users, adjust queues)
- Gate actions based on calibration confidence
- Escalate to humans when confidence is low

You have access to these tools:
- tool_send_slack_notification: Notify users via Slack
- tool_requeue_job: Move a job to a different queue
- tool_adjust_priority: Change job priority
- tool_create_alert: Create a PagerDuty/ops alert
- tool_escalate_to_human: Flag for human review

ACTION GATING RULES (strictly follow):
1. If calibration > 0.85: Execute actions autonomously
2. If calibration 0.60-0.85: Execute action AND notify human
3. If calibration < 0.60: Do NOT execute action, only escalate to human

Never take autonomous action when calibration is below 0.60."""

    async def invoke_tool(self, tool_name: str, parameters: dict[str, Any]) -> ToolResult:
        """Invoke an actor tool."""
        # TODO: Implement tool invocations
        raise NotImplementedError(f"Tool {tool_name} not yet implemented")

    async def execute_with_gating(
        self,
        cluster_id: str,
        action: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute an action with calibration gating.

        This is the key method that implements confidence-gated actions.
        """
        from .calibrator import get_calibration_state

        # Get calibration state
        calibration = await get_calibration_state(cluster_id)
        scope = determine_action_scope(calibration)

        # Handle based on action scope
        if scope == ActionScope.ESCALATE:
            # Don't execute, escalate to human
            await self.invoke_tool(
                "tool_escalate_to_human",
                {
                    "reason": f"Low calibration ({calibration.score:.2f}) for cluster {cluster_id}",
                    "context": {"action": action, "parameters": parameters},
                },
            )
            return {
                "executed": False,
                "reason": "Escalated to human due to low calibration",
                "action_scope": scope.value,
            }

        if scope == ActionScope.NOTIFY:
            # Execute and notify human
            result = await self.invoke_tool(action, parameters)
            await self.invoke_tool(
                "tool_send_slack_notification",
                {
                    "channel": "#gpu-alerts",
                    "message": f"⚠️ Action taken with moderate confidence: {action}",
                },
            )
            return {
                "executed": True,
                "result": result,
                "notified_human": True,
                "action_scope": scope.value,
            }

        # AUTONOMOUS - execute without notification
        result = await self.invoke_tool(action, parameters)
        return {
            "executed": True,
            "result": result,
            "notified_human": False,
            "action_scope": scope.value,
        }
