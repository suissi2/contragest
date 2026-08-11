import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from datetime import datetime
from contragest.core.i18n import tr
from contragest.core.system_info import get_pc_info
from contragest.core.gui_utils import DesignTokens
import socket


class StatusBar(ttk.Frame):
    """
    A persistent status bar showing system info, session user, and clock.
    This is the full-featured version used exclusively in the main window.
    """
    def __init__(self, parent, user=None, bootstyle=DARK, show_user=True, **kwargs):
        super().__init__(parent, bootstyle=bootstyle, **kwargs)
        self.user = user
        self.show_user = show_user
        self._setup_ui()
        self._update_clock()

    def _setup_ui(self):
        style = ttk.Style()
        style.configure('StatusBar.TFrame', background=DesignTokens.SECONDARY)
        style.configure('StatusBar.TLabel', background=DesignTokens.SECONDARY, foreground=DesignTokens.PRIMARY, font=(DesignTokens.FONT_PRIMARY, 9))
        self.configure(style='StatusBar.TFrame')

        # 1. PC Info Section
        pc_name, local_ip = get_pc_info()
        self.lbl_pc = ttk.Label(
            self,
            text=f" {pc_name} ({local_ip})",
            style="StatusBar.TLabel"
        )
        self.lbl_pc.pack(side=LEFT, padx=10, pady=2)

        # 2. Session Section (Optional)
        if self.show_user and self.user:
            self.lbl_user = ttk.Label(
                self,
                text=f"\U0001f464 {self.user.username} ({self.user.role})",
                style="StatusBar.TLabel"
            )
            self.lbl_user.pack(side=LEFT, padx=10, pady=2)
            ttk.Separator(self, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5, pady=2)

        # 3. Environmental Info Section (Managed by parent update calls)
        self.lbl_env = ttk.Label(
            self,
            text="\U0001f30d " + tr("loading") + "...",
            style="StatusBar.TLabel"
        )
        self.lbl_env.pack(side=LEFT, padx=10, pady=2)

        ttk.Separator(self, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5, pady=2)

        # Status Message area (for dynamic feedback)
        self.lbl_status = ttk.Label(
            self,
            text="",
            style="StatusBar.TLabel"
        )
        self.lbl_status.pack(side=LEFT, padx=10, pady=2)

        # 4. Clock Section (Flush Right)
        self.lbl_clock = ttk.Label(
            self,
            text="",
            style="StatusBar.TLabel"
        )
        self.lbl_clock.pack(side=RIGHT, padx=10, pady=2)

        ttk.Sizegrip(self).pack(side=RIGHT)

    def set_env_info(self, location, temp):
        """Update the location and temperature displays."""
        if self.lbl_env.winfo_exists():
            self.lbl_env.config(text=f"\U0001f30d {location}   \U0001f321\ufe0f {temp}")

    def set_status(self, text, bootstyle="inverse-dark"):
        """Update the middle status text area."""
        if self.lbl_status.winfo_exists():
            self.lbl_status.config(text=text, bootstyle=bootstyle)

    def _update_clock(self):
        """Internal loop for ticking every second."""
        if not self.winfo_exists():
            return
        now = datetime.now()
        self.lbl_clock.config(text=now.strftime("\U0001f4c5 %d/%m/%Y   \U0001f552 %H:%M:%S"))
        self.after(1000, self._update_clock)


class StatusLabel(ttk.Label):
    """
    Lightweight status bar for child windows.
    Compatible drop-in for StatusBar — same set_status() API,
    but renders as a single ttk.Label with no clock, PC info, or env section.
    Avoids redundant widget trees, style configurations, and after() loops.
    """

    def __init__(self, parent, bootstyle="inverse-dark", **kwargs):
        super().__init__(parent, text="", bootstyle=bootstyle, **kwargs)

    def set_status(self, text, bootstyle="inverse-dark"):
        if self.winfo_exists():
            self.config(text=text, bootstyle=bootstyle)


class StatusBarController:
    """
    Owns the one true StatusBar widget in the main window.
    Provides set_status / set_env_info that delegate to the widget.
    Keeps a single after() clock loop instead of one per window.
    """

    def __init__(self, parent_frame, user=None):
        self._widget = StatusBar(parent_frame, user=user)
        self._widget.pack(side=BOTTOM, fill=X)

    def set_status(self, text, bootstyle="inverse-dark"):
        if self._widget.winfo_exists():
            self._widget.set_status(text, bootstyle)

    def set_env_info(self, location, temp):
        if self._widget.winfo_exists():
            self._widget.set_env_info(location, temp)

    def winfo_exists(self):
        return self._widget.winfo_exists()
