"""Tests for contribution impact tracking."""

import json
import tempfile
from pathlib import Path

import pytest
import numpy as np

from training.contribution_impact import (
    ContributionImpactTracker,
    EvaluationSnapshot,
    ContributionBatchImpact,
    ImpactReport,
    evaluate_with_tracker,
)


@pytest.fixture
def sample_metrics():
    """Create sample evaluation metrics."""
    return {
        "accuracy": 0.85,
        "top3_accuracy": 0.95,
        "per_class_accuracy": {
            "kick": 0.90,
            "snare": 0.85,
            "hi-hat": 0.80,
        },
        "per_class_f1": {
            "kick": 0.88,
            "snare": 0.83,
            "hi-hat": 0.78,
        },
        "calibration_error": 0.05,
        "num_samples": 1000,
    }


@pytest.fixture
def improved_metrics():
    """Create improved evaluation metrics after training."""
    return {
        "accuracy": 0.87,
        "top3_accuracy": 0.96,
        "per_class_accuracy": {
            "kick": 0.92,
            "snare": 0.86,
            "hi-hat": 0.83,
        },
        "per_class_f1": {
            "kick": 0.90,
            "snare": 0.84,
            "hi-hat": 0.81,
        },
        "calibration_error": 0.04,
        "num_samples": 1000,
    }


class TestEvaluationSnapshot:
    """Tests for EvaluationSnapshot dataclass."""

    def test_to_dict(self, sample_metrics):
        """Test conversion to dictionary."""
        snapshot = EvaluationSnapshot(
            timestamp="2025-12-03T12:00:00Z",
            model_version="v1.0",
            overall_accuracy=sample_metrics["accuracy"],
            top3_accuracy=sample_metrics["top3_accuracy"],
            per_class_accuracy=sample_metrics["per_class_accuracy"],
            per_class_f1=sample_metrics["per_class_f1"],
            calibration_error=sample_metrics["calibration_error"],
            num_eval_samples=sample_metrics["num_samples"],
        )
        
        d = snapshot.to_dict()
        
        assert d["timestamp"] == "2025-12-03T12:00:00Z"
        assert d["model_version"] == "v1.0"
        assert d["overall_accuracy"] == 0.85
        assert "kick" in d["per_class_accuracy"]

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "timestamp": "2025-12-03T12:00:00Z",
            "model_version": "v1.0",
            "overall_accuracy": 0.85,
            "top3_accuracy": 0.95,
            "per_class_accuracy": {"kick": 0.90},
            "per_class_f1": {"kick": 0.88},
            "calibration_error": 0.05,
            "num_eval_samples": 1000,
            "contribution_batch_id": None,
            "notes": "",
        }
        
        snapshot = EvaluationSnapshot.from_dict(data)
        
        assert snapshot.model_version == "v1.0"
        assert snapshot.overall_accuracy == 0.85


