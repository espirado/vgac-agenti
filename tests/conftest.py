"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_vgac_client():
    """Mock VGAC API client for testing."""
    client = AsyncMock()

    # Default responses
    client.predict.return_value = {
        "wait_time_seconds": 3600,
        "confidence": 0.85,
        "risk_score": 0.23,
        "calibration_score": 0.92,
    }
    client.get_cluster_state.return_value = {
        "cluster_id": "eks-prod",
        "platform": "kubernetes",
        "queue_depth": 12,
        "gpu_utilization": 0.78,
        "gpu_memory_used": 0.65,
        "active_jobs": 8,
        "pending_jobs": 12,
    }
    client.get_calibration.return_value = {
        "ece": 0.018,
        "brier_score": 0.12,
        "sample_count": 1847,
        "last_recalibration": "2025-02-01T00:00:00Z",
        "recalibration_needed": False,
    }

    return client


@pytest.fixture
def mock_slack_client():
    """Mock Slack client for testing."""
    client = AsyncMock()
    client.send_prediction_notification.return_value = None
    client.send_escalation.return_value = None
    return client


@pytest.fixture(autouse=True)
def reset_calibration_cache():
    """Reset the in-memory calibration cache between tests."""
    from src.agents.calibrator import _calibration_cache

    _calibration_cache.clear()
    yield
    _calibration_cache.clear()
