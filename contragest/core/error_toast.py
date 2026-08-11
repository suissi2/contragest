"""
error_toast.py
──────────────
OLED-dark animated toast notification for Contragest.

Usage:
    from contragest.core.error_toast import ErrorToastManager
    # Once at startup:
    toast_mgr = ErrorToastManager(root_window)
    # Then pass toast_mgr.show as the ui_callback to ErrorReporter:
    ErrorReporter.set_ui_callback(root_window, toast_mgr.show)
"""

from __future__ import annotations

import tkinter as tk
import time
from tkinter import scrolledtext
from collections import deque
from typing import Deque, Optional, Callable
import ttkbootstrap as ttk
from ttkbootstrap.tableview import Tableview
from contragest.core.gui_utils import center_window

# ── Design constants (matches DesignTokens) ───────────────────────────────────
_BG          = "#1E293B"
_BORDER      = "#334155"
_TEXT        = "#F8FAFC"
_TEXT_MUTED  = "#94A3B8"
_FONT_BODY   = ("Segoe UI", 9)
_FONT_BOLD   = ("Segoe UI", 9, "bold")
_FONT_MONO   = ("Consolas", 8)

_CATEGORY_COLORS = {
    "SQL / Database":    "#FF6B6B",
    "Authentication":    "#FFD166",
    "Network / SMTP":    "#06D6A0",
    "File / IO":         "#118AB2",
    "Threading":         "#9B5DE5",
    "Application":       "#EF476F",
}
_CATEGORY_ICONS = {
    "SQL / Database":    "🗄️",
    "Authentication":    "🔐",
    "Network / SMTP":    "🌐",
    "File / IO":         "📂",
    "Threading":         "🧵",
    "Application":       "⚠️",
}

_TOAST_W       = 380
_TOAST_H       = 110
_MARGIN_RIGHT  = 18
_MARGIN_BOTTOM = 54   # above status bar
_STACK_GAP     = 8
_MAX_STACK     = 4
_DISPLAY_MS    = 7000
_SLIDE_STEPS   = 14
_SLIDE_MS      = 16   # ~60 fps