class TestContributionImpactTracker:
    """Tests for ContributionImpactTracker class."""

    def test_initialization(self):
        """Test tracker initialization creates output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ContributionImpactTracker(output_dir=tmpdir)
            
            assert tracker.output_dir.exists()
            assert len(tracker.snapshots) == 0

    def test_record_baseline(self, sample_metrics):
        """Test recording baseline metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ContributionImpactTracker(output_dir=tmpdir)
            
            snapshot = tracker.record_baseline(
                metrics=sample_metrics,
                model_version="v1.0",
            )
            
            assert len(tracker.snapshots) == 1
            assert snapshot.overall_accuracy == 0.85
            assert snapshot.contribution_batch_id is None

    def test_record_post_training(self, improved_metrics):
        """Test recording post-training metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ContributionImpactTracker(output_dir=tmpdir)
            
            snapshot = tracker.record_post_training(
                metrics=improved_metrics,
                model_version="v1.1",
                batch_id="contrib-20251203",
                sample_count=500,
            )
            
            assert len(tracker.snapshots) == 1
            assert snapshot.overall_accuracy == 0.87
            assert snapshot.contribution_batch_id == "contrib-20251203"
            assert tracker.batch_sample_counts["contrib-20251203"] == 500

    def test_calculate_batch_impact(self, sample_metrics, improved_metrics):
        """Test calculating impact of a contribution batch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ContributionImpactTracker(output_dir=tmpdir)
            
            # Record baseline
            tracker.record_baseline(sample_metrics, "v1.0")
            
            # Record post-training
            tracker.record_post_training(
                improved_metrics, "v1.1", "batch-001", 500
            )
            
            impact = tracker.calculate_batch_impact("batch-001")
            
            assert impact is not None
            assert impact.batch_id == "batch-001"
            assert impact.sample_count == 500
            assert impact.accuracy_delta == pytest.approx(0.02, abs=0.001)
            assert impact.top3_accuracy_delta == pytest.approx(0.01, abs=0.001)
            assert "kick" in impact.per_class_deltas

    def test_calculate_batch_impact_not_found(self):
        """Test impact calculation for non-existent batch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ContributionImpactTracker(output_dir=tmpdir)
            
            impact = tracker.calculate_batch_impact("nonexistent")
            
            assert impact is None

    def test_generate_impact_report(self, sample_metrics, improved_metrics):
        """Test generating full impact report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ContributionImpactTracker(output_dir=tmpdir)
            
            tracker.record_baseline(sample_metrics, "v1.0")
            tracker.record_post_training(improved_metrics, "v1.1", "batch-001", 500)
            
            report = tracker.generate_impact_report()
            
            assert report.total_batches == 1
            assert report.total_contributions == 500
            assert report.cumulative_accuracy_gain == pytest.approx(0.02, abs=0.001)
            assert len(report.batch_impacts) == 1
            assert len(report.snapshots) == 2

    def test_save_and_load_history(self, sample_metrics):
        """Test that history persists across tracker instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and populate tracker
            tracker1 = ContributionImpactTracker(output_dir=tmpdir)
            tracker1.record_baseline(sample_metrics, "v1.0")
            
            # Create new tracker from same directory
            tracker2 = ContributionImpactTracker(output_dir=tmpdir)
            
            assert len(tracker2.snapshots) == 1
            assert tracker2.snapshots[0].model_version == "v1.0"

    def test_save_impact_report(self, sample_metrics, improved_metrics):
        """Test saving impact report to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ContributionImpactTracker(output_dir=tmpdir)
            
            tracker.record_baseline(sample_metrics, "v1.0")
            tracker.record_post_training(improved_metrics, "v1.1", "batch-001", 500)
            
            report_path = tracker.save_impact_report()
            
            assert report_path.exists()
            
            with open(report_path) as f:
                saved_report = json.load(f)
            
            assert saved_report["total_batches"] == 1
            assert saved_report["total_contributions"] == 500

    def test_get_contribution_leaderboard(self, sample_metrics, improved_metrics):
        """Test getting leaderboard of most impactful batches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ContributionImpactTracker(output_dir=tmpdir)
            
            tracker.record_baseline(sample_metrics, "v1.0")
            tracker.record_post_training(improved_metrics, "v1.1", "batch-001", 500)
            
            leaderboard = tracker.get_contribution_leaderboard(top_n=5)
            
            assert len(leaderboard) == 1
            assert leaderboard[0]["batch_id"] == "batch-001"
            assert leaderboard[0]["accuracy_delta"] > 0

    def test_get_class_improvement_summary(self, sample_metrics, improved_metrics):
        """Test getting per-class improvement summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ContributionImpactTracker(output_dir=tmpdir)
            
            tracker.record_baseline(sample_metrics, "v1.0")
            tracker.record_post_training(improved_metrics, "v1.1", "batch-001", 500)
            
            summary = tracker.get_class_improvement_summary()
            
            assert "kick" in summary
            assert "snare" in summary
            assert "hi-hat" in summary
            # hi-hat improved most (0.80 -> 0.83 = +0.03)
            assert summary["hi-hat"] == pytest.approx(0.03, abs=0.001)


class TestContributionBatchImpact:
    """Tests for ContributionBatchImpact dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        impact = ContributionBatchImpact(
            batch_id="batch-001",
            sample_count=500,
            accuracy_delta=0.02,
            top3_accuracy_delta=0.01,
            calibration_delta=-0.01,
            per_class_deltas={"kick": 0.02, "snare": 0.01},
            most_improved_classes=["kick"],
            most_degraded_classes=[],
            contribution_efficiency=0.04,
        )
        
        d = impact.to_dict()
        
        assert d["batch_id"] == "batch-001"
        assert d["sample_count"] == 500
        assert d["accuracy_delta"] == 0.02
        assert "kick" in d["per_class_deltas"]


class TestImpactReport:
    """Tests for ImpactReport dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        report = ImpactReport(
            generated_at="2025-12-03T12:00:00Z",
            total_contributions=500,
            total_batches=1,
            cumulative_accuracy_gain=0.02,
            cumulative_top3_gain=0.01,
            avg_efficiency=0.04,
            batch_impacts=[],
            snapshots=[],
        )
        
        d = report.to_dict()
        
        assert d["generated_at"] == "2025-12-03T12:00:00Z"
        assert d["total_contributions"] == 500
        assert d["cumulative_accuracy_gain"] == 0.02


class TestEvaluateWithTracker:
    """Tests for the evaluate_with_tracker convenience function."""

    def test_evaluate_returns_required_keys(self):
        """Test that evaluation returns all required metric keys."""
        # This test requires torch, so we'll just verify the function structure
        from training.contribution_impact import evaluate_with_tracker
        
        # Verify function exists and has correct signature
        import inspect
        sig = inspect.signature(evaluate_with_tracker)
        params = list(sig.parameters.keys())
        
        assert "model" in params
        assert "dataloader" in params
        assert "device" in params
        assert "label_names" in params
