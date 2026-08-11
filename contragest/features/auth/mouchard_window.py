import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from contragest.lib.auth_core.ui.mouchard import MouchardPanel
from typing import Any
from contragest.core.status_bar import StatusLabel

class MouchardWindow(ttk.Toplevel):
    """
    Toplevel window container for the Mouchard audit log viewer.
    """
    def __init__(self, parent, auth_service: Any, current_user: Any):
        super().__init__(parent)
        self.title("Mouchard - Audit Log Viewer")
        self.geometry("1000x700")
        self.auth_service = auth_service
        self.current_user = current_user
        
        self._create_widgets()
        self._center_window()

    def _create_widgets(self):
        # Add Persistent Status Bar (Bottom) - Reserve before panel build
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status("Viewing Audit Logs")

        self.panel = MouchardPanel(self, self.auth_service, self.current_user)
        self.panel.pack(fill=BOTH, expand=YES)

    def _center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
