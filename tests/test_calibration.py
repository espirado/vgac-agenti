"""Tests for calibration logic - the core differentiator."""

import pytest
from datetime import datetime, timezone

from src.agents.base import ActionScope, CalibrationState, determine_action_scope
from src.agents.calibrator import (
    check_calibration_drift,
    ece_to_calibration_score,
    get_calibration_state,
    update_calibration_state,
)


class TestActionScopeDetermination:
    """Test confidence gating logic."""

    def test_new_environment_escalates(self):
        """New environments with few samples should escalate."""
        calibration = CalibrationState(
            cluster_id="new-cluster",
            score=0.9,  # High score but...
            sample_count=10,  # Too few samples
            last_updated=datetime.now(timezone.utc),
            is_learning_mode=True,
        )
        assert determine_action_scope(calibration) == ActionScope.ESCALATE

    def test_high_calibration_is_autonomous(self):
        """Well-calibrated environments allow autonomous action."""
        calibration = CalibrationState(
            cluster_id="eks-prod",
            score=0.92,
            sample_count=1847,
            last_updated=datetime.now(timezone.utc),
            is_learning_mode=False,
        )
        assert determine_action_scope(calibration) == ActionScope.AUTONOMOUS

    def test_medium_calibration_notifies(self):
        """Moderate calibration should act but notify human."""
        calibration = CalibrationState(
            cluster_id="slurm-hpc",
            score=0.72,
            sample_count=500,
            last_updated=datetime.now(timezone.utc),
            is_learning_mode=False,
        )
        assert determine_action_scope(calibration) == ActionScope.NOTIFY

    def test_low_calibration_escalates(self):
        """Low calibration should escalate without action."""
        calibration = CalibrationState(
            cluster_id="unknown-batch",
            score=0.45,
            sample_count=200,
            last_updated=datetime.now(timezone.utc),
            is_learning_mode=False,
        )
        assert determine_action_scope(calibration) == ActionScope.ESCALATE

    def test_threshold_at_085(self):
        """Test the 0.85 threshold boundary."""
        # Just above
        high = CalibrationState(
            cluster_id="test",
            score=0.86,
            sample_count=100,
            last_updated=datetime.now(timezone.utc),
        )
        assert determine_action_scope(high) == ActionScope.AUTONOMOUS

        # Just below
        low = CalibrationState(
            cluster_id="test",
            score=0.84,
            sample_count=100,
            last_updated=datetime.now(timezone.utc),
        )
        assert determine_action_scope(low) == ActionScope.NOTIFY

    def test_threshold_at_060(self):
        """Test the 0.60 threshold boundary (matches VGAC policy generator)."""
        # Just above
        above = CalibrationState(
            cluster_id="test",
            score=0.61,
            sample_count=100,
            last_updated=datetime.now(timezone.utc),
        )
        assert determine_action_scope(above) == ActionScope.NOTIFY

        # Just below
        below = CalibrationState(
            cluster_id="test",
            score=0.59,
            sample_count=100,
            last_updated=datetime.now(timezone.utc),
        )
        assert determine_action_scope(below) == ActionScope.ESCALATE


class TestCalibrationDrift:
    """Test drift detection logic."""

    def test_no_drift(self):
        """Stable calibration should show no drift."""
        drift = check_calibration_drift(current_ece=0.020, baseline_ece=0.018)
        assert drift.severity == "none"
        assert drift.action == "continue"

    def test_moderate_drift(self):
        """1.5-2× drift should trigger monitoring."""
        drift = check_calibration_drift(current_ece=0.030, baseline_ece=0.018)
        assert drift.severity == "moderate"
        assert drift.action == "monitor"

    def test_significant_drift(self):
        """2-5× drift should reduce autonomy."""
        drift = check_calibration_drift(current_ece=0.060, baseline_ece=0.018)
        assert drift.severity == "significant"
        assert drift.action == "reduce_autonomy"

    def test_critical_drift(self):
        """5× drift should trigger recalibration."""
        drift = check_calibration_drift(current_ece=0.100, baseline_ece=0.018)
        assert drift.severity == "critical"
        assert drift.action == "trigger_recalibration"

    def test_extreme_drift_approaching_22x(self):
        """Test drift approaching the 22× research finding."""
        drift = check_calibration_drift(current_ece=0.396, baseline_ece=0.018)  # 22×
        assert drift.severity == "critical"
        assert drift.drift_ratio >= 20


class TestECEConversion:
    """Test ECE to calibration score conversion."""

    def test_perfect_calibration(self):
        """ECE of 0 should give score of 1.0."""
        assert ece_to_calibration_score(0.0) == 1.0

    def test_baseline_ece(self):
        """VGAC baseline ECE should give high score."""
        score = ece_to_calibration_score(0.018)
        assert score > 0.90
        assert score < 0.95

    def test_poor_calibration(self):
        """High ECE should give low score."""
        score = ece_to_calibration_score(0.2)
        assert score == 0.0  # Clamped to 0

    def test_moderate_calibration(self):
        """Moderate ECE should give moderate score."""
        score = ece_to_calibration_score(0.08)
        assert 0.5 < score < 0.7


@pytest.mark.asyncio
class TestCalibrationState:
    """Test calibration state management."""

    async def test_unknown_cluster_returns_learning_mode(self):
        """Unknown clusters should be in learning mode."""
        state = await get_calibration_state("never-seen-before")
        assert state.is_learning_mode is True
        assert state.sample_count == 0

    async def test_update_calibration_state(self):
        """Test updating calibration state."""
        await update_calibration_state(
            cluster_id="test-cluster",
            score=0.88,
            sample_count=500,
        )

        state = await get_calibration_state("test-cluster")
        assert state.score == 0.88
        assert state.sample_count == 500
        assert state.is_learning_mode is False

    async def test_learning_mode_threshold(self):
        """Clusters with <50 samples should be in learning mode."""
        await update_calibration_state(
            cluster_id="small-sample",
            score=0.95,
            sample_count=49,
        )

        state = await get_calibration_state("small-sample")
        assert state.is_learning_mode is True

        await update_calibration_state(
            cluster_id="small-sample",
            score=0.95,
            sample_count=50,
        )

        state = await get_calibration_state("small-sample")
        assert state.is_learning_mode is False
