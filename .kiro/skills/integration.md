# Integration Points

## Overview

The agentic layer is a SEPARATE deployment that CALLS existing VGAC APIs. It does not modify the VGAC codebase.

```
┌─────────────────────────────────────────────────────────────────┐
│                      VGAC PLATFORM                              │
│                      (existing, unchanged)                      │
│                                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │ Prediction  │  │ Collectors  │  │   Policy    │            │
│   │   Engine    │  │ (K8s/Slurm) │  │  Generator  │            │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│          │                │                │                    │
│          └────────────────┼────────────────┘                    │
│                           │                                     │
│                    FastAPI Endpoints                            │
│                    /api/v1/...                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                      HTTP/REST calls
                            │
┌───────────────────────────┴─────────────────────────────────────┐
│                    AGENTIC LAYER (this project)                 │
│                    (new AWS deployment)                         │
│                                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │   Lambda    │  │  AgentCore  │  │  DynamoDB   │            │
│   │  Functions  │  │ Orchestrator│  │   State     │            │
│   └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## VGAC Client

A thin wrapper for calling VGAC APIs:

```python
# src/vgac_client.py
import httpx
from pydantic import BaseModel
from typing import Optional
import os

class VGACConfig(BaseModel):
    base_url: str = os.getenv("VGAC_API_BASE_URL", "https://api.vgac.cloud")
    api_key: Optional[str] = os.getenv("VGAC_API_KEY")
    timeout_seconds: int = int(os.getenv("VGAC_TIMEOUT_SECONDS", "10"))

class PredictionResult(BaseModel):
    wait_time_seconds: int
    confidence: float
    risk_score: float
    calibration_score: float

class ClusterState(BaseModel):
    cluster_id: str
    platform: str
    queue_depth: int
    gpu_utilization: float
    gpu_memory_used: float
    active_jobs: int
    pending_jobs: int

class CalibrationMetrics(BaseModel):
    ece: float
    brier_score: float
    sample_count: int
    last_recalibration: str
    recalibration_needed: bool

