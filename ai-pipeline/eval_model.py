"""Quick model evaluation on validation data."""
import torch
import numpy as np
import sys
from training.models.cnn_v5 import cnn_v5_large
from sklearn.metrics import f1_score

print("Loading model...", flush=True)
ckpt = torch.load('runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt', map_location='cuda', weights_only=False)
sd = {k.replace('backbone.', ''): v for k,v in ckpt['model_state_dict'].items()}
model = cnn_v5_large(num_classes=12, drop_path_rate=0.0, use_deep_supervision=False, use_multi_task=False)
model.load_state_dict(sd, strict=True)
model.cuda().eval()

print("Loading val data...", flush=True)
val_feats = np.load('F:/datasets/multilabel_cached/val/features.npy', mmap_mode='r')
val_labels = np.load('F:/datasets/multilabel_cached/val/labels.npy', mmap_mode='r')
n = len(val_feats)
print(f'Samples: {n}', flush=True)

all_probs = []
for start in range(0, n, 256):
    end = min(start + 256, n)
    batch = val_feats[start:end].copy()
    x = torch.from_numpy(batch).float().unsqueeze(1).cuda()
    with torch.inference_mode():
        probs = torch.sigmoid(model(x)).cpu().numpy()
    all_probs.append(probs)
all_probs = np.concatenate(all_probs, axis=0)

components = ['china','crash','cross_stick','hihat_closed','hihat_open','hihat_pedal','kick','ride_bell','ride_bow','snare','splash','tom']
preds_05 = (all_probs >= 0.5).astype(int)
labels = val_labels[:n]

micro_f1 = f1_score(labels, preds_05, average='micro')
macro_f1 = f1_score(labels, preds_05, average='macro')
print(f'\nMicro-F1={micro_f1:.4f}, Macro-F1={macro_f1:.4f}', flush=True)

print('\nPer-class (threshold=0.5):', flush=True)
for i, name in enumerate(components):
    gt_pos = labels[:, i].sum()
    pred_pos = preds_05[:, i].sum()
    tp = ((preds_05[:, i] == 1) & (labels[:, i] == 1)).sum()
    mp = all_probs[:, i].mean()
    print(f'{name:15s}: GT={int(gt_pos):5d} Pred={int(pred_pos):5d} TP={int(tp):5d} MeanP={mp:.4f}', flush=True)

print('\nSplash prob distribution:', flush=True)
splash_probs = all_probs[:, 10]
for t in [0.1, 0.3, 0.5, 0.7, 0.9]:
    print(f'  splash>={t:.1f}: {(splash_probs>=t).sum()}', flush=True)
print(f'  splash GT pos: {int(labels[:,10].sum())}', flush=True)
print('\nDONE', flush=True)
