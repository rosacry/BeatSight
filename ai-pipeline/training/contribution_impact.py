"""
Contribution Impact Tracking

Tracks how community contributions affect model accuracy over time.
This module provides infrastructure to:
1. Record baseline model metrics before adding contribution data
2. Track accuracy improvements after training with contributions
3. Link improvements to specific contribution batches
4. Generate impact reports for contributors

Usage:
    from training.contribution_impact import ContributionImpactTracker
    
    tracker = ContributionImpactTracker(output_dir="impact_reports")
    
    # Record baseline
    tracker.record_baseline(model, eval_dataset, "model_v1.0")
    
    # Train with contributions
    train_with_contributions(model, contribution_batch)
    
    # Record improvement
    tracker.record_post_training(model, eval_dataset, batch_id="contrib-20251203")
    
    # Generate report
    report = tracker.generate_impact_report()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EvaluationSnapshot:
    """Snapshot of model evaluation metrics at a point in time."""
    
    timestamp: str
    model_version: str
    overall_accuracy: float
    top3_accuracy: float
    per_class_accuracy: Dict[str, float]
    per_class_f1: Dict[str, float]
    calibration_error: float
    num_eval_samples: int
    contribution_batch_id: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "model_version": self.model_version,
            "overall_accuracy": self.overall_accuracy,
            "top3_accuracy": self.top3_accuracy,
            "per_class_accuracy": self.per_class_accuracy,
            "per_class_f1": self.per_class_f1,
            "calibration_error": self.calibration_error,
            "num_eval_samples": self.num_eval_samples,
            "contribution_batch_id": self.contribution_batch_id,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationSnapshot":
        return cls(**data)


@dataclass
class ContributionBatchImpact:
    """Impact metrics for a specific contribution batch."""
    
    batch_id: str
    sample_count: int
    accuracy_delta: float
    top3_accuracy_delta: float
    calibration_delta: float
    per_class_deltas: Dict[str, float]
    most_improved_classes: List[str]
    most_degraded_classes: List[str]
    contribution_efficiency: float  # Accuracy gain per sample
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "sample_count": self.sample_count,
            "accuracy_delta": self.accuracy_delta,
            "top3_accuracy_delta": self.top3_accuracy_delta,
            "calibration_delta": self.calibration_delta,
            "per_class_deltas": self.per_class_deltas,
            "most_improved_classes": self.most_improved_classes,
            "most_degraded_classes": self.most_degraded_classes,
            "contribution_efficiency": self.contribution_efficiency,
        }


@dataclass
class ImpactReport:
    """Full impact report across all contribution batches."""
    
    generated_at: str
    total_contributions: int
    total_batches: int
    cumulative_accuracy_gain: float
    cumulative_top3_gain: float
    avg_efficiency: float
    batch_impacts: List[ContributionBatchImpact]
    snapshots: List[EvaluationSnapshot]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_contributions": self.total_contributions,
            "total_batches": self.total_batches,
            "cumulative_accuracy_gain": self.cumulative_accuracy_gain,
            "cumulative_top3_gain": self.cumulative_top3_gain,
            "avg_efficiency": self.avg_efficiency,
            "batch_impacts": [b.to_dict() for b in self.batch_impacts],
            "snapshots": [s.to_dict() for s in self.snapshots],
        }


class ContributionImpactTracker:
    """
    Tracks and measures the impact of community contributions on model accuracy.
    
    This tracker maintains a history of evaluation snapshots before and after
    training with contribution batches, enabling measurement of:
    - Per-batch accuracy improvements
    - Per-class impact (which drum types improved most)
    - Contribution efficiency (accuracy gain per sample)
    - Cumulative impact over time
    """
    
    def __init__(self, output_dir: str = "impact_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.snapshots: List[EvaluationSnapshot] = []
        self.batch_sample_counts: Dict[str, int] = {}
        
        # Load existing history if available
        self._load_history()
    
    def _load_history(self) -> None:
        """Load existing snapshot history from disk."""
        history_file = self.output_dir / "history.json"
        if history_file.exists():
            try:
                with open(history_file) as f:
                    data = json.load(f)
                self.snapshots = [
                    EvaluationSnapshot.from_dict(s) for s in data.get("snapshots", [])
                ]
                self.batch_sample_counts = data.get("batch_sample_counts", {})
                logger.info(f"Loaded {len(self.snapshots)} historical snapshots")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")
    
    def _save_history(self) -> None:
        """Save snapshot history to disk."""
        history_file = self.output_dir / "history.json"
        with open(history_file, "w") as f:
            json.dump({
                "snapshots": [s.to_dict() for s in self.snapshots],
                "batch_sample_counts": self.batch_sample_counts,
            }, f, indent=2)
    
    def record_baseline(
        self,
        metrics: Dict[str, Any],
        model_version: str,
        notes: str = "Baseline before contributions",
    ) -> EvaluationSnapshot:
        """
        Record baseline model metrics before training with contributions.
        
        Args:
            metrics: Dictionary containing evaluation metrics
            model_version: Version identifier for the model
            notes: Optional notes about this snapshot
            
        Returns:
            The created EvaluationSnapshot
        """
        snapshot = EvaluationSnapshot(
            timestamp=datetime.utcnow().isoformat() + "Z",
            model_version=model_version,
            overall_accuracy=metrics.get("accuracy", 0.0),
            top3_accuracy=metrics.get("top3_accuracy", 0.0),
            per_class_accuracy=metrics.get("per_class_accuracy", {}),
            per_class_f1=metrics.get("per_class_f1", {}),
            calibration_error=metrics.get("calibration_error", 0.0),
            num_eval_samples=metrics.get("num_samples", 0),
            contribution_batch_id=None,
            notes=notes,
        )
        
        self.snapshots.append(snapshot)
        self._save_history()
        
        logger.info(
            f"Recorded baseline: accuracy={snapshot.overall_accuracy:.4f}, "
            f"model={model_version}"
        )
        
        return snapshot
    
    def record_post_training(
        self,
        metrics: Dict[str, Any],
        model_version: str,
        batch_id: str,
        sample_count: int,
        notes: str = "",
    ) -> EvaluationSnapshot:
        """
        Record metrics after training with a contribution batch.
        
        Args:
            metrics: Dictionary containing evaluation metrics
            model_version: Version identifier for the model
            batch_id: ID of the contribution batch used for training
            sample_count: Number of samples in the contribution batch
            notes: Optional notes about this snapshot
            
        Returns:
            The created EvaluationSnapshot
        """
        snapshot = EvaluationSnapshot(
            timestamp=datetime.utcnow().isoformat() + "Z",
            model_version=model_version,
            overall_accuracy=metrics.get("accuracy", 0.0),
            top3_accuracy=metrics.get("top3_accuracy", 0.0),
            per_class_accuracy=metrics.get("per_class_accuracy", {}),
            per_class_f1=metrics.get("per_class_f1", {}),
            calibration_error=metrics.get("calibration_error", 0.0),
            num_eval_samples=metrics.get("num_samples", 0),
            contribution_batch_id=batch_id,
            notes=notes,
        )
        
        self.snapshots.append(snapshot)
        self.batch_sample_counts[batch_id] = sample_count
        self._save_history()
        
        logger.info(
            f"Recorded post-training: accuracy={snapshot.overall_accuracy:.4f}, "
            f"batch={batch_id}, samples={sample_count}"
        )
        
        return snapshot
    
    def calculate_batch_impact(
        self,
        batch_id: str,
    ) -> Optional[ContributionBatchImpact]:
        """
        Calculate the impact of a specific contribution batch.
        
        Compares the snapshot immediately before and after training
        with the batch to measure its impact.
        
        Args:
            batch_id: The contribution batch ID to analyze
            
        Returns:
            ContributionBatchImpact or None if batch not found
        """
        # Find the snapshot for this batch
        batch_snapshot = None
        prev_snapshot = None
        
        for i, snapshot in enumerate(self.snapshots):
            if snapshot.contribution_batch_id == batch_id:
                batch_snapshot = snapshot
                if i > 0:
                    prev_snapshot = self.snapshots[i - 1]
                break
        
        if not batch_snapshot or not prev_snapshot:
            logger.warning(f"Cannot calculate impact for batch {batch_id}: missing snapshots")
            return None
        
        sample_count = self.batch_sample_counts.get(batch_id, 0)
        
        # Calculate deltas
        accuracy_delta = batch_snapshot.overall_accuracy - prev_snapshot.overall_accuracy
        top3_delta = batch_snapshot.top3_accuracy - prev_snapshot.top3_accuracy
        calibration_delta = batch_snapshot.calibration_error - prev_snapshot.calibration_error
        
        # Per-class deltas
        per_class_deltas = {}
        all_classes = set(batch_snapshot.per_class_accuracy.keys()) | set(prev_snapshot.per_class_accuracy.keys())
        
        for cls in all_classes:
            new_acc = batch_snapshot.per_class_accuracy.get(cls, 0.0)
            old_acc = prev_snapshot.per_class_accuracy.get(cls, 0.0)
            per_class_deltas[cls] = new_acc - old_acc
        
        # Find most improved/degraded
        sorted_deltas = sorted(per_class_deltas.items(), key=lambda x: x[1], reverse=True)
        most_improved = [cls for cls, delta in sorted_deltas[:3] if delta > 0]
        most_degraded = [cls for cls, delta in sorted_deltas[-3:] if delta < 0]
        
        # Calculate efficiency (accuracy gain per 1000 samples)
        efficiency = (accuracy_delta * 1000 / sample_count) if sample_count > 0 else 0.0
        
        return ContributionBatchImpact(
            batch_id=batch_id,
            sample_count=sample_count,
            accuracy_delta=accuracy_delta,
            top3_accuracy_delta=top3_delta,
            calibration_delta=calibration_delta,
            per_class_deltas=per_class_deltas,
            most_improved_classes=most_improved,
            most_degraded_classes=most_degraded,
            contribution_efficiency=efficiency,
        )
    
    def generate_impact_report(self) -> ImpactReport:
        """
        Generate a comprehensive impact report across all contribution batches.
        
        Returns:
            ImpactReport with cumulative statistics and per-batch breakdowns
        """
        # Find all contribution batches
        batch_ids = [
            s.contribution_batch_id 
            for s in self.snapshots 
            if s.contribution_batch_id
        ]
        
        # Calculate impact for each batch
        batch_impacts = []
        for batch_id in batch_ids:
            impact = self.calculate_batch_impact(batch_id)
            if impact:
                batch_impacts.append(impact)
        
        # Calculate cumulative metrics
        total_samples = sum(self.batch_sample_counts.values())
        cumulative_accuracy = sum(b.accuracy_delta for b in batch_impacts)
        cumulative_top3 = sum(b.top3_accuracy_delta for b in batch_impacts)
        
        avg_efficiency = (
            sum(b.contribution_efficiency for b in batch_impacts) / len(batch_impacts)
            if batch_impacts else 0.0
        )
        
        return ImpactReport(
            generated_at=datetime.utcnow().isoformat() + "Z",
            total_contributions=total_samples,
            total_batches=len(batch_impacts),
            cumulative_accuracy_gain=cumulative_accuracy,
            cumulative_top3_gain=cumulative_top3,
            avg_efficiency=avg_efficiency,
            batch_impacts=batch_impacts,
            snapshots=self.snapshots,
        )
    
    def save_impact_report(self, report: Optional[ImpactReport] = None) -> Path:
        """
        Save impact report to disk.
        
        Args:
            report: Optional report to save (generates new one if not provided)
            
        Returns:
            Path to the saved report file
        """
        if report is None:
            report = self.generate_impact_report()
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"impact_report_{timestamp}.json"
        
        with open(report_file, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        
        logger.info(f"Saved impact report to {report_file}")
        return report_file
    
    def get_contribution_leaderboard(
        self,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Generate a leaderboard of most impactful contribution batches.
        
        Args:
            top_n: Number of top batches to return
            
        Returns:
            List of batch impacts sorted by accuracy improvement
        """
        report = self.generate_impact_report()
        
        # Sort by accuracy delta (descending)
        sorted_batches = sorted(
            report.batch_impacts,
            key=lambda b: b.accuracy_delta,
            reverse=True,
        )
        
        return [b.to_dict() for b in sorted_batches[:top_n]]
    
    def get_class_improvement_summary(self) -> Dict[str, float]:
        """
        Get total accuracy improvement per class across all batches.
        
        Returns:
            Dictionary mapping class name to cumulative accuracy delta
        """
        report = self.generate_impact_report()
        
        class_totals: Dict[str, float] = {}
        for impact in report.batch_impacts:
            for cls, delta in impact.per_class_deltas.items():
                class_totals[cls] = class_totals.get(cls, 0.0) + delta
        
        return dict(sorted(class_totals.items(), key=lambda x: x[1], reverse=True))


