"""
Safe print utility for Windows console encoding issues.

Windows cmd.exe and PowerShell using cp1252 encoding cannot handle many Unicode
characters like emoji. This module provides a safe print function that gracefully
handles these encoding issues.

Usage:
    from training.utils.safe_print import safe_print
    safe_print("✓ Success!")  # Won't crash on Windows
"""

from __future__ import annotations

import io
import sys


# Common emoji to ASCII replacements for Windows console
EMOJI_REPLACEMENTS = {
    '⚠️': '[!]',
    '⚠': '[!]',
    '✓': '[OK]',
    '✗': '[X]',
    '📊': '[STATS]',
    '🎯': '[TARGET]',
    '💡': '[TIP]',
    '🔥': '[HOT]',
    '📈': '[UP]',
    '❌': '[X]',
    '✅': '[OK]',
    '🔷': '[*]',
    '💎': '[*]',
    '🧪': '[TEST]',
    '📌': '[NOTE]',
    '🎉': '[SUCCESS]',
    '⚡': '[FAST]',
    '📂': '[DIR]',
    '📤': '[SYNC]',
    '🤖': '[BOT]',
    '🔄': '[REFRESH]',
    '→': '->',
    '←': '<-',
    '↔': '<->',
    '•': '-',
    '●': '*',
    '○': 'o',
    '■': '#',
    '□': '[ ]',
    '▪': '-',
    '▫': '-',
    '━': '-',
    '═': '=',
    '║': '|',
    '╔': '+',
    '╗': '+',
    '╚': '+',
    '╝': '+',
    '╠': '+',
    '╣': '+',
    '╦': '+',
    '╩': '+',
    '╬': '+',
    '─': '-',
    '│': '|',
    '┌': '+',
    '┐': '+',
    '└': '+',
    '┘': '+',
    '├': '+',
    '┤': '+',
    '┬': '+',
    '┴': '+',
    '┼': '+',
}


def safe_print(*args, **kwargs) -> None:
    """
    Print with fallback for Windows encoding issues (cp1252 can't handle emoji).
    
    This function tries normal print first, and if that fails due to encoding
    issues, it replaces known emoji with ASCII equivalents.
    
    Args:
        *args: Positional arguments to pass to print()
        **kwargs: Keyword arguments to pass to print()
    """
    # Try normal print first
    try:
        print(*args, **kwargs)
        return
    except UnicodeEncodeError:
        pass
    
    # Fallback: replace unencodable characters
    output = io.StringIO()
    print(*args, file=output, **kwargs)
    text = output.getvalue()
    
    # Replace common emoji with ASCII equivalents
    for emoji, ascii_rep in EMOJI_REPLACEMENTS.items():
        text = text.replace(emoji, ascii_rep)
    
    # Final fallback: encode with 'replace' errors
    if sys.stdout.encoding:
        try:
            text = text.encode(sys.stdout.encoding, errors='replace').decode(
                sys.stdout.encoding, errors='replace'
            )
        except (UnicodeError, LookupError):
            pass
    
    sys.stdout.write(text)
    sys.stdout.flush()


def safe_format(text: str) -> str:
    """
    Format a string by replacing emoji with ASCII equivalents if needed.
    
    Args:
        text: The text to format
        
    Returns:
        The text with emoji replaced if encoding would fail
    """
    if sys.stdout.encoding:
        try:
            text.encode(sys.stdout.encoding)
            return text  # Encoding works, return as-is
        except UnicodeEncodeError:
            pass
    
    # Replace emoji
    for emoji, ascii_rep in EMOJI_REPLACEMENTS.items():
        text = text.replace(emoji, ascii_rep)
    
    return text


# Alias for convenience
sprint = safe_print


if __name__ == "__main__":
    # Quick test
    print("Testing safe_print...")
    safe_print("Test 1: ⚠️  Warning message with emoji")
    safe_print("Test 2: ✓ Success message")
    safe_print("Test 3: ❌ Error message")
    safe_print("Test 4: 🎉 Celebration!")
    safe_print("Test 5: Regular message without emoji")
    print("All tests passed!")
