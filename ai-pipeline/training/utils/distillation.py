"""
Knowledge Distillation for Drum Classification

Knowledge distillation transfers knowledge from a larger "teacher" model
to a smaller "student" model, often achieving better accuracy than
training the student directly.

Paper: "Distilling the Knowledge in a Neural Network" (Hinton et al., 2015)
       https://arxiv.org/abs/1503.02531

How it works:
1. Train a large teacher model (or use an ensemble as teacher)
2. Train student model on both:
   - Hard labels (actual ground truth)
   - Soft labels (teacher's probabilistic outputs)
3. The "soft" labels contain dark knowledge about class similarities

Benefits for drum classification:
- Smaller production model with teacher-level accuracy
- Knowledge about drum sound similarities (e.g., hi-hat open vs closed)
- Teacher can be an ensemble for even better soft labels
- Can use unlabeled data for self-training

Expected improvement: 1-3% accuracy on student model over direct training.

Usage:
    from training.utils.distillation import DistillationLoss, DistillationTrainer
    
    teacher = load_large_model(...)
    student = create_small_model(...)
    
    criterion = DistillationLoss(temperature=4.0, alpha=0.7)
    
    for batch in dataloader:
        student_logits = student(batch)
        teacher_logits = teacher(batch)
        loss = criterion(student_logits, teacher_logits, labels)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, List, Tuple
import copy


class DistillationLoss(nn.Module):
    """
    Knowledge Distillation Loss.
    
    Combines:
    - Hard loss: CrossEntropy with ground truth labels
    - Soft loss: KL divergence with teacher's soft predictions
    
    Args:
        temperature: Temperature for softening predictions (higher = softer)
                     Typical values: 2.0-8.0
        alpha: Weight of soft loss vs hard loss
               alpha=0.7 means 70% soft loss + 30% hard loss
        reduction: 'mean', 'sum', or 'none'
    
    Example:
        >>> criterion = DistillationLoss(temperature=4.0, alpha=0.7)
        >>> loss = criterion(student_logits, teacher_logits, labels)
    """
    
    def __init__(
        self,
        temperature: float = 4.0,
        alpha: float = 0.7,
        reduction: str = 'mean'
    ):
        super().__init__()
        self.temperature = temperature
        self.alpha = alpha
        self.reduction = reduction
        
        self.ce_loss = nn.CrossEntropyLoss(reduction=reduction)
        self.kl_loss = nn.KLDivLoss(reduction='batchmean')
    
    def forward(
        self,
        student_logits: torch.Tensor,
        teacher_logits: torch.Tensor,
        labels: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute distillation loss.
        
        Args:
            student_logits: Student model outputs [B, num_classes]
            teacher_logits: Teacher model outputs [B, num_classes]
            labels: Ground truth labels [B]
            
        Returns:
            Combined distillation loss
        """
        # Hard loss (student vs ground truth)
        hard_loss = self.ce_loss(student_logits, labels)
        
        # Soft loss (student vs teacher)
        # Both need to be softened by temperature
        student_soft = F.log_softmax(student_logits / self.temperature, dim=-1)
        teacher_soft = F.softmax(teacher_logits / self.temperature, dim=-1)
        
        # KL divergence expects log-probs for input, probs for target
        soft_loss = self.kl_loss(student_soft, teacher_soft)
        
        # Scale by T^2 as per Hinton's paper
        soft_loss = soft_loss * (self.temperature ** 2)
        
        # Combine losses
        total_loss = (1 - self.alpha) * hard_loss + self.alpha * soft_loss
        
        return total_loss


