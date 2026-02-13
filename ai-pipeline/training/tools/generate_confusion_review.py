#!/usr/bin/env python3
"""
Generate HTML Review Page for Confused Samples

Creates an interactive HTML page showing spectrograms of confused samples
for visual verification. Useful when audio files are not available.

Usage:
    python generate_confusion_review.py \
        --confusion-json confused_samples/kick_to_hihat_closed_confused.json \
        --feature-cache-dir F:/feature_cache \
        --dataset F:/datasets/prod_v5_cleaned \
        --output confused_samples/review_kick_hihat.html \
        --max-samples 50
"""

import argparse
import base64
import io
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

# Add ai-pipeline to path
AI_PIPELINE_ROOT = Path(__file__).resolve().parents[2]
if str(AI_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_ROOT))


def spectrogram_to_base64(spec: np.ndarray) -> str:
    """Convert spectrogram to base64-encoded PNG."""
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.imshow(spec, aspect='auto', origin='lower', cmap='magma')
    ax.set_xlabel('Time')
    ax.set_ylabel('Frequency')
    ax.set_xticks([])
    ax.set_yticks([])
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=80)
    plt.close(fig)
    buf.seek(0)
    
    return base64.b64encode(buf.read()).decode('utf-8')


def generate_html(
    samples: List[Dict],
    true_class: str,
    pred_class: str,
    total_confused: int,
) -> str:
    """Generate HTML review page."""
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Confusion Review: {true_class} → {pred_class}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            color: #ff6b6b;
            text-align: center;
        }}
        .stats {{
            background: #16213e;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .stats span {{
            font-size: 24px;
            color: #4ecdc4;
            font-weight: bold;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: #16213e;
            border-radius: 10px;
            padding: 15px;
            border: 2px solid transparent;
            transition: border-color 0.3s;
        }}
        .card.marked-kick {{
            border-color: #4ecdc4;
        }}
        .card.marked-hihat {{
            border-color: #ff6b6b;
        }}
        .card.marked-unclear {{
            border-color: #ffd93d;
        }}
        .card img {{
            width: 100%;
            border-radius: 5px;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .confidence {{
            background: #ff6b6b;
            padding: 5px 10px;
            border-radius: 15px;
            font-weight: bold;
        }}
        .file-path {{
            font-size: 12px;
            color: #888;
            word-break: break-all;
            margin-top: 10px;
        }}
        .buttons {{
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }}
        .buttons button {{
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.1s;
        }}
        .buttons button:hover {{
            transform: scale(1.05);
        }}
        .btn-kick {{
            background: #4ecdc4;
            color: #1a1a2e;
        }}
        .btn-hihat {{
            background: #ff6b6b;
            color: white;
        }}
        .btn-unclear {{
            background: #ffd93d;
            color: #1a1a2e;
        }}
        .summary {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #16213e;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        .summary h3 {{
            margin-top: 0;
        }}
        .summary-item {{
            display: flex;
            justify-content: space-between;
            gap: 20px;
            margin: 5px 0;
        }}
        #export-btn {{
            margin-top: 15px;
            padding: 10px 20px;
            background: #4ecdc4;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            width: 100%;
        }}
        .legend {{
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-bottom: 20px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .legend-dot {{
            width: 15px;
            height: 15px;
            border-radius: 50%;
        }}
    </style>
</head>
<body>
    <h1>🔍 Confusion Review: {true_class} → {pred_class}</h1>
    
    <div class="stats">
        <p>Model predicted <span>{pred_class}</span> but labels say <span>{true_class}</span></p>
        <p>Total confused samples: <span>{total_confused:,}</span> | Showing top <span>{len(samples)}</span> by confidence</p>
    </div>
    
    <div class="legend">
        <div class="legend-item">
            <div class="legend-dot" style="background: #4ecdc4;"></div>
            <span>Actually {true_class} (label correct)</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #ff6b6b;"></div>
            <span>Actually {pred_class} (label wrong)</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #ffd93d;"></div>
            <span>Unclear / Could be either</span>
        </div>
    </div>
    
    <div class="grid">
"""
    
    for i, sample in enumerate(samples):
        html += f"""
        <div class="card" id="card-{i}" data-idx="{sample['index']}">
            <div class="card-header">
                <span>#{i+1}</span>
                <span class="confidence">{sample['confidence']*100:.1f}% {pred_class}</span>
            </div>
            <img src="data:image/png;base64,{sample['spectrogram']}" alt="Spectrogram">
            <div class="file-path">{sample['file']}</div>
            <div class="buttons">
                <button class="btn-kick" onclick="mark({i}, 'kick')">✓ {true_class}</button>
                <button class="btn-hihat" onclick="mark({i}, 'hihat')">✗ {pred_class}</button>
                <button class="btn-unclear" onclick="mark({i}, 'unclear')">? Unclear</button>
            </div>
        </div>
"""
    
    html += f"""
    </div>
    
    <div class="summary">
        <h3>Review Progress</h3>
        <div class="summary-item">
            <span>Label Correct ({true_class}):</span>
            <span id="count-kick">0</span>
        </div>
        <div class="summary-item">
            <span>Label Wrong ({pred_class}):</span>
            <span id="count-hihat">0</span>
        </div>
        <div class="summary-item">
            <span>Unclear:</span>
            <span id="count-unclear">0</span>
        </div>
        <button id="export-btn" onclick="exportResults()">Export Results</button>
    </div>
    
    <script>
        const marks = {{}};
        const samples = {json.dumps([{'index': s['index'], 'file': s['file']} for s in samples])};
        
        function mark(idx, type) {{
            const card = document.getElementById('card-' + idx);
            card.className = 'card marked-' + type;
            marks[idx] = type;
            updateCounts();
        }}
        
        function updateCounts() {{
            let kick = 0, hihat = 0, unclear = 0;
            for (const [idx, type] of Object.entries(marks)) {{
                if (type === 'kick') kick++;
                else if (type === 'hihat') hihat++;
                else if (type === 'unclear') unclear++;
            }}
            document.getElementById('count-kick').textContent = kick;
            document.getElementById('count-hihat').textContent = hihat;
            document.getElementById('count-unclear').textContent = unclear;
        }}
        
        function exportResults() {{
            const results = {{
                true_class: '{true_class}',
                pred_class: '{pred_class}',
                total_reviewed: Object.keys(marks).length,
                label_correct: [],
                label_wrong: [],
                unclear: []
            }};
            
            for (const [idx, type] of Object.entries(marks)) {{
                const sample = samples[parseInt(idx)];
                if (type === 'kick') results.label_correct.push(sample);
                else if (type === 'hihat') results.label_wrong.push(sample);
                else results.unclear.push(sample);
            }}
            
            const blob = new Blob([JSON.stringify(results, null, 2)], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = '{true_class}_to_{pred_class}_review_results.json';
            a.click();
        }}
    </script>
</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML confusion review page")
    parser.add_argument("--confusion-json", type=Path, required=True)
    parser.add_argument("--feature-cache-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-samples", type=int, default=50)
    args = parser.parse_args()
    
    # Load confusion data
    with open(args.confusion_json, 'r') as f:
        data = json.load(f)
    
    true_class, pred_class = data['confusion_pair']
    samples = data['samples'][:args.max_samples]
    total_confused = data['total_confused']
    
    print(f"Generating review for {true_class} → {pred_class}")
    print(f"Total confused: {total_confused:,}, showing {len(samples)}")
    
    # Load dataset to get spectrograms
    print("\nLoading dataset for spectrogram extraction...")
    from training.train_classifier import DrumSampleDataset
    
    val_dir = args.dataset / "val"
    labels_file = None
    if (val_dir / "val_labels_files.npy").exists():
        labels_file = val_dir / "val_labels.npy"
    elif (val_dir / "labels.json").exists():
        labels_file = val_dir / "labels.json"
    
    cache_mapping = val_dir / "cache_mapping.npz"
    if not cache_mapping.exists():
        cache_mapping = None
    
    val_dataset = DrumSampleDataset(
        data_dir=val_dir,
        labels_file=labels_file,
        cache_dir=args.feature_cache_dir / "val",
        cache_mapping=cache_mapping,
    )
    
    # Extract spectrograms
    print("Extracting spectrograms...")
    for i, sample in enumerate(samples):
        idx = sample['index']
        try:
            spec_tensor, label = val_dataset[idx]
            spec = spec_tensor.squeeze().numpy()
            sample['spectrogram'] = spectrogram_to_base64(spec)
            print(f"  [{i+1}/{len(samples)}] Index {idx} ✓")
        except Exception as e:
            print(f"  [{i+1}/{len(samples)}] Index {idx} ✗ {e}")
            # Create placeholder
            placeholder = np.random.rand(128, 128) * 0.1
            sample['spectrogram'] = spectrogram_to_base64(placeholder)
    
    # Generate HTML
    html = generate_html(samples, true_class, pred_class, total_confused)
    
    # Save
    if args.output is None:
        args.output = args.confusion_json.parent / f"review_{true_class}_{pred_class}.html"
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✓ Generated: {args.output}")
    print(f"  Open in browser to review samples and mark them as:")
    print(f"    - '{true_class}' (label is correct)")
    print(f"    - '{pred_class}' (label is wrong - model is right)")
    print(f"    - 'Unclear' (can't tell)")


if __name__ == "__main__":
    main()
