from ttkbootstrap.constants import *
from contragest.core.i18n import get_lang_manager

def is_rtl():
    return get_lang_manager().is_rtl()

def pack_start(widget, **kwargs):
    """Packs widget to the START (Left in LTR, Right in RTL)."""
    side = RIGHT if is_rtl() else LEFT
    widget.pack(side=side, **kwargs)

def pack_end(widget, **kwargs):
    """Packs widget to the END (Right in LTR, Left in RTL)."""
    side = LEFT if is_rtl() else RIGHT
    widget.pack(side=side, **kwargs)
    
def get_anchor_start():
    """Returns 'e' (East/Right) for RTL, 'w' (West/Left) for LTR."""
    return E if is_rtl() else W

def get_anchor_end():
    """Returns 'w' (West/Left) for RTL, 'e' (East/Right) for LTR."""
    return W if is_rtl() else E