class FeatureDistillationLoss(nn.Module):
    """
    Feature-level Knowledge Distillation.
    
    In addition to matching output logits, this also matches intermediate
    feature representations between teacher and student.
    
    Benefits:
    - Richer knowledge transfer
    - Better gradient flow during training
    - Student learns better internal representations
    
    Args:
        temperature: Temperature for logit distillation
        alpha: Weight of soft loss
        beta: Weight of feature loss
        feature_transform: Optional projection if dimensions don't match
    """
    
    def __init__(
        self,
        temperature: float = 4.0,
        alpha: float = 0.5,
        beta: float = 0.5,
        student_dim: Optional[int] = None,
        teacher_dim: Optional[int] = None
    ):
        super().__init__()
        self.distill_loss = DistillationLoss(temperature, alpha)
        self.beta = beta
        
        # Projection layer if dimensions don't match
        if student_dim and teacher_dim and student_dim != teacher_dim:
            self.transform = nn.Linear(student_dim, teacher_dim)
        else:
            self.transform = None
    
    def forward(
        self,
        student_logits: torch.Tensor,
        teacher_logits: torch.Tensor,
        student_features: torch.Tensor,
        teacher_features: torch.Tensor,
        labels: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute feature + logit distillation loss.
        """
        # Logit distillation
        logit_loss = self.distill_loss(student_logits, teacher_logits, labels)
        
        # Feature distillation (MSE between features)
        if self.transform is not None:
            student_features = self.transform(student_features)
        
        feature_loss = F.mse_loss(student_features, teacher_features)
        
        return logit_loss + self.beta * feature_loss


class SelfDistillation(nn.Module):
    """
    Self-Distillation: Model distills knowledge from its own earlier checkpoints.
    
    This is useful when you don't have a separate teacher model.
    The idea: later layers learn from earlier layers, creating a
    form of deep supervision.
    
    Paper: "Be Your Own Teacher: Improve the Performance of Convolutional 
           Neural Networks via Self Distillation" (2019)
    """
    
    def __init__(
        self,
        model: nn.Module,
        temperature: float = 4.0,
        alpha: float = 0.5,
        checkpoint_interval: int = 10
    ):
        super().__init__()
        self.model = model
        self.temperature = temperature
        self.alpha = alpha
        self.checkpoint_interval = checkpoint_interval
        
        self.teacher_checkpoint = None
        self.epochs_since_checkpoint = 0
    
    def update_teacher(self, epoch: int):
        """Optionally update teacher from current model."""
        if epoch > 0 and epoch % self.checkpoint_interval == 0:
            # Save current model as new teacher
            self.teacher_checkpoint = copy.deepcopy(self.model.state_dict())
            self.epochs_since_checkpoint = 0
        else:
            self.epochs_since_checkpoint += 1
    
    @torch.no_grad()
    def get_teacher_logits(self, x: torch.Tensor) -> Optional[torch.Tensor]:
        """Get logits from teacher checkpoint."""
        if self.teacher_checkpoint is None:
            return None
        
        # Temporarily load teacher weights
        current_state = copy.deepcopy(self.model.state_dict())
        self.model.load_state_dict(self.teacher_checkpoint)
        self.model.eval()
        
        teacher_logits = self.model(x)
        
        # Restore current weights
        self.model.load_state_dict(current_state)
        self.model.train()
        
        return teacher_logits


class EnsembleTeacher(nn.Module):
    """
    Use an ensemble of models as the teacher.
    
    Multiple diverse models provide better soft labels than a single teacher.
    The ensemble's averaged predictions are smoother and more informative.
    
    Args:
        models: List of teacher models
        averaging: 'mean' for arithmetic mean, 'geometric' for geometric mean
    """
    
    def __init__(
        self,
        models: List[nn.Module],
        averaging: str = 'mean',
        device: Optional[torch.device] = None
    ):
        super().__init__()
        self.models = nn.ModuleList(models)
        self.averaging = averaging
        self.device = device
        
        # Freeze all teacher models
        for model in self.models:
            model.eval()
            for param in model.parameters():
                param.requires_grad = False
    
    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Get ensemble prediction."""
        all_logits = []
        
        for model in self.models:
            logits = model(x)
            all_logits.append(logits)
        
        stacked = torch.stack(all_logits, dim=0)
        
        if self.averaging == 'geometric':
            # Geometric mean in log space
            log_probs = F.log_softmax(stacked, dim=-1)
            avg_log_probs = log_probs.mean(dim=0)
            return avg_log_probs * 10  # Scale back to logit range
        else:
            # Arithmetic mean
            return stacked.mean(dim=0)


class DistillationTrainer:
    """
    Complete distillation training pipeline.
    
    Handles:
    - Teacher inference (with no_grad)
    - Student training
    - Optional feature distillation
    - Progressive temperature scheduling
    
    Args:
        teacher: Pre-trained teacher model
        student: Student model to train
        temperature: Initial temperature
        alpha: Soft label weight
        progressive_temperature: If True, decay temperature during training
    """
    
    def __init__(
        self,
        teacher: nn.Module,
        student: nn.Module,
        temperature: float = 4.0,
        alpha: float = 0.7,
        progressive_temperature: bool = True
    ):
        self.teacher = teacher
        self.student = student
        self.temperature = temperature
        self.alpha = alpha
        self.progressive_temperature = progressive_temperature
        
        self.initial_temperature = temperature
        
        # Freeze teacher
        self.teacher.eval()
        for param in self.teacher.parameters():
            param.requires_grad = False
        
        self.criterion = DistillationLoss(temperature, alpha)
    
    def get_temperature(self, epoch: int, total_epochs: int) -> float:
        """Get temperature for current epoch (optionally scheduled)."""
        if not self.progressive_temperature:
            return self.temperature
        
        # Decay temperature from initial to 1.0
        progress = epoch / total_epochs
        return 1.0 + (self.initial_temperature - 1.0) * (1 - progress)
    
    def train_step(
        self,
        inputs: torch.Tensor,
        labels: torch.Tensor,
        optimizer: torch.optim.Optimizer,
        epoch: int = 0,
        total_epochs: int = 100
    ) -> Tuple[float, torch.Tensor]:
        """
        Perform one training step.
        
        Returns:
            loss: Scalar loss value
            predictions: Student predictions
        """
        optimizer.zero_grad()
        
        # Get teacher predictions (no gradients)
        with torch.no_grad():
            teacher_logits = self.teacher(inputs)
        
        # Get student predictions
        student_logits = self.student(inputs)
        
        # Update temperature if using progressive scheduling
        current_temp = self.get_temperature(epoch, total_epochs)
        self.criterion.temperature = current_temp
        
        # Compute loss
        loss = self.criterion(student_logits, teacher_logits, labels)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        return loss.item(), student_logits


class OnlineDistillation(nn.Module):
    """
    Online Mutual Distillation: Multiple models teach each other simultaneously.
    
    Instead of teacher → student, we have:
    Model A ↔ Model B ↔ Model C
    
    Each model learns from the ensemble of all other models.
    This eliminates the need for a pre-trained teacher.
    
    Paper: "Deep Mutual Learning" (2018)
    """
    
    def __init__(
        self,
        models: List[nn.Module],
        temperature: float = 4.0,
        alpha: float = 0.5
    ):
        super().__init__()
        self.models = nn.ModuleList(models)
        self.temperature = temperature
        self.alpha = alpha
        
        self.ce_loss = nn.CrossEntropyLoss()
        self.kl_loss = nn.KLDivLoss(reduction='batchmean')
    
    def forward(
        self,
        x: torch.Tensor,
        labels: torch.Tensor
    ) -> Tuple[List[torch.Tensor], torch.Tensor]:
        """
        Forward pass with mutual distillation.
        
        Returns:
            all_logits: Logits from each model
            total_loss: Combined loss for all models
        """
        all_logits = [model(x) for model in self.models]
        
        total_loss = 0
        
        for i, logits in enumerate(all_logits):
            # Hard loss
            hard_loss = self.ce_loss(logits, labels)
            
            # Soft loss: learn from other models' ensemble
            other_logits = [l.detach() for j, l in enumerate(all_logits) if j != i]
            ensemble_logits = torch.stack(other_logits, dim=0).mean(dim=0)
            
            student_soft = F.log_softmax(logits / self.temperature, dim=-1)
            teacher_soft = F.softmax(ensemble_logits / self.temperature, dim=-1)
            soft_loss = self.kl_loss(student_soft, teacher_soft) * (self.temperature ** 2)
            
            total_loss += (1 - self.alpha) * hard_loss + self.alpha * soft_loss
        
        return all_logits, total_loss
