# Testing Requirements

## Test Framework
- pytest for all tests
- pytest-asyncio for async tests
- moto for AWS service mocking
- responses for HTTP mocking

## Test Structure
```
tests/
├── unit/
│   ├── test_observer.py
│   ├── test_predictor.py
│   ├── test_actor.py
│   └── test_calibrator.py
├── integration/
│   ├── test_agent_orchestration.py
│   └── test_vgac_integration.py
└── conftest.py              # Shared fixtures
```

## Coverage Requirements
- Unit tests: All agent tools must have tests
- Integration tests: Agent orchestration flow
- No tests required for infrastructure (SAM template)

## Unit Test Pattern
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_tool_predict_wait_time_returns_prediction():
    """Tool should return prediction with confidence score."""
    # Arrange
    mock_vgac_response = {
        "wait_time_seconds": 3600,
        "confidence": 0.87,
        "calibration_score": 0.92
    }
    
    with patch("agents.predictor.vgac_client.predict") as mock:
        mock.return_value = mock_vgac_response
        
        # Act
        result = await tool_predict_wait_time(
            job_id="job-123",
            cluster_id="eks-prod"
        )
        
        # Assert
        assert result.wait_time_seconds == 3600
        assert result.confidence == 0.87
        assert result.calibration_score == 0.92


@pytest.mark.asyncio
async def test_tool_predict_wait_time_handles_vgac_error():
    """Tool should gracefully handle VGAC API errors."""
    with patch("agents.predictor.vgac_client.predict") as mock:
        mock.side_effect = VGACAPIError("Connection refused")
        
        # Should not raise, should return error result
        result = await tool_predict_wait_time(
            job_id="job-123",
            cluster_id="eks-prod"
        )
        
        assert result.error is not None
        assert result.confidence == 0.0  # No confidence when errored
```

## Calibration Test Pattern
```python
@pytest.mark.asyncio
async def test_confidence_gating_high_calibration():
    """High calibration should allow autonomous action."""
    calibrator = CalibratorAgent()
    calibrator.set_calibration_score("eks-prod", 0.92)
    
    action = await calibrator.determine_action_scope("eks-prod")
    
    assert action.autonomous == True
    assert action.notify_human == False


@pytest.mark.asyncio
async def test_confidence_gating_low_calibration():
    """Low calibration should escalate to human."""
    calibrator = CalibratorAgent()
    calibrator.set_calibration_score("slurm-hpc", 0.45)
    
    action = await calibrator.determine_action_scope("slurm-hpc")
    
    assert action.autonomous == False
    assert action.escalate == True
```

## Mock VGAC API Fixture
```python
# conftest.py
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_vgac_client():
    """Mock VGAC API client for testing."""
    client = AsyncMock()
    
    # Default responses
    client.predict.return_value = {
        "wait_time_seconds": 3600,
        "confidence": 0.85
    }
    client.get_cluster_state.return_value = {
        "cluster_id": "eks-prod",
        "queue_depth": 12,
        "gpu_utilization": 0.78
    }
    client.get_calibration.return_value = {
        "ece": 0.018,
        "brier_score": 0.12,
        "sample_count": 1847
    }
    
    return client


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB for testing."""
    with moto.mock_dynamodb():
        # Create table
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="vgac-agentic",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        yield client
```

## Running Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=agents --cov=tools --cov-report=html

# Only unit tests
pytest tests/unit/

# Specific agent
pytest tests/unit/test_predictor.py -v
```

## Pre-Commit
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/unit/ -q
        language: system
        pass_filenames: false
        always_run: true
```
