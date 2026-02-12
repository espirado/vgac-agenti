"""Observer Agent - Watches cluster state and detects anomalies."""

from typing import Any

from .base import BaseAgent, ToolResult


class ObserverAgent(BaseAgent):
    """
    Observer Agent for VGAC GPU infrastructure monitoring.

    Responsibilities:
    - Monitor GPU cluster state across environments (K8s, Slurm, AWS Batch)
    - Detect anomalies (unusual queue depth, GPU utilization spikes)
    - Provide current state to other agents when requested
    """

    def __init__(self) -> None:
        super().__init__(
            name="ObserverAgent",
            description="Watches cluster state, detects anomalies, provides situational awareness",
        )

    @property
    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "tool_get_cluster_state",
                "description": "Get current state of a GPU cluster including utilization, queue depth, and node status",
                "parameters": {
                    "cluster_id": {"type": "string", "description": "Cluster identifier"}
                },
            },
            {
                "name": "tool_get_queue_depth",
                "description": "Get number of jobs waiting in queue",
                "parameters": {
                    "cluster_id": {"type": "string", "description": "Cluster identifier"}
                },
            },
            {
                "name": "tool_detect_anomaly",
                "description": "Check if current cluster state is anomalous compared to historical patterns",
                "parameters": {
                    "cluster_id": {"type": "string", "description": "Cluster identifier"},
                    "metric": {
                        "type": "string",
                        "enum": ["queue_depth", "gpu_util", "memory"],
                    },
                },
            },
        ]

    @property
    def system_prompt(self) -> str:
        return """You are the Observer Agent for VGAC GPU infrastructure monitoring.

Your role:
- Monitor GPU cluster state across environments (K8s, Slurm, AWS Batch)
- Detect anomalies (unusual queue depth, GPU utilization spikes)
- Provide current state to other agents when requested

You have access to these tools:
- tool_get_cluster_state: Get current cluster metrics
- tool_get_queue_depth: Get number of pending jobs
- tool_detect_anomaly: Check if current state is anomalous

Always report facts. Do not make predictions (that's PredictorAgent's job)."""

    async def invoke_tool(self, tool_name: str, parameters: dict[str, Any]) -> ToolResult:
        """Invoke an observer tool."""
        # TODO: Implement tool invocations
        # These will call VGAC API endpoints
        raise NotImplementedError(f"Tool {tool_name} not yet implemented")