def evaluate_with_tracker(
    model: "torch.nn.Module",
    dataloader: "torch.utils.data.DataLoader",
    device: str = "cuda",
    label_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluate a model and return metrics in tracker-compatible format.
    
    This is a convenience function that runs evaluation and formats
    results for use with ContributionImpactTracker.
    
    Args:
        model: The PyTorch model to evaluate
        dataloader: DataLoader for evaluation data
        device: Device to run evaluation on
        label_names: Optional list of class names
        
    Returns:
        Dictionary of evaluation metrics
    """
    import torch
    
    model.eval()
    model.to(device)
    
    all_preds = []
    all_labels = []
    all_probs = []
    
    with torch.no_grad():
        for batch in dataloader:
            if isinstance(batch, (list, tuple)):
                inputs, labels = batch[0], batch[1]
            else:
                inputs, labels = batch, None
            
            inputs = inputs.to(device)
            outputs = model(inputs)
            probs = torch.softmax(outputs, dim=1)
            preds = outputs.argmax(dim=1)
            
            all_preds.extend(preds.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
            if labels is not None:
                all_labels.extend(labels.numpy())
    
    all_preds = np.array(all_preds)
    all_probs = np.array(all_probs)
    all_labels = np.array(all_labels) if all_labels else None
    
    metrics = {
        "num_samples": len(all_preds),
    }
    
    if all_labels is not None and len(all_labels) > 0:
        # Overall accuracy
        metrics["accuracy"] = float(np.mean(all_preds == all_labels))
        
        # Top-3 accuracy
        top3_preds = np.argsort(all_probs, axis=1)[:, -3:]
        top3_correct = np.array([
            all_labels[i] in top3_preds[i] for i in range(len(all_labels))
        ])
        metrics["top3_accuracy"] = float(np.mean(top3_correct))
        
        # Per-class accuracy
        if label_names:
            per_class_acc = {}
            per_class_f1 = {}
            
            for i, name in enumerate(label_names):
                mask = all_labels == i
                if mask.sum() > 0:
                    per_class_acc[name] = float(np.mean(all_preds[mask] == i))
                    
                    # F1 calculation
                    tp = np.sum((all_preds == i) & (all_labels == i))
                    fp = np.sum((all_preds == i) & (all_labels != i))
                    fn = np.sum((all_preds != i) & (all_labels == i))
                    
                    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
                    per_class_f1[name] = float(f1)
            
            metrics["per_class_accuracy"] = per_class_acc
            metrics["per_class_f1"] = per_class_f1
        
        # Calibration error (ECE)
        confidences = np.max(all_probs, axis=1)
        correct = all_preds == all_labels
        
        n_bins = 10
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        
        for i in range(n_bins):
            in_bin = (confidences > bin_boundaries[i]) & (confidences <= bin_boundaries[i + 1])
            prop_in_bin = in_bin.mean()
            
            if prop_in_bin > 0:
                avg_confidence = confidences[in_bin].mean()
                avg_accuracy = correct[in_bin].mean()
                ece += np.abs(avg_accuracy - avg_confidence) * prop_in_bin
        
        metrics["calibration_error"] = float(ece)
    
    return metrics


if __name__ == "__main__":
    # Demo usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Contribution Impact Tracker Demo")
    parser.add_argument("--output-dir", default="impact_reports", help="Output directory")
    parser.add_argument("--show-report", action="store_true", help="Show current report")
    
    args = parser.parse_args()
    
    tracker = ContributionImpactTracker(output_dir=args.output_dir)
    
    if args.show_report:
        report = tracker.generate_impact_report()
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"Tracker initialized with {len(tracker.snapshots)} snapshots")
        print(f"Output directory: {tracker.output_dir}")
