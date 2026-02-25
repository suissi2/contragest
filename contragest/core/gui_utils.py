import tkinter as tk

def center_window(window, width=None, height=None):
    """
    Centers a tkinter window on the screen.
    Handles high DPI scaling if width/height are already set.
    """
    window.update_idletasks()
    
    # If no dimensions provided, use current ones
    if width is None:
        width = window.winfo_width()
    if height is None:
        height = window.winfo_height()
        
    # Get screen dimensions
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # Calculate position
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    
    # Apply geometry
    window.geometry(f'{width}x{height}+{max(0, x)}+{max(0, y)}')

def make_transient(child, parent):
    """Makes a child window transient for a parent."""
    child.transient(parent)
    child.grab_set()
    center_window(child)
