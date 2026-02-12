"""Predictor Agent - Predicts wait times with calibrated confidence."""

from typing import Any

from .base import ActionScope, BaseAgent, ToolResult, determine_action_scope


class PredictorAgent(BaseAgent):
    """
    Predictor Agent for VGAC GPU job scheduling.

    Responsibilities:
    - Predict when GPU jobs will start running
    - Provide confidence scores with predictions
    - Check calibration before making predictions
    - Communicate uncertainty when calibration is low
    """

    def __init__(self) -> None:
        super().__init__(
            name="PredictorAgent",
            description="Predicts wait times with calibration-aware confidence",
        )

    @property
    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "tool_predict_wait_time",
                "description": "Predict when a GPU job will start running",
                "parameters": {
                    "job_id": {"type": "string", "description": "Job identifier"},
                    "cluster_id": {"type": "string", "description": "Target cluster"},
                },
            },
            {
                "name": "tool_get_calibration_score",
                "description": "Get current calibration score (ECE) for a cluster",
                "parameters": {
                    "cluster_id": {"type": "string", "description": "Cluster identifier"}
                },
            },
            {
                "name": "tool_get_environment_profile",
                "description": "Get historical prediction accuracy for a cluster",
                "parameters": {
                    "cluster_id": {"type": "string", "description": "Cluster identifier"}
                },
            },
        ]

    @property
    def system_prompt(self) -> str:
        return """You are the Predictor Agent for VGAC GPU job scheduling.

Your role:
- Predict when GPU jobs will start running
- Provide confidence scores with predictions
- Check calibration before making predictions
- Communicate uncertainty when calibration is low

You have access to these tools:
- tool_predict_wait_time: Get prediction for a specific job
- tool_get_calibration_score: Check calibration for a cluster
- tool_get_environment_profile: Get historical accuracy for a cluster

CRITICAL: Always check calibration score before predicting.
- If calibration > 0.85: Provide prediction with confidence
- If calibration 0.60-0.85: Provide prediction with uncertainty flag
- If calibration < 0.60: State that predictions are unreliable for this environment"""

    async def invoke_tool(self, tool_name: str, parameters: dict[str, Any]) -> ToolResult:
        """Invoke a predictor tool."""
        # TODO: Implement tool invocations
        raise NotImplementedError(f"Tool {tool_name} not yet implemented")

    async def predict_with_calibration(
        self, job_id: str, cluster_id: str
    ) -> dict[str, Any]:
        """
        Make a prediction with calibration-aware confidence.

        This is the key method that implements confidence gating.
        """
        from .calibrator import get_calibration_state

        # Get calibration state
        calibration = await get_calibration_state(cluster_id)
        scope = determine_action_scope(calibration)

        # If we can't make reliable predictions, say so
        if scope == ActionScope.ESCALATE:
            return {
                "job_id": job_id,
                "cluster_id": cluster_id,
                "prediction": None,
                "message": "Predictions unreliable for this environment",
                "action_scope": scope.value,
                "calibration_score": calibration.score,
            }

        # TODO: Call VGAC prediction API
        # prediction = await self.vgac_client.predict(job_id, cluster_id)

        # For now, return placeholder
        return {
            "job_id": job_id,
            "cluster_id": cluster_id,
            "prediction": {"wait_time_seconds": 3600, "confidence": 0.87},
            "action_scope": scope.value,
            "calibration_score": calibration.score,
        }
