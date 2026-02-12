# Calibration Methodology

## Core Research Finding

**Calibration degrades 22× across different GPU schedulers.**

An agent trained on AWS EKS will be dangerously overconfident when applied to Slurm HPC. This is the research insight that differentiates VGAC from every other AI agent.

Source: Andrew Espira's research on GPU scheduling prediction (TechRxiv preprint, ASPLOS Architecture 2.0 Workshop submission)

## Why This Matters for Agents

Most AI agents are **equally confident everywhere**. They have no mechanism to detect when they're operating outside their training distribution.

VGAC agents implement **environment-aware calibration**:
- Track accuracy per environment
- Detect when predictions are unreliable
- Reduce autonomy when calibration drifts
- Request human validation in unfamiliar environments

## Calibration Metrics

### Primary: Expected Calibration Error (ECE)
```
ECE = Σ (|accuracy_in_bin - confidence_in_bin| × samples_in_bin) / total_samples
```

Lower is better. Perfect calibration = 0.0.

VGAC baseline: `last_known_good_ece = 0.018`

### Secondary: Brier Score
```
Brier = (1/N) × Σ (predicted_probability - actual_outcome)²
```

Lower is better. Measures both calibration AND discrimination.

### Calibration Score (for agents)
For simplicity, agents use a normalized calibration score:

```python
def calibration_score(ece: float) -> float:
    """
    Convert ECE to a 0-1 score where higher is better.
    
    ECE of 0.018 (our baseline) → score of ~0.92
    ECE of 0.1 → score of ~0.60
    ECE of 0.2+ → score of ~0.30
    """
    # Exponential decay from perfect calibration
    return max(0.0, 1.0 - (ece * 5))  # Simplified
```

## Per-Environment Tracking

Each cluster maintains its own calibration profile:

```python
class EnvironmentProfile(BaseModel):
    cluster_id: str
    platform: Platform  # kubernetes, slurm, aws_batch
    
    # Calibration metrics
    current_ece: float
    last_known_good_ece: float
    brier_score: float
    
    # Sample tracking
    sample_count: int
    predictions_made: int
    outcomes_observed: int
    
    # State
    calibration_score: float  # Derived from ECE
    recalibration_needed: bool
    last_recalibration: datetime
    last_updated: datetime
    
    # Learning state
    is_learning_mode: bool  # True if sample_count < 50

# DynamoDB schema
{
    "PK": "CLUSTER#eks-prod-gpu",
    "SK": "CALIBRATION",
    "platform": "kubernetes",
    "current_ece": 0.018,
    "last_known_good_ece": 0.018,
    "calibration_score": 0.92,
    "sample_count": 1847,
    "recalibration_needed": false,
    "is_learning_mode": false,
    "last_updated": "2025-02-10T14:30:00Z"
}
```

## Calibration State Machine

```
                    ┌─────────────────┐
                    │  NEW ENVIRONMENT │
                    │  (< 50 samples)  │
                    └────────┬────────┘
                             │
                    50 samples collected
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ┌─────────────────┐         ┌─────────────────┐                │
│  │ WELL-CALIBRATED │ ◄─────► │    DRIFTING     │                │
│  │   score > 0.85  │         │  0.60 < score   │                │
│  │                 │         │    < 0.85       │                │
│  │ Full autonomy   │         │ Notify human    │                │
│  └────────┬────────┘         └────────┬────────┘                │
│           │                           │                          │
│           │    ECE drift detected     │                          │
│           └───────────────────────────┘                          │
│                       │                                          │
│              severe drift (ECE > 2× baseline)                    │
│                       │                                          │
│                       ▼                                          │
│           ┌─────────────────┐                                    │
│           │  UNCALIBRATED   │                                    │
│           │  score < 0.60   │                                    │
│           │                 │                                    │
│           │ Escalate only   │                                    │
│           │ No autonomous   │                                    │
│           │ action          │                                    │
│           └────────┬────────┘                                    │
│                    │                                             │
│           recalibration complete                                 │
│                    │                                             │
│                    ▼                                             │
│           Back to WELL-CALIBRATED                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Drift Detection

```python
def check_calibration_drift(
    current_ece: float,
    baseline_ece: float,
    sample_window: int = 100
) -> DriftStatus:
    """
    Detect if calibration has drifted from baseline.
    
    Returns:
        DriftStatus with severity and recommended action
    """
    drift_ratio = current_ece / baseline_ece if baseline_ece > 0 else float('inf')
    
    if drift_ratio <= 1.5:
        return DriftStatus(
            severity="none",
            action="continue",
            message="Calibration stable"
        )
    
    if drift_ratio <= 2.0:
        return DriftStatus(
            severity="moderate",
            action="monitor",
            message=f"ECE increased {drift_ratio:.1f}× from baseline"
        )
    
    if drift_ratio <= 5.0:
        return DriftStatus(
            severity="significant",
            action="reduce_autonomy",
            message=f"ECE increased {drift_ratio:.1f}× — reducing autonomous actions"
        )
    
    # drift_ratio > 5.0
    return DriftStatus(
        severity="critical",
        action="trigger_recalibration",
        message=f"ECE increased {drift_ratio:.1f}× — recalibration required"
    )
