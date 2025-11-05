"""
Simple training script for the drum classifier CNN.

Usage:
    python train_classifier.py --dataset ./dataset --epochs 50 --batch-size 32

Optionally emit a metrics JSON for downstream automation:
    python train_classifier.py --dataset ./dataset --metrics-json reports/run.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import librosa
import numpy as np
from tqdm import tqdm

# Import our model
import sys
sys.path.append(str(Path(__file__).parent.parent))
from transcription.ml_drum_classifier import DrumClassifierCNN


class DrumSampleDataset(Dataset):
    """PyTorch dataset for drum samples."""
    
    def __init__(self, data_dir: str, labels_file: str, sr: int = 44100):
        self.data_dir = Path(data_dir)
        self.sr = sr
        
        with open(labels_file, 'r') as f:
            self.labels = json.load(f)
    
    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        item = self.labels[idx]
        audio_path = self.data_dir / item['file']
        label = item['component_idx']
        
        # Load audio
        audio, _ = librosa.load(audio_path, sr=self.sr)
        
        # Compute mel-spectrogram
        mel_spec = librosa.feature.melspectrogram(
            y=audio,
            sr=self.sr,
            n_mels=128,
            fmax=8000,
            hop_length=len(audio) // 128 + 1
        )
        
        # Convert to log scale
        mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
        
        # Normalize
        mel_spec_norm = (mel_spec_db - mel_spec_db.min()) / (mel_spec_db.max() - mel_spec_db.min() + 1e-8)
        
        # Resize to 128x128
        if mel_spec_norm.shape[1] != 128:
            mel_spec_norm = np.resize(mel_spec_norm, (128, 128))
        
        # Convert to tensor
        features = torch.from_numpy(mel_spec_norm).float().unsqueeze(0)
        
        return features, label


def train_epoch(model, dataloader, criterion, optimizer, device):
    """Train for one epoch."""
    model.train()
    total_loss = 0
    correct = 0
    total = 0
    
    pbar = tqdm(dataloader, desc="Training")
    for features, labels in pbar:
        features, labels = features.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(features)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()
        
        pbar.set_postfix({'loss': f'{loss.item():.4f}', 'acc': f'{100 * correct / total:.2f}%'})
    
    return total_loss / len(dataloader), 100 * correct / total


def validate(model, dataloader, criterion, device):
    """Validate the model."""
    model.eval()
    total_loss = 0
    correct = 0
    total = 0
    
    with torch.no_grad():
        for features, labels in tqdm(dataloader, desc="Validation"):
            features, labels = features.to(device), labels.to(device)
            outputs = model(features)
            loss = criterion(outputs, labels)
            
            total_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    
    return total_loss / len(dataloader), 100 * correct / total


def main():
    parser = argparse.ArgumentParser(description="Train Drum Classifier CNN")
    parser.add_argument("--dataset", required=True, help="Path to dataset directory")
    parser.add_argument("--epochs", type=int, default=50, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--output", default="models", help="Output directory for models")
    parser.add_argument("--device", default=None, help="Device (cuda/cpu)")
    parser.add_argument(
        "--metrics-json",
        type=Path,
        help="Optional path to write training metrics as JSON",
    )
    
    args = parser.parse_args()
    
    # Setup device
    device = args.device or ('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Load datasets
    dataset_path = Path(args.dataset)
    train_dataset = DrumSampleDataset(
        dataset_path / "train",
        dataset_path / "train_labels.json"
    )
    val_dataset = DrumSampleDataset(
        dataset_path / "val",
        dataset_path / "val_labels.json"
    )
    
    print(f"Training samples: {len(train_dataset)}")
    print(f"Validation samples: {len(val_dataset)}")
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    
    # Load component info
    with open(dataset_path / "components.json", 'r') as f:
        components_info = json.load(f)
    num_classes = components_info['num_classes']
    
    # Initialize model
    model = DrumClassifierCNN(num_classes=num_classes)
    model.to(device)
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=5)
    
    # Training loop
    best_val_acc = 0.0
    best_epoch = -1
    best_model_path: Path | None = None
    history: List[Dict[str, float]] = []
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)
    
    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch + 1}/{args.epochs}")
        print("-" * 60)
        
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = validate(model, val_loader, criterion, device)

        history.append(
            {
                "epoch": float(epoch + 1),
                "train_loss": float(train_loss),
                "train_accuracy": float(train_acc),
                "val_loss": float(val_loss),
                "val_accuracy": float(val_acc),
            }
        )
        
        scheduler.step(val_loss)
        
        print(f"Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.2f}%")
        print(f"Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2f}%")
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch + 1
            model_path = output_dir / "best_drum_classifier.pth"
            torch.save(model.state_dict(), model_path)
            best_model_path = model_path
            print(f"✓ Saved best model (acc: {val_acc:.2f}%)")
    
    # Save final model
    final_model_path = output_dir / "final_drum_classifier.pth"
    torch.save(model.state_dict(), final_model_path)
    
    print("\n" + "=" * 60)
    print(f"Training complete!")
    print(f"Best validation accuracy: {best_val_acc:.2f}%")
    print(f"Models saved to: {output_dir}")
    print("=" * 60)

    if args.metrics_json:
        metrics = {
            "epochs": int(args.epochs),
            "batch_size": int(args.batch_size),
            "learning_rate": float(args.lr),
            "device": str(device),
            "best_validation_accuracy": float(best_val_acc),
            "best_epoch": int(best_epoch),
            "best_model_path": str(best_model_path) if best_model_path else None,
            "final_train_loss": float(history[-1]["train_loss"]) if history else None,
            "final_val_loss": float(history[-1]["val_loss"]) if history else None,
            "final_train_accuracy": float(history[-1]["train_accuracy"]) if history else None,
            "final_val_accuracy": float(history[-1]["val_accuracy"]) if history else None,
            "history": history,
        }
        metrics_path = args.metrics_json
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with metrics_path.open("w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)


if __name__ == "__main__":
    main()