class _Toast(tk.Toplevel):
    """Single toast banner — slides in from the right, auto-dismisses."""

    def __init__(self, root: tk.Tk, entry, slot: int,
                 on_dismiss: callable):
        super().__init__(root)
        self._entry      = entry
        self._slot       = slot
        self._on_dismiss = on_dismiss

        # Window chrome
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.97)
        except Exception:
            pass

        color = _CATEGORY_COLORS.get(entry.category, "#EF476F")
        icon  = _CATEGORY_ICONS.get(entry.category,  "⚠️")

        # ── Layout ────────────────────────────────────────────────────────────
        outer = tk.Frame(self, bg=color, padx=2, pady=2)
        outer.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(outer, bg=_BG, padx=10, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        # Top row
        top = tk.Frame(inner, bg=_BG)
        top.pack(fill=tk.X)

        tk.Label(top, text=f"{icon}  {entry.category}",
                 font=_FONT_BOLD, bg=_BG, fg=color, anchor="w"
                 ).pack(side=tk.LEFT)

        tk.Label(top, text="✕", font=_FONT_BOLD, bg=_BG, fg=_TEXT_MUTED,
                 cursor="hand2"
                 ).pack(side=tk.RIGHT)
        top.winfo_children()[-1].bind("<Button-1>", lambda _e: self._dismiss())

        # Time + module
        ts_str = entry.timestamp.strftime("%H:%M:%S")
        tk.Label(inner,
                 text=f"{ts_str}  ·  {entry.module}",
                 font=_FONT_MONO, bg=_BG, fg=_TEXT_MUTED, anchor="w"
                 ).pack(fill=tk.X, pady=(2, 0))

        # Message (truncated)
        msg = entry.message[:120] + ("…" if len(entry.message) > 120 else "")
        msg_lbl = tk.Label(inner, text=msg, font=_FONT_BODY, bg=_BG, fg=_TEXT,
                           anchor="w", wraplength=_TOAST_W - 30, justify=tk.LEFT)
        msg_lbl.pack(fill=tk.X, pady=(4, 0))

        # Progress indicator
        self.prog_bg = tk.Frame(inner, bg=_BORDER, height=2)
        self.prog_bg.pack(fill=tk.X, pady=(8, 0))
        self.prog_bar = tk.Frame(self.prog_bg, bg=color, height=2)
        self.prog_bar.place(relx=0, rely=0, relwidth=1.0)

        # Details button
        details_btn = tk.Label(inner, text="Details →", font=_FONT_BOLD, bg=_BG, fg=color,
                               cursor="hand2")
        details_btn.pack(anchor="e", pady=(2, 0))
        details_btn.bind("<Button-1>", lambda _e: self._show_details())

        # Click anywhere else to dismiss (excluding the details button)
        inner.bind("<Button-1>", lambda _e: self._dismiss())
        msg_lbl.bind("<Button-1>", lambda _e: self._dismiss())

        # Position & slide in
        self._root      = root
        self._color     = color
        self._dismissed = False
        self._place(animate=True)

        # Auto-dismiss & Progress
        self._start_time = time.time()
        self._update_prog()
        self.after(_DISPLAY_MS, self._dismiss)

    def _update_prog(self):
        if self._dismissed or not self.winfo_exists(): return
        elapsed = (time.time() - self._start_time) * 1000
        ratio = 1.0 - (elapsed / _DISPLAY_MS)
        if ratio < 0: ratio = 0
        
        try:
            self.prog_bar.place(relwidth=ratio)
            if ratio > 0:
                self.after(50, self._update_prog)
        except Exception:
            pass

    def _show_details(self):
        """Open the detailed error dialog and dismiss the toast."""
        self._dismissed = True
        DetailedErrorDialog(self._root, self._entry)
        self.destroy()
        self._on_dismiss(self)

    # ── Positioning ──────────────────────────────────────────────────────────

    def _target_y(self) -> int:
        sh = self._root.winfo_screenheight()
        return sh - _MARGIN_BOTTOM - (_TOAST_H + _STACK_GAP) * (self._slot + 1)

    def _target_x(self) -> int:
        sw = self._root.winfo_screenwidth()
        return sw - _TOAST_W - _MARGIN_RIGHT

    def _place(self, animate: bool = False) -> None:
        x = self._target_x()
        y = self._target_y()

        if animate:
            sw = self._root.winfo_screenwidth()
            start_x = sw + 20   # off-screen right
            self.geometry(f"{_TOAST_W}x{_TOAST_H}+{start_x}+{y}")
            self.deiconify()
            self._slide(start_x, x, y)
        else:
            self.geometry(f"{_TOAST_W}x{_TOAST_H}+{x}+{y}")

    def _slide(self, cx: int, tx: int, y: int, step: int = 0) -> None:
        if self._dismissed or not self.winfo_exists():
            return
        if step >= _SLIDE_STEPS:
            self.geometry(f"{_TOAST_W}x{_TOAST_H}+{tx}+{y}")
            return
        t = step / _SLIDE_STEPS
        ease = 1 - (1 - t) ** 3   # ease-out cubic
        nx = int(cx + (tx - cx) * ease)
        self.geometry(f"{_TOAST_W}x{_TOAST_H}+{nx}+{y}")
        self.after(_SLIDE_MS, self._slide, cx, tx, y, step + 1)

    def reposition(self, new_slot: int) -> None:
        """Smoothly shift to a new vertical slot."""
        self._slot = new_slot
        x = self._target_x()
        y = self._target_y()
        self.geometry(f"{_TOAST_W}x{_TOAST_H}+{x}+{y}")

    # ── Dismiss ───────────────────────────────────────────────────────────────

    def _dismiss(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        self._fade_out()

    def _fade_out(self, alpha: float = 0.97) -> None:
        if not self.winfo_exists():
            self._on_dismiss(self)
            return
        if alpha <= 0.0:
            self.destroy()
            self._on_dismiss(self)
            return
        try:
            self.attributes("-alpha", alpha)
        except Exception:
            pass
        self.after(30, self._fade_out, alpha - 0.12)


class DetailedErrorDialog(tk.Toplevel):
    """A professional-grade scrollable dialog to show full tracebacks."""
    def __init__(self, parent, entry):
        super().__init__(parent)
        self.title(f"Contragest Error — {entry.exc_type}")
        self.geometry("900x650")
        self.configure(bg="#0F172A")
        center_window(self)
        
        # Try to make it transient and focused
        try:
            self.transient(parent)
            self.grab_set()
        except Exception:
            pass

        # Header
        header = tk.Frame(self, bg="#1E293B", pady=20, padx=30)
        header.pack(fill=tk.X)
        
        color = _CATEGORY_COLORS.get(entry.category, "#EF476F")
        icon = _CATEGORY_ICONS.get(entry.category, "⚠️")

        tk.Label(header, text=f"{icon} {entry.category} Error", 
                 font=("Segoe UI", 18, "bold"), bg="#1E293B", fg=color).pack(anchor="w")
        
        tk.Label(header, text=f"{entry.timestamp.strftime('%A, %d %B %Y at %H:%M:%S')} · Module: {entry.module}",
                 font=("Segoe UI", 10), bg="#1E293B", fg="#94A3B8").pack(anchor="w", pady=(5, 0))

        # Exception Details
        details_frame = tk.Frame(self, bg="#0F172A", padx=30, pady=20)
        details_frame.pack(fill=tk.X)
        
        # Color based on type
        type_color = "#EF4444" # Red for Error
        if entry.exc_type == "Warning":
            type_color = "#F59E0B" # Amber for Warning
        elif entry.exc_type == "Information":
            type_color = "#3B82F6" # Blue for Info

        tk.Label(details_frame, text=f"Type: {entry.exc_type}", font=("Segoe UI", 11, "bold"), 
                 bg="#0F172A", fg=type_color).pack(anchor="w")
        tk.Label(details_frame, text=f"Module: {entry.module} | Category: {entry.category}", 
                 font=("Segoe UI", 9), bg="#0F172A", fg="#94A3B8").pack(anchor="w", pady=(2, 0))
        
        msg_box = tk.Frame(details_frame, bg="#1E293B", padx=15, pady=15, 
                           highlightthickness=1, highlightbackground="#334155")
        msg_box.pack(fill=tk.X, pady=(8, 0))
        
        tk.Label(msg_box, text=entry.message, font=("Segoe UI", 11), bg="#1E293B", fg="#F8FAFC",
                 wraplength=840, justify=tk.LEFT).pack(anchor="w")

        # Traceback
        trace_frame = tk.Frame(self, bg="#0F172A", padx=30, pady=0)
        trace_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        tk.Label(trace_frame, text="FULL STACK TRACE (TERMINAL OUTPUT)", font=("Segoe UI", 9, "bold"), 
                 bg="#0F172A", fg="#94A3B8").pack(anchor="w")
        
        txt = scrolledtext.ScrolledText(trace_frame, bg="#020617", fg="#7DD3FC", 
                                       insertbackground="white", font=("Consolas", 10),
                                       borderwidth=0, highlightthickness=1, 
                                       highlightbackground="#334155", padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        txt.insert(tk.END, entry.trace)
        txt.configure(state=tk.DISABLED)

        # Footer
        footer = tk.Frame(self, bg="#0F172A", pady=15, padx=30)
        footer.pack(fill=tk.X)
        
        tk.Button(footer, text="Copy to Clipboard", command=lambda: self._copy_trace(entry.trace),
                  bg="#334155", fg="white", font=("Segoe UI", 9, "bold"), 
                  activebackground="#475569", activeforeground="white", 
                  relief=tk.FLAT, padx=15, pady=8, cursor="hand2").pack(side=tk.LEFT)
        
        # New "Notify Admin" button
        self.report_btn = tk.Button(footer, text="📧 Notify Admin", command=lambda: self._notify_admin(entry),
                  bg="#0891B2", fg="white", font=("Segoe UI", 9, "bold"), 
                  activebackground="#0E7490", activeforeground="white", 
                  relief=tk.FLAT, padx=15, pady=8, cursor="hand2")
        self.report_btn.pack(side=tk.LEFT, padx=10)
        
        tk.Button(footer, text="Close Window", command=self.destroy,
                  bg="#EF4444", fg="white", font=("Segoe UI", 9, "bold"), 
                  activebackground="#DC2626", activeforeground="white", 
                  relief=tk.FLAT, padx=25, pady=8, cursor="hand2").pack(side=tk.RIGHT)

    def _notify_admin(self, entry):
        """Triggers the backend email logic and provides UI feedback."""
        from contragest.core.error_reporter import ErrorReporter
        success = ErrorReporter.send_to_admin(entry)
        
        if success:
            self.report_btn.config(text="✅ Sent to Admin", bg="#059669", state=tk.DISABLED)
        else:
            self.report_btn.config(text="❌ Failed to Send", bg="#B91C1C")
            self.after(2000, lambda: self.report_btn.config(text="📧 Notify Admin", bg="#0891B2"))

    def _copy_trace(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        # Optional: show a temporary "Copied!" message or change button text


# ── Manager ───────────────────────────────────────────────────────────────────

class ErrorToastManager:
    """
    Manages a stack of up to _MAX_STACK toasts.
    Excess notifications are queued and shown as space frees up.
    """

    def __init__(self, root: tk.Tk):
        self._root:    tk.Tk = root
        self._active:  list[Optional[_Toast]] = []   # slot → toast | None
        self._pending: Deque = deque()

    def show(self, entry) -> None:
        """Called by ErrorReporter._maybe_notify_ui (via root.after)."""
        free_slot = self._find_free_slot()
        if free_slot is not None:
            self._spawn(entry, free_slot)
        else:
            self._pending.append(entry)

    def _find_free_slot(self) -> Optional[int]:
        for slot in range(_MAX_STACK):
            if slot >= len(self._active) or self._active[slot] is None:
                return slot
        return None

    def _spawn(self, entry, slot: int) -> None:
        # Pad list if needed
        while len(self._active) <= slot:
            self._active.append(None)

        toast = _Toast(
            root=self._root,
            entry=entry,
            slot=slot,
            on_dismiss=self._on_toast_dismissed,
        )
        self._active[slot] = toast

    def _on_toast_dismissed(self, toast: _Toast) -> None:
        try:
            idx = self._active.index(toast)
            self._active[idx] = None
        except ValueError:
            pass

        # Collapse gaps — shift remaining toasts down
        compact = [t for t in self._active if t is not None]
        self._active = [None] * _MAX_STACK
        for new_slot, t in enumerate(compact):
            self._active[new_slot] = t
            t.reposition(new_slot)

        # Show next pending if any
        if self._pending:
            free = self._find_free_slot()
            if free is not None:
                self._spawn(self._pending.popleft(), free)


class ErrorHistoryWindow(tk.Toplevel):
    """A professional window showing a list of recent errors."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Contragest — System Error History")
        self.geometry("1100x750")
        self.configure(bg="#0F172A")
        center_window(self)
        
        # Header
        header = tk.Frame(self, bg="#1E293B", pady=25, padx=30)
        header.pack(fill=tk.X)
        
        tk.Label(header, text="⚠️ System Error History", 
                 font=("Segoe UI", 20, "bold"), bg="#1E293B", fg="#F8FAFC").pack(anchor="w")
        
        tk.Label(header, text="Review captured application errors and stack traces from the current session.",
                 font=("Segoe UI", 10), bg="#1E293B", fg="#94A3B8").pack(anchor="w", pady=(5, 0))

        # Main Area
        from contragest.core.error_reporter import ErrorReporter
        
        self.container = tk.Frame(self, bg="#0F172A", padx=20, pady=20)
        self.container.pack(fill=tk.BOTH, expand=True)
        
        self._build_table()

        # Footer
        footer = tk.Frame(self, bg="#0F172A", pady=20, padx=30)
        footer.pack(fill=tk.X)
        
        tk.Button(footer, text="Refresh List", command=self._refresh,
                  bg="#334155", fg="white", font=("Segoe UI", 9, "bold"), 
                  activebackground="#475569", activeforeground="white", 
                  relief=tk.FLAT, padx=20, pady=10, cursor="hand2").pack(side=tk.LEFT)
        
        tk.Button(footer, text="Clear All Logs", command=self._clear_log,
                  bg="#991B1B", fg="white", font=("Segoe UI", 9, "bold"), 
                  activebackground="#7F1D1D", activeforeground="white", 
                  relief=tk.FLAT, padx=20, pady=10, cursor="hand2").pack(side=tk.LEFT, padx=15)
        
        tk.Button(footer, text="Close", command=self.destroy,
                  bg="#1E293B", fg="white", font=("Segoe UI", 9, "bold"), 
                  activebackground="#334155", activeforeground="white", 
                  relief=tk.FLAT, padx=30, pady=10, cursor="hand2").pack(side=tk.RIGHT)

    def _build_table(self):
        from contragest.core.error_reporter import ErrorReporter
        
        cols = [
            {"text": "Timestamp", "stretch": False, "width": 160},
            {"text": "Category", "stretch": False, "width": 130},
            {"text": "Exception Type", "stretch": False, "width": 180},
            {"text": "Module / Context", "stretch": False, "width": 150},
            {"text": "Error Message", "stretch": True}
        ]
        
        log_data = ErrorReporter.get_log()
        row_data = []
        for entry in reversed(log_data):
            row_data.append((
                entry['timestamp'],
                entry['category'],
                entry['exc_type'],
                entry['module'],
                entry['message']
            ))
            
        # Clean previous table if any
        for widget in self.container.winfo_children():
            widget.destroy()

        self.table = Tableview(
            master=self.container,
            coldata=cols,
            rowdata=row_data,
            paginated=False,
            searchable=True,
            bootstyle="primary",
            autoalign=False
        )
        self.table.pack(fill=tk.BOTH, expand=True)
        self.table.view.bind("<Double-1>", self._on_double_click)

    def _on_double_click(self, _event):
        selected = self.table.view.selection()
        if not selected:
            return
        
        # Get the timestamp from the selected row to find the matching entry
        values = self.table.view.item(selected[0], "values")
        timestamp = values[0]
        
        from contragest.core.error_reporter import ErrorReporter
        with ErrorReporter._lock:
            for entry in ErrorReporter._log:
                if entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") == timestamp:
                    DetailedErrorDialog(self, entry)
                    break

    def _refresh(self):
        self._build_table()
    
    def _clear_log(self):
        from contragest.core.error_reporter import ErrorReporter
        ErrorReporter.clear_log()
        self._refresh()