```

## Feedback Loop

Every prediction becomes a data point for calibration:

```
1. PREDICTION MADE
   └── Store: job_id, cluster_id, predicted_wait, confidence, timestamp
   
2. OUTCOME OBSERVED
   └── Store: actual_wait, error (predicted - actual)
   
3. CALIBRATION UPDATE (every 100 predictions)
   └── Recalculate ECE over recent window
   └── Compare to baseline
   └── Update calibration_score
   └── If drift detected: adjust agent behavior
   
4. RECALIBRATION (if triggered)
   └── Retrain calibrator on new data
   └── Update baseline ECE
   └── Reset drift detection
```

```python
async def log_prediction_outcome(
    job_id: str,
    cluster_id: str,
    predicted_wait: int,
    actual_wait: int,
    confidence: float
):
    """Log prediction outcome and update calibration."""
    # Store outcome
    await dynamodb.put_item(
        TableName="vgac-agentic",
        Item={
            "PK": f"CLUSTER#{cluster_id}",
            "SK": f"PREDICTION#{datetime.utcnow().isoformat()}",
            "job_id": job_id,
            "predicted_wait": predicted_wait,
            "actual_wait": actual_wait,
            "confidence": confidence,
            "error": predicted_wait - actual_wait,
            "squared_error": (confidence - (1 if abs(predicted_wait - actual_wait) < 300 else 0)) ** 2
        }
    )
    
    # Check if recalibration window reached
    profile = await get_environment_profile(cluster_id)
    if profile.predictions_made % 100 == 0:
        await recalculate_calibration(cluster_id)
```

## Agent Behavior by Calibration State

| State | Calibration Score | Autonomous Actions | User Communication |
|-------|-------------------|-------------------|-------------------|
| Learning | N/A (< 50 samples) | None | "I'm still learning this environment. [Escalate]" |
| Well-calibrated | > 0.85 | Full | "Your job will start in 2h 15m" |
| Drifting | 0.60 - 0.85 | Limited + notify | "Your job will start in ~2h 15m (±30m uncertainty)" |
| Uncalibrated | < 0.60 | None | "I can't reliably predict for this cluster. [Escalate]" |

## Implementation in Agents

```python
class PredictorAgent:
    async def predict_with_calibration(
        self,
        job_id: str,
        cluster_id: str
    ) -> PredictionResponse:
        # Get calibration state
        calibration = await self.get_calibration_score(cluster_id)
        scope = determine_action_scope(calibration)
        
        # Get raw prediction
        prediction = await self.vgac_client.predict(job_id, cluster_id)
        
        # Adjust response based on calibration
        if scope == ActionScope.ESCALATE:
            return PredictionResponse(
                prediction=None,
                message="Predictions unreliable for this environment",
                action="escalate",
                calibration_score=calibration.score
            )
        
        if scope == ActionScope.NOTIFY:
            # Widen confidence interval
            uncertainty_minutes = int(prediction.wait_time_seconds * 0.2 / 60)
            return PredictionResponse(
                prediction=prediction,
                message=f"~{prediction.wait_time_seconds // 60}m (±{uncertainty_minutes}m)",
                action="notify_human",
                calibration_score=calibration.score
            )
        
        # AUTONOMOUS - high confidence
        return PredictionResponse(
            prediction=prediction,
            message=f"{prediction.wait_time_seconds // 60}m",
            action="autonomous",
            calibration_score=calibration.score
        )
```
