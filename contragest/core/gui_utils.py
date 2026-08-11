from datetime import datetime

def calculate_daily_password() -> str:
    """
    Standard security formula for sensitive deletions:
    ((day + month + (year % 100)) * 2) - 10
    """
    now = datetime.now()
    day = now.day
    month = now.month
    year_short = now.year % 100
    password = ((day + month + year_short) * 2) - 10
    return str(password)

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

class DesignTokens:
    """Centralized Design System tokens based on Nebula Deep Slate theme."""
    PRIMARY = "#7DD3FC"   # Lighter Sky Blue (Desaturated Azure)
    SECONDARY = "#334155" # Slate Blue/Gray
    SUCCESS = "#10B981"   # Emerald
    WARNING = "#F59E0B"   # Amber
    DANGER = "#EF4444"    # Rose
    SURFACE = "#1E293B"   # Midnight Card
    TEXT = "#F8FAFC"      # Clean White Text
    TEXT_MUTED = "#94A3B8" # Slate Gray
    
    # Background for the "Void"
    BG_APP = "#0F172A"    # Standard Midnight (Less dark than before)
    
    # Fonts
    FONT_PRIMARY = "Plus Jakarta Sans"
    FONT_DISPLAY = "Plus Jakarta Sans"
    FONT_MONO = "JetBrains Mono"
    
    # Density: Hybrid
    CARD_PADDING = 12
    TABLE_ROW_HEIGHT = 38
    FONT_SIZE_BODY = 10
    FONT_SIZE_HEADER = 16

def apply_premium_style(style_obj):
    """Applies Nebula Deep Slate style overrides."""
    # Global Dark Mode Base
    style_obj.configure('.', background=DesignTokens.BG_APP, foreground=DesignTokens.TEXT)
    
    # Tableview / Treeview - Slate High Contrast
    style_obj.configure('Treeview', 
                        rowheight=DesignTokens.TABLE_ROW_HEIGHT, 
                        font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY),
                        background=DesignTokens.SURFACE,
                        fieldbackground=DesignTokens.SURFACE,
                        foreground=DesignTokens.TEXT)
    style_obj.configure('Treeview.Heading', 
                        font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY, 'bold'),
                        background=DesignTokens.SECONDARY,
                        foreground=DesignTokens.PRIMARY)
    
    # Labelframe - Deep Blue Cards
    style_obj.configure('TLabelframe', 
                        background=DesignTokens.SURFACE,
                        bordercolor=DesignTokens.SECONDARY,
                        padding=DesignTokens.CARD_PADDING)
    style_obj.configure('TLabelframe.Label', 
                        background=DesignTokens.SURFACE,
                        foreground=DesignTokens.PRIMARY,
                        font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY + 1, 'bold'))
    
    # Standard Controls
    style_obj.configure('TFrame', background=DesignTokens.BG_APP)
    style_obj.configure('TLabel', background=DesignTokens.BG_APP, foreground=DesignTokens.TEXT)
    
    # Notebook Tabs - Modern Slate look
    style_obj.configure('TNotebook', background=DesignTokens.BG_APP, padding=0)
    style_obj.configure('TNotebook.Tab', 
                        padding=[15, 8], 
                        font=(DesignTokens.FONT_PRIMARY, 9, 'bold'),
                        background=DesignTokens.SECONDARY,
                        foreground=DesignTokens.TEXT_MUTED)
    style_obj.map('TNotebook.Tab',
                  background=[('selected', DesignTokens.SURFACE)],
                  foreground=[('selected', DesignTokens.PRIMARY)])
    
    # Buttons - Luminous Sky Blue
    style_obj.configure('TButton', font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY, 'bold'))
    style_obj.map("TButton",
                  background=[('active', DesignTokens.PRIMARY), ('!disabled', DesignTokens.SECONDARY)],
                  foreground=[('!disabled', '#FFFFFF')])
    
    # Focus States
    style_obj.map("TEntry", bordercolor=[("focus", DesignTokens.PRIMARY)])
    style_obj.map("TCombobox", bordercolor=[("focus", DesignTokens.PRIMARY)])