class VGACClient:
    """Client for VGAC API calls."""
    
    def __init__(self, config: Optional[VGACConfig] = None):
        self.config = config or VGACConfig()
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            headers={"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        )
    
    async def predict(self, job_id: str, cluster_id: str) -> PredictionResult:
        """Get prediction for a job."""
        response = await self._client.post(
            "/api/v1/predict/score",
            json={"job_id": job_id, "cluster_id": cluster_id}
        )
        response.raise_for_status()
        return PredictionResult(**response.json())
    
    async def get_cluster_state(self, cluster_id: str) -> ClusterState:
        """Get current cluster state."""
        response = await self._client.get(
            f"/api/v1/cluster/state",
            params={"cluster_id": cluster_id}
        )
        response.raise_for_status()
        return ClusterState(**response.json())
    
    async def get_calibration(self, cluster_id: str) -> CalibrationMetrics:
        """Get calibration metrics for a cluster."""
        response = await self._client.get(
            f"/api/v1/jobs/calibration",
            params={"cluster_id": cluster_id}
        )
        response.raise_for_status()
        return CalibrationMetrics(**response.json())
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
```

## DynamoDB Schema

Single-table design for all agentic layer state:

```
Table: vgac-agentic

Primary Key:
  PK (Partition Key): String
  SK (Sort Key): String

Access Patterns:
  1. Get calibration for cluster: PK=CLUSTER#{id}, SK=CALIBRATION
  2. Get predictions for cluster: PK=CLUSTER#{id}, SK=PREDICTION#{timestamp}
  3. Get environment profile: PK=CLUSTER#{id}, SK=PROFILE
  4. List all clusters: GSI on SK=CALIBRATION

Items:

# Calibration State
{
    "PK": "CLUSTER#eks-prod-gpu",
    "SK": "CALIBRATION",
    "platform": "kubernetes",
    "current_ece": 0.018,
    "last_known_good_ece": 0.018,
    "calibration_score": 0.92,
    "sample_count": 1847,
    "recalibration_needed": false,
    "last_updated": "2025-02-10T14:30:00Z"
}

# Environment Profile
{
    "PK": "CLUSTER#eks-prod-gpu",
    "SK": "PROFILE",
    "platform": "kubernetes",
    "avg_queue_depth": 8.3,
    "avg_gpu_utilization": 0.72,
    "peak_hours": ["09:00", "14:00"],
    "typical_wait_minutes": 45,
    "created_at": "2025-01-15T10:00:00Z",
    "last_updated": "2025-02-10T14:30:00Z"
}

# Prediction Log
{
    "PK": "CLUSTER#eks-prod-gpu",
    "SK": "PREDICTION#2025-02-10T14:35:00Z",
    "job_id": "train-llm-v3",
    "predicted_wait": 3600,
    "actual_wait": 3420,  # null until outcome known
    "confidence": 0.87,
    "error": 180,  # null until outcome known
    "ttl": 1710288000  # Auto-delete after 30 days
}
```

## Slack Integration

```python
# src/slack_client.py
import httpx
import os
from pydantic import BaseModel
from typing import Optional, List

class SlackConfig(BaseModel):
    webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    default_channel: str = os.getenv("SLACK_DEFAULT_CHANNEL", "#gpu-alerts")

class SlackMessage(BaseModel):
    channel: str
    text: str
    blocks: Optional[List[dict]] = None

class SlackClient:
    """Client for Slack notifications."""
    
    def __init__(self, config: Optional[SlackConfig] = None):
        self.config = config or SlackConfig()
    
    async def send_prediction_notification(
        self,
        channel: str,
        job_id: str,
        wait_time_minutes: int,
        confidence: float,
        calibration_score: float
    ):
        """Send a prediction notification to Slack."""
        # Confidence emoji
        if calibration_score > 0.85:
            emoji = "✅"
            confidence_text = "High confidence"
        elif calibration_score > 0.60:
            emoji = "⚠️"
            confidence_text = "Moderate confidence"
        else:
            emoji = "❓"
            confidence_text = "Low confidence"
        
        message = {
            "channel": channel,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *Job Prediction*\n\n"
                                f"Job `{job_id}` will start in approximately *{wait_time_minutes} minutes*\n\n"
                                f"_{confidence_text} (calibration: {calibration_score:.0%})_"
                    }
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(self.config.webhook_url, json=message)
    
    async def send_escalation(
        self,
        channel: str,
        reason: str,
        context: dict
    ):
        """Send an escalation request to Slack."""
        message = {
            "channel": channel,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🚨 *Human Review Needed*\n\n"
                                f"Reason: {reason}\n\n"
                                f"```{context}```"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Acknowledge"},
                            "action_id": "acknowledge_escalation"
                        }
                    ]
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(self.config.webhook_url, json=message)
```

## Lambda Handler Structure

Each agent's tools are Lambda functions:

```python
# lambdas/predictor/handler.py
import json
import logging
from vgac_client import VGACClient
from calibration import get_calibration_state, determine_action_scope

logger = logging.getLogger()
logger.setLevel(logging.INFO)

vgac = VGACClient()

async def handler(event, context):
    """
    Lambda handler for PredictorAgent tools.
    
    Event format (from AgentCore):
    {
        "tool_name": "tool_predict_wait_time",
        "parameters": {
            "job_id": "train-llm-v3",
            "cluster_id": "eks-prod-gpu"
        }
    }
    """
    tool_name = event.get("tool_name")
    params = event.get("parameters", {})
    
    logger.info(f"Tool invoked: {tool_name} with params: {params}")
    
    try:
        if tool_name == "tool_predict_wait_time":
            return await predict_wait_time(**params)
        elif tool_name == "tool_get_calibration_score":
            return await get_calibration_score(**params)
        elif tool_name == "tool_get_environment_profile":
            return await get_environment_profile(**params)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        logger.error(f"Tool error: {e}")
        return {"error": str(e)}

