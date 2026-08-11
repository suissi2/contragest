import re

def safe_excel_sheet_title(title):
    r"""
    Sanitizes a string for use as an Excel worksheet title.
    Removes illegal characters: * : ? / \ [ ]
    And truncates to 31 characters.
    """
    if not title:
        return "Sheet"
    
    # Replace illegal characters with underscore
    clean_title = re.sub(r'[*:?/\\\[\]]', '_', str(title))
    
    # Truncate to 31 chars
    return clean_title[:31]

def safe_excel_cell_str(val):
    """
    Sanitizes a value for use in an Excel cell.
    Removes control characters that cause openpyxl.utils.exceptions.IllegalCharacterError.
    """
    if val is None:
        return ""
    
    s = str(val)
    
    # Remove control characters (ASCII 0-31 except tab 9, LF 10, CR 13)
    # This is the most common cause of IllegalCharacterError in openpyxl
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s)
    
    return s
