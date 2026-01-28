"""
UTF-8 Encoding Fix for Windows
===============================
Import this at the top of every phase to prevent UnicodeEncodeError on Windows.

Usage:
    from utils.encoding_fix import force_utf8
    force_utf8()  # Call once at module level
"""
import sys
import io


def force_utf8():
    """Force UTF-8 encoding for all file operations on Windows."""
    if sys.platform=='win32':
        # Force UTF-8 for stdout/stderr
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

        # Monkey-patch built-in open to default to UTF-8
        import builtins
        _original_open = builtins.open

        def utf8_open(file, mode='r', buffering=-1, encoding=None, *args, **kwargs):
            """Override built-in open to use UTF-8 by default on Windows."""
            if encoding is None and isinstance(file, (str, bytes)):
                # Default to UTF-8 for text mode
                if 'b' not in mode:
                    encoding = 'utf-8'
            return _original_open(file, mode, buffering, encoding, *args, **kwargs)

        # Replace built-in open
        builtins.open = utf8_open


# Auto-apply when imported
force_utf8()
