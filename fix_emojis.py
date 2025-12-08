#!/usr/bin/env python3
"""Replace emojis with ASCII-safe alternatives for Windows compatibility."""

import sys

def main():
    filepath = "ai-pipeline/training/train_classifier.py"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace emojis with ASCII-safe alternatives
    replacements = [
        ('\U0001F52C', '[DIAG]'),      # 🔬
        ('\U0001F4CA', '[STATS]'),     # 📊
        ('\U0001F6A8', '[ALERT]'),     # 🚨
        ('\u274C', '[X]'),             # ❌
        ('\u26A0\uFE0F', '[WARN]'),    # ⚠️
        ('\u26A0', '[WARN]'),          # ⚠ (without variation selector)
        ('\u2705', '[OK]'),            # ✅
        ('\U0001F4A1', '[TIP]'),       # 💡
        ('\U0001F6D1', '[STOP]'),      # 🛑
        ('\U0001F3E5', '[HEALTH]'),    # 🏥
    ]
    
    count = 0
    for emoji, replacement in replacements:
        if emoji in content:
            occurrences = content.count(emoji)
            content = content.replace(emoji, replacement)
            count += occurrences
            print(f"  Replaced {occurrences}x {repr(emoji)} -> {replacement}")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\nTotal replacements: {count}")
    print("Done! File is now Windows-safe.")

if __name__ == "__main__":
    main()
