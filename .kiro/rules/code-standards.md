# Code Standards

## Language
- Python 3.11+
- Type hints required on all functions
- Pydantic v2 models for data structures
- Async where appropriate (FastAPI patterns)

## Style
- Follow existing VGAC patterns in the codebase
- Use existing models — don't recreate data structures
- Use existing enums (Platform, JobState, etc.) when referencing VGAC

## Error Handling
- Never swallow exceptions silently
- Log errors with context (job_id, cluster_id, timestamp)
- Graceful degradation: if agent fails, fall back to defaults
- Use structured logging (JSON format for Lambda)

## Dependencies
Existing in VGAC (prefer these):
- fastapi
- pydantic >= 2.0
- numpy
- scikit-learn
- boto3

New for agentic layer:
- boto3 (Bedrock, DynamoDB, S3, Lambda)
- slack-sdk (notifications)

## Naming Conventions
- `snake_case` for functions and variables
- `PascalCase` for classes
- `SCREAMING_CASE` for constants
- Prefix agent tools with `tool_` (e.g., `tool_predict_wait_time`)
- Prefix Lambda handlers with `handler_`

## Function Signatures
```python
# Always typed, always documented
async def tool_predict_wait_time(
    job_id: str,
    cluster_id: str,
    *,
    include_confidence: bool = True,
) -> PredictionResult:
    """
    Predict when a GPU job will start running.
    
    Args:
        job_id: The job identifier
        cluster_id: Target cluster identifier
        include_confidence: Whether to include calibration score
        
    Returns:
        PredictionResult with wait_time_seconds and confidence
        
    Raises:
        JobNotFoundError: If job_id doesn't exist
        ClusterUnavailableError: If cluster is unreachable
    """
```

## File Organization
```
# Each agent in its own module
agents/
    observer.py      # ObserverAgent class + tools
    predictor.py     # PredictorAgent class + tools
    actor.py         # ActorAgent class + tools
    calibrator.py    # CalibratorAgent class + tools

# Lambda handlers separate from agent logic
lambdas/
    observer/handler.py
    predictor/handler.py
    ...
```

## Configuration
- Use environment variables for secrets (never hardcode)
- Use Pydantic Settings for config validation
- Required env vars:
  - `VGAC_API_BASE_URL`
  - `SLACK_WEBHOOK_URL`
  - `DYNAMODB_TABLE_NAME`
  - `AWS_REGION`