async def predict_wait_time(job_id: str, cluster_id: str) -> dict:
    """Get prediction with calibration-aware response."""
    # Get calibration state first
    calibration = await get_calibration_state(cluster_id)
    scope = determine_action_scope(calibration)
    
    # Get raw prediction from VGAC
    prediction = await vgac.predict(job_id, cluster_id)
    
    return {
        "job_id": job_id,
        "cluster_id": cluster_id,
        "wait_time_seconds": prediction.wait_time_seconds,
        "wait_time_minutes": prediction.wait_time_seconds // 60,
        "confidence": prediction.confidence,
        "calibration_score": calibration.score,
        "action_scope": scope.value,
        "message": format_prediction_message(prediction, calibration, scope)
    }

def format_prediction_message(prediction, calibration, scope) -> str:
    """Format human-readable prediction message."""
    minutes = prediction.wait_time_seconds // 60
    
    if scope.value == "autonomous":
        return f"Job will start in {minutes} minutes"
    elif scope.value == "notify":
        uncertainty = int(minutes * 0.2)
        return f"Job will start in ~{minutes} minutes (±{uncertainty}m)"
    else:
        return "Prediction unreliable for this environment"
```

## SAM Template Integration

```yaml
# infrastructure/template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: VGAC Agentic Layer

Parameters:
  VGACApiBaseUrl:
    Type: String
    Default: https://api.vgac.cloud
  SlackWebhookUrl:
    Type: String
    NoEcho: true

Globals:
  Function:
    Runtime: python3.11
    Timeout: 30
    MemorySize: 256
    Environment:
      Variables:
        VGAC_API_BASE_URL: !Ref VGACApiBaseUrl
        DYNAMODB_TABLE_NAME: !Ref AgenticTable
        SLACK_WEBHOOK_URL: !Ref SlackWebhookUrl

Resources:
  # DynamoDB Table
  AgenticTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: vgac-agentic
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: PK
          AttributeType: S
        - AttributeName: SK
          AttributeType: S
      KeySchema:
        - AttributeName: PK
          KeyType: HASH
        - AttributeName: SK
          KeyType: RANGE
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true

  # Lambda Functions
  PredictorFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: vgac-agentic-predictor
      CodeUri: ../lambdas/predictor/
      Handler: handler.handler
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref AgenticTable

  ActorFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: vgac-agentic-actor
      CodeUri: ../lambdas/actor/
      Handler: handler.handler
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref AgenticTable

  CalibratorFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: vgac-agentic-calibrator
      CodeUri: ../lambdas/calibrator/
      Handler: handler.handler
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref AgenticTable

Outputs:
  PredictorFunctionArn:
    Value: !GetAtt PredictorFunction.Arn
  ActorFunctionArn:
    Value: !GetAtt ActorFunction.Arn
  CalibratorFunctionArn:
    Value: !GetAtt CalibratorFunction.Arn
  TableName:
    Value: !Ref AgenticTable
```

## Environment Variables

```bash
# .env.example (never commit actual values)
VGAC_API_BASE_URL=https://api.vgac.cloud
VGAC_API_KEY=your-api-key-here
VGAC_TIMEOUT_SECONDS=10

SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
SLACK_DEFAULT_CHANNEL=#gpu-alerts

DYNAMODB_TABLE_NAME=vgac-agentic
AWS_REGION=us-east-1
```

## Local Development

For local testing without deploying:

```python
# scripts/local_test.py
import asyncio
from vgac_client import VGACClient, VGACConfig

async def main():
    # Point to local VGAC instance
    config = VGACConfig(base_url="http://localhost:8000")
    client = VGACClient(config)
    
    # Test prediction
    result = await client.predict(
        job_id="test-job-123",
        cluster_id="local-minikube"
    )
    print(f"Prediction: {result}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```
