"""
Ensemble Training Script for Maximum Accuracy

Trains multiple models with different random seeds and configurations,
then combines them into an ensemble for maximum accuracy.

Benefits of Ensemble Training:
- 2-3% accuracy improvement over single model
- More robust predictions
- Better uncertainty estimation
- Reduced variance

Training Strategy:
1. Train N models with different seeds (diversity from randomness)
2. Optionally vary hyperparameters slightly (diversity from architecture)
3. Weight models by validation performance
4. Save ensemble configuration for inference

Usage:
    python train_ensemble.py --num-models 5 --dataset ./data --output ./ensemble
    
    # With different model types
    python train_ensemble.py --num-models 5 --model-types v2 v2 v2 ast ast
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple



@dataclass
class ModelConfig:
    """Configuration for a single model in the ensemble."""
    seed: int
    model_version: str = "v2"
    use_se: bool = True
    learning_rate: float = 0.0006
    weight_decay: float = 0.0001
    dropout: float = 0.3
    epochs: int = 100
    extra_flags: List[str] = field(default_factory=list)
    
    def to_cli_args(self) -> List[str]:
        """Convert to CLI arguments for train_classifier.py."""
        args = [
            "--seed", str(self.seed),
            "--model-version", self.model_version,
            "--lr", str(self.learning_rate),
            "--weight-decay", str(self.weight_decay),
            "--epochs", str(self.epochs),
        ]
        
        if self.use_se:
            args.append("--use-se")
        
        args.extend(self.extra_flags)
        return args


@dataclass
class EnsembleConfig:
    """Configuration for the entire ensemble."""
    num_models: int = 5
    base_seed: int = 1337
    model_configs: List[ModelConfig] = field(default_factory=list)
    output_dir: Path = field(default_factory=lambda: Path("./ensemble"))
    
    # Hyperparameter variation for diversity
    vary_learning_rate: bool = True
    vary_dropout: bool = True
    vary_architecture: bool = False
    
    def generate_configs(self):
        """Generate diverse model configurations."""
        self.model_configs = []
        
        # Learning rate variations
        lr_variations = [0.0004, 0.0005, 0.0006, 0.0007, 0.0008]
        
        # Dropout variations
        dropout_variations = [0.2, 0.25, 0.3, 0.35, 0.4]
        
        for i in range(self.num_models):
            seed = self.base_seed + i * 1000  # Well-separated seeds
            
            config = ModelConfig(
                seed=seed,
                model_version="v2",
                use_se=True,
            )
            
            if self.vary_learning_rate and i < len(lr_variations):
                config.learning_rate = lr_variations[i]
            
            if self.vary_dropout and i < len(dropout_variations):
                config.dropout = dropout_variations[i]
            
            self.model_configs.append(config)


class EnsembleTrainer:
    """
    Train multiple models for ensembling.
    
    Features:
    - Trains models sequentially with different seeds
    - Tracks validation performance for weighting
    - Saves ensemble configuration
    - Supports resume on failure
    """
    
    def __init__(
        self,
        config: EnsembleConfig,
        dataset_dir: Path,
        cache_dir: Optional[Path] = None,
        train_script: Optional[Path] = None,
    ):
        self.config = config
        self.dataset_dir = dataset_dir
        self.cache_dir = cache_dir
        self.train_script = train_script or Path("ai-pipeline/training/train_classifier.py")
        
        # Track results
        self.results: Dict[int, Dict] = {}
    
    def train_single_model(
        self, 
        model_config: ModelConfig,
        model_idx: int,
    ) -> Tuple[Path, float]:
        """
        Train a single model.
        
        Returns:
            Tuple of (model_path, validation_accuracy)
        """
        output_dir = self.config.output_dir / f"seed_{model_config.seed}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = [
            sys.executable,
            str(self.train_script),
            "--dataset", str(self.dataset_dir),
            "--output", str(output_dir),
        ]
        
        if self.cache_dir:
            cmd.extend(["--feature-cache-dir", str(self.cache_dir)])
        
        # Add model-specific args
        cmd.extend(model_config.to_cli_args())
        
        # Add cutting-edge features
        cmd.extend([
            "--mixup-alpha", "0.4",
            "--cutmix-alpha", "1.0",
            "--specaugment", "drum",
            "--focal-loss",
            "--focal-gamma", "2.0",
            "--use-ema",
            "--ema-decay", "0.999",
            "--progressive-augmentation",
            "--label-smoothing", "0.05",
            "--class-weights", "effective",
            "--max-class-weight", "10.0",
        ])
        
        print(f"\n{'='*60}")
        print(f"Training Model {model_idx + 1}/{self.config.num_models}")
        print(f"Seed: {model_config.seed}")
        print(f"Output: {output_dir}")
        print(f"{'='*60}\n")
        
        # Run training
        start_time = time.time()
        
        env = {
            **dict(__import__('os').environ),
            "PYTHONPATH": "ai-pipeline",
        }
        
        result = subprocess.run(
            cmd,
            env=env,
            cwd=str(self.config.output_dir.parent.parent.parent),
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode != 0:
            print(f"WARNING: Training failed for seed {model_config.seed}")
            return None, 0.0
        
        # Get validation accuracy from metrics
        metrics_file = output_dir / "metrics.json"
        best_model = output_dir / "best_drum_classifier.pth"
        ema_model = output_dir / "best_drum_classifier_ema.pth"
        
        # Prefer EMA model if available
        model_path = ema_model if ema_model.exists() else best_model
        
        # Read validation accuracy
        val_acc = 0.0
        if metrics_file.exists():
            try:
                with open(metrics_file) as f:
                    metrics = json.load(f)
                val_acc = metrics.get("best_val_accuracy", 0.0)
            except Exception:
                pass
        
        print(f"\nModel {model_idx + 1} completed in {elapsed/60:.1f} minutes")
        print(f"Validation accuracy: {val_acc:.2%}")
        print(f"Model saved to: {model_path}")
        
        return model_path, val_acc
    
    def train_all(self) -> Dict[str, any]:
        """
        Train all models in the ensemble.
        
        Returns:
            Dictionary with ensemble configuration and weights
        """
        if not self.config.model_configs:
            self.config.generate_configs()
        
        model_paths = []
        val_accuracies = []
        
        for i, model_config in enumerate(self.config.model_configs):
            path, acc = self.train_single_model(model_config, i)
            
            if path is not None:
                model_paths.append(str(path))
                val_accuracies.append(acc)
                
                self.results[model_config.seed] = {
                    "path": str(path),
                    "val_accuracy": acc,
                    "config": model_config.__dict__,
                }
        
        if not model_paths:
            raise RuntimeError("No models trained successfully")
        
        # Compute weights based on validation accuracy
        total_acc = sum(val_accuracies)
        if total_acc > 0:
            weights = [acc / total_acc for acc in val_accuracies]
        else:
            weights = [1.0 / len(val_accuracies)] * len(val_accuracies)
        
        # Create ensemble configuration
        ensemble_config = {
            "num_models": len(model_paths),
            "model_paths": model_paths,
            "model_classes": ["v2"] * len(model_paths),
            "weights": weights,
            "val_accuracies": val_accuracies,
            "training_configs": self.results,
        }
        
        # Save ensemble config
        config_path = self.config.output_dir / "ensemble_config.json"
        with open(config_path, "w") as f:
            json.dump(ensemble_config, f, indent=2)
        
        print(f"\n{'='*60}")
        print("ENSEMBLE TRAINING COMPLETE")
        print(f"{'='*60}")
        print(f"Models trained: {len(model_paths)}")
        print(f"Average accuracy: {sum(val_accuracies)/len(val_accuracies):.2%}")
        print(f"Best accuracy: {max(val_accuracies):.2%}")
        print(f"Config saved to: {config_path}")
        
        return ensemble_config
    
    def create_inference_pipeline(self):
        """Create inference pipeline from trained ensemble."""
        try:
            from training.inference.ultimate import UltimateInference
            
            config_path = self.config.output_dir / "ensemble_config.json"
            with open(config_path) as f:
                ensemble_config = json.load(f)
            
            return UltimateInference(
                model_paths=ensemble_config["model_paths"],
                model_classes=ensemble_config["model_classes"],
                weights=ensemble_config["weights"],
                use_tta=True,
            )
        except Exception as e:
            print(f"Could not create inference pipeline: {e}")
            return None


def main():
    parser = argparse.ArgumentParser(
        description="Train ensemble of drum classifiers for maximum accuracy"
    )
    
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to training dataset"
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./ensemble"),
        help="Output directory for ensemble"
    )
    
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Feature cache directory"
    )
    
    parser.add_argument(
        "--num-models",
        type=int,
        default=5,
        help="Number of models to train (default: 5)"
    )
    
    parser.add_argument(
        "--base-seed",
        type=int,
        default=1337,
        help="Base random seed (default: 1337)"
    )
    
    parser.add_argument(
        "--vary-lr",
        action="store_true",
        help="Vary learning rate across models"
    )
    
    parser.add_argument(
        "--vary-dropout",
        action="store_true",
        help="Vary dropout across models"
    )
    
    args = parser.parse_args()
    
    # Create ensemble config
    config = EnsembleConfig(
        num_models=args.num_models,
        base_seed=args.base_seed,
        output_dir=args.output,
        vary_learning_rate=args.vary_lr,
        vary_dropout=args.vary_dropout,
    )
    
    # Create trainer
    trainer = EnsembleTrainer(
        config=config,
        dataset_dir=args.dataset,
        cache_dir=args.cache_dir,
    )
    
    # Train ensemble
    ensemble_config = trainer.train_all()
    
    print("\nEnsemble training complete!")
    print(f"Configuration saved to: {args.output / 'ensemble_config.json'}")


if __name__ == "__main__":
    main()
