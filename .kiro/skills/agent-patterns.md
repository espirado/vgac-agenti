# Agent Patterns for VGAC

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 BEDROCK AGENTCORE ORCHESTRATOR                  │
│                                                                 │
│   Manages: Agent coordination, memory, tool routing             │
└─────────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│ OBSERVER  │  │ PREDICTOR │  │   ACTOR   │  │CALIBRATOR │
│   AGENT   │  │   AGENT   │  │   AGENT   │  │   AGENT   │
└───────────┘  └───────────┘  └───────────┘  └───────────┘
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    TOOL REGISTRY    │
                    │                     │
                    │  VGAC API calls     │
                    │  DynamoDB ops       │
                    │  Slack notifications│
                    │  Calibration checks │
                    └─────────────────────┘
```

## Agent Definitions

### ObserverAgent
**Purpose:** Watch cluster state, detect anomalies, provide situational awareness

**System Prompt:**
```
You are the Observer Agent for VGAC GPU infrastructure monitoring.

Your role:
- Monitor GPU cluster state across environments (K8s, Slurm, AWS Batch)
- Detect anomalies (unusual queue depth, GPU utilization spikes)
- Provide current state to other agents when requested

You have access to these tools:
- tool_get_cluster_state: Get current cluster metrics
- tool_get_queue_depth: Get number of pending jobs
- tool_detect_anomaly: Check if current state is anomalous

Always report facts. Do not make predictions (that's PredictorAgent's job).
```

**Tools:**
```python
tools = [
    {
        "name": "tool_get_cluster_state",
        "description": "Get current state of a GPU cluster including utilization, queue depth, and node status",
        "parameters": {
            "cluster_id": {"type": "string", "description": "Cluster identifier"}
        }
    },
    {
        "name": "tool_get_queue_depth",
        "description": "Get number of jobs waiting in queue",
        "parameters": {
            "cluster_id": {"type": "string", "description": "Cluster identifier"}
        }
    },
    {
        "name": "tool_detect_anomaly",
        "description": "Check if current cluster state is anomalous compared to historical patterns",
        "parameters": {
            "cluster_id": {"type": "string", "description": "Cluster identifier"},
            "metric": {"type": "string", "enum": ["queue_depth", "gpu_util", "memory"]}
        }
    }
]
```

### PredictorAgent
**Purpose:** Predict wait times with calibrated confidence

**System Prompt:**
```
You are the Predictor Agent for VGAC GPU job scheduling.

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
- If calibration < 0.60: State that predictions are unreliable for this environment
```

**Tools:**
```python
tools = [
    {
        "name": "tool_predict_wait_time",
        "description": "Predict when a GPU job will start running",
        "parameters": {
            "job_id": {"type": "string", "description": "Job identifier"},
            "cluster_id": {"type": "string", "description": "Target cluster"}
        }
    },
    {
        "name": "tool_get_calibration_score",
        "description": "Get current calibration score (ECE) for a cluster",
        "parameters": {
            "cluster_id": {"type": "string", "description": "Cluster identifier"}
        }
    },
    {
        "name": "tool_get_environment_profile",
        "description": "Get historical prediction accuracy for a cluster",
        "parameters": {
            "cluster_id": {"type": "string", "description": "Cluster identifier"}
        }
    }
]
```

### ActorAgent
**Purpose:** Take actions based on predictions and calibration

**System Prompt:**
```
You are the Actor Agent for VGAC GPU infrastructure.

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

Never take autonomous action when calibration is below 0.60.
```

**Tools:**
```python
tools = [
    {
        "name": "tool_send_slack_notification",
        "description": "Send a notification to a Slack channel or user",
        "parameters": {
            "channel": {"type": "string", "description": "Slack channel or user ID"},
            "message": {"type": "string", "description": "Notification message"}
        }
    },
    {
        "name": "tool_requeue_job",
        "description": "Move a job to a different queue or cluster",
        "parameters": {
            "job_id": {"type": "string", "description": "Job identifier"},
            "target_queue": {"type": "string", "description": "Target queue name"}
        }
    },
    {
        "name": "tool_adjust_priority",
        "description": "Change the priority of a job",
        "parameters": {
            "job_id": {"type": "string", "description": "Job identifier"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "critical"]}
        }
    },
    {
        "name": "tool_create_alert",
        "description": "Create an operational alert",
        "parameters": {
            "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
            "message": {"type": "string", "description": "Alert message"}
        }
    },
    {
        "name": "tool_escalate_to_human",
        "description": "Flag a situation for human review",
        "parameters": {
            "reason": {"type": "string", "description": "Why escalation is needed"},
            "context": {"type": "object", "description": "Relevant context data"}
        }
    }
]
```

### CalibratorAgent
**Purpose:** Monitor calibration, manage recalibration, track per-environment accuracy

**System Prompt:**
```
You are the Calibrator Agent for VGAC prediction reliability.

