import re

def safe_pdf_str(val):
    """
    Sanitizes a string for FPDF default fonts (Helvetica, etc.).
    Replaces common non-Latin1 characters with their nearest equivalents
    or a safe placeholder to prevent UnicodeEncodeError.
    """
    if val is None:
        return ""
    
    s = str(val)
    
    # 1. Common smart quotes and dashes from Word/Copy-Paste
    replacements = {
        "\u2013": "-", # en dash
        "\u2014": "-", # em dash
        "\u2018": "'", # left single quote
        "\u2019": "'", # right single quote
        "\u201c": '"', # left double quote
        "\u201d": '"', # right double quote
        "\u2026": "...", # ellipsis
        "\u00a0": " ",  # non-breaking space
    }
    
    for char, replacement in replacements.items():
        s = s.replace(char, replacement)
        
    # 2. Final defensive pass: encode to latin-1 and back, replacing unknown chars
    # Note: 'replace' will put a '?' which is better than a crash.
    # 'ignore' would just remove them.
    try:
        return s.encode("latin-1", "replace").decode("latin-1")
    except:
        # Fallback to absolute basics if even that fails
        return "".join(c if ord(c) < 256 else "?" for c in s)