Your role:
- Monitor calibration scores across all environments
- Detect calibration drift
- Trigger recalibration when needed
- Maintain per-environment accuracy profiles

You have access to these tools:
- tool_check_calibration_drift: Compare current vs historical calibration
- tool_trigger_recalibration: Flag a cluster for model retraining
- tool_update_environment_profile: Store new accuracy metrics
- tool_get_all_calibrations: Get calibration scores for all clusters

DRIFT DETECTION:
- If current ECE > 2× last_known_good_ece: Flag as drifting
- If accuracy drops below 0.85 over 100 samples: Trigger recalibration
- New environments (< 50 samples): Mark as "learning mode"
```

**Tools:**
```python
tools = [
    {
        "name": "tool_check_calibration_drift",
        "description": "Check if calibration has drifted from baseline",
        "parameters": {
            "cluster_id": {"type": "string", "description": "Cluster identifier"}
        }
    },
    {
        "name": "tool_trigger_recalibration",
        "description": "Flag a cluster for model recalibration",
        "parameters": {
            "cluster_id": {"type": "string", "description": "Cluster identifier"},
            "reason": {"type": "string", "description": "Why recalibration is needed"}
        }
    },
    {
        "name": "tool_update_environment_profile",
        "description": "Update stored accuracy metrics for a cluster",
        "parameters": {
            "cluster_id": {"type": "string", "description": "Cluster identifier"},
            "metrics": {"type": "object", "description": "New calibration metrics"}
        }
    },
    {
        "name": "tool_get_all_calibrations",
        "description": "Get calibration scores for all monitored clusters",
        "parameters": {}
    }
]
```

## Confidence Gating Pattern (Critical)

This is the key differentiator. All agents must implement:

```python
from enum import Enum
from pydantic import BaseModel

class ActionScope(str, Enum):
    AUTONOMOUS = "autonomous"      # Act without human
    NOTIFY = "notify"              # Act and notify human
    ESCALATE = "escalate"          # Don't act, ask human

class CalibrationState(BaseModel):
    cluster_id: str
    score: float  # 0.0 to 1.0
    sample_count: int
    last_updated: datetime

def determine_action_scope(calibration: CalibrationState) -> ActionScope:
    """
    Determine what actions the agent can take based on calibration.
    
    This maps to the existing 0.6 threshold in VGAC's generator.py.
    """
    if calibration.sample_count < 50:
        # New environment, learning mode
        return ActionScope.ESCALATE
    
    if calibration.score > 0.85:
        # Well-calibrated, full autonomy
        return ActionScope.AUTONOMOUS
    
    if calibration.score > 0.60:
        # Moderate calibration, act but notify
        return ActionScope.NOTIFY
    
    # Poor calibration, escalate
    return ActionScope.ESCALATE
```

## Orchestration Flow

```
User: "When will my job start?"
           │
           ▼
┌─────────────────────────────────────────┐
│         AGENTCORE ORCHESTRATOR          │
│                                         │
│  1. Route to PredictorAgent             │
│  2. PredictorAgent checks calibration   │
│  3. If calibrated: return prediction    │
│  4. If not: flag uncertainty            │
│  5. Route to ActorAgent for response    │
│  6. ActorAgent sends Slack message      │
└─────────────────────────────────────────┘
           │
           ▼
User receives: "Your job will start in ~2h 15m (confidence: 87%)"
```

## Lambda Handler Pattern

Each agent's tools are implemented as Lambda functions:

```python
# lambdas/predictor/handler.py
import json
import boto3
from vgac_client import VGACClient

vgac = VGACClient()

def handler(event, context):
    """Lambda handler for PredictorAgent tools."""
    tool_name = event.get("tool_name")
    parameters = event.get("parameters", {})
    
    if tool_name == "tool_predict_wait_time":
        return predict_wait_time(
            job_id=parameters["job_id"],
            cluster_id=parameters["cluster_id"]
        )
    elif tool_name == "tool_get_calibration_score":
        return get_calibration_score(
            cluster_id=parameters["cluster_id"]
        )
    else:
        return {"error": f"Unknown tool: {tool_name}"}

def predict_wait_time(job_id: str, cluster_id: str) -> dict:
    """Call VGAC prediction API."""
    result = vgac.predict(job_id=job_id, cluster_id=cluster_id)
    return {
        "wait_time_seconds": result["wait_time_seconds"],
        "confidence": result["confidence"],
        "calibration_score": result["calibration_score"]
    }
```
