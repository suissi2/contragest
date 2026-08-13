"""
Pointage Window - Full-featured time & attendance management UI.

Provides 9 tabs:
1. Attendance         - Download / upload attendance data (ZK Machines)
2. Analytics & Recap  - Dashboard and summary data
3. Calendar           - View and manage public holidays / schedules
4. Schedules          - Manage work schedules and assignments
5. Status of Days      - Define and view daily status codes
6. Note Management    - Predefined notes for attendance corrections
7. Personal           - Sync employees with machine (names and registration)
8. Machine Config     - Configure and test ZK attendance hardware
9. Audit Logs         - Trace system changes and activity
"""

import os
from PIL import Image, ImageTk
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox, Querybox
from ttkbootstrap.widgets import DateEntry, ToolTip
import re

from contragest.core.gui_utils import DesignTokens, apply_premium_style
from ttkbootstrap.tableview import Tableview
from contragest.core.i18n import tr
from contragest.core.database import SessionLocal, WorkSchedule
from contragest.core.status_bar import StatusLabel
from datetime import datetime
import threading
from contragest.features.pointage.service import PointageService
from contragest.features.pointage.machine_connector import PYZK_AVAILABLE
from contragest.features.pointage.export_reports import generate_attendance_excel, generate_attendance_pdf
from contragest.core.logging import setup_logger
from contragest.lib.task_manager import TaskManager

# Suppress OpenCV terminal warnings for absent cameras
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
import cv2
import numpy as np

logger = setup_logger("pointage_ui")

# Punch time columns in the attendance grid, left → right. Used by the
# keyboard editing mode for navigation (Tab) and value moves (Ctrl+←/→).
PUNCH_COLS = ["IN 1", "OUT 1", "IN 2", "OUT 2"]

# Cell-move diagnostics — always traced to _drag_debug.log so a failed
# interaction can be reproduced and diagnosed. CONTRA_DRAG_DEBUG=1 also prints.
_DRAG_DEBUG = os.environ.get("CONTRA_DRAG_DEBUG", "").strip().lower() in ("1", "true", "yes")

_DRAG_DEBUG_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_drag_debug.log")

def _drag_dbg(msg):
    line = "[drag-dbg] " + str(msg)
    if _DRAG_DEBUG:
        print(line, flush=True)
    try:
        # Cap the trace file so it cannot grow unbounded.
        if os.path.exists(_DRAG_DEBUG_LOG) and os.path.getsize(_DRAG_DEBUG_LOG) > 2_000_000:
            with open(_DRAG_DEBUG_LOG, "w", encoding="utf-8") as f:
                f.write("[drag-dbg] === trace rotated ===\n")
        with open(_DRAG_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass

_drag_dbg(f"instrumented pointage ui loaded from {os.path.abspath(__file__)}")


def _date_sort_key(r):
    """Sort key for a records row's DATE cell ("Day. DD-MM-YYYY")."""
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", str(r[0]))
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return (yyyy, mm, dd)
    return ("9999", "99", "99")


def _sort_records_rows(rows):
    """Group records by employee (REG), then order chronologically by DATE.

    Produces the ATTENDANCE RECORDS grid layout: every row of a given employee
    is contiguous and their dates run from oldest to newest.
    """
    return sorted(rows, key=lambda r: (r[2], _date_sort_key(r)))  # REG, DATE


# ─── COLOR TOKENS (NEBULA MIDNIGHT DESIGN SYSTEM) ────────────────────────────
PANEL_BG = DesignTokens.SURFACE
MAIN_BG = DesignTokens.BG_APP
ACCENT_BLUE = DesignTokens.PRIMARY
ACCENT_AMBER = DesignTokens.WARNING
TEXT_HIGH = DesignTokens.TEXT
TEXT_MUTED = DesignTokens.TEXT_MUTED
BORDER_COLOR = DesignTokens.SECONDARY
SUCCESS_EMERALD = DesignTokens.SUCCESS
DANGER_ROSE = DesignTokens.DANGER
# ─────────────────────────────────────────────────────────────────────────────

class PointageTooltip:
    """A floating information window that displays detailed attendance logs."""
    def __init__(self, master):
        self.master = master
        self.tw = None
        self.last_item = None

    def show(self, x, y, content=None, employee_info=None, punches=None):
        if self.tw:
            try: self.tw.destroy()
            except: pass
        
        # Create a borderless toplevel
        self.tw = tk.Toplevel(self.master)
        self.tw.wm_overrideredirect(True)
        self.tw.attributes("-topmost", True)
        self.tw.attributes("-alpha", 0.95) # Subtle transparency
        self.tw.geometry(f"+{x+25}+{y+20}")
        
        # Outer container for shadowing effect/border
        container = tk.Frame(self.tw, bg=BORDER_COLOR, padx=1, pady=1)
        container.pack()
        
        # Inner content matching the requested aesthetic
        inner = tk.Frame(container, bg=PANEL_BG, padx=9, pady=6)
        inner.pack()
        
        if employee_info:
            # Header section
            header_f = tk.Frame(inner, bg=PANEL_BG)
            header_f.pack(fill=tk.X)
            
            tk.Label(header_f, text=f"{employee_info['name']}", 
                     font=("Space Mono", 9), bg=PANEL_BG, fg=TEXT_HIGH).pack(anchor="w")
            tk.Label(header_f, text=f"{employee_info['dept']} | {employee_info['reg_number']}", 
                     font=("Space Mono", 8), bg=PANEL_BG, fg=TEXT_MUTED).pack(anchor="w")
            
            # Divider
            tk.Frame(inner, bg=BORDER_COLOR, height=1).pack(fill=tk.X, pady=4)
            
            # Data Table
            table_f = tk.Frame(inner, bg=PANEL_BG)
            table_f.pack(fill=tk.X)
            
            h_font = ("Space Mono", 8)
            v_font = ("JetBrains Mono", 9)
            
            # Table Labels
            tk.Label(table_f, text="TIME", font=h_font, bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=0, sticky=tk.W)
            tk.Label(table_f, text="MACHINE", font=h_font, bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=1, sticky=tk.W, padx=6)
            tk.Label(table_f, text="EVENT", font=h_font, bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=2, sticky=tk.W)
            
            # Punches Rows
            if punches:
                for i, p in enumerate(punches[:5]): # Cap to latest 5 to prevent screen-blocking
                    r = i + 1
                    tk.Label(table_f, text=p['time'], font=v_font, bg=PANEL_BG, fg=TEXT_HIGH).grid(row=r, column=0, sticky=tk.W)
                    tk.Label(table_f, text=f"{p['machine'][:12]}", font=v_font, bg=PANEL_BG, fg=TEXT_HIGH).grid(row=r, column=1, sticky=tk.W, padx=6)
                    tk.Label(table_f, text=f"{p['type']}", font=v_font, bg=PANEL_BG, fg=TEXT_HIGH).grid(row=r, column=2, sticky=tk.W)
                
                if len(punches) > 5:
                    tk.Label(inner, text=f"+ {len(punches)-5} more events", font=("Space Mono", 7, "italic"), bg=PANEL_BG, fg=TEXT_MUTED).pack()
        else:
            tk.Label(inner, text=content or "No Details Available", font=("JetBrains Mono", 9), bg=PANEL_BG, fg=TEXT_MUTED).pack()

    def hide(self, event=None):
        if self.tw:
            try: self.tw.destroy()
            except: pass
            self.tw = None
        self.last_item = None


class ManualPunchDialog(ttk.Toplevel):
    def __init__(self, parent, service, reg_number, emp_name, date_str, refresh_callback, current_times=None):
        super().__init__(parent)
        self.title("Fix / Add Punch")
        self.geometry("400x380")
        self.resizable(False, False)
        
        self.service = service
        self.reg_number = reg_number
        self.refresh_callback = refresh_callback
        self.parent_window = parent
        self.current_times = current_times or {}

        # Check admin
        admin_name = "System"
        if hasattr(parent, "main_window") and parent.main_window and parent.main_window.current_user:
            admin_name = parent.main_window.current_user.username

        self.admin_name = admin_name
        self.date_str = date_str

        # Add Persistent Status Bar (Bottom) - Reserve before any widget build
        # Parent is PointageWindow, it has current_user (inherited from parent_window -> main_window)
        main_win = getattr(parent, 'main_window', None)
        user = getattr(main_win, 'current_user', None) if main_win else getattr(parent, 'current_user', None)
        
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status("Manual Attendance Correction")

        self._build_ui(emp_name, date_str)

    def _on_punch_type_changed(self, event=None):
        """Pre-fill the time field with the existing value for the selected punch slot."""
        selected = self.type_var.get()
        existing = self.current_times.get(selected, "")
        # Truncate to HH:MM if longer (e.g. HH:MM:SS)
        if existing and len(existing) >= 5:
            existing = existing[:5]
        self.time_var.set(existing)

    def _on_note_selected(self, event=None):
        """Populate the reason text with the selected predefined note."""
        selected_name = self.note_select_var.get()
        if selected_name:
            self.reason_text.delete("1.0", END)
            self.reason_text.insert("1.0", selected_name)

    def _build_ui(self, emp_name, date_str):
        ttk.Label(self, text=f"Employee: {emp_name}", font=("Space Mono", 9, "bold")).pack(pady=(12, 3))
        ttk.Label(self, text=f"Date: {date_str}").pack(pady=3)

        form = ttk.Frame(self, takefocus=0)
        form.pack(fill=X, padx=12, pady=6)

        ttk.Label(form, text="Time (HH:MM):").grid(row=0, column=0, sticky=W, pady=3)
        self.time_var = ttk.StringVar()
        ttk.Entry(form, textvariable=self.time_var, width=10).grid(row=0, column=1, sticky=W, pady=3, padx=6)

        ttk.Label(form, text="Punch Type:").grid(row=1, column=0, sticky=W, pady=3)
        self.type_var = ttk.StringVar(value="Check In 1")
        cb = ttk.Combobox(form, textvariable=self.type_var, values=["Check In 1", "Check Out 1", "Check In 2", "Check Out 2"], state="readonly", width=15)
        cb.grid(row=1, column=1, sticky=W, pady=3, padx=6)
        cb.bind("<<ComboboxSelected>>", self._on_punch_type_changed)

        # ── Predefined Notes ──
        ttk.Label(form, text="Quick Note:").grid(row=2, column=0, sticky=W, pady=3)
        self.predefined_notes = self.service.get_predefined_notes()
        note_names = [n["name"] for n in self.predefined_notes]
        self.note_select_var = ttk.StringVar()
        note_cb = ttk.Combobox(form, textvariable=self.note_select_var, values=note_names, state="readonly", width=15)
        note_cb.grid(row=2, column=1, sticky=W, pady=3, padx=6)
        note_cb.bind("<<ComboboxSelected>>", self._on_note_selected)

        ttk.Label(form, text="Reason:").grid(row=3, column=0, sticky=NW, pady=3)
        self.reason_text = ttk.Text(form, width=25, height=3)
        self.reason_text.grid(row=3, column=1, sticky=W, pady=3, padx=6)

        btn_frame = ttk.Frame(self, takefocus=0)
        btn_frame.pack(fill=X, pady=(6, 3))
        ttk.Button(btn_frame, text="✅ Save", bootstyle=SUCCESS, command=self._save).pack(side=RIGHT, padx=12)
        ttk.Button(btn_frame, text="🗑 Delete", bootstyle=DANGER, command=self._delete).pack(side=RIGHT, padx=(1, 1))
        ttk.Button(btn_frame, text="❌ Cancel", bootstyle=SECONDARY, command=self.destroy).pack(side=RIGHT, padx=12)

        sync_frame = ttk.Frame(self, takefocus=0)
        sync_frame.pack(fill=X, padx=12, pady=(1, 9))
        ttk.Button(
            sync_frame,
            text="📡  Sync Employee to ZK",
            bootstyle="outline-primary",
            command=self._sync_employee_to_zk
        ).pack(side=RIGHT)

        # Pre-fill with the default selection (Check In 1)
        self._on_punch_type_changed()

    def _save(self):
        time_str = self.time_var.get().strip()
        reason = self.reason_text.get("1.0", END).strip()
        
        if len(time_str) != 5 or ":" not in time_str:
            Messagebox.show_error("Please enter time in HH:MM format.", "Invalid Format", parent=self)
            return
        if not reason:
            Messagebox.show_error("Please provide a reason for this modification.", "Missing Reason", parent=self)
            return

        type_str = self.type_var.get()
        punch_type = "check_in" if "In" in type_str else "check_out"
        slot_id = 2 if " 2" in type_str else 1

        success, msg = self.service.add_manual_punch(
            registration_number=self.reg_number,
            punch_date=self.date_str,
            punch_time=time_str,
            punch_type=punch_type,
            admin_name=self.admin_name,
            reason=reason,
            slot_index=slot_id
        )

        if success:
            Messagebox.show_info("Record updated successfully.", "Success", parent=self)
            self.refresh_callback()
            self.destroy()
        else:
            Messagebox.show_error(f"Failed to add record:\n{msg}", "Error", parent=self)

    def _delete(self):
        reason = self.reason_text.get("1.0", END).strip()
        if not reason:
            Messagebox.show_error("Please provide a reason for this deletion.", "Missing Reason", parent=self)
            return

        type_str = self.type_var.get()
        punch_type = "check_in" if "In" in type_str else "check_out"
        slot_id = 2 if " 2" in type_str else 1

        ans = Messagebox.show_question(
            f"Are you sure you want to delete '{type_str}' for this employee on {self.date_str}?",
            "Confirm Deletion",
            buttons=["Cancel:secondary", "Delete:danger"],
            parent=self
        )
        if ans != "Delete":
            return

        success, msg = self.service.delete_manual_punch(
            registration_number=self.reg_number,
            punch_date=self.date_str,
            punch_type=punch_type,
            admin_name=self.admin_name,
            reason=reason,
            slot_index=slot_id
        )

        if success:
            Messagebox.show_info(msg, "Success", parent=self)
            if self.refresh_callback:
                self.refresh_callback() # Refresh parent table
            self.destroy()
        else:
            Messagebox.show_error(msg, "Error", parent=self)

    def _sync_employee_to_zk(self):
        """Push this single employee's user record to all active ZK machines via centralized TaskManager."""
        from contragest.core.database import Employee, AttendanceMachine

        emp = self.service.session.query(Employee).filter(
            Employee.registration_number == self.reg_number
        ).first()

        if not emp or not emp.registration_number:
            Messagebox.show_warning("Cannot sync: employee has no registration number.", "Sync Skipped", parent=self)
            return

        machines = self.service.session.query(AttendanceMachine).filter_by(is_active=True).all()
        if not machines:
            Messagebox.show_warning("No active ZK machines configured.", "Sync Skipped", parent=self)
            return

        user_payload = [{
            "uid": int(emp.registration_number),
            "name": f"{emp.first_name} {emp.last_name}"
        }]

        # Use parent's professional task manager if available
        task_mgr = getattr(self.parent_window, "task_manager", None)
        if task_mgr:
            self.parent_window._prog_frame.pack(fill=X, padx=6, pady=(1, 6))
            task_mgr.run_task(
                task_id=f"sync_emp_{self.reg_number}",
                name=f"📡 Syncing {emp.first_name} to ZK",
                target=self._do_push_bg,
                args=(machines, user_payload),
                on_progress=self.parent_window._update_progress_ui,
                on_complete=lambda res: self._after_push_final(res, f"{emp.first_name} {emp.last_name}")
            )
            self.destroy() # Close dialog, task continues in background
        else:
            # Fallback if no task manager (should not happen in PointageWindow)
            Messagebox.show_error("Task Manager not found in parent window.", "Error")

    def _do_push_bg(self, machines, user_payload, progress_callback=None):
        """Background worker for employee sync."""
        lines = []
        total = len(machines)
        for i, m in enumerate(machines):
            if progress_callback:
                progress_callback(i, total, f"Pushing to {m.name}...")
            try:
                s, f = self.service.connector.push_users_bulk(m.ip_address, m.port, m.password or "", user_payload)
                icon = "✅" if f == 0 else "⚠️"
                lines.append(f"{icon}  {m.name}: {s} pushed, {f} failed")
            except Exception as ex:
                lines.append(f"❌  {m.name}: {ex}")
        return "\n".join(lines)

    def _after_push_final(self, results, emp_name):
        """Final notification after background sync completes."""
        if hasattr(self.parent_window, "_transfer_status"):
            self.parent_window._transfer_status.configure(text=f"✅ Sync complete for {emp_name}", fg=SUCCESS_EMERALD)
        Messagebox.show_info(f"Employee Sync Results for {emp_name}:\n\n{results}", "Sync Complete")
        if hasattr(self.parent_window, "_prog_frame"):
            def _hide():
                pw = self.parent_window
                if pw.winfo_exists() and getattr(pw, "_prog_frame", None) and pw._prog_frame.winfo_exists():
                    pw._prog_frame.pack_forget()
            self.parent_window.master.after(4000, _hide)


class PointageWindow(ttk.Toplevel):
    """Main Pointage management window - opened from the HR ribbon."""

    def center_window(self):
        self.update_idletasks()
        w, h = 1200, 750
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def __init__(self, parent, main_window=None, initial_tab=None):
        super().__init__(parent)
        self.title(f"⏱️ {tr('pointage_title')}")
        self.geometry("1200x750")
        self.resizable(True, True)
        self.center_window()

        self.main_window = main_window
        self._initial_tab = initial_tab

        self.session = SessionLocal()
        self.service = PointageService(self.session)
        self.task_manager = TaskManager(self)
        self.selected_machine_id = None
        self._tooltip = PointageTooltip(self)
        self._tooltip_after_id = None  # Pending (deferred) tooltip show callback
        self._after_grid_id = None
        self._is_exporting = False # Busy flag
        self._pending_timers = set()  # Track after() IDs for cleanup on destroy

        # Cell-move state (click-to-select + click-to-drop, Excel-style)
        self._drag_src = None      # {reg, date, col, time} of the selected source cell
        self._drag_moved = False   # True once the pointer has moved (classic drag path)
        self._move_src_item = None # Treeview item ID of the highlighted source row
        self._move_src_emp = ""    # Employee name of the armed cell (for edit dialogs)
        self._inline_entry = None  # Active inline Entry overlay (Excel-like editing)
        self._inline_col = ""      # Column being edited inline (for Tab navigation)

        # Last reason typed in the punch edit dialog — pre-filled on the next
        # edit so repeated corrections are one keystroke faster (audit kept).
        self._last_edit_reason = ""

        # Global Suppression of "Focus Rectangles" (Dashed lines on clicks)
        style_init = ttk.Style()
        apply_premium_style(style_init)
        
        # Remove dashed line focus for Treeview items
        style_init.layout("Treeview.Item", [
            ('Treeview.padding', {'sticky': 'nswe', 'children': [
                ('Treeview.indicator', {'side': 'left', 'sticky': ''}),
                ('Treeview.image', {'side': 'left', 'sticky': ''}),
                ('Treeview.text', {'sticky': 'nswe'})
            ]})
        ])
        # Remove dash marks from interactive buttons and tabs globally
        style_init.map("TButton", focuscolor=[("focus", style_init.colors.primary if hasattr(style_init.colors, "primary") else "gray")])
        style_init.map("TNotebook.Tab", focuscolor=[("focus", style_init.colors.secondary if hasattr(style_init.colors, "secondary") else "gray")])

        # Filter Variables
        self._filter_dept = tk.StringVar()
        self._filter_emp = tk.StringVar()
        self._filter_type = tk.StringVar(value=tr("all_types"))

        # Initialize status keys and colors for summary counts (from DB)
        try:
            from contragest.core.database import DayStatus
            db_statuses = self.session.query(DayStatus).all()
            db_statuses = sorted(db_statuses, key=lambda x: x.id)
            self._status_keys = [s.code for s in db_statuses]
            self._status_colors = {s.code: s.color_hex for s in db_statuses}
        except Exception as e:
            # Revert to defaults if DB fails or table is empty
            self._status_keys = ["P", "AB", "CA", "JF", "RH", "RHB", "CR", "CM", "MAP", "PJF", "MIS", "JFP", "CSS", "DS"]
            self._status_colors = {
                "P":   DesignTokens.PRIMARY,
                "AB":  DesignTokens.DANGER,
                "CA":  DesignTokens.PRIMARY,
                "JF":  DesignTokens.WARNING,
                "RH":  DesignTokens.PRIMARY,
                "RHB": DesignTokens.PRIMARY,
                "CR":  DesignTokens.WARNING,
                "CM":  DesignTokens.PRIMARY,
                "MIS": DesignTokens.DANGER,
                "MAP": DesignTokens.PRIMARY,
                "PJF": DesignTokens.WARNING,
                "JFP": DesignTokens.TEXT_MUTED,
                "CSS": DesignTokens.PRIMARY,
                "DS":  DesignTokens.TEXT_MUTED,
                "SOR": DesignTokens.WARNING,
                "JFB": DesignTokens.PRIMARY
            }

        # Add Persistent Status Bar (Reserve bottom area before UI build)
        user = getattr(main_window, 'current_user', None)
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status("Attendance Management Terminal Engaged")

        self._last_checked_date = datetime.now().date()
        self._build_ui()
        self.update_idletasks()
        self._load_machines()
        self._load_schedules()

        # Bind events to hide tooltip when window loses focus or is hidden
        self.bind("<FocusOut>", self._tooltip.hide)
        self.bind("<Unmap>", self._tooltip.hide)
        self.bind("<Destroy>", self._tooltip.hide)

        # Start automatic midnight check
        self._schedule_midnight_check()

        # Premium UX: Clear focus rectangles on accidental clicks
        self.bind_all("<Button-1>", self._clear_accidental_focus)
        self.after(1000, self._apply_global_style_suppression)

    def _clear_accidental_focus(self, event):
        """Clears focus if the user clicks on non-input widgets to avoid accidental focus rectangles."""
        try:
            # ONLY clear focus if the click was within THIS window to avoid interfering with dialogs
            if event.widget.winfo_toplevel() != self.winfo_toplevel():
                return
                
            # Allow common input widgets to retain focus
            if not isinstance(event.widget, (ttk.Entry, tk.Entry, ttk.Combobox, tk.Text)):
                # If clicking on a Frame, Label or any decorative element, transfer focus to main window
                self.focus_set()
        except: pass

    def _apply_global_style_suppression(self):
        """Globally removes the focus element from ttk layouts for various widgets across all themes."""
        s = ttk.Style()
        
        # List of all common style prefixes and variants in ttkbootstrap to target comprehensively
        prefixes = ["", "primary.", "secondary.", "success.", "info.", "warning.", "danger.", "light.", "dark.", "inverse-"]
        suffixes = ["TButton", "Outline.TButton", "Link.TButton", "Toolbutton.TButton"]
        
        # 1. Remove focus element from ALL Button layout combinations
        for p in prefixes:
            for s_style in suffixes:
                full_style = f"{p}{s_style}"
                try:
                    s.layout(full_style, [
                        ('Button.button', {'children': [
                            ('Button.padding', {'children': [
                                ('Button.label', {'sticky': 'nswe'})
                            ], 'sticky': 'nswe'})
                        ], 'sticky': 'nswe'})
                    ])
                except: pass

        # 2. Remove dashed line focus for Treeview items (specifically targeting standard and dark)
        for tv_style in ["Treeview", "dark.Treeview"]:
            try:
                s.layout(f"{tv_style}.Item", [
                    ('Treeview.padding', {'sticky': 'nswe', 'children': [
                        ('Treeview.indicator', {'side': 'left', 'sticky': ''}),
                        ('Treeview.image', {'side': 'left', 'sticky': ''}),
                        ('Treeview.text', {'sticky': 'nswe'})
                    ]})
                ])
            except: pass
        
        # 3. Remove focus element from Notebook Tabs
        s.layout("TNotebook.Tab", [
            ('Notebook.tab', {'children': [
                ('Notebook.padding', {'children': [
                    ('Notebook.label', {'sticky': 'nswe'})
                ], 'sticky': 'nswe'})
            ], 'sticky': 'nswe'})
        ])
        
        # 4. Remove focus from Checkbuttons and Radiobuttons
        for r_style in ["TCheckbutton", "TRadiobutton", "Toolbutton.TCheckbutton"]:
            try:
                s.layout(r_style, [
                    (r_style.replace('T', '') + '.padding', {'children': [
                        (r_style.replace('T', '') + '.indicator', {'side': 'left', 'sticky': ''}),
                        (r_style.replace('T', '') + '.label', {'sticky': 'nswe'})
                    ], 'sticky': 'nswe'})
                ])
            except: pass
        
        # 5. Suppress focus thickness and ring color globally
        s.configure(".", focusthickness=0, focuscolor="")

        # 6. Global standard for Premium OLED LabelFrames
        s.configure('TLabelframe', background=PANEL_BG, bordercolor=BORDER_COLOR)
        s.configure('TLabelframe.Label', background=PANEL_BG, foreground=TEXT_HIGH, font=('Space Mono', 9, 'bold'))

    # ── Layout ────────────────────────────────────────────────────────────

    def center_window(self):
        self.update_idletasks()
        w, h = 1200, 750
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.configure(background=MAIN_BG)

    def _build_ui(self):
        # Header (Now with a deeper color integrated with the OLED theme)
        header = ttk.Frame(self, bootstyle=SECONDARY)
        header.pack(fill=X)
        # Logo container in main header
        self._main_logo_lbl = ttk.Label(header, bootstyle="inverse-primary")
        self._main_logo_lbl.pack(side=tk.LEFT, padx=12)
        self._load_main_logo()

        ttk.Label(
            header, text=f"⏱️ {tr('pointage_title')}",
            font=("Space Mono", 14, "bold"),
            bootstyle="inverse-primary",
        ).pack(side=tk.LEFT, padx=6, pady=6)



        if not PYZK_AVAILABLE:
            warn_frame = ttk.Frame(self, bootstyle=WARNING)
            warn_frame.pack(fill=X, padx=6, pady=(3, 1))
            ttk.Label(
                warn_frame,
                text=f"⚠️ {tr('pyzk_not_installed')}",
                font=("Space Mono", 9),
                bootstyle="inverse-warning",
            ).pack(padx=6, pady=3)

        # Notebook with 4 tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=YES, padx=6, pady=6)

        self._tab_machine = tk.Frame(self.notebook, background=MAIN_BG, padx=6, pady=6)
        self._tab_transfer = tk.Frame(self.notebook, background=MAIN_BG, padx=6, pady=6)
        self._tab_schedules = tk.Frame(self.notebook, background=MAIN_BG, padx=6, pady=6)
        self._tab_status_days = tk.Frame(self.notebook, background=MAIN_BG, padx=6, pady=6)
        self._tab_notes = tk.Frame(self.notebook, background=MAIN_BG, padx=6, pady=6)
        self._tab_analytics = tk.Frame(self.notebook, background=MAIN_BG, padx=6, pady=6)
        self._tab_calendar = tk.Frame(self.notebook, background=MAIN_BG, padx=6, pady=6)
        self._tab_audit = tk.Frame(self.notebook, background=MAIN_BG, padx=6, pady=6)

        self.notebook.add(self._tab_transfer, text=f"📥 {tr('data_transfer').upper()}")
        self.notebook.add(self._tab_analytics, text="📊 ANALYTICS & RECAP")
        self.notebook.add(self._tab_calendar, text="📅 CALENDAR")
        self.notebook.add(self._tab_schedules, text=f"🕒 {tr('schedule_admin').upper()}")
        self.notebook.add(self._tab_status_days, text="🗓️ STATUS OF DAYS")
        self.notebook.add(self._tab_notes, text="📝 NOTE MANAGEMENT")
        self.notebook.add(self._tab_machine, text=f"🛠️ {tr('machine_config').upper()}")
        self.notebook.add(self._tab_audit, text="📑 AUDIT LOGS")

        self._build_machine_tab()
        self._build_transfer_tab()
        self._build_schedules_tab()
        self._build_status_days_tab()
        self._build_notes_tab()
        self._build_audit_tab()
        self._build_analytics_tab()
        self._build_calendar_tab()
        
        if self._initial_tab == "Schedules":
             self.notebook.select(self._tab_schedules)
        elif self._initial_tab == "Analytics":
             self.notebook.select(self._tab_analytics)
        elif self._initial_tab == "Calendar":
             self.notebook.select(self._tab_calendar)
        
        # 3. Footer Status Bar
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status("Connected to Terminal Engine")

        # Status Bar
        self._status_bar = ttk.Label(self, text=tr('ready'), bootstyle=SECONDARY)
        self._status_bar.pack(side=BOTTOM, fill=X, padx=6, pady=3)



    def _schedule_midnight_check(self):
        """Periodically checks if the date has changed (midnight) and refreshes default date filters."""
        try:
            current_date = datetime.now().date()
            
            if current_date != self._last_checked_date:
                self._last_checked_date = current_date
                
                # Formatted current date
                current_date_str = current_date.strftime('%Y-%m-%d')
                
                # Update DateEntry widgets in main Transfer tab
                def force_date_update(widget, date_str):
                    if hasattr(widget, "entry"):
                        widget.entry.delete(0, "end")
                        widget.entry.insert(0, date_str)
                        # Force ttkbootstrap internal validation and refresh
                        widget.entry.event_generate('<Return>')
                        widget.entry.event_generate('<FocusOut>')

                if hasattr(self, "_filter_from_de"):
                    force_date_update(self._filter_from_de, current_date_str)
                
                if hasattr(self, "_filter_to_de"):
                    force_date_update(self._filter_to_de, current_date_str)

                # Also update Audit tab dates if they were previously set
                if hasattr(self, "_audit_from_de") and self._audit_from_de.entry.get().strip():
                    force_date_update(self._audit_from_de, current_date_str)
                if hasattr(self, "_audit_to_de") and self._audit_to_de.entry.get().strip():
                    force_date_update(self._audit_to_de, current_date_str)
                
                # Ensure UI refreshes visually immediately
                self.update_idletasks()
                
                # Update status bar to indicate automatic maintenance happened
                if hasattr(self, "status_bar"):
                    self.status_bar.set_status(f"Automatic daily update completed for {current_date_str}")
                    
                # Automatically refresh records for the new day
                # We use after 500ms to ensure the DateEntry has registered the change
                self.after(500, self._load_recent_records)

                # Refresh analytics if currently in analytics tab
                if hasattr(self, "notebook"):
                    try:
                        active_tab = self.notebook.tab(self.notebook.select(), "text")
                        if "ANALYTICS" in active_tab:
                            self.after(1000, self._update_analytics_gui)
                    except:
                        pass
        except Exception as e:
            # Silent fail to keep the loop alive, but log if possible
            print(f"Midnight check error: {e}")
        finally:
            # Check again in 30 seconds for better precision around midnight
            self.after(30000, self._schedule_midnight_check)

    def _load_main_logo(self):
        """Loads the company logo from AppConfig dynamically."""
        from contragest.core.database import SessionLocal, AppConfig
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            if config and config.company_logo_path and os.path.exists(config.company_logo_path):
                img = Image.open(config.company_logo_path)
                img.thumbnail((32, 32)) # Sized for title bar integration
                self._main_logo_img = ImageTk.PhotoImage(img)
                self._main_logo_lbl.configure(image=self._main_logo_img)
        except Exception as e:
            print(f"Error loading logo in PointageWindow: {e}")
        finally:
            session.close()

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 1 - Machine Config
    # ═══════════════════════════════════════════════════════════════════════

    def _build_machine_tab(self):
        parent = self._tab_machine

        # ── Outer vertical split: top = form+list, bottom = logs ──
        outer_paned = ttk.Panedwindow(parent, orient=VERTICAL)
        outer_paned.pack(fill=BOTH, expand=YES)

        top_frame = ttk.Frame(outer_paned)
        top_frame.pack_propagate(False)
        outer_paned.add(top_frame, weight=3)

        # ── Inner horizontal split: form (left) | machine list (right) ──
        inner_paned = ttk.Panedwindow(top_frame, orient=HORIZONTAL)
        inner_paned.pack(fill=BOTH, expand=YES)

        # ── Form Panel ──
        form_frame = ttk.LabelFrame(inner_paned, text=f"🔧 {tr('machine_config')}")
        inner_paned.add(form_frame, weight=1)

        fields = [
            ("machine_name", tr("machine_name")),
            ("ip_address", tr("ip_address")),
            ("port", tr("port")),
            ("machine_number", "Machine ID"),
            ("comm_type", "Comm Type"),
            ("baud_rate", "Baud Rate"),
            ("username", tr("username")),
            ("password", tr("password")),
            ("product_name", "Product Name"),
            ("serial_number", "Serial Number"),
        ]
        self._machine_vars = {}
        for i, (key, label) in enumerate(fields):
            ttk.Label(form_frame, text=label, font=("Space Mono", 9, "bold")).grid(
                row=i, column=0, sticky=W, padx=3, pady=3)
            var = ttk.StringVar()
            if key == "port": var.set("4370")
            elif key == "machine_number": var.set("1")
            elif key == "comm_type": var.set("Ethernet")
            elif key == "baud_rate": var.set("115200")
            
            show = "*" if key == "password" else None
            
            if key == "comm_type":
                entry = ttk.Combobox(form_frame, textvariable=var, values=["Ethernet", "RS232", "RS485"], state="readonly", width=28)
            elif key == "baud_rate":
                entry = ttk.Combobox(form_frame, textvariable=var, values=["9600", "19200", "38400", "57600", "115200"], state="readonly", width=28)
            elif key in ("product_name", "serial_number", "clock_time"):
                entry = ttk.Entry(form_frame, textvariable=var, width=32, state="readonly")
            else:
                entry = ttk.Entry(form_frame, textvariable=var, width=32, show=show)
                
            entry.grid(row=i, column=1, sticky=EW, padx=3, pady=3)
            self._machine_vars[key] = var

        # Additional: Clock Time field (after serial_number)
        clock_row = len(fields)
        ttk.Label(form_frame, text="Clock Time", font=("Space Mono", 9, "bold")).grid(
            row=clock_row, column=0, sticky=W, padx=3, pady=3)
        self._machine_vars["clock_time"] = ttk.StringVar()
        clock_entry = ttk.Entry(form_frame, textvariable=self._machine_vars["clock_time"],
                                width=32, state="readonly")
        clock_entry.grid(row=clock_row, column=1, sticky=EW, padx=3, pady=3)
        ttk.Button(
            form_frame, text="🕒", bootstyle="outline-info",
            command=self._fetch_selected_machine_time, width=4
        ).grid(row=clock_row, column=2, padx=1)

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=len(fields) + 1, column=0, columnspan=3, pady=9)

        ttk.Button(
            btn_frame, text=f"🔍 {tr('test_connection')}", bootstyle=INFO,
            command=self._test_connection, padding=(7, 3)
        ).pack(side=LEFT, padx=4)
        ttk.Button(
            btn_frame, text=f"💾 {tr('save_machine')}", bootstyle=SUCCESS,
            command=self._save_machine, padding=(7, 3)
        ).pack(side=LEFT, padx=4)
        ttk.Button(
            btn_frame, text=f"🗑️ {tr('delete_machine')}", bootstyle=DANGER,
            command=self._delete_machine, padding=(7, 3)
        ).pack(side=LEFT, padx=4)
        ttk.Button(
            btn_frame, text="🕒 SYNC TIME", bootstyle="outline-primary",
            command=self._sync_machine_time, padding=(7, 3)
        ).pack(side=LEFT, padx=4)
        ttk.Button(
            btn_frame, text="🔄 REBOOT", bootstyle="outline-danger",
            command=self._reboot_machine, padding=(7, 3)
        ).pack(side=LEFT, padx=4)

        # Auto Reboot options
        auto_row = len(fields) + 2
        auto_frame = ttk.LabelFrame(form_frame, text="🔄 Auto Reboot")
        auto_frame.grid(row=auto_row, column=0, columnspan=3, sticky=EW, padx=2, pady=(4, 2))
        auto_frame.columnconfigure(1, weight=1)

        self._auto_reboot_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            auto_frame, text="Enable Auto Reboot",
            variable=self._auto_reboot_var, bootstyle="round-toggle"
        ).grid(row=0, column=0, sticky=W, padx=4, pady=2)

        ttk.Label(auto_frame, text="Time:", font=("Space Mono", 9, "bold")).grid(
            row=0, column=1, sticky=E, padx=(10, 2))
        self._auto_reboot_hour_var = ttk.StringVar(value="03")
        self._auto_reboot_min_var = ttk.StringVar(value="00")
        ttk.Spinbox(
            auto_frame, from_=0, to=23, textvariable=self._auto_reboot_hour_var,
            width=3, font=("JetBrains Mono", 9), format="%02.0f", wrap=True
        ).grid(row=0, column=2, padx=1)
        ttk.Label(auto_frame, text=":", font=("Space Mono", 9, "bold")).grid(
            row=0, column=3)
        ttk.Spinbox(
            auto_frame, from_=0, to=59, textvariable=self._auto_reboot_min_var,
            width=3, font=("JetBrains Mono", 9), format="%02.0f", wrap=True
        ).grid(row=0, column=4, padx=(1, 4))

        # Status label
        self._machine_status = ttk.Label(form_frame, text="", font=("Space Mono", 9))
        self._machine_status.grid(row=auto_row + 1, column=0, columnspan=3, sticky=W, padx=3)

        # ── Machine List Panel ──
        list_frame = ttk.LabelFrame(inner_paned, text="📋 MACHINES")
        list_frame.pack_propagate(False)
        inner_paned.add(list_frame, weight=2)

        self._machine_table_frame = ttk.Frame(list_frame)
        self._machine_table_frame.pack(fill=BOTH, expand=YES)
        self._machine_table = None

        # ── Clock Time display below table ──
        time_bar = ttk.Frame(list_frame)
        time_bar.pack(fill=X, padx=3, pady=(0, 3))
        ttk.Label(time_bar, text="🕒 Clock Time:", font=("Space Mono", 8, "bold")).pack(side=LEFT, padx=2)
        self._machine_clock_time_var = ttk.StringVar(value="—")
        self._machine_clock_time_entry = ttk.Entry(
            time_bar, textvariable=self._machine_clock_time_var,
            width=22, state="readonly", font=("JetBrains Mono", 9)
        )
        self._machine_clock_time_entry.pack(side=LEFT, padx=2)
        ttk.Button(
            time_bar, text="🔄", bootstyle="outline-info",
            command=self._fetch_selected_machine_time, width=4
        ).pack(side=LEFT, padx=2)

        # ── LOGS Panel ──
        logs_frame = ttk.LabelFrame(outer_paned, text="📝 LOGS")
        outer_paned.add(logs_frame, weight=1)

        logs_inner = tk.Frame(logs_frame, bg="#0F172A")
        logs_inner.pack(fill=BOTH, expand=YES, padx=2, pady=2)

        self._machine_logs_text = tk.Text(
            logs_inner, height=6, bg="#0F172A", fg="#94A3B8",
            font=("JetBrains Mono", 9), wrap=WORD,
            state=DISABLED, relief=FLAT, bd=0, highlightthickness=0
        )
        logs_scroll = ttk.Scrollbar(logs_inner, orient=VERTICAL,
                                     command=self._machine_logs_text.yview)
        self._machine_logs_text.configure(yscrollcommand=logs_scroll.set)
        logs_scroll.pack(side=RIGHT, fill=Y)
        self._machine_logs_text.pack(fill=BOTH, expand=YES)

        # Reload machines when this tab is selected
        self.notebook.bind("<<NotebookTabChanged>>", self._on_machine_tab_selected)

    # ── Machine Actions ───────────────────────────────────────────────────

    def _load_machines(self):
        machines = self.service.get_all_machines()
        # Columns mapped to reference image
        cols = [
            "ID", 
            "Device Name", 
            "State", 
            "Machine ID", 
            "Comm Type", 
            "Baud Rate", 
            "IP Address", 
            "Port", 
            "Product", 
            "Users", 
            "Faces",
            "Admins", 
            "Fingers", 
            "Passwd", 
            "Punches", 
            "Serial"
        ]
        rows = []
        for m in machines:
            # We initialize status/stats as placeholders unless recently tested
            rows.append((
                m.id, 
                m.name, 
                "Unknown", 
                m.machine_number or 1,
                m.comm_type or "Ethernet",
                m.baud_rate or 115200,
                m.ip_address, 
                m.port,
                m.product_name or "-",
                m.user_count or 0,
                f"{m.face_count or 0} / {m.face_cap or 0}",
                m.admin_count or 0,
                m.fingerprint_count or 0,
                m.password_count or 0,
                m.punch_count or 0,
                m.serial_number or "-"
            ))

        for w in self._machine_table_frame.winfo_children():
            w.destroy()

        self._machine_table = Tableview(
            master=self._machine_table_frame,
            coldata=cols,
            rowdata=rows,
            paginated=False,
            searchable=False,
            bootstyle="dark",
            autofit=True,
        )
        self._machine_table.pack(fill=BOTH, expand=YES)
        self._machine_table.view.bind("<<TreeviewSelect>>", self._on_machine_select)

        # Configure status tags for coloring
        # Note: 'Online' and 'Offline' are the literals we'll inject into the 'State' column
        self._machine_table.view.tag_configure('online', foreground="#10B981", font=("Space Mono", 9, "bold")) # Emerald
        self._machine_table.view.tag_configure('offline', foreground="#EF4444", font=("Space Mono", 9, "bold")) # Rose

        # Trigger background status check
        threading.Thread(target=self._check_machines_status, daemon=True).start()

    def _check_machines_status(self):
        """Pings all machines in the background and updates the UI table."""
        if not hasattr(self, "_machine_table") or not self._machine_table:
            return

        import time
        from contragest.features.pointage.service import PointageService
        
        # We need a fresh session for the background check
        from contragest.core.database import SessionLocal
        session = SessionLocal()
        try:
            svc = PointageService(session)
            machines = svc.get_all_machines()
            
            for m in machines:
                if not self.winfo_exists(): break
                
                # Ping check
                online = svc.connector.ping(m.ip_address)
                status_text = "Online" if online else "Offline"
                tag = "online" if online else "offline"
                
                # Update the table row
                # We find the row by the ID (column 0)
                def update_row(mid=m.id, text=status_text, t=tag):
                    if not self._machine_table: return
                    for item in self._machine_table.view.get_children():
                        values = self._machine_table.view.item(item, "values")
                        if values and int(values[0]) == mid:
                            new_values = list(values)
                            new_values[2] = text # "State" is at index 2
                            self._machine_table.view.item(item, values=new_values, tags=(t,))
                            break
                            
                self.after(0, update_row)
                # Small delay between pings to avoid flooding the network
                time.sleep(0.05)
        except Exception as e:
            logger.warning(f"Background status check error: {e}")
        finally:
            session.close()

    def _on_machine_select(self, event=None):
        sel = self._machine_table.view.selection()
        if not sel:
            return
        values = self._machine_table.view.item(sel[0], "values")
        if not values: return
        
        self.selected_machine_id = int(values[0])
        machine = self.service.get_machine(self.selected_machine_id)
        
        if machine:
            # Populate from DB object primary, fallback to table values for safety
            self._machine_vars["machine_name"].set(machine.name or values[1])
            self._machine_vars["ip_address"].set(machine.ip_address or values[6])
            self._machine_vars["port"].set(str(machine.port or values[7]))
            self._machine_vars["machine_number"].set(str(machine.machine_number or values[3]))
            self._machine_vars["comm_type"].set(machine.comm_type or values[4])
            self._machine_vars["baud_rate"].set(str(machine.baud_rate or values[5]))
            self._machine_vars["username"].set(machine.username or "")
            self._machine_vars["password"].set(machine.password or "")
            self._machine_vars["product_name"].set(machine.product_name or values[8] or "")
            self._machine_vars["serial_number"].set(machine.serial_number or values[15] or "")
            
            # Auto-reboot fields
            reboot_enabled = bool(machine.auto_reboot_enabled)
            reboot_time = machine.auto_reboot_time or "03:00"
            self._auto_reboot_var.set(reboot_enabled)
            parts = reboot_time.split(":")
            self._auto_reboot_hour_var.set(f"{int(float(parts[0])):02d}")
            self._auto_reboot_min_var.set(f"{int(float(parts[1] if len(parts) > 1 else 0)):02d}")
            self._log_machine(f"🔧 Loaded auto-reboot: enabled={reboot_enabled}, time={reboot_time}")
            
            # Clear clock time and auto-fetch
            self._machine_vars["clock_time"].set("")
            self._machine_clock_time_var.set("—")
            self._fetch_selected_machine_time()

            # Clear status
            self._machine_status.configure(text="", bootstyle=SECONDARY)
        else:
            # Fallback to pure table values if DB fetch failed
            self._machine_vars["machine_name"].set(values[1])
            self._machine_vars["ip_address"].set(values[6])
            self._machine_vars["port"].set(values[7])
            self._machine_vars["machine_number"].set(values[3])
            self._machine_vars["comm_type"].set(values[4])
            self._machine_vars["baud_rate"].set(values[5])
            self._machine_vars["product_name"].set(values[8])
            self._machine_vars["serial_number"].set(values[15])
            self._machine_vars["clock_time"].set("")
            self._machine_clock_time_var.set("—")
            self._auto_reboot_var.set(False)
            self._auto_reboot_hour_var.set("03")
            self._auto_reboot_min_var.set("00")

    def _test_connection(self):
        """Tests connection to the machine in the background via TaskManager."""
        ip = self._machine_vars["ip_address"].get().strip()
        port_str = self._machine_vars["port"].get().strip()
        pwd = self._machine_vars["password"].get().strip()
        
        if not ip:
            Messagebox.show_warning(tr("ip_address") + " is required.", tr("information"))
            return
            
        try:
            port = int(port_str or 4370)
        except ValueError:
            Messagebox.show_error("Invalid port number.", "Error")
            return

        self._machine_status.configure(text=f"⏳ {tr('testing_connection')}...", bootstyle=INFO)
        self._log_machine(f"🔌 Testing connection to {ip}:{port}...")
        
        # Use centralized task manager
        self.task_manager.run_task(
            task_id="machine_test",
            name=f"🔌 Connection Test: {ip}",
            target=self.service.test_connection_direct,
            args=(ip, port, pwd),
            on_complete=self._finalize_connection_test,
            on_error=lambda err: self._machine_status.configure(text=f"❌ {err}", bootstyle=DANGER)
        )

    def _finalize_connection_test(self, result):
        """Handles the UI update after a connection test finishes."""
        success, msg = result
        ip = self._machine_vars["ip_address"].get().strip()
        if success:
            if self.selected_machine_id:
                info = self.service.fetch_device_info(self.selected_machine_id)
                if info:
                    self.service.save_machine({
                        "machine_number": info.get("machine_number", 1),
                        "product_name": info.get("product_name"),
                        "serial_number": info.get("serial_number"),
                        "user_count": info.get("user_count", 0),
                        "face_count": info.get("face_count", 0),
                        "face_cap": info.get("face_cap", 0),
                        "admin_count": info.get("admin_count", 0),
                        "fingerprint_count": info.get("fingerprint_count", 0),
                        "password_count": info.get("password_count", 0),
                        "punch_count": info.get("punch_count", 0),
                    }, machine_id=self.selected_machine_id)
                    
                    self._machine_vars["machine_number"].set(str(info.get("machine_number", 1)))
                    self._machine_vars["product_name"].set(info.get("product_name") or "")
                    self._machine_vars["serial_number"].set(info.get("serial_number") or "")
                    
                    status_msg = f"✅ {msg}\n"
                    status_msg += f"Device: {info.get('product_name')} | S/N: {info.get('serial_number')}\n"
                    status_msg += f"Users: {info.get('user_count')} | Faces: {info.get('face_count')} / {info.get('face_cap')}\n"
                    status_msg += f"Fingers: {info.get('fingerprint_count')} | Punches: {info.get('punch_count')}"
                    self._machine_status.configure(text=status_msg, bootstyle=SUCCESS)
                    self._load_machines()
                    device = f"{info.get('product_name')} ({ip})"
                    self._log_machine(f"✅ Connected to {device} | {info.get('user_count')} users, {info.get('punch_count')} punches")
                else:
                    self._machine_status.configure(text=f"✅ {msg}", bootstyle=SUCCESS)
                    self._log_machine(f"✅ {ip}: connected (no device info)")
            else:
                self._machine_status.configure(text=f"✅ {msg}", bootstyle=SUCCESS)
                self._log_machine(f"✅ {ip}: {msg}")
        else:
            self._machine_status.configure(text=f"❌ {msg}", bootstyle=DANGER)
            self._log_machine(f"❌ {ip}: {msg}")

    def _save_machine(self):
        try:
            hour_raw = self._auto_reboot_hour_var.get().strip()
            min_raw = self._auto_reboot_min_var.get().strip()
            reboot_time = f"{int(float(hour_raw)):02d}:{int(float(min_raw)):02d}"
        except Exception:
            reboot_time = "03:00"

        data = {
            "name": self._machine_vars["machine_name"].get().strip() or "Machine",
            "ip_address": self._machine_vars["ip_address"].get().strip(),
            "port": int(self._machine_vars["port"].get() or 4370),
            "machine_number": int(self._machine_vars["machine_number"].get() or 1),
            "comm_type": self._machine_vars["comm_type"].get(),
            "baud_rate": int(self._machine_vars["baud_rate"].get() or 115200),
            "username": self._machine_vars["username"].get().strip(),
            "password": self._machine_vars["password"].get().strip(),
            "auto_reboot_enabled": self._auto_reboot_var.get(),
            "auto_reboot_time": reboot_time,
        }
        if not data["ip_address"]:
            Messagebox.show_warning(tr("ip_address") + " is required.", tr("information"))
            return
        try:
            name = data["name"]
            mid = self.selected_machine_id
            self.service.save_machine(data, machine_id=mid)
            self._log_machine(
                f"💾 Saved machine '{name}' ({data['ip_address']}) "
                f"| auto_reboot: enabled={data['auto_reboot_enabled']}, time={data['auto_reboot_time']}"
            )
            # Verify save by reading back
            if mid:
                ver = self.service.get_machine(mid)
                if ver:
                    self._log_machine(
                        f"🔍 Verify: auto_reboot_enabled={bool(ver.auto_reboot_enabled)}, "
                        f"auto_reboot_time={ver.auto_reboot_time}"
                    )
            self._machine_status.configure(text=f"✅ {tr('machine_saved')}", bootstyle=SUCCESS)
            self.selected_machine_id = None
            self._clear_machine_form()
            self._load_machines()
        except Exception as e:
            self._log_machine(f"❌ Save failed: {e}")
            Messagebox.show_error(str(e), tr("error"))

    def _delete_machine(self):
        if not self.selected_machine_id:
            Messagebox.show_info(tr("no_machine_selected"), tr("information"))
            return
        ans = Messagebox.show_question(
            tr("confirm_delete_machine"), tr("confirmation"),
            buttons=["No:secondary", "Yes:danger"]
        )
        if ans == "Yes":
            mid = self.selected_machine_id
            self.service.delete_machine(mid)
            self._machine_status.configure(text=f"✅ {tr('machine_deleted')}", bootstyle=SUCCESS)
            self._log_machine(f"🗑️ Deleted machine #{mid}")
            self.selected_machine_id = None
            self._clear_machine_form()
            self._load_machines()

    def _clear_machine_form(self):
        for key, var in self._machine_vars.items():
            var.set("4370" if key == "port" else "")
        self._machine_clock_time_var.set("—")
        self._auto_reboot_var.set(False)
        self._auto_reboot_hour_var.set("03")
        self._auto_reboot_min_var.set("00")
        self.selected_machine_id = None

    def _fetch_selected_machine_time(self):
        """Fetch and display clock time for the selected machine."""
        if not self.selected_machine_id:
            Messagebox.show_info("Select a machine first.", "No Selection")
            return
        machine = self.service.get_machine(self.selected_machine_id)
        if not machine or not machine.ip_address:
            return
        self._machine_vars["clock_time"].set("Fetching...")
        self._machine_clock_time_var.set("Fetching...")
        import threading
        threading.Thread(target=self._fetch_machine_time_bg,
                         args=(machine,), daemon=True).start()

    def _fetch_machine_time_bg(self, machine):
        """Background worker for fetching machine clock time."""
        try:
            result = self.service.connector.get_device_time(
                machine.ip_address, machine.port, machine.password or ""
            )
            if result.get("success") and result.get("machine_time"):
                t = result["machine_time"]
                formatted = t.strftime("%Y-%m-%d %H:%M:%S")
                self.after(0, lambda: self._machine_vars["clock_time"].set(formatted))
                self.after(0, lambda: self._machine_clock_time_var.set(formatted))
            else:
                msg = result.get("message", "Failed")
                self.after(0, lambda: self._machine_vars["clock_time"].set(f"❌ {msg}"))
                self.after(0, lambda: self._machine_clock_time_var.set(f"❌ {msg}"))
        except Exception as e:
            self.after(0, lambda: self._machine_vars["clock_time"].set(f"❌ {e}"))
            self.after(0, lambda: self._machine_clock_time_var.set(f"❌ {e}"))

    def _log_machine(self, msg):
        """Append a timestamped message to the machine config logs pane."""
        text = getattr(self, "_machine_logs_text", None)
        if not text or not text.winfo_exists():
            return
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        text.configure(state=NORMAL)
        text.insert(END, f"[{ts}] {msg}\n")
        text.see(END)
        text.configure(state=DISABLED)

    def _on_machine_tab_selected(self, event=None):
        """Reload machines when the Machine Config tab is selected."""
        if not self.winfo_exists():
            return
        current = self.notebook.select()
        tab_id = str(self._tab_machine)
        if str(current) == tab_id:
            self._load_machines()

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 2 - Data Transfer
    # ═══════════════════════════════════════════════════════════════════════

    def _build_transfer_tab(self):
        parent = self._tab_transfer
        # Apply Main BG to tab container for full OLED effect
        parent.configure(background=MAIN_BG)

        # ─── SECTION 1: ATTENDANCE SUMMARY DASHBOARD ───
        summary_container = tk.Frame(parent, background=MAIN_BG)
        summary_container.pack(fill=X, padx=9, pady=(6, 4))

        # Header row
        header_row = tk.Frame(summary_container, background=MAIN_BG)
        header_row.pack(fill=X, pady=(1, 4))
        tk.Label(
            header_row,
            text=f"📊 {tr('attendance_summary').replace('_', ' ').upper()}",
            font=("JetBrains Mono", 9, "bold"),
            bg=MAIN_BG, fg=ACCENT_BLUE
        ).pack(side=LEFT)
        tk.Label(
            header_row, text="Live - Updated on Search",
            font=("Space Mono", 8), bg=MAIN_BG, fg=TEXT_MUTED
        ).pack(side=LEFT, padx=6)

        # ─── KPI CARDS ───
        outer_scroll = tk.Frame(summary_container, background=MAIN_BG)
        outer_scroll.pack(fill=X)

        cards_canvas = tk.Canvas(outer_scroll, height=95, bg=MAIN_BG, highlightthickness=0)
        cards_canvas.pack(fill=X, side=TOP)

        cards_inner = tk.Frame(cards_canvas, background=MAIN_BG)
        cards_canvas.create_window((0, 0), window=cards_inner, anchor=NW)

        self._summary_labels = {}
        self._summary_pcts = {}

        # Card accent colours per status code
        code_accent = {
            "TOTAL": ACCENT_BLUE,
            "P":     SUCCESS_EMERALD,
            "AB":    DANGER_ROSE,
            "CA":    "#6366F1",   # indigo
            "JF":    "#F59E0B",   # amber
            "RH":     "#00A6F4",   # violet
            "RHB":   "#A78BFA",
            "CR":    "#F97316",   # orange
            "CM":    "#14B8A6",   # teal
            "MIS":   "#EF4444",
            "MAP":   "#EC4899",
            "PJF":   "#F59E0B",
            "JFP":   "#EAB308",
            "CSS":   "#22D3EE",
            "DS":    "#94A3B8",
        }
        code_icons = {
            "TOTAL": "#",  "P": "✓",  "AB": "✗",  "CA": "🏥",
            "JF": "☀",    "RH": "🏠", "CR": "↘",  "CM": "⚕",
            "MIS": "?",   "MAP": "~", "RHB": "▷",
        }

        all_display_keys = ["TOTAL"] + self._status_keys
        for key in all_display_keys:
            accent = code_accent.get(key, "#64748B")
            icon   = code_icons.get(key, "▸")

             # Flat modern card styling - Use subtle border, vibrant accent
            # For Maximum color, we use the accent color as bottom border or background highlight
            card_bg = PANEL_BG # Keep contrast
            card = tk.Frame(cards_inner, bg=card_bg, padx=7, pady=4,
                            highlightbackground=accent, highlightthickness=1, takefocus=0)
            card.pack(side=LEFT, padx=3, pady=1)

            # Icon + Code row
            tk.Label(card,
                     text=f"{icon}  {key}",
                     font=("JetBrains Mono", 9, "bold"),
                     fg=accent, bg=card_bg).pack(anchor=W)

            # Big Count
            val_var = tk.StringVar(value="0")
            count_lbl = tk.Label(card, textvariable=val_var,
                                 font=("Space Mono", 16, "bold"),
                                 fg=TEXT_HIGH, bg=card_bg)
            count_lbl.pack(anchor=W)
            count_lbl._val_var = val_var
            self._summary_labels[key] = count_lbl

            # Percentage in muted colour
            pct_var = tk.StringVar(value="0.0%")
            pct_lbl = tk.Label(card, textvariable=pct_var,
                               font=("Space Mono", 9),
                               fg="#CBD5E1",
                               bg=card_bg)
            pct_lbl.pack(anchor=W)
            pct_lbl._pct_var = pct_var
            self._summary_pcts[key] = pct_lbl

        cards_inner.update_idletasks()
        cards_canvas.config(scrollregion=cards_canvas.bbox("all"))

        h_scroll = ttk.Scrollbar(outer_scroll, orient=HORIZONTAL,
                                 command=cards_canvas.xview, bootstyle="round")
        if cards_inner.winfo_reqwidth() > 1150:
            h_scroll.pack(fill=X, side=BOTTOM, pady=(2, 1))
            cards_canvas.configure(xscrollcommand=h_scroll.set)

        # ─── SECTION 2: MACHINE DOWNLOAD BAR ───
        conn_bar = tk.Frame(parent, bg=PANEL_BG,
                            highlightbackground=BORDER_COLOR, highlightthickness=1, takefocus=0)
        conn_bar.pack(fill=X, padx=9, pady=(1, 4))

        # Left label
        tk.Label(conn_bar, text="📍 MACHINE", font=("JetBrains Mono", 9, "bold"),
                 fg=TEXT_MUTED, bg=PANEL_BG).pack(side=LEFT, padx=(7, 4), pady=6)

        self._transfer_machine_var = tk.StringVar()
        self._transfer_combo = ttk.Combobox(
            conn_bar, textvariable=self._transfer_machine_var,
            state="readonly", font=("Space Mono", 9), width=30
        )
        self._transfer_combo.pack(side=LEFT, padx=(1, 3), pady=4)

        ttk.Button(conn_bar, text="⟳", bootstyle="outline-secondary",
                   command=self._refresh_transfer_combo, width=3
                   ).pack(side=LEFT, padx=1, pady=4)

        ttk.Button(conn_bar, text=f"📥  {tr('download_data').upper()}",
                   bootstyle=SUCCESS, command=self._download_attendance, width=22
                   ).pack(side=LEFT, padx=(7, 1), pady=4)

        self._transfer_status = tk.Label(
            conn_bar, text="", font=("Space Mono", 9, "italic"),
            bg=PANEL_BG, fg=ACCENT_BLUE
        )
        self._transfer_status.pack(side=LEFT, padx=7, pady=4)

        # ─── Sync result pills ───
        sync_meta_frame = tk.Frame(parent, background=MAIN_BG)
        sync_meta_frame.pack(fill=X, padx=9, pady=(1, 3))

        def _pill(parent, text, color):
            f = tk.Frame(parent, bg=color, padx=4, pady=1)
            f.pack(side=LEFT, padx=(1, 3))
            return tk.Label(f, text=text, font=("JetBrains Mono", 8, "bold"),
                            bg=color, fg=MAIN_BG)

        # ─── Inline canvas progress bar — packed RIGHT first (Tkinter rule) ───
        cli_prog_frame = tk.Frame(sync_meta_frame, bg=MAIN_BG)
        cli_prog_frame.pack(side=RIGHT, padx=(2, 9), pady=0)

        # Percentage badge
        self._cli_pct_label = tk.Label(
            cli_prog_frame, text="  0%",
            font=("JetBrains Mono", 8, "bold"),
            bg=MAIN_BG, fg="#334155", width=5, anchor="e"
        )
        self._cli_pct_label.pack(side=RIGHT, padx=(3, 0))

        # Canvas-drawn segmented bar (20 segments)
        _BAR_W, _BAR_H, _SEGS = 140, 10, 20
        self._cli_canvas = tk.Canvas(
            cli_prog_frame, width=_BAR_W, height=_BAR_H,
            bg=MAIN_BG, highlightthickness=0
        )
        self._cli_canvas.pack(side=RIGHT, padx=(0, 2))

        # Draw initial empty segments
        _seg_w   = (_BAR_W - (_SEGS - 1) * 2) // _SEGS
        _seg_gap = 2
        _cli_seg_ids = []
        for _i in range(_SEGS):
            _x0 = _i * (_seg_w + _seg_gap)
            _x1 = _x0 + _seg_w
            _r = _cli_seg_ids.__len__
            sid = self._cli_canvas.create_rectangle(
                _x0, 0, _x1, _BAR_H,
                fill="#1E293B", outline="#334155", width=1
            )
            _cli_seg_ids.append(sid)

        self._cli_seg_ids = _cli_seg_ids
        self._cli_seg_w   = _seg_w
        self._cli_seg_gap = _seg_gap
        self._cli_segs    = _SEGS
        self._cli_prog_pct = 0

        def _color_for_pct(pct):
            """Returns fill/outline colors for the active segment color."""
            if pct < 40:
                return "#00A6F4", "#38BDF8"   # Cyan
            elif pct < 75:
                return "#A855F7", "#C084FC"   # Purple
            else:
                return "#22C55E", "#4ADE80"   # Green

        def _update_cli_bar(pct):
            """Redraws canvas segments for 0-100."""
            if not self.winfo_exists():
                return
            self._cli_prog_pct = pct
            n_lit = int(round(pct / 100 * _SEGS))
            fill_c, outline_c = _color_for_pct(pct)
            for idx, sid in enumerate(self._cli_seg_ids):
                if idx < n_lit:
                    # Gradient brightness: earlier segs slightly dimmer
                    alpha = 0.65 + 0.35 * (idx / max(n_lit - 1, 1))
                    # Simple brightness by blending with BG — approximate via hex
                    self._cli_canvas.itemconfigure(sid, fill=fill_c, outline=outline_c)
                else:
                    self._cli_canvas.itemconfigure(sid, fill="#1E293B", outline="#334155")
            # Update pct badge
            badge_fg = fill_c if pct > 0 else "#334155"
            self._cli_pct_label.configure(
                text=f"{int(pct):3d}%",
                fg=badge_fg
            )

        self._update_cli_bar = _update_cli_bar
        _update_cli_bar(0)

        # ─── LEFT-side pills (packed after RIGHT so they don't push the bar) ───
        self._lbl_raw_result  = _pill(sync_meta_frame, "⬇  Extracted: 0",  "#334155")
        self._lbl_raw_result.config(fg=TEXT_MUTED)
        self._lbl_raw_result.pack()
        self._lbl_ui_result = _pill(sync_meta_frame, "✔  Formatted: 0", ACCENT_AMBER)
        self._lbl_ui_result.pack()


        # ─── SECTION 3: SEARCH & FILTERS TOOLBAR ───
        filter_container = tk.Frame(
            parent, bg=PANEL_BG,
            highlightbackground=BORDER_COLOR, highlightthickness=1, takefocus=0
        )
        filter_container.pack(fill=X, padx=9, pady=(1, 4))

        # Filter header strip
        flt_header = tk.Frame(filter_container, bg=MAIN_BG) # Light header
        flt_header.pack(fill=X)
        tk.Label(flt_header, text=f"  🔍  {tr('search_filters').replace('_', ' ').upper()}",
                 font=("JetBrains Mono", 9, "bold"), bg=MAIN_BG, fg=TEXT_MUTED
                 ).pack(side=LEFT, pady=3, padx=3)

        flt_body = tk.Frame(filter_container, bg=PANEL_BG)
        flt_body.pack(fill=X, padx=7, pady=6)

        # Row 1: dropdowns
        grid_f = tk.Frame(flt_body, bg=PANEL_BG)
        grid_f.pack(fill=X, pady=(1, 4))
        grid_f.columnconfigure((1, 3, 5), weight=1)

        def _flbl(parent, text):
            return tk.Label(parent, text=text, font=("Space Mono", 9, "bold"),
                            fg=TEXT_MUTED, bg=PANEL_BG)

        _flbl(grid_f, f"🏢 {tr('department')}").grid(row=0, column=0, padx=(1, 3), sticky=W)
        self._cb_dept = ttk.Combobox(grid_f, textvariable=self._filter_dept, state="normal",
                                     font=("Space Mono", 9))
        self._cb_dept.grid(row=0, column=1, sticky=EW, padx=(1, 10))
        self._cb_dept.bind("<<ComboboxSelected>>", self._on_dept_selected)

        _flbl(grid_f, f"👤 {tr('employee')}").grid(row=0, column=2, padx=(1, 3), sticky=W)
        self._cb_emp = ttk.Combobox(grid_f, textvariable=self._filter_emp, state="readonly",
                                  font=("Space Mono", 9))
        self._cb_emp.grid(row=0, column=3, sticky=EW, padx=(1, 10))

        _flbl(grid_f, f"🚥 {tr('punch_type')}").grid(row=0, column=4, padx=(1, 3), sticky=W)
        cb_type = ttk.Combobox(grid_f, textvariable=self._filter_type,
                               values=[tr("all_types"), tr("check_in_type"), tr("check_out_type")],
                               state="readonly", font=("Space Mono", 9))
        cb_type.grid(row=0, column=5, sticky=EW)

        # Row 2: dates + action buttons
        bottom_row = tk.Frame(flt_body, bg=PANEL_BG)
        bottom_row.pack(fill=X)

        today_str = datetime.now().strftime('%Y-%m-%d')

        _flbl(bottom_row, "📅 FROM").pack(side=LEFT, padx=(1, 3))
        self._filter_from_de = DateEntry(bottom_row, bootstyle=SECONDARY, dateformat='%Y-%m-%d')
        self._filter_from_de.pack(side=LEFT, padx=(1, 10))
        self._filter_from_de.entry.delete(0, "end")
        self._filter_from_de.entry.insert(0, today_str)

        _flbl(bottom_row, "📅 TO").pack(side=LEFT, padx=(1, 3))
        self._filter_to_de = DateEntry(bottom_row, bootstyle=SECONDARY, dateformat='%Y-%m-%d')
        self._filter_to_de.pack(side=LEFT, padx=(1, 13))
        self._filter_to_de.entry.delete(0, "end")
        self._filter_to_de.entry.insert(0, today_str)

        # Separator
        ttk.Separator(bottom_row, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=6, pady=1)

        ttk.Button(bottom_row, text="🔍  SEARCH", bootstyle=PRIMARY,
                   command=self._load_recent_records, width=14).pack(side=LEFT, padx=(1, 2))
        ttk.Button(bottom_row, text="✖  CLEAR", bootstyle="outline-secondary",
                   command=self._clear_filters, width=10).pack(side=LEFT, padx=2)
        ttk.Button(bottom_row, text="➕  FIX / ADD PUNCH", bootstyle=WARNING,
                   command=self._open_manual_punch_dialog_from_btn
                   ).pack(side=LEFT, padx=(7, 1))
        ttk.Button(bottom_row, text="🔄  RECALCULATE", bootstyle="outline-info",
                   command=self._recalculate_attendance
                   ).pack(side=LEFT, padx=(4, 1))
        # Right export buttons - Organized into Panes
        stat_pane = ttk.Labelframe(bottom_row, text="Statistics", bootstyle=DANGER)
        stat_pane.pack(side=RIGHT, padx=(2, 1))
        ttk.Button(stat_pane, text="📕 PDF", bootstyle=DANGER,
                   command=self._export_pdf, width=10).pack(padx=3, pady=3)

        report_pane = ttk.Labelframe(bottom_row, text="Reports", bootstyle=SUCCESS)
        report_pane.pack(side=RIGHT, padx=2)

        ttk.Button(report_pane, text="📗 EXCEL", bootstyle=SUCCESS,
                   command=self._export_excel, width=11).pack(side=RIGHT, padx=3, pady=3)

        # ─── SECTION 4: PROGRESS & STATUS (Loading State) ───
        # Custom canvas-drawn gradient progress bar — replaces ttkbootstrap Progressbar
        self._prog_frame = tk.Frame(parent, background=MAIN_BG, height=110)
        self._prog_frame.pack_propagate(False)
        self._prog_frame.pack_forget()  # Hidden by default

        # Inner container — centered vertically
        inner_prog = tk.Frame(self._prog_frame, background=MAIN_BG)
        inner_prog.place(relx=0.5, rely=0.5, anchor=tk.CENTER, relwidth=0.88)

        # ── Top row: task icon + name ──
        top_row = tk.Frame(inner_prog, bg=MAIN_BG)
        top_row.pack(fill=tk.X, pady=(0, 6))

        self._task_name_label = tk.Label(
            top_row, text="",
            font=("JetBrains Mono", 9, "bold"),
            bg=MAIN_BG, fg=DesignTokens.PRIMARY, anchor="w"
        )
        self._task_name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Percentage badge (top-right)
        self._progress_pct_label = tk.Label(
            top_row, text="0%",
            font=("JetBrains Mono", 11, "bold"),
            bg=MAIN_BG, fg="#22C55E", anchor="e", width=6
        )
        self._progress_pct_label.pack(side=tk.RIGHT)

        # ── Canvas progress bar ──
        _PB_H = 18  # bar height in pixels
        self._progress_var = tk.DoubleVar(value=0)
        self._prog_canvas = tk.Canvas(
            inner_prog, height=_PB_H, bg="#1E293B",
            highlightthickness=1, highlightbackground="#334155"
        )
        self._prog_canvas.pack(fill=tk.X, pady=(0, 4))

        # Track fill rect and shimmer rect ids
        self._prog_fill_id    = self._prog_canvas.create_rectangle(0, 0, 0, _PB_H, fill="#00A6F4", outline="")
        self._prog_shimmer_id = self._prog_canvas.create_rectangle(0, 0, 0, _PB_H, fill="#FFFFFF", outline="", stipple="gray25")
        self._prog_canvas.itemconfigure(self._prog_shimmer_id, state="hidden")

        # Canvas resize callback
        def _on_prog_canvas_resize(event):
            self._redraw_prog_canvas(self._progress_var.get())
        self._prog_canvas.bind("<Configure>", _on_prog_canvas_resize)

        def _redraw_prog_canvas(pct):
            """Repaints the canvas bar and shimmer for a given 0-100 pct."""
            if not self.winfo_exists():
                return
            cw = self._prog_canvas.winfo_width()
            ch = self._prog_canvas.winfo_height()
            fill_w = int(cw * pct / 100)

            # Gradient color by phase
            if pct < 40:
                bar_color = "#00A6F4"   # Cyan
                pct_color = "#38BDF8"
            elif pct < 75:
                bar_color = "#A855F7"   # Purple
                pct_color = "#C084FC"
            else:
                bar_color = "#22C55E"   # Green
                pct_color = "#4ADE80"

            self._prog_canvas.coords(self._prog_fill_id, 0, 0, fill_w, ch)
            self._prog_canvas.itemconfigure(self._prog_fill_id, fill=bar_color)

            # Shimmer stripe on active area
            if fill_w > 12:
                shimmer_x = max(0, fill_w - 30)
                self._prog_canvas.coords(self._prog_shimmer_id, shimmer_x, 0, fill_w, ch)
                self._prog_canvas.itemconfigure(self._prog_shimmer_id, state="normal")
            else:
                self._prog_canvas.itemconfigure(self._prog_shimmer_id, state="hidden")

            self._progress_pct_label.configure(text=f"{int(pct)}%", fg=pct_color)

        self._redraw_prog_canvas = _redraw_prog_canvas

        # Trace DoubleVar so external code that sets _progress_var also redraws
        def _on_progress_var_write(*_):
            if not self.winfo_exists():
                return
            pct = self._progress_var.get()
            self._redraw_prog_canvas(pct)
        self._progress_var.trace_add("write", _on_progress_var_write)

        # Shimmer animation loop
        self._shimmer_offset = 0
        self._shimmer_running = False

        def _shimmer_tick():
            if not self._shimmer_running:
                return
            if not self.winfo_exists():
                return
            if not self._prog_canvas.winfo_exists():
                return
            pct = self._progress_var.get()
            if 5 < pct < 100:
                cw = self._prog_canvas.winfo_width()
                fill_w = int(cw * pct / 100)
                # Move shimmer stripe across fill area
                self._shimmer_offset = (self._shimmer_offset + 4) % max(fill_w, 1)
                s0 = self._shimmer_offset
                s1 = min(s0 + 24, fill_w)
                self._prog_canvas.coords(self._prog_shimmer_id, s0, 0, s1, _PB_H)
                self._prog_canvas.itemconfigure(self._prog_shimmer_id, state="normal")
            else:
                self._prog_canvas.itemconfigure(self._prog_shimmer_id, state="hidden")
            self.after(40, _shimmer_tick)  # ~25 fps

        self._shimmer_tick = _shimmer_tick

        # ── Bottom row: ETA label ──
        bottom_row = tk.Frame(inner_prog, bg=MAIN_BG)
        bottom_row.pack(fill=tk.X)

        self._progress_eta_label = tk.Label(
            bottom_row, text="Initializing...",
            font=("Space Mono", 8), bg=MAIN_BG,
            fg=DesignTokens.TEXT_MUTED, anchor="w"
        )
        self._progress_eta_label.pack(side=tk.LEFT)

        # Backward-compat alias
        self._progress_bar   = self._prog_canvas   # some callers call .configure(bootstyle=...)
        self._progress_label = self._progress_eta_label


        # ─── SECTION 6: RESULTS TABLE CONTAINER ───

        self._records_container = ttk.Frame(parent)
        self._records_container.pack(side=tk.TOP, fill=BOTH, expand=YES, padx=9, pady=3)
        
        # Bottom Metadata / Navigation Bar Frame
        self._records_footer = tk.Frame(self._records_container, bg=MAIN_BG, pady=4, padx=9)
        self._records_footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(3, 1))
        
        # Left side: Navigation identifier
        nav_left = tk.Frame(self._records_footer, bg=MAIN_BG)
        nav_left.pack(side=LEFT)
        tk.Label(nav_left, text=f"📑 {tr('attendance_records').upper()} - AUDIT VIEW", 
                 font=("JetBrains Mono", 9, "bold"), bg=MAIN_BG, fg=TEXT_MUTED).pack(side=LEFT)
                 
        # Center: Beautiful Custom Paginator Controls
        nav_center = tk.Frame(self._records_footer, bg=MAIN_BG)
        nav_center.pack(side=LEFT, expand=YES)
        ttk.Button(nav_center, text="«  PREV", bootstyle="outline-primary", command=self._cmd_prev_page).pack(side=LEFT, padx=6)
        self._nav_page_lbl = tk.Label(nav_center, text="Page 1 of 1", font=("Space Mono", 9, "bold"), bg=MAIN_BG, fg=TEXT_HIGH)
        self._nav_page_lbl.pack(side=LEFT, padx=9)
        ttk.Button(nav_center, text="NEXT  »", bootstyle="outline-primary", command=self._cmd_next_page).pack(side=LEFT, padx=6)

        # Right side: Stats and metadata
        nav_right = tk.Frame(self._records_footer, bg=MAIN_BG)
        nav_right.pack(side=RIGHT)
        self._records_meta_lbl = tk.Label(nav_right, text="", font=("Space Mono", 9, "italic"), bg=MAIN_BG, fg=SUCCESS_EMERALD)
        self._records_meta_lbl.pack(side=RIGHT, padx=9)
        self._records_count_label = tk.Label(nav_right, text=tr("total_rows", count=0), font=("Space Mono", 9, "bold"), bg=MAIN_BG, fg=TEXT_HIGH)
        self._records_count_label.pack(side=RIGHT)

        # --- INLINE SEARCH BAR (DISBLED BY USER REQUEST) ---
        self._search_bar = tk.Frame(self._records_container, bg=PANEL_BG, pady=3, padx=7)
        # self._search_bar.pack(side=tk.TOP, fill=tk.X, pady=(1, 1))
        
        # Search icon + label
        tk.Label(self._search_bar, text="🔍", font=("Space Mono", 10),
                 bg=PANEL_BG, fg=ACCENT_BLUE).pack(side=LEFT, padx=(1, 3))
        
        # Search entry with placeholder
        self._grid_search_var = tk.StringVar()
        self._grid_search_entry = tk.Entry(
            self._search_bar,
            textvariable=self._grid_search_var,
            font=("Space Mono", 10),
            bg=MAIN_BG, fg=TEXT_HIGH,
            insertbackground=TEXT_HIGH,
            relief="flat",
            highlightthickness=1,
            highlightcolor=ACCENT_BLUE,
            highlightbackground=BORDER_COLOR,
            width=36,
        )
        self._grid_search_entry.pack(side=LEFT, padx=(1, 4), ipady=2)
        self._grid_search_entry.insert(0, "Search records...")
        self._grid_search_entry.config(fg=TEXT_MUTED)
        
        # Placeholder focus handlers
        def _on_search_focus_in(e):
            if self._grid_search_entry.get() == "Search records...":
                self._grid_search_entry.delete(0, "end")
                self._grid_search_entry.config(fg=TEXT_HIGH)
        
        def _on_search_focus_out(e):
            if not self._grid_search_entry.get().strip():
                self._grid_search_entry.insert(0, "Search records...")
                self._grid_search_entry.config(fg=TEXT_MUTED)
        
        self._grid_search_entry.bind("<FocusIn>", _on_search_focus_in)
        self._grid_search_entry.bind("<FocusOut>", _on_search_focus_out)
        
        # Debounced search on keypress
        self._search_debounce_id = None
        def _on_search_key(e):
            if self._search_debounce_id:
                self.after_cancel(self._search_debounce_id)
            self._search_debounce_id = self.after(250, self._apply_grid_search)
        self._grid_search_entry.bind("<KeyRelease>", _on_search_key)
        
        # Keyboard shortcut: Escape to clear search
        def _on_search_escape(e):
            self._grid_search_var.set("")
            self._grid_search_entry.delete(0, "end")
            self._grid_search_entry.insert(0, "Search records...")
            self._grid_search_entry.config(fg=TEXT_MUTED)
            self._grid_search_entry.master.focus()
            self._apply_grid_search()
        self._grid_search_entry.bind("<Escape>", _on_search_escape)
        
        # Results count indicator
        self._search_results_lbl = tk.Label(
            self._search_bar, text="",
            font=("Space Mono", 9, "italic"),
            bg=PANEL_BG, fg=TEXT_MUTED
        )
        self._search_results_lbl.pack(side=LEFT, padx=(2, 4))
        
        # Clear button (×)
        self._search_clear_btn = tk.Label(
            self._search_bar, text="✕", font=("Space Mono", 10, "bold"),
            bg=PANEL_BG, fg=TEXT_MUTED, cursor="hand2",
        )
        self._search_clear_btn.pack(side=LEFT, padx=(1, 7))
        self._search_clear_btn.bind("<Button-1>", _on_search_escape)
        self._search_clear_btn.bind("<Enter>", lambda e: self._search_clear_btn.config(fg=DANGER_ROSE))
        self._search_clear_btn.bind("<Leave>", lambda e: self._search_clear_btn.config(fg=TEXT_MUTED))
        
        # Keyboard shortcut hint (right side)
        tk.Label(self._search_bar, text="Ctrl+F  ·  Esc to clear",
                 font=("Space Mono", 8), bg=PANEL_BG, fg="#4B5563").pack(side=RIGHT, padx=(1, 2))
        
        # --- GLOBAL SHORTCUTS ---
        # Escape key to reset all inline filters
        self.bind_all("<Escape>", lambda e: self._clear_inline_filters())

        # Table Frame
        self._records_table_frame = ttk.Frame(self._records_container)
        self._records_table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._records_table = None

# Grand Total Footer Frame
        self._records_grand_total_frame = ttk.Frame(self._records_container)
        self._records_grand_total_frame.pack(side=tk.TOP, fill=tk.X, padx=9, pady=(2, 0))
        self._records_grand_total_frame.pack_propagate(False)

        # Footer layout: Grand Total label + values
        lbl_frame = ttk.Frame(self._records_grand_total_frame)
        lbl_frame.pack(side=tk.LEFT, fill=tk.X)
        ttk.Label(lbl_frame, text="GRAND TOTAL:", font=("JetBrains Mono", 8, "bold"),
                  background=PANEL_BG, foreground=TEXT_HIGH).pack(side=tk.LEFT, padx=(0, 12))
        self._grand_total_vars = {}
        for col in ["ATT.", "WORK.", "DIFF"]:
            self._grand_total_vars[col] = ttk.StringVar(value="-")
        ttk.Label(lbl_frame, textvariable=self._grand_total_vars["ATT."],
                  background=PANEL_BG, foreground="#94A3B8", font=("Space Mono", 8)).pack(side=tk.LEFT, padx=(4, 10))
        ttk.Label(lbl_frame, textvariable=self._grand_total_vars["WORK."],
                  background=PANEL_BG, foreground="#94A3B8", font=("Space Mono", 8)).pack(side=tk.LEFT, padx=(4, 10))
        ttk.Label(lbl_frame, textvariable=self._grand_total_vars["DIFF"],
                  background=PANEL_BG, foreground="#94A3B8", font=("Space Mono", 8)).pack(side=tk.LEFT, padx=(4, 0))

        self._refresh_transfer_combo()
        self._populate_filter_dropdowns()
        self._load_recent_records()

    def _cmd_next_page(self):
        """Advances to the next page of Tableview records."""
        if getattr(self, "_records_table", None):
            self._records_table.goto_next_page()
            # Explicitly sync view because Tableview internal load_table_data 
            # might not trigger the correct view update on custom pack-forget frames
            if hasattr(self._records_table, 'load_table_data'):
                self._records_table.load_table_data()
            self._apply_row_tags()
            self._update_nav_lbl()

    def _cmd_prev_page(self):
        """Returns to the previous page of Tableview records."""
        if getattr(self, "_records_table", None):
            self._records_table.goto_prev_page()
            if hasattr(self._records_table, 'load_table_data'):
                self._records_table.load_table_data()
            self._apply_row_tags()
            self._update_nav_lbl()

    # ── Column classification helpers ──────────────────────────────────────
    # These class-level sets define how each column header is treated by the
    # inline filter row.  Adjust here to change behaviour for new columns.
    _CATEGORICAL_COLS = {"DEPT", "EMPLOYEE", "STAT", "SCHED", "NOTE", "MACH."}
    _grid_cols_config = {
        "DATE": {"width": 120, "stretch": False},
        "DEPT": {"width": 100, "stretch": False},
        "REG": {"width": 60, "stretch": False},
        "EMPLOYEE": {"width": 180, "stretch": True},
        "ROLE": {"width": 140, "stretch": False},
        "STAT": {"width": 50, "stretch": False},
        "SCHED": {"width": 160, "stretch": False},
        "IN 1": {"width": 80, "stretch": False},
        "OUT 1": {"width": 80, "stretch": False},
        "IN 2": {"width": 80, "stretch": False},
        "OUT 2": {"width": 80, "stretch": False},
        "ATT.": {"width": 60, "stretch": False},
        "WORK": {"width": 60, "stretch": False},
        "DIFF": {"width": 70, "stretch": False},
        "NOTE": {"width": 150, "stretch": True},
        "MACH.": {"width": 80, "stretch": False},
        "SYNC": {"width": 120, "stretch": False}
    }
    _DATE_COLS        = {"DATE", "SYNC"}                 # Range: from ≤ x ≤ to
    _NUMERIC_COLS     = {"REG", "WORK", "ATT.", "DIFF"}  # Numeric ≥ / ≤ prefix
    # Everything else → substring text search

    def _collect_filter_state(self):
        """
        Snapshot the current inline filter values (before `_create_inline_filters`
        rebuilds the widgets).  Returns a dict keyed by column index.
        """
        state = {}
        if not hasattr(self, "_col_filter_vars"):
            return state
        for idx, var_or_pair in self._col_filter_vars.items():
            try:
                if isinstance(var_or_pair, tuple):
                    state[idx] = ("date", var_or_pair[0].get(), var_or_pair[1].get())
                else:
                    state[idx] = ("single", var_or_pair.get())
            except Exception:
                pass
        return state

    def _restore_filter_state(self, state):
        """
        Re-populate fresh filter widgets from a previously collected snapshot.
        Silently skips any indices that no longer exist (e.g. column set changed).
        Triggers a search pass if *any* filter value was restored.
        """
        if not state or not hasattr(self, "_col_filter_vars"):
            return
        any_restored = False
        for idx, entry in state.items():
            var_or_pair = self._col_filter_vars.get(idx)
            if var_or_pair is None:
                continue
            try:
                kind = entry[0]
                if kind == "date" and isinstance(var_or_pair, tuple):
                    _, v_from, v_to = entry
                    if v_from or v_to:
                        var_or_pair[0].set(v_from)
                        var_or_pair[1].set(v_to)
                        any_restored = True
                elif kind == "single" and not isinstance(var_or_pair, tuple):
                    val = entry[1]
                    if val:
                        var_or_pair.set(val)
                        any_restored = True
            except Exception:
                pass
        if any_restored:
            # Defer to allow new widgets to finish rendering before filtering
            self.after(120, self._apply_grid_search)

    def _create_inline_filters(self, cols):
        """
        Build a scroll-synced row of per-column filter widgets placed
        immediately above the Treeview header.

        Widget types per column:
          • Categorical  - readonly Combobox (exact match, unique values from data)
          • Date         - two compact Entry widgets (from / to, ISO format)
          • Numeric      - single Entry; prefix '>=' or '<=' supported
          • Text (default) - Entry, substring / multi-word match

        Visual feedback:
          • Active filters are highlighted with an amber border
          • A ⊘ clear-all button sits at the far right of the bar

        Scroll-sync:
          • Filter canvas mirrors the Treeview's horizontal scroll without
            relying on brittle Tcl-string scrollcommand intercepts.
        """
        # ── Destroy previous filter bar if it exists ──────────────────────
        if hasattr(self, "_filter_canvas") and self._filter_canvas.winfo_exists():
            try:
                self._filter_canvas.destroy()
            except Exception:
                pass

        # ── Container bar ─────────────────────────────────────────────────
        # Height=30 gives enough room for Combobox drop-button + border glow
        FILTER_H   = 30
        BAR_BG     = "#161B22"
        ACTIVE_CLR = ACCENT_AMBER   # amber border when a filter is active

        self._filter_canvas = tk.Canvas(
            self._records_table_frame,
            height=FILTER_H, bg=BAR_BG,
            highlightthickness=0
        )
        self._filter_canvas.pack(side=tk.TOP, fill=tk.X)

        self._filter_inner = tk.Frame(self._filter_canvas, bg=BAR_BG)
        self._filter_canvas_win = self._filter_canvas.create_window(
            (0, 0), window=self._filter_inner, anchor=tk.NW
        )

        # ── State storage ─────────────────────────────────────────────────
        self._col_filter_vars    = {}   # idx -> StringVar  (or (StringVar, StringVar) for date)
        self._col_filter_widgets = {}   # idx -> widget  (or (w_from, w_to) for date)
        self._col_filter_types   = {}   # idx -> 'categorical'|'date'|'numeric'|'text'

        # ── Debounce helper ───────────────────────────────────────────────
        self._inline_search_debounce_id = None

        def _schedule_search(event=None):
            if self._inline_search_debounce_id:
                self.after_cancel(self._inline_search_debounce_id)
            self._inline_search_debounce_id = self.after(300, self._apply_grid_search)


        def _highlight_tk_widget(var, widget):
            """
            Amber border glow for native tk widgets (Entry) that support
            `highlightbackground` / `highlightthickness`.
            """
            def _cb(*_):
                try:
                    active = bool(var.get().strip())
                    widget.config(
                        highlightbackground=ACTIVE_CLR if active else BORDER_COLOR,
                        highlightthickness=1
                    )
                except Exception:
                    pass
            var.trace_add("write", _cb)

        def _highlight_frame_border(var, frame):
            """
            Amber border glow for frame-wrapped widgets (ttk.Combobox, date pairs).
            Achieved by changing the Frame's highlightbackground.
            """
            def _cb(*_):
                try:
                    active = bool(str(var.get()).strip())
                    frame.config(
                        highlightbackground=ACTIVE_CLR if active else BORDER_COLOR,
                        highlightthickness=1
                    )
                except Exception:
                    pass
            var.trace_add("write", _cb)

        def _make_numeric_tooltip(widget, cid):
            """
            Attaches a one-line tooltip popup to a numeric filter Entry showing
            the supported comparison-operator syntax.
            """
            tip_text = f"{cid}: plain value = substring  |  >=N  <=N  >N  <N"
            tip_win  = [None]

            def _show(ev=None):
                if tip_win[0]: return
                tw = tk.Toplevel(widget)
                tw.wm_overrideredirect(True)
                tw.attributes("-topmost", True)
                tw.geometry(f"+{ev.x_root + 12}+{ev.y_root - 28}")
                tk.Label(
                    tw, text=tip_text,
                    font=("Space Mono", 8), bg="#1E2533", fg=ACCENT_AMBER,
                    padx=3, pady=1).pack()
                tip_win[0] = tw

            def _hide(ev=None):
                if tip_win[0]:
                    try: tip_win[0].destroy()
                    except Exception: pass
                    tip_win[0] = None

            widget.bind("<Enter>", _show)
            widget.bind("<Leave>", _hide)
            widget.bind("<FocusOut>", _hide)

        # ── Build one widget per column ───────────────────────────────────
        dataset = getattr(self, "_all_table_rows", [])

        for idx, c in enumerate(cols):
            cid = c.get("text", str(c)) if isinstance(c, dict) else str(c)

            # ── Categorical ───────────────────────────────────────────────
            if cid in self._CATEGORICAL_COLS:
                self._col_filter_types[idx] = "categorical"
                unique_vals = sorted({
                    str(row[idx]).strip()
                    for row in dataset
                    if idx < len(row) and str(row[idx]).strip() not in ("", "None")
                })
                var = tk.StringVar()
                self._col_filter_vars[idx] = var

                # Wrap in a bordered Frame so we can light it up amber
                wrap = tk.Frame(
                    self._filter_inner, bg=BAR_BG,
                    highlightthickness=1, highlightbackground=BORDER_COLOR
                )
                e = ttk.Combobox(
                    wrap, textvariable=var,
                    values=[""] + unique_vals,
                    font=("Space Mono", 9), state="normal"
                )
                # Forced-clipping placement
                e.place(relx=0, rely=0, relwidth=1, relheight=1)

                e.bind("<<ComboboxSelected>>", lambda ev, i=idx, c=cid: self._on_inline_categorical_selected(ev, i, c))
                # Trigger search on any key release for immediate feedback
                def _on_cat_key(ev, v=var):
                    self._apply_grid_search()
                e.bind("<KeyRelease>", _on_cat_key)
                _highlight_frame_border(var, wrap)
                # Store the wrapper frame as the placed widget
                self._col_filter_widgets[idx] = wrap

            # ── Date header filter (Hybrid Text + Calendar Picker) ────────
            elif cid in self._DATE_COLS:
                self._col_filter_types[idx] = "date"
                var = tk.StringVar()
                self._col_filter_vars[idx] = var

                wrap = tk.Frame(self._filter_inner, bg="#1E2533", highlightthickness=1, highlightbackground=BORDER_COLOR)
                
                e = tk.Entry(
                    wrap, textvariable=var,
                    font=("Space Mono", 9), bg="#1E2533", fg=TEXT_HIGH,
                    insertbackground=ACCENT_BLUE, relief="flat"
                )
                
                def _picker_for_header(v=var):
                    from ttkbootstrap.dialogs import DatePickerDialog
                    dlg = DatePickerDialog(parent=self, title="Pick Date", bootstyle=INFO)
                    dlg.show()
                    if dlg.date:
                        v.set(dlg.date.strftime("%Y-%m-%d"))

                btn = tk.Button(
                    wrap, text="📅", font=("Space Mono", 8),
                    bg="#1E2533", fg=TEXT_MUTED, activebackground="#2D3748", 
                    activeforeground=TEXT_HIGH, relief="flat", bd=0, 
                    cursor="hand2", command=_picker_for_header
                )
                
                e.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 1))
                btn.pack(side=tk.RIGHT, fill=tk.Y, padx=(1, 1))

                # Logic sync
                e.bind("<KeyRelease>", lambda ev: _schedule_search())
                var.trace_add("write", lambda *_: _schedule_search())
                _highlight_frame_border(var, wrap)
                
                self._col_filter_widgets[idx] = wrap

            # ── Numeric ───────────────────────────────────────────────────
            elif cid in self._NUMERIC_COLS:
                self._col_filter_types[idx] = "numeric"
                var = tk.StringVar()
                self._col_filter_vars[idx] = var

                e = tk.Entry(
                    self._filter_inner, textvariable=var,
                    font=("Space Mono", 9), bg="#1E2533", fg=TEXT_HIGH,
                    insertbackground=ACCENT_BLUE, relief="flat",
                    highlightthickness=1, highlightbackground=BORDER_COLOR
                )
                e.bind("<KeyRelease>", _schedule_search)
                _highlight_tk_widget(var, e)
                _make_numeric_tooltip(e, cid)
                self._col_filter_widgets[idx] = e

            # ── Plain text (default) ──────────────────────────────────────
            else:
                self._col_filter_types[idx] = "text"
                var = tk.StringVar()
                self._col_filter_vars[idx] = var

                e = tk.Entry(
                    self._filter_inner, textvariable=var,
                    font=("Space Mono", 9), bg="#1E2533", fg=TEXT_HIGH,
                    insertbackground=ACCENT_BLUE, relief="flat",
                    highlightthickness=1, highlightbackground=BORDER_COLOR
                )
                e.place(x=0, y=0, width=1, height=1) # Initial dummy placement, sync_filter_widths will override

                e.bind("<KeyRelease>", _schedule_search)
                _highlight_tk_widget(var, e)
                self._col_filter_widgets[idx] = e

        # ── Clear-all button (fixed, right edge) ──────────────────────────
        self._filter_clear_btn = tk.Label(
            self._filter_canvas, text=" ⊘ ",
            font=("Space Mono", 9, "bold"),
            bg="#1E2533", fg=TEXT_MUTED,
            cursor="hand2"
        )
        self._filter_canvas.create_window(
            (0, 0), window=self._filter_clear_btn, anchor=tk.NE, tags="clear_btn"
        )
        self._filter_clear_btn.bind("<Button-1>", lambda e: self._clear_inline_filters())
        self._filter_clear_btn.bind("<Enter>",   lambda e: self._filter_clear_btn.config(fg=DANGER_ROSE))
        self._filter_clear_btn.bind("<Leave>",   lambda e: self._filter_clear_btn.config(fg=TEXT_MUTED))

        # ── Width sync ────────────────────────────────────────────────────
        def _sync_filter_widths(event=None):
            """Lay every filter widget at the exact x-offset of its column."""
            if not hasattr(self, "_filter_canvas"):
                return
            try:
                if not self._filter_canvas.winfo_exists():
                    return
            except Exception:
                return

            table = getattr(self, "_records_table", None)
            if table is None:
                return

            try:
                view = table.view
                display_cols = view["displaycolumns"]
                # displaycolumns == "#all" (str) or ("#all",) (tuple) → all columns
                if display_cols in ("#all", ("#all",)):
                    display_cols = list(view["columns"])
                all_cols = list(view["columns"])

                # Calibration: Get the actual X-offset of the treeview widget within the Tableview container.
                # This accounts for any internal padding/margins in the ttkbootstrap Tableview layout.
                tree_x = view.winfo_x()
                # Most themes have a 1-2px border/indent on the first column header
                cal_offset = tree_x + 1 

                total_w = 0
                for cid in display_cols:
                    col_w = view.column(cid, "width")
                    try:
                        true_idx = all_cols.index(cid)
                        widget = self._col_filter_widgets.get(true_idx)
                        if widget and widget.winfo_exists():
                            # We place the widget relative to the accumulated column widths, 
                            # plus our calibration offset to match the Treeview headers perfectly.
                            widget.place(x=total_w + cal_offset, y=1, width=col_w, height=FILTER_H - 2)
                    except (ValueError, tk.TclError):
                        pass
                    total_w += col_w

                canvas_w = self._filter_canvas.winfo_width()
                # Ensure scrollregion is wide enough for the calibrated end of the headers
                self._filter_canvas.configure(scrollregion=(0, 0, total_w + cal_offset + 50, FILTER_H))
                
                # Size the inner Frame window to the full virtual width
                try:
                    self._filter_canvas.itemconfigure(
                        self._filter_canvas_win,
                        width=total_w + cal_offset + 50, height=FILTER_H
                    )
                except Exception:
                    pass
                # Keep clear button anchored to visible right edge
                self._filter_canvas.coords("clear_btn", canvas_w, 0)
            except Exception:
                pass

        # Bind resize / drag events that change column widths
        self._filter_canvas.bind("<Configure>", _sync_filter_widths)
        try:
            self._records_table.view.bind("<Configure>",      _sync_filter_widths, add="+")
            self._records_table.view.bind("<B1-Motion>",      _sync_filter_widths, add="+")
            self._records_table.view.bind("<ButtonRelease-1>", _sync_filter_widths, add="+")
        except Exception:
            pass

        # ── Horizontal scroll-sync (robust) ──────────────────────────────
        # We intercept the Treeview's xscroll to also move the filter canvas.
        # Works regardless of whether xscrollcommand is a Tcl string or Python callable.
        def _intercept_xscroll(lo, hi):
            """Called by tkinter whenever the Treeview horizontal scroll moves."""
            try:
                # Forward to the original scroll handler (e.g., a Scrollbar)
                orig = getattr(self, "_orig_tree_xscroll", None)
                if orig:
                    orig(lo, hi)
                # Mirror position to the filter canvas
                if hasattr(self, "_filter_canvas") and self._filter_canvas.winfo_exists():
                    self._filter_canvas.xview_moveto(lo)
            except Exception:
                pass

        try:
            raw_cmd = self._records_table.view.cget("xscrollcommand")
            # Guard: if the view already has OUR interceptor installed (re-run),
            # restore the true original first so we never chain-wrap it.
            true_orig = getattr(self, "_true_tree_xscroll", None)
            if true_orig is None:
                # First time – capture the real scrollbar command
                if isinstance(raw_cmd, str) and raw_cmd:
                    # Tcl command string (e.g. ".!scrollbar set").
                    # Unpack with * so tk.call receives individual args, not a list.
                    _parts = raw_cmd.split()
                    true_orig = lambda lo, hi: self._records_table.view.tk.call(
                        *_parts, str(lo), str(hi)
                    )
                elif callable(raw_cmd):
                    true_orig = raw_cmd
                else:
                    true_orig = None
                self._true_tree_xscroll = true_orig
            self._orig_tree_xscroll = true_orig
            self._records_table.view.configure(xscrollcommand=_intercept_xscroll)
        except Exception:
            pass

        # Initial layout pass after Tk has rendered the table
        self.after(80, _sync_filter_widths)
        self.after(300, _sync_filter_widths)   # Second pass catches autofit settling

    def _clear_inline_filters(self):
        """Resets all per-column inline filter widgets to an empty state and re-applies search."""
        if not hasattr(self, "_col_filter_vars"):
            return
        for idx, var_or_pair in self._col_filter_vars.items():
            try:
                if isinstance(var_or_pair, tuple):
                    # Date range pair
                    var_or_pair[0].set("")
                    var_or_pair[1].set("")
                else:
                    var_or_pair.set("")
            except Exception:
                pass
        self._apply_grid_search()

    def _on_inline_categorical_selected(self, event, col_idx, col_id):
        """
        Handles categorical filter selection in the grid header.
        Highly interactive: implements cascading logic (e.g. Dept -> Employee).
        """
        self._apply_grid_search()
        
        # Cascading Logic: If Department is filtered, narrow down the Employee list
        if col_id == "DEPT":
            try:
                dept_val = self._col_filter_vars[col_idx].get().strip()
                
                # Find Employee column index
                emp_idx = None
                for i, c in enumerate(getattr(self, "_all_table_cols", [])):
                    if c == "EMPLOYEE":
                        emp_idx = i; break
                
                if emp_idx is not None and emp_idx in self._col_filter_widgets:
                    if not dept_val:
                        # Restore full list of employees
                        new_vals = sorted({
                            str(row[emp_idx]).strip() 
                            for row in self._all_table_rows 
                            if len(row) > emp_idx and str(row[emp_idx]).strip() != ""
                        })
                    else:
                        # Filter employee list by selected department
                        new_vals = sorted({
                            str(row[emp_idx]).strip() 
                            for row in self._all_table_rows 
                            if len(row) > max(emp_idx, col_idx) 
                            and str(row[col_idx]).strip() == dept_val 
                            and str(row[emp_idx]).strip() not in ("", "\u2014")
                        })
                    
                    wrap = self._col_filter_widgets[emp_idx]
                    from tkinter import ttk
                    for child in wrap.winfo_children():
                        if isinstance(child, ttk.Combobox):
                            child.configure(values=[""] + new_vals)
                            break
            except Exception:
                pass

    def _apply_grid_search(self):
        """Triggers a debounced refresh of the table data based on inline filters."""
        if self._after_grid_id:
            self.after_cancel(self._after_grid_id)
        self._after_grid_id = self.after(300, self._apply_grid_search_immediate)

    def _apply_grid_search_immediate(self):
        """
        Actually performs the filtering logic:
          1. Global full-row keyword search (the search bar above the table)
          2. Per-column inline filters with type-aware matching:
               • categorical → exact case-insensitive match
               • date        → ISO date range (from ≤ date ≤ to)
               • numeric     → supports prefix modifiers >=, <=, >, <  (default: >=)
               • text        → multi-word substring (all words must appear)
        """
        if self._after_grid_id:
             self.after_cancel(self._after_grid_id)
             self._after_grid_id = None
             
        if not hasattr(self, "_all_table_rows") or not self._all_table_rows:
            return
        query = self._grid_search_var.get().strip()
        if query == "Search records...":
            query = ""

        if not self._all_table_rows or not getattr(self, "_all_table_cols", None):
            return

        # ── Build active column filter list ──────────────────────────────
        # Each entry: (col_idx, filter_type, value_or_pair)
        active_col_filters = []
        if hasattr(self, "_col_filter_vars"):
            for idx, var_or_pair in self._col_filter_vars.items():
                if not isinstance(idx, int):
                    continue
                ftype = self._col_filter_types.get(idx, "text")

                if ftype == "date":
                    if isinstance(var_or_pair, tuple):
                        v_from = var_or_pair[0].get().strip()
                        v_to   = var_or_pair[1].get().strip()
                        if v_from or v_to:
                            active_col_filters.append((idx, "date", (v_from, v_to)))
                    else:
                        val = var_or_pair.get().strip()
                        if val:
                            active_col_filters.append((idx, "date", val))
                else:
                    val = var_or_pair.get().strip()
                    if val:
                        active_col_filters.append((idx, ftype, val))

        terms = query.lower().split() if query else []

        # ── Filter rows ───────────────────────────────────────────────────
        if not terms and not active_col_filters:
            filtered = self._all_table_rows
            if hasattr(self, "_search_results_lbl") and self._search_results_lbl.winfo_exists():
                self._search_results_lbl.config(text="")
        else:
            filtered = []
            import re as _re

            for row in self._all_table_rows:
                # 1. Global keyword pass (all terms must appear anywhere in row)
                if terms:
                    row_text = " ".join(str(v).lower() for v in row)
                    if not all(t in row_text for t in terms):
                        continue

                # 2. Per-column filter pass
                passed = True
                for idx, ftype, value in active_col_filters:
                    try:
                        cell_raw = str(row[idx]).strip()
                        cell_lo  = cell_raw.lower()

                        if ftype == "categorical":
                            # Use substring match (looser) instead of exact check to allow typing and filtering
                            if value.lower() not in cell_lo:
                                passed = False; break

                        elif ftype == "date":
                            # Primary: Substring match (Very Simple & User-Friendly for typing e.g. "13-4-26")
                            if value.lower() in cell_lo:
                                passed = True # Immediate pass if substring matches
                            else:
                                # Secondary: Robust ISO matching (for Calendar picker or ISO typing)
                                cell_iso = ""
                                try:
                                    # Try to match DD-MM-YY or DD-MM-YYYY anywhere (handles "Mon. 13-04-26")
                                    d_match = _re.search(r"(\d{2}-\d{2}-\d{2}(?:\d{2})?)", cell_raw)
                                    if d_match:
                                        raw_match = d_match.group(1)
                                        if len(raw_match) == 8: # DD-MM-YY
                                            cell_iso = datetime.strptime(raw_match, "%d-%m-%y").strftime("%Y-%m-%d")
                                        else: # DD-MM-YYYY
                                            cell_iso = datetime.strptime(raw_match, "%d-%m-%Y").strftime("%Y-%m-%d")
                                    else:
                                        if len(cell_raw) >= 10:
                                            test_val = cell_raw[:10]
                                            if test_val[4] == '-' and test_val[7] == '-':
                                                cell_iso = test_val
                                except Exception:
                                    pass

                                if isinstance(value, tuple):
                                    # Range filter (Toolbar)
                                    v_from, v_to = value
                                    if v_from and cell_iso < v_from:
                                        passed = False; break
                                    if v_to and cell_iso > v_to:
                                        passed = False; break
                                else:
                                    # Exact ISO match or check empty
                                    if value and value != cell_iso:
                                        passed = False; break

                        elif ftype == "numeric":
                            # Supported prefixes: >=, <=, >, <  (default: substring then numeric >=)
                            val_str = value.strip()
                            prefix  = ""
                            num_str = val_str
                            for pfx in (">=", "<=", ">", "<"):
                                if val_str.startswith(pfx):
                                    prefix  = pfx
                                    num_str = val_str[len(pfx):].strip()
                                    break

                            # Attempt numeric comparison
                            if num_str:
                                try:
                                    num_val  = float(num_str)
                                    # Extract numeric part from cell (strip units, colons, etc.)
                                    cell_num_str = _re.sub(r"[^0-9.\-]", "", cell_raw.replace(":", "."))
                                    cell_num = float(cell_num_str) if cell_num_str else None

                                    if cell_num is None:
                                        # Non-numeric cell never satisfies numeric filter
                                        passed = False; break

                                    if prefix == ">=":
                                        if not (cell_num >= num_val): passed = False; break
                                    elif prefix == "<=":
                                        if not (cell_num <= num_val): passed = False; break
                                    elif prefix == ">":
                                        if not (cell_num > num_val):  passed = False; break
                                    elif prefix == "<":
                                        if not (cell_num < num_val):  passed = False; break
                                    else:
                                        # No prefix → substring match on the raw cell
                                        if val_str.lower() not in cell_lo:
                                            passed = False; break
                                except ValueError:
                                    # num_str isn't a float → fall back to substring
                                    if val_str.lower() not in cell_lo:
                                        passed = False; break

                        else:  # text
                            # All space-separated terms must appear in the cell
                            words = value.lower().split()
                            if not all(w in cell_lo for w in words):
                                passed = False; break

                    except (IndexError, Exception):
                        passed = False; break

                if passed:
                    filtered.append(row)

            # Results counter feedback
            total = len(self._all_table_rows)
            found = len(filtered)
            if hasattr(self, "_search_results_lbl") and self._search_results_lbl.winfo_exists():
                if found == total:
                    self._search_results_lbl.config(text="", fg=TEXT_MUTED)
                elif found == 0:
                    self._search_results_lbl.config(text="No matches", fg=DANGER_ROSE)
                else:
                    self._search_results_lbl.config(
                        text=f"{found} of {total} records", fg=ACCENT_BLUE
                    )

        if not getattr(self, "_records_table", None):
            return
            
        if not getattr(self._records_table, "view", None) or not self._records_table.view.winfo_exists():
            return

        try:
            self._records_table.delete_rows()
            self._records_table.insert_rows("end", filtered)
            self._records_table.goto_first_page()
            self._records_table.load_table_data()

            self._current_total_rows = len(filtered)
            if hasattr(self, "_records_count_label") and self._records_count_label.winfo_exists():
                self._records_count_label.configure(
                    text=tr("total_rows", count=len(filtered))
                )
            self._apply_row_tags()
            self._update_nav_lbl()
        except Exception as e:
            logger.error(f"Grid search error: {e}")

    def _update_nav_lbl(self):
        """Updates the custom navigation label to track pagination progress."""
        try:
            # Tableview uses internal tk.Variables for page tracking
            # We must handle cases where variables might not yet be initialized
            p_idx_var = getattr(self._records_table, "_pageindex", None)
            p_limit_var = getattr(self._records_table, "_pagelimit", None)
            
            # Use self._pagesize if internal p_sz_var is not yet available
            p_sz = 50
            p_sz_var = getattr(self._records_table, "_pagesize", None)
            if p_sz_var:
                p_sz = int(p_sz_var.get() if hasattr(p_sz_var, 'get') else p_sz_var)

            # Get values safely
            current_page = 1
            if p_idx_var:
                try: current_page = (p_idx_var.get() if hasattr(p_idx_var, 'get') else int(p_idx_var)) + 1
                except: pass
            
            rows_len = getattr(self, "_current_total_rows", 0)
            total_pages = 1
            
            # Best source for total pages: the pagelimit variable if it exists
            if p_limit_var:
                try: total_pages = int(p_limit_var.get() if hasattr(p_limit_var, 'get') else p_limit_var)
                except: total_pages = max(1, (rows_len + p_sz - 1) // p_sz)
            else:
                total_pages = max(1, (rows_len + p_sz - 1) // p_sz)
            
            # Robust clamping
            current_page = max(1, min(current_page, total_pages))

            self._nav_page_lbl.config(text=f"Page {current_page} of {total_pages}")
        except Exception as e:
            logger.error(f"Error updating navigation label: {e}")
            pass


    def _populate_filter_dropdowns(self, department_name=None):
        """Fetches unique values from DB to populate the search comboboxes with autocomplete."""
        vals = self.service.get_filter_dropdown_values(department_name=department_name)
        
        self._filter_full_lists = {
            "employees": vals.get("employees", []),
            "reg_numbers": vals.get("reg_numbers", []),
            "departments": vals.get("departments", [])
        }
        
        if hasattr(self, "_cb_emp"):
            self._cb_emp.configure(values=self._filter_full_lists["employees"])
            self._cb_emp.bind("<<ComboboxSelected>>", lambda e: self._load_recent_records())

        if hasattr(self, "_cb_dept"):
            if not department_name:
                self._cb_dept.configure(values=self._filter_full_lists["departments"])
                self._cb_dept.bind("<KeyRelease>", lambda e: self._on_combobox_key(e, self._cb_dept, self._filter_full_lists["departments"]))
                self._cb_dept.bind("<ButtonPress-1>", lambda e: self._on_combobox_click(self._cb_dept, self._filter_full_lists["departments"]))

    def _on_dept_selected(self, event=None):
        """When a department is selected, filter employee dropdown."""
        dept = self._filter_dept.get().strip()
        self._filter_emp.set("")
        self._populate_filter_dropdowns(department_name=dept if dept else None)

    def _on_combobox_key(self, event, combobox, full_list):
        """Filters combobox choices dynamically as the user types."""
        # Ignore navigation and control keys
        if event.keysym in ('Up', 'Down', 'Return', 'Left', 'Right', 'Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R'):
            return
            
        typed_text = combobox.get().lower()
        if not typed_text:
            combobox.configure(values=full_list)
        else:
            filtered = [item for item in full_list if typed_text in str(item).lower()]
            combobox.configure(values=filtered)
            
        # Re-open the drop-down to show the updated filtered results
        # Use after idle to ensure tkinter has processed the value update
        combobox.after("idle", lambda: combobox.event_generate('<Down>'))
        
    def _on_combobox_click(self, combobox, full_list):
        """Restore full list if the box is empty when clicked."""
        if not combobox.get():
            combobox.configure(values=full_list)

    def _refresh_transfer_combo(self):
        machines = self.service.get_all_machines()
        self._transfer_machines = {f"{m.name} ({m.ip_address})": m.id for m in machines}
        self._transfer_combo["values"] = list(self._transfer_machines.keys())
        if self._transfer_machines:
            self._transfer_combo.current(0)

    def _on_transfer_machine_selected(self, event=None):
        pass  # Selection is read when action buttons are clicked

    def _get_selected_transfer_machine_id(self):
        key = self._transfer_machine_var.get()
        return self._transfer_machines.get(key)

    def _download_attendance(self):
        mid = self._get_selected_transfer_machine_id()
        if not mid:
            Messagebox.show_info(tr("no_machine_selected"), tr("information"))
            return
            
        # UI Setup for progress
        self._prog_frame.pack(side=tk.TOP, fill=tk.X, pady=3)
        self._progress_var.set(0)
        self._progress_pct_label.configure(text="0%", fg="#38BDF8")
        self._progress_eta_label.configure(text="Initializing sync...")
        self._task_name_label.configure(text=f"\U0001f4e5 {tr('download_data').upper()}")

        # Start shimmer animation
        self._shimmer_offset = 0
        self._shimmer_running = True
        self._shimmer_tick()

        self._transfer_status.configure(text=f"⏳ {tr('transfer_in_progress') or 'Syncing...'}", fg=ACCENT_BLUE)
        
        # Start background task via TaskManager
        self.task_manager.run_task(
            task_id="attendance_download",
            name=f"📥 {tr('download_data')}",
            target=self.service.download_attendance,
            args=(mid,),
            on_progress=self._update_progress_ui,
            on_complete=lambda res: self._finalize_sync_ui(tr('transfer_complete', count=res[0]), f"100%", raw_total=res[1]),
            on_error=lambda err: self._finalize_sync_ui(tr('transfer_failed', error=err), "Error", bootstyle=DANGER)
        )

    def _update_progress_ui(self, percent, text):
        """Canvas-based progress updates with dynamic color phasing."""
        self._progress_var.set(percent)  # triggers _on_progress_var_write -> _redraw_prog_canvas

        # Also drive the CLI inline bar
        if hasattr(self, "_update_cli_bar"):
            self._update_cli_bar(percent)

        # Split text into status and ETA
        if " - ETA:" in text:
            msg, eta = text.split(" - ETA:", 1)
            clean_msg = re.sub(r'^\d+%\s*', '', msg).strip()
            self._progress_eta_label.configure(text=f"{clean_msg} • ETA: {eta.strip()}")
        else:
            self._progress_eta_label.configure(text=text)
            
    def _set_task_name(self, name):
        """Updates the visible task name in the progress bar area."""
        self._task_name_label.configure(text=name.upper())


    def _finalize_sync_ui(self, status_msg, progress_text, bootstyle="success", raw_total=0):
        # Stop shimmer
        self._shimmer_running = False
        self._prog_canvas.itemconfigure(self._prog_shimmer_id, state="hidden")

        fg_color = SUCCESS_EMERALD if bootstyle == "success" else DANGER_ROSE if bootstyle == "danger" else ACCENT_BLUE
        self._transfer_status.configure(
            text=f"✅ {status_msg}" if bootstyle == "success" else f"❌ {status_msg}",
            fg=fg_color
        )
        final_pct = 100 if bootstyle == SUCCESS else 0
        self._progress_var.set(final_pct)  # triggers canvas redraw
        self._progress_eta_label.configure(text=progress_text)

        if bootstyle == SUCCESS:
            enriched = self.service.get_attendance_records_enriched(limit=50000)
            ui_count = len(enriched)
            self._lbl_raw_result.configure(text=tr("raw_extraction_complete", count=raw_total))
            self._lbl_ui_result.configure(text=tr("ui_representation", count=ui_count))

            # CLI bar: hold at 100% then fade to 0
            if hasattr(self, "_update_cli_bar"):
                self._update_cli_bar(100)
                self.after(3000, lambda: self._update_cli_bar(0))

        self._load_recent_records()
        # Hide progress overlay after 3 s
        def _hide_prog():
            if self.winfo_exists() and self._prog_frame.winfo_exists():
                self._prog_frame.pack_forget()
            self._progress_var.set(0)  # reset bar
        self.master.after(3000, _hide_prog)



    def _get_export_data(self):
        """Helper to get currently filtered data for export (Main Thread Only)."""
        filters = self._capture_ui_filters()
        
        punch_type = None
        if filters["punch_type_val"] == tr("check_in_type"):
            punch_type = "check_in"
        elif filters["punch_type_val"] == tr("check_out_type"):
            punch_type = "check_out"

        return self.service.get_attendance_records_enriched(
            name_filter=filters["name_filter"],
            reg_filter=filters["reg_filter"],
            dept_filter=filters["dept_filter"],
            start_date=filters["date_from"],
            end_date=filters["date_to"],
            punch_type=punch_type,
            limit=0 
        ), filters["date_from"], filters["date_to"]

    def _upload_attendance(self):
        Messagebox.show_info("Upload to machine is a placeholder for custom data push.", tr("information"))

    def _get_export_data_safe(self, filters):
        """
        Background-safe data retrieval. 
        Creates a new DB session and service instance to avoid thread conflicts.
        """
        temp_session = SessionLocal()
        try:
            temp_service = PointageService(temp_session)
            
            # Map filter values from the captured dict
            name_filter = filters.get("name_filter")
            reg_filter = filters.get("reg_filter")
            dept_filter = filters.get("dept_filter")
            date_from = filters.get("date_from")
            date_to = filters.get("date_to")
            punch_type_val = filters.get("punch_type_val")
            
            punch_type = None
            if punch_type_val == tr("check_in_type"):
                punch_type = "check_in"
            elif punch_type_val == tr("check_out_type"):
                punch_type = "check_out"

            data = temp_service.get_attendance_records_enriched(
                name_filter=name_filter,
                reg_filter=reg_filter,
                dept_filter=dept_filter,
                start_date=date_from,
                end_date=date_to,
                punch_type=punch_type,
                limit=0 
            )
            return data, date_from, date_to
        finally:
            temp_session.close()

    def _capture_ui_filters(self):
        """Captures all filter values from widgets (MAIN THREAD ONLY)."""
        name_filter = getattr(self, "_filter_emp", None) and self._filter_emp.get().strip() or None
        reg_filter = None
        
        if name_filter:
            import re
            # Match any content inside parentheses as the REG number (robust for alphanumeric)
            match = re.search(r"\(([^)]+)\)", name_filter)
            if match:
                reg_filter = match.group(1).strip()
                name_filter = None
            elif name_filter.strip().replace(" ", "").isalnum():
                # If the whole filter is alphanumeric, treat it as REG if it's not a common name
                # Actually, usually users type name first. Let's keep it safe.
                if len(name_filter) <= 10 and any(c.isdigit() for c in name_filter):
                    reg_filter = name_filter.strip()
                    name_filter = None
        
        return {
            "name_filter": name_filter,
            "reg_filter": reg_filter,
            "dept_filter": getattr(self, "_filter_dept", None) and self._filter_dept.get().strip() or None,
            "date_from": self._filter_from_de.entry.get().strip() if hasattr(self, "_filter_from_de") else None,
            "date_to": self._filter_to_de.entry.get().strip() if hasattr(self, "_filter_to_de") else None,
            "punch_type_val": getattr(self, "_filter_type", None) and self._filter_type.get().strip() or None
        }

    def _deprecated_export_logic(self):
        return None
        # The following block is deprecated and can be removed
        """Helper to get currently filtered data for export."""
        name_filter = getattr(self, "_filter_emp", None) and self._filter_emp.get().strip() or None
        reg_filter = None
        
        # Extract registration number if present in name_filter (e.g. "NAME (REG)")
        if name_filter and "(" in name_filter and ")" in name_filter:
            import re
            match = re.search(r"\(([^)]+)\)", name_filter)
            if match:
                reg_filter = match.group(1)
                name_filter = None # Use exact REG filter instead of partial name filter
        
        dept_filter = getattr(self, "_filter_dept", None) and self._filter_dept.get().strip() or None
        
        date_from = None
        if hasattr(self, "_filter_from_de") and self._filter_from_de.entry.get().strip():
            date_from = self._filter_from_de.entry.get().strip()
            
        date_to = None
        if hasattr(self, "_filter_to_de") and self._filter_to_de.entry.get().strip():
            date_to = self._filter_to_de.entry.get().strip()

        punch_type_val = getattr(self, "_filter_type", None) and self._filter_type.get().strip() or None
        punch_type = None
        if punch_type_val == tr("check_in_type"):
            punch_type = "check_in"
        elif punch_type_val == tr("check_out_type"):
            punch_type = "check_out"

        return self.service.get_attendance_records_enriched(
            name_filter=name_filter,
            reg_filter=reg_filter,
            dept_filter=dept_filter,
            start_date=date_from,
            end_date=date_to,
            punch_type=punch_type,
            limit=0 # No limit for exports
        ), date_from, date_to

    def _export_pdf_detailed(self):
        """Generates a detailed PDF report in the background."""
        try:
            from tkinter import filedialog
            from datetime import datetime

            date_from = self._filter_from_de.entry.get().strip() if hasattr(self, "_filter_from_de") else ""
            date_to = self._filter_to_de.entry.get().strip() if hasattr(self, "_filter_to_de") else ""

            if date_from and date_to and date_from != date_to:
                report_type = "period"
            else:
                report_type = "daily"

            from contragest.features.pointage.export_reports import format_date_locale
            f_label = format_date_locale(date_from, short=True) if date_from else ""
            t_label = format_date_locale(date_to, short=True) if date_to else ""

            if report_type == "daily":
                initial_name = f"Daily Detailed Attendance Report {f_label}.pdf".strip()
            else:
                range_label = f"{f_label} To {t_label}" if f_label and t_label and f_label != t_label else (f_label or t_label or datetime.now().strftime('%Y%m%d'))
                initial_name = f"Detailed Attendance Report {range_label}.pdf".strip()

            filepath = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=initial_name
            )

            if not filepath: return

            captured_filters = self._capture_ui_filters()
            self._prog_frame.pack(fill=X, padx=6, pady=(1, 6))
            self._transfer_status.configure(text=f"⏳ Preparing Detailed PDF...", fg=ACCENT_BLUE)

            self.task_manager.run_task(
                task_id="export_pdf_detailed",
                name=f"📄 Detailed PDF {report_type.capitalize()} Export",
                target=self._export_report_bg,
                args=(filepath, report_type, captured_filters, "pdf_detailed"),
                on_progress=self._update_progress_ui,
                on_complete=lambda res: self._finalize_export_ui(res, report_type, "pdf"),
                on_error=lambda err: self._finalize_sync_ui(f"Detailed PDF Export failed: {err}", "Error", bootstyle=DANGER)
            )
        except Exception as e:
            Messagebox.show_error(f"Error preparing Detailed PDF Export: {e}", "Error")

    def _export_excel(self):
        """Generates an Excel report in the background."""
        try:
            from tkinter import filedialog
            from datetime import datetime

            date_from = self._filter_from_de.entry.get().strip() if hasattr(self, "_filter_from_de") else ""
            date_to = self._filter_to_de.entry.get().strip() if hasattr(self, "_filter_to_de") else ""

            if date_from and date_to and date_from != date_to:
                report_type = "period"
            else:
                report_type = "daily"

            from contragest.features.pointage.export_reports import format_date_locale
            f_label = format_date_locale(date_from, short=True) if date_from else ""
            t_label = format_date_locale(date_to, short=True) if date_to else ""

            initial_name = f"Attendance Report {f_label}.xlsx" if report_type == "daily" else f"Attendance Report {f_label} To {t_label}.xlsx"

            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=initial_name
            )

            if not filepath: return

            captured_filters = self._capture_ui_filters()
            
            # UI Setup for progress
            self._prog_frame.pack(side=tk.TOP, fill=tk.X, pady=3)

            self._progress_var.set(0)
            self._progress_pct_label.configure(text="0%")
            self._progress_eta_label.configure(text="Preparing data...")

            self._transfer_status.configure(text=f"⏳ Preparing Excel...", fg=ACCENT_BLUE)


            self.task_manager.run_task(
                task_id="export_excel",
                name=f"📊 Excel {report_type.capitalize()} Export",
                target=self._export_report_bg,
                args=(filepath, report_type, captured_filters, "excel"),
                on_progress=self._update_progress_ui,
                on_complete=lambda res: self._finalize_export_ui(res, report_type, "excel"),
                on_error=lambda err: self._finalize_sync_ui(f"Excel Export failed: {err}", "Error", bootstyle=DANGER)
            )
        except Exception as e:
            Messagebox.show_error(f"Error preparing Excel Export: {e}", "Error")

    def _export_pdf(self):
        """Generates a standard PDF report in the background."""
        try:
            from tkinter import filedialog
            from datetime import datetime

            date_from = self._filter_from_de.entry.get().strip() if hasattr(self, "_filter_from_de") else ""
            date_to = self._filter_to_de.entry.get().strip() if hasattr(self, "_filter_to_de") else ""

            if date_from and date_to and date_from != date_to:
                report_type = "period"
            else:
                report_type = "daily"

            from contragest.features.pointage.export_reports import format_date_locale
            f_label = format_date_locale(date_from, short=True) if date_from else ""
            t_label = format_date_locale(date_to, short=True) if date_to else ""

            initial_name = f"Attendance Report {f_label}.pdf" if report_type == "daily" else f"Attendance Report {f_label} To {t_label}.pdf"

            filepath = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=initial_name
            )

            if not filepath: return

            captured_filters = self._capture_ui_filters()
            
            # UI Setup for progress
            self._prog_frame.pack(side=tk.TOP, fill=tk.X, pady=3)

            self._progress_var.set(0)
            self._progress_pct_label.configure(text="0%")
            self._progress_eta_label.configure(text="Preparing data...")

            self._transfer_status.configure(text=f"⏳ Preparing PDF...", fg=ACCENT_BLUE)


            self.task_manager.run_task(
                task_id="export_pdf",
                name=f"📄 PDF {report_type.capitalize()} Export",
                target=self._export_report_bg,
                args=(filepath, report_type, captured_filters, "pdf"),
                on_progress=self._update_progress_ui,
                on_complete=lambda res: self._finalize_export_ui(res, report_type, "pdf"),
                on_error=lambda err: self._finalize_sync_ui(f"PDF Export failed: {err}", "Error", bootstyle=DANGER)
            )
        except Exception as e:
            Messagebox.show_error(f"Error preparing PDF Export: {e}", "Error")

    def _export_report_bg(self, filepath, report_type, captured_filters, format="pdf", progress_callback=None):
        """Asynchronous report generation helper (Background Thread)."""
        if progress_callback: progress_callback(10, 100, "Retrieving data...")
        data, from_date, to_date = self._get_export_data_safe(captured_filters)
        
        if not data: return False, "No data found matching current filters."

        if progress_callback: progress_callback(50, 100, f"Formatting {format.upper()}...")
        try:
            if format == "pdf":
                from contragest.features.pointage.export_reports import generate_attendance_pdf
                generate_attendance_pdf(data, filepath, from_date, to_date)
            elif format == "pdf_detailed":
                if report_type == "period":
                    from contragest.features.pointage.export_reports import generate_detailed_attendance_pdf
                    generate_detailed_attendance_pdf(data, filepath, from_date, to_date)
                else:
                    from contragest.features.pointage.export_reports import generate_daily_detailed_attendance_pdf
                    generate_daily_detailed_attendance_pdf(data, filepath, from_date, to_date)
            else: # excel
                if report_type == "period":
                    from contragest.features.pointage.export_reports import generate_attendance_excel
                    generate_attendance_excel(data, filepath, from_date, to_date)
                else:
                    from contragest.features.pointage.export_reports import generate_daily_attendance_excel
                    generate_daily_attendance_excel(data, filepath, from_date, to_date)
            return True, filepath
        except PermissionError:
            return False, "Permission Denied: The file is currently open elsewhere."
        except Exception as e:
            logger.error(f"Export Error: {e}")
            return False, str(e)

    def _finalize_export_ui(self, result, report_type, format):
        """Finalizes the UI after an export task completes."""
        success, info = result
        if success:
            self._transfer_status.configure(text=f"✅ {format.upper()} Exported: {os.path.basename(info)}", fg=SUCCESS_EMERALD)
            Messagebox.show_info(f"{format.upper()} {report_type} report generated successfully.", "Success")
        else:
            self._transfer_status.configure(text=f"❌ Export failed: {info}", fg=DANGER_ROSE)
            Messagebox.show_error(f"Failed to generate {format.upper()}:\n{info}", "Error")
        
        self.after(4000, lambda: self._safe_pack_forget("_prog_frame"))



    def _on_save_records(self):
        """Callback to save currently filtered records to the DailyAttendance table."""
        try:
            data, from_date, to_date = self._get_export_data()
            if not data:
                Messagebox.show_info(tr("no_records_to_save"), tr("save_records"))
                return
            
            # Confirm with user
            ans = Messagebox.show_question(
                f"You are about to save/update {len(data)} attendance records to the database.\nProceed?",
                "Confirm Save",
                buttons=["No:secondary", "Yes:primary"]
            )
            if ans != "Yes": return
                
            self._prog_frame.pack(fill=X, padx=6, pady=(1, 6))
            self._transfer_status.configure(text="⏳ Saving records to DB...", fg=ACCENT_BLUE)
            
            self.task_manager.run_task(
                task_id="save_attendance_records",
                name=f"💾 Saving {len(data)} records",
                target=self.service.sync_attendance_to_db,
                args=(data,),
                on_progress=self._update_progress_ui,
                on_complete=lambda res: self._finalize_sync_ui(res[1], "100%", bootstyle=SUCCESS if res[0] else DANGER),
                on_error=lambda err: self._finalize_sync_ui(f"Save failed: {err}", "Error", bootstyle=DANGER)
            )
        except Exception as e:
            Messagebox.show_error(f"Error during save prep: {e}", "Error")

    def _load_recent_records(self):
        """Loads attendance records based on the current UI filters asynchronously."""
        name_filter = getattr(self, "_filter_emp", None) and self._filter_emp.get().strip() or None
        reg_filter = None
        
        # Extract registration number if present in name_filter (e.g. "NAME (REG)")
        if name_filter and "(" in name_filter and ")" in name_filter:
            import re
            match = re.search(r"\(([^)]+)\)", name_filter)
            if match:
                reg_filter = match.group(1)
                name_filter = None 
        
        def _clean(s, is_time=False):
            if s is None or s == "" or s == "None":
                return "-"
            return s
        
        dept_filter = getattr(self, "_filter_dept", None) and self._filter_dept.get().strip() or None
        
        date_from = self._filter_from_de.entry.get().strip() if hasattr(self, "_filter_from_de") else None
        date_to = self._filter_to_de.entry.get().strip() if hasattr(self, "_filter_to_de") else None

        # Date Validation
        if date_from and date_to:
            try:
                from datetime import datetime
                if datetime.strptime(date_to, "%Y-%m-%d") < datetime.strptime(date_from, "%Y-%m-%d"):
                    Messagebox.show_warning("The 'To Date' cannot be earlier than the 'From Date'.", "Invalid Date Range")
                    return
            except: pass

        punch_type_val = getattr(self, "_filter_type", None) and self._filter_type.get().strip() or None
        punch_type = "check_in" if punch_type_val == tr("check_in_type") else ("check_out" if punch_type_val == tr("check_out_type") else None)

        if hasattr(self, "_loading_records") and self._loading_records:
            return
        self._loading_records = True

        self._prog_frame.pack(fill=X, padx=6, pady=(1, 6))
        self._transfer_status.configure(text="🔍 Searching records...", fg=ACCENT_BLUE)

        self.task_manager.run_task(
            task_id="fetch_records",
            name="🔍 Attendance Search",
            target=self._fetch_records_bg,
            args=(name_filter, reg_filter, dept_filter, date_from, date_to, punch_type),
            on_progress=self._update_progress_ui,
            on_complete=self._finalize_fetch_records,
            on_error=self._on_fetch_error
        )

    def _fetch_records_bg(self, name_filter, reg_filter, dept_filter, date_from, date_to, punch_type, progress_callback=None):
        """Worker thread for background data retrieval."""
        if progress_callback: progress_callback(20, 100, "Querying database...")
        try:
            records = self.service.get_attendance_records_enriched(
                name_filter=name_filter, reg_filter=reg_filter, dept_filter=dept_filter,
                start_date=date_from, end_date=date_to, punch_type=punch_type, limit=50000
            )

            cols = ["DATE", "DEPT", "REG", "EMPLOYEE", "ROLE", "STAT", "SCHED", "IN 1", "OUT 1", "IN 2", "OUT 2", "ATT.", "WORK", "DIFF", "NOTE", "MACH.", "SYNC"]
            
            def _clean(val, is_time=False):
                s = str(val).strip() if val is not None else ""
                return "-" if (not s or s in ["None", "NoneType", "-", "--", "---", "False", "0"] or (is_time and s == "00:00:00")) else s

            if progress_callback: progress_callback(60, 100, f"Processing {len(records)} entries...")
            rows = [tuple(_clean(r.get(k.lower().replace(" ", "_").replace(".", "").replace("1", "").replace("2", "").strip()), is_time=("IN" in k or "OUT" in k or "TIME" in k)) for k in cols) for r in records]
            
            # Correction for mapping (the above list comprehension is a bit risky, let's do it explicitly)
            rows = []
            for r in records:
                rows.append((
                    _clean(r.get("date")), _clean(r.get("department")), _clean(r.get("reg_number")), 
                    _clean(r.get("employee")), _clean(r.get("role_title")), _clean(r.get("status")),
                    _clean(r.get("schedule")), _clean(r.get("check_in"), True), _clean(r.get("check_out"), True),
                    _clean(r.get("check_in_2"), True), _clean(r.get("check_out_2"), True),
                    _clean(r.get("attendance_time"), True), _clean(r.get("work_time"), True),
                    _clean(r.get("difference")), _clean(r.get("note")), _clean(r.get("machine")), _clean(r.get("synced_at"))
                ))
            return cols, rows
        finally:
            # NOTE: _loading_records is NOT cleared here. It stays True until
            # _finalize_fetch_records (or _on_fetch_error) finishes updating
            # the UI, preventing a race condition where multiple successive
            # rebuilds cascade (the background thread sets False, then
            # _finalize_fetch_records starts, but _deferred_reload_records
            # fires in between and starts another fetch → 5+ Tableview rebuilds
            # → grid becomes unresponsive with item='' for all clicks).
            pass

    def _finalize_fetch_records(self, result):
        """Updates UI after data load."""
        try:
            cols, rows = result
            self._update_records_table_ui(cols, rows)
            if hasattr(self, "_records_meta_lbl"):
                self._records_meta_lbl.configure(text=f"Refreshed: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            self._transfer_status.configure(text=f"✅ Loaded {len(rows)} records.", fg=SUCCESS_EMERALD)
            self._progress_var.set(100)
            self.master.after(2000, lambda: self._safe_pack_forget("_prog_frame"))
        finally:
            self._loading_records = False




    def _deferred_reload_records(self):
        """Calls _load_recent_records with retry if a fetch is still in progress."""
        if not self.winfo_exists():
            return
        if getattr(self, "_loading_records", False):
            self.after(500, self._deferred_reload_records)
            return
        self._load_recent_records()

    def _update_records_table_ui(self, cols, rows):
        """Update the UI with fetched records (must run in main thread)."""
        # Cancel any existing periodic tag-refresh callback to avoid TclError
        # when _bind_pagination_events fires on an already-destroyed treeview.
        if hasattr(self, "_pagination_poll_id") and self._pagination_poll_id:
            try:
                self.after_cancel(self._pagination_poll_id)
            except Exception:
                pass
            self._pagination_poll_id = None

        # Clear loading label
        for w in self._records_table_frame.winfo_children():
            w.destroy()

        # Reset xscroll origin guard - the new Tableview will have a fresh scrollbar,
        # so any previously stored reference is now stale.
        self._true_tree_xscroll = None

        # --- Automatically set status to 'P' ONLY if verified Check-In exists ---
        def is_valid_time_punch(s):
            val = str(s).strip()
            # Stricter check: Valid times in this app always contain a colon (HH:MM:SS) 
            # and numeric digits. This prevents dashes or dates from being misidentified.
            if not val or val in ["", "-", "--", "---", "00:00:00", "None", "NoneType", "0"]:
                return False
            return ":" in val and any(c.isdigit() for c in val)

        # Global Style adjustment for better readability (distinct rows)
        style = ttk.Style()
        style.configure("Treeview", rowheight=28) # Higher rows for better parsing

        processed_rows = []
        for r in rows:
            r_list = list(r)
            if len(r_list) > 13:
                in1, in2 = r_list[7], r_list[9]
                out1, out2 = r_list[8], r_list[10]
                status = str(r_list[5]).strip()
                
                has_punch = (
                    is_valid_time_punch(in1) or 
                    is_valid_time_punch(in2) or 
                    is_valid_time_punch(out1) or 
                    is_valid_time_punch(out2) or
                    str(r_list[2]).strip() == "728"
                )

                # AUTO-DETECTION: Only fill in status if it's currently empty/default or incorrectly marked AB
                # We prioritize 'P' if any punch activity is detected, unless it's a specific leave status (RH, JF, CA, etc.)
                if has_punch and (status in ["", "-", "--", "None", "NoneType", "AB"]):
                    # Automatically identify presence if any punch activity is detected
                    r_list[5] = "P"
                # Note: We removed the 'elif status == "P": r_list[13] = "-"' block
                # to respect manual entries where an employee might be marked 'P' 
                # even without a machine punch (e.g., manual override).
                    
            processed_rows.append(tuple(r_list))
        rows = processed_rows

        # ── Insert subtotal rows grouped by REG (employee) ──
        def _parse_hm(t):
            """Convert 'HH:MM' to total minutes; return None if invalid."""
            if not t or t in ("-", "None", ""):
                return None
            try:
                p = t.strip().split(":")
                return int(p[0]) * 60 + int(p[1])
            except (ValueError, IndexError):
                return None

        def _parse_diff(t):
            """Convert '[+-]HH:MM' to signed minutes; return None if invalid."""
            if not t or t in ("-", "None", ""):
                return None
            s = 1
            v = t.strip()
            if v.startswith("-"):
                s = -1; v = v[1:]
            elif v.startswith("+"):
                v = v[1:]
            try:
                p = v.split(":")
                return s * (int(p[0]) * 60 + int(p[1]))
            except (ValueError, IndexError):
                return None

        def _fmt_min(m):
            """Format minutes → 'HH:MM' (with '-' prefix for negative)."""
            if m is None:
                return "-"
            a = abs(m)
            sign = "-" if m < 0 else ""
            return f"{sign}{a // 60:02d}:{a % 60:02d}"

        # Store first group info for grand total footer later
        grand_att = grand_work = grand_diff = 0
        grand_att_n = grand_work_n = grand_diff_n = 0

        # Group records by employee (REG), then sort each employee's records
        # chronologically, so the grid reads employee-by-employee by date.
        rows = _sort_records_rows(rows)

        # Pre-compute per-employee subtotals so each employee's subtotal row
        # can be placed right after their last record in the date-sorted list.
        sub_info: dict = {}
        for r in rows:
            reg = r[2]
            if reg not in sub_info:
                sub_info[reg] = {
                    "emp": r[3], "count": 0,
                    "att_total": 0, "work_total": 0, "diff_total": 0,
                    "att_n": 0, "work_n": 0, "diff_n": 0,
                }
            info = sub_info[reg]
            info["count"] += 1
            a = _parse_hm(r[11])
            if a is not None:
                info["att_total"] += a; info["att_n"] += 1
            w = _parse_hm(r[12])
            if w is not None:
                info["work_total"] += w; info["work_n"] += 1
            d = _parse_diff(r[13])
            if d is not None:
                info["diff_total"] += d; info["diff_n"] += 1

        # Accumulate for grand total
        for info in sub_info.values():
            grand_att += info["att_total"]; grand_att_n += info["att_n"]
            grand_work += info["work_total"]; grand_work_n += info["work_n"]
            grand_diff += info["diff_total"]; grand_diff_n += info["diff_n"]

        # Build the final list: each employee's subtotal follows their last record.
        subtotal_rows = []
        placed = set()
        for i, r in enumerate(rows):
            subtotal_rows.append(r)
            reg = r[2]
            is_last_for_reg = (i == len(rows) - 1) or (rows[i + 1][2] != reg)
            if is_last_for_reg and reg not in placed:
                placed.add(reg)
                info = sub_info[reg]
                subtotal_rows.append((
                    "─" * 120,                      # DATE (wide separator)
                    "",                              # DEPT
                    reg,                             # REG
                    info["emp"],                     # EMPLOYEE
                    "",                              # ROLE
                    "",                              # STAT
                    "Subtotal",                      # SCHED (cleaner marker)
                    "",                              # IN 1
                    "",                              # OUT 1
                    "",                              # IN 2
                    "",                              # OUT 2
                    _fmt_min(info["att_total"]) if info["att_n"] else "-",
                    _fmt_min(info["work_total"]) if info["work_n"] else "-",
                    _fmt_min(info["diff_total"]) if info["diff_n"] else "-",
                    f"{info['count']} d",            # NOTE (compact)
                    "",                              # MACH.
                    "",                              # SYNC
                ))
        rows = subtotal_rows

        # Store full dataset for inline grid search
        self._all_table_rows = rows
        self._all_table_cols = cols

        # Save grand totals for footer
        self._grand_totals = {
            "ATT.": (grand_att, grand_att_n),
            "WORK.": (grand_work, grand_work_n),
            "DIFF": (grand_diff, grand_diff_n)
        }

        coldata = []
        for c in cols:
            config = self._grid_cols_config.get(c, {"width": 100, "stretch": False})
            coldata.append({"text": c, "stretch": config["stretch"], "width": config["width"]})

        self._records_table = Tableview(
            master=self._records_table_frame,
            coldata=coldata,
            rowdata=rows,
            paginated=True,
            pagesize=50, 
            searchable=False,
            bootstyle="dark",
            autofit=False,
            height=35,
        )
        # Suppress native minimal navigation frame in favour of custom navigation bar
        for c in self._records_table.winfo_children():
            if str(type(c)) == "<class 'tkinter.ttk.Frame'>" and any('label' in w.winfo_name() for w in c.winfo_children()):
                c.pack_forget()
        
        # Save any active inline filter values entered before this refresh
        _saved = self._collect_filter_state()

        self._create_inline_filters(cols)
        self._records_table.pack(fill=BOTH, expand=YES)

        # Restore filter state so the user's active filters survive the refresh
        if _saved:
            self._restore_filter_state(_saved)
        
        # Store total row count and sync custom navigation label
        self._current_total_rows = len(rows)
        self._update_nav_lbl()
        
        # Store total count for metadata updates
        self._current_total_rows = len(rows)
        
        # Modern Grid Aesthetics
        # NB: ttkbootstrap Tableview builds its Treeview with the derived
        # style "<bootstyle>.Table.Treeview", NOT "<bootstyle>.Treeview".
        # Configuring the wrong name left rows at the default 15px height,
        # which made drag & drop cell moves unreliable (release often missed
        # the razor-thin row bands). Configure the actual style the view uses.
        style = ttk.Style()
        style.configure("dark.Table.Treeview", rowheight=28, font=("Space Mono", 9), background=PANEL_BG, fieldbackground=PANEL_BG, foreground=TEXT_HIGH)
        style.configure("dark.Table.Treeview.Heading", font=("JetBrains Mono", 9, "bold"), background="#1E2533", foreground=TEXT_MUTED, borderwidth=0)
        style.map("dark.Table.Treeview", 
                  background=[("selected", ACCENT_BLUE)], 
                  foreground=[("selected", "#ffffff")],
                  focuscolor=[("focus", ACCENT_BLUE)]) 
        # Redundant layout check to ensure focus ring is gone across pages
        style.layout("Treeview.Item", [
            ('Treeview.padding', {'sticky': 'nswe', 'children': [
                ('Treeview.indicator', {'side': 'left', 'sticky': ''}),
                ('Treeview.image', {'side': 'left', 'sticky': ''}),
                ('Treeview.text', {'sticky': 'nswe'})
            ]})
        ])

        
        # Configure tags for alerts and structural states
        self._records_table.view.tag_configure("alert", foreground="white", background=DANGER_ROSE)
        self._records_table.view.tag_configure("absent", foreground=TEXT_MUTED, background="#2A2F3A") # Subtle gray for absence
        # Tag for a selected-source cell waiting to be dropped (Excel cut highlight)
        self._records_table.view.tag_configure("move_src", foreground="#000000", background="#F59E0B")  # Amber highlight

        # Configure tags for all known status codes for visual distinction
        for code, color in getattr(self, "_status_colors", {}).items():
            # Apply color to the text or background?
            # Background makes it VERY visible
            fg = "#ffffff"
            try:
                hex_c = color.lstrip('#')
                if len(hex_c) == 6:
                    r, g, b = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
                    if ((0.299 * r + 0.587 * g + 0.114 * b) / 255) > 0.6: fg = "#000000"
            except: pass
            self._records_table.view.tag_configure(f"stat_{code}", background=color, foreground=fg)

        # Subtotal row styling: professional separator
        self._records_table.view.tag_configure(
            "subtotal",
            background="#0F172A",
            foreground="#64748B",
            font=("JetBrains Mono", 8, "normal"),
        )
        
        # Apply specific column widths and alignments (Optimized Layout)
        # Monospace effect for time columns where possible
        COLUMN_CONFIGS = [
            {"width": 90,  "stretch": NO, "anchor": W},      # Date
            {"width": 120, "stretch": NO, "anchor": W},      # Dept
            {"width": 60,  "stretch": NO, "anchor": CENTER}, # Reg
            {"width": 180, "stretch": YES, "anchor": W},     # Employee
            {"width": 150, "stretch": YES, "anchor": W},     # Role
            {"width": 55,  "stretch": NO, "anchor": CENTER}, # Status
            {"width": 100, "stretch": NO, "anchor": CENTER}, # Schedule
            {"width": 85,  "stretch": NO, "anchor": CENTER}, # In 1
            {"width": 85,  "stretch": NO, "anchor": CENTER}, # Out 1
            {"width": 85,  "stretch": NO, "anchor": CENTER}, # In 2
            {"width": 85,  "stretch": NO, "anchor": CENTER}, # Out 2
            {"width": 85,  "stretch": NO, "anchor": CENTER}, # Att
            {"width": 85,  "stretch": NO, "anchor": CENTER}, # Work
            {"width": 85,  "stretch": NO, "anchor": CENTER}, # Diff
            {"width": 200, "stretch": YES, "anchor": W},     # Note
            {"width": 100, "stretch": NO, "anchor": CENTER}, # Mach
            {"width": 140, "stretch": NO, "anchor": CENTER}, # Sync
        ]

        # Force column properties
        for i, cfg in enumerate(COLUMN_CONFIGS):
            if i < len(cols):
                self._records_table.view.column(
                    i, 
                    width=cfg["width"], 
                    stretch=cfg["stretch"], 
                    anchor=cfg["anchor"], 
                    minwidth=cfg["width"] # Prevent columns from shrinking internally
                )
                # Also align the heading
                self._records_table.view.heading(i, anchor=cfg["anchor"])

        # Apply tags for the current (first) page
        self._apply_row_tags()
        self._update_nav_lbl()

        # Bind to Tableview internal events if possible, or common UI events
        self._records_table.view.bind("<<TreeviewSelect>>", self._on_record_select)
        self._records_table.view.bind("<Leave>", lambda e: self._tooltip.hide())
        self._records_table.view.bind("<Button-3>", self._on_right_click_record)
        self._records_table.view.bind("<Double-1>", self._on_record_double_click)

        # Left-click cell move: click-to-select + click-to-drop (Excel-style).
        # Also supports classic drag-hold for power users.
        self._records_table.view.bind("<Button-1>", self._on_drag_press, add="+")
        self._records_table.view.bind("<B1-Motion>", self._on_drag_motion, add="+")
        self._records_table.view.bind("<ButtonRelease-1>", self._on_drag_release, add="+")
        self._records_table.view.bind("<Escape>", lambda e: self._cancel_move_src())

        # Keyboard editing on the armed punch cell (Excel-like fast corrections).
        # Bound on BOTH the inner Treeview and the outer Tableview so the
        # shortcuts still work whichever widget currently holds keyboard focus.
        self._records_table.view.bind("<KeyPress>", self._on_punch_keypress, add="+")
        self._records_table.bind("<KeyPress>", self._on_punch_keypress, add="+")
        self._records_table.view.bind("<Return>", self._on_punch_edit, add="+")
        self._records_table.bind("<Return>", self._on_punch_edit, add="+")
        self._records_table.view.bind("<F2>", self._on_punch_edit, add="+")
        self._records_table.bind("<F2>", self._on_punch_edit, add="+")
        self._records_table.view.bind("<Tab>", self._on_punch_tab, add="+")
        self._records_table.bind("<Tab>", self._on_punch_tab, add="+")
        self._records_table.view.bind("<Shift-Tab>", self._on_punch_tab, add="+")
        self._records_table.bind("<Shift-Tab>", self._on_punch_tab, add="+")
        self._records_table.view.bind("<Control-Right>", self._on_punch_ctrl_arrow, add="+")
        self._records_table.bind("<Control-Right>", self._on_punch_ctrl_arrow, add="+")
        self._records_table.view.bind("<Control-Left>", self._on_punch_ctrl_arrow, add="+")
        self._records_table.bind("<Control-Left>", self._on_punch_ctrl_arrow, add="+")
        self._records_table.view.bind("<Control-Down>", self._on_punch_ctrl_arrow, add="+")
        self._records_table.bind("<Control-Down>", self._on_punch_ctrl_arrow, add="+")
        self._records_table.view.bind("<Control-Up>", self._on_punch_ctrl_arrow, add="+")
        self._records_table.bind("<Control-Up>", self._on_punch_ctrl_arrow, add="+")
        self._records_table.view.bind("<Delete>", self._on_punch_delete, add="+")
        self._records_table.bind("<Delete>", self._on_punch_delete, add="+")
        _drag_dbg(f"bindings applied to view {self._records_table.view}")
        
        # Add a refresh mechanism for tags when pagination happens
        self.after(100, self._bind_pagination_events)
        
        # Update row count label
        if hasattr(self, "_records_count_label"):
            self._records_count_label.configure(text=tr("total_rows", count=len(rows)))
            
        # Update Status Summary
        self._update_summary(rows)

        # Update Grand Total footer
        if (hasattr(self, "_records_grand_total_frame") and
            hasattr(self, "_grand_totals") and
            hasattr(self, "_grand_total_vars") and
            self._grand_total_vars is not None):
            footer_vars = self._grand_total_vars
        elif (hasattr(self, "_grand_totals") and hasattr(self, "_grand_total_vars") and
              self._grand_total_vars is not None):
            footer_vars = self._grand_total_vars
        else:
            footer_vars = None
        
        if footer_vars is not None:
            for col, (total, count) in self._grand_totals.items():
                if count > 0:
                    footer_vars[col].set(f"{total // 60:02d}:{total % 60:02d}")
                else:
                    footer_vars[col].set("-")
        # Footer not created, skip update


    def _load_mini_logo(self, label_widget):
        """Loads a mini logo for headers, preferring the configured company logo."""
        from contragest.core.database import SessionLocal, AppConfig
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            logo_path = config.company_logo_path if config and config.company_logo_path else None
            
            if logo_path and os.path.exists(logo_path):
                img = Image.open(logo_path)
                img.thumbnail((24, 24))
                photo = ImageTk.PhotoImage(img)
                label_widget.image = photo # Keep reference
                label_widget.configure(image=photo)
            else:
                # Fallback to local asset if no config path
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                for ext in ["png", "jpg"]:
                    fallback = os.path.join(base_dir, "assets", f"company_logo.{ext}")
                    if os.path.exists(fallback):
                        img = Image.open(fallback)
                        img.thumbnail((24, 24))
                        photo = ImageTk.PhotoImage(img)
                        label_widget.image = photo
                        label_widget.configure(image=photo)
                        break
        except Exception:
            pass
        finally:
            session.close()



    def _update_summary(self, rows):
        """Calculates counts and percentages for each status in the result set dynamically rendering cards."""
        if not hasattr(self, "_summary_labels"): 
            return
            
        from collections import Counter
        status_counts = Counter()
        data_rows = [r for r in rows if len(r) > 6 and "Subtotal" not in str(r[6])]
        for r in data_rows:
            try:
                stat = str(r[5]).strip().upper()
                if stat:
                    status_counts[stat] += 1
            except:
                pass

        grand_total = len(data_rows)
        all_display_keys = ["TOTAL"] + self._status_keys
        
        # Step 1: Update counts and safely hide all cards initially to refresh layout
        for key in all_display_keys:
            count = status_counts.get(key, 0) if key != "TOTAL" else grand_total
            pct = (count / grand_total * 100) if grand_total > 0 else 0
            
            lbl = self._summary_labels.get(key)
            plt = self._summary_pcts.get(key)
            
            if lbl and hasattr(lbl, "_val_var"):
                lbl._val_var.set(str(count))
            elif lbl:
                lbl.configure(text=str(count))

            if plt and hasattr(plt, "_pct_var"):
                plt._pct_var.set(f"{pct:.1f}%")
            elif plt:
                plt.configure(text=f"{pct:.1f}%")
                
            if lbl:
                lbl.master.pack_forget()

        # Step 2: Repack cards with logical structure (Always show core, hide zeroes for sparse codes)
        always_show = {"TOTAL", "P", "AB", "CA"}
        for key in all_display_keys:
            count = status_counts.get(key, 0) if key != "TOTAL" else grand_total
            if count > 0 or key in always_show:
                lbl = self._summary_labels.get(key)
                if lbl:
                    lbl.master.pack(side=tk.LEFT, padx=3, pady=1)

    def _apply_row_tags(self):
        """Iterates through visible rows and applies highlighting tags based on NOTE and STATUS columns."""
        if not self._records_table:
            return
        try:
            view = self._records_table.view
            for item in view.get_children():
                values = view.item(item, "values")
                if not values: continue
                
                tags = []
                # Preserve the amber move-source highlight while a move is armed,
                # otherwise the periodic tag refresh would wipe it after ~1.5s.
                if item == getattr(self, "_move_src_item", None):
                    tags.append("move_src")

                # Check if this is a subtotal row (SCHED column at index 6)
                if len(values) > 6 and "subtotal" in str(values[6]).lower():
                    tags.append("subtotal")
                    view.item(item, tags=tuple(tags))
                    continue
                
                # STATUS is now at index 5
                if len(values) > 5:
                    stat_code = str(values[5]).strip()
                    if stat_code and f"stat_{stat_code}" in view.tag_names():
                        tags.append(f"stat_{stat_code}")

                # NOTE is at index 14
                if len(values) > 14:
                    note = values[14]
                    if note == "To be checked":
                        tags.append("alert")
                    elif note == "Absent":
                        tags.append("absent")
                
                if tags:
                    view.item(item, tags=tuple(tags))
                else:
                    view.item(item, tags=())
        except Exception:
            pass

    def _bind_pagination_events(self):
        """Re-applies row tags on page changes and updates metadata."""
        if not self._records_table: return
        if not self.winfo_exists(): return
        if not self._records_table.view.winfo_exists(): return
        self._apply_row_tags()
        
        # Periodic refresh of navigation label to ensure it matches internal Tableview state
        self._update_nav_lbl()
        
        # Update row count label safely from stored value
        if hasattr(self, "_records_count_label") and hasattr(self, "_current_total_rows"):
            self._records_count_label.configure(text=f"🎧 Total Rows: {self._current_total_rows}")
            
        # Store the job ID so it can be cancelled when the table is rebuilt
        self._pagination_poll_id = self.after(1500, self._bind_pagination_events)

    def _on_fetch_error(self, error):
        """Handle fetch errors in the UI thread."""
        try:
            for w in self._records_table_frame.winfo_children():
                w.destroy()
            ttk.Label(self._records_table_frame, text=f"Error loading records: {error}", bootstyle=DANGER).pack(expand=YES)
        finally:
            self._loading_records = False

    def _parse_iso_date(self, formatted_date):
        """Converts UI formatted date (e.g., '10/05/2026' or 'Ven. 19-06-2026') -> '2026-05-10'"""
        if not formatted_date or formatted_date == "-":
            return datetime.now().strftime("%Y-%m-%d")
            
        formatted_date = str(formatted_date).strip()
        
        # 1. Already ISO: YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", formatted_date):
            return formatted_date
            
        # 2. DD/MM/YYYY
        try:
            return datetime.strptime(formatted_date, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

        # 3. Match format like 'Ven. 19-06-2026' (DD-MM-YYYY)
        match = re.search(r"(\d{2}-\d{2}-\d{4})", formatted_date)
        if match:
            try:
                return datetime.strptime(match.group(1), "%d-%m-%Y").strftime("%Y-%m-%d")
            except ValueError:
                pass
            
        # 4. Legacy / fallback format: extract last 8 chars for DD-MM-YY (e.g. 'Sat. 07-03-26')
        try:
            date_part = formatted_date[-8:]
            return datetime.strptime(date_part, "%d-%m-%y").strftime("%Y-%m-%d")
        except ValueError:
            pass
            
        return datetime.now().strftime("%Y-%m-%d") # Fallback

    def _current_admin_name(self):
        """Name of the logged-in user used to stamp corrections in the audit log."""
        cu = getattr(self.main_window, "current_user", None)
        return getattr(cu, "username", "SYSTEM") if cu else "SYSTEM"

    def _is_current_admin(self):
        cu = getattr(self.main_window, "current_user", None)
        return bool(cu and getattr(cu, "role", None) == "admin")

    def _on_right_click_record(self, event):
        """Show context menu for quick edits on an attendance record row."""
        item = self._records_table.view.identify_row(event.y)
        if not item:
            return

        self._records_table.view.selection_set(item)
        values = self._records_table.view.item(item, "values")

        reg_number = str(values[2]).strip() if len(values) > 2 else "-"
        formatted_date = str(values[0]).strip() if len(values) > 0 else "-"
        current_sched = str(values[6]).strip() if len(values) > 6 else "-"
        current_stat = str(values[5]).strip() if len(values) > 5 else "-"

        if not reg_number or reg_number == "-" or not formatted_date or formatted_date == "-":
            return

        if "─" in formatted_date or any("Subtotal" in str(v) for v in values):
            return

        emp_name = values[3] if len(values) > 3 else "-"
        iso_date = self._parse_iso_date(formatted_date)
        current_note = str(values[14]).strip() if len(values) > 14 else "-"

        # Column-aware: right-click directly on the SCHED or STAT column opens
        # a focused editing menu (change / reset). Other columns keep the full
        # quick-edit menu.
        try:
            col_id = self._records_table.view.identify_column(event.x)
            idx = int(col_id.lstrip("#")) - 1
            col_name = self._all_table_cols[idx] if 0 <= idx < len(self._all_table_cols) else None
        except Exception:
            col_name = None

        if col_name == "SCHED":
            self._open_sched_column_menu(event, values, reg_number, emp_name, iso_date, current_sched)
            return

        if col_name == "STAT":
            self._open_stat_column_menu(event, values, reg_number, emp_name, iso_date, current_stat)
            return

        if col_name == "NOTE":
            current_note = str(values[14]).strip() if len(values) > 14 else "-"
            self._open_note_editor_dialog(
                reg_number=reg_number,
                emp_name=emp_name,
                iso_date=iso_date,
                current_note=current_note,
            )
            return

        if col_name in ("IN 1", "OUT 1", "IN 2", "OUT 2"):
            self._open_punch_column_menu(event, values, reg_number, emp_name, iso_date, col_name)
            return

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label=f"👁  View Record Details",
            command=lambda: self._open_record_detail_card(values)
        )
        menu.add_separator()
        menu.add_command(
            label=f"🎯  Change Status  ({current_stat})",
            command=lambda: self._open_status_picker_dialog(
                reg_number=reg_number,
                emp_name=emp_name,
                iso_date=iso_date,
                current_stat=current_stat,
            )
        )
        menu.add_command(
            label=f"🕒  Change Schedule  ({current_sched})",
            command=lambda: self._open_change_schedule_dialog(
                reg_number=reg_number,
                emp_name=emp_name,
                iso_date=iso_date,
                current_sched=current_sched,
            )
        )
        menu.add_command(
            label=f"📝  Edit Note  ({reg_number})",
            command=lambda: self._open_note_editor_dialog(
                reg_number=reg_number,
                emp_name=emp_name,
                iso_date=iso_date,
                current_note=current_note,
            )
        )
        menu.add_separator()
        menu.add_command(
            label=f"➕  Fix / Add Punch  ({reg_number})",
            command=lambda: self._open_manual_punch_dialog(
                reg_number=reg_number,
                emp_name=values[3] if len(values) > 3 else "-",
                date_str=self._parse_iso_date(formatted_date),
                current_times=self._extract_current_times(values),
            )
        )
        menu.add_command(
            label=f"📋  View Audit Trail  ({reg_number})",
            command=lambda: self.view_audit_for_employee(reg_number)
        )
        menu.add_command(
            label=f"👤  Edit Employee Profile  ({reg_number})",
            command=lambda: self._open_edit_employee_dialog(reg_number)
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _open_sched_column_menu(self, event, values, reg_number, emp_name, iso_date, current_sched):
        """Context menu specialized for the SCHED column: change / reset override."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="🕒  Change Schedule...",
            command=lambda: self._open_change_schedule_dialog(
                reg_number=reg_number,
                emp_name=emp_name,
                iso_date=iso_date,
                current_sched=current_sched,
            )
        )
        override = self.service.get_schedule_override(reg_number, iso_date)
        menu.add_command(
            label="↩  Reset to Automatic Schedule" if override
                  else "↩  Reset to Automatic Schedule (no override)",
            state="normal" if override else "disabled",
            command=lambda: self._reset_schedule_override(reg_number, iso_date)
        )
        menu.add_separator()
        menu.add_command(
            label=f"👁  View Record Details  ({reg_number})",
            command=lambda: self._open_record_detail_card(values)
        )

        selection = self._records_table.view.selection()
        if len(selection) > 1:
            menu.add_separator()
            menu.add_command(
                label=f"⚡  Apply to {len(selection)} selected rows...",
                state="disabled"
            )
            menu.add_separator()
            try:
                schedules = self.service.get_all_work_schedules()
            except Exception:
                schedules = []
            for s in schedules:
                menu.add_command(
                    label=f"    {s.name} (bulk)",
                    command=lambda s=s: self._apply_schedule_to_selection(s.name),
                )
        menu.tk_popup(event.x_root, event.y_root)

    def _status_options(self):
        """Returns ordered [(code, name, color_hex)] status options (DB first, hardcoded fallback)."""
        from contragest.core.database import DayStatus
        options = []
        seen = set()
        try:
            for s in self.session.query(DayStatus).order_by(DayStatus.id).all():
                options.append((s.code, s.name, s.color_hex))
                seen.add(s.code)
        except Exception:
            pass
        fallback = [("P", "Present", DesignTokens.PRIMARY),
                    ("AB", "Absent", DesignTokens.DANGER),
                    ("CA", "Congé", DesignTokens.PRIMARY),
                    ("CR", "Congé rémunéré", DesignTokens.WARNING),
                    ("CM", "Congé maladie", DesignTokens.PRIMARY),
                    ("MAP", "Maladie", DesignTokens.PRIMARY),
                    ("MIS", "Mission", DesignTokens.DANGER),
                    ("JF", "Jour férié", DesignTokens.WARNING),
                    ("JFB", "JF travaillé", DesignTokens.PRIMARY),
                    ("RH", "Repos hebdo", DesignTokens.PRIMARY),
                    ("RHB", "RH travaillé", DesignTokens.PRIMARY),
                    ("PJF", "Présent JF", DesignTokens.WARNING),
                    ("JFP", "JF payé", DesignTokens.TEXT_MUTED),
                    ("CSS", "Cessation", DesignTokens.PRIMARY),
                    ("SOR", "Sortie", DesignTokens.WARNING)]
        for code, name, color in fallback:
            if code not in seen:
                options.append((code, name, color))
        return options

    def _text_color_for(self, hex_color):
        """Black or white depending on the luminance of a hex color."""
        try:
            c = hex_color.lstrip("#")
            if len(c) != 6:
                return "#ffffff"
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            return "#000000" if ((0.299 * r + 0.587 * g + 0.114 * b) / 255) > 0.6 else "#ffffff"
        except Exception:
            return "#ffffff"

    def _populate_status_menu(self, menu, reg_number, iso_date, current_stat):
        """Fills a tk.Menu with colored status options + reset + bulk actions."""
        override = self.service.get_status_override(reg_number, iso_date)
        has_override = override is not None

        display = current_stat if current_stat not in ("-", "") else "Automatic"
        menu.add_command(
            label=f"🎯  Status: {display}" + (f"  (manual override)" if has_override else "  (automatic)"),
            state="disabled"
        )
        menu.add_separator()

        for code, name, color in self._status_options():
            menu.add_command(
                label=f"{code}   —   {name}",
                command=lambda c=code: self._set_status_for_date(reg_number, iso_date, c),
            )

        menu.add_separator()
        menu.add_command(
            label="↩  Reset to Automatic Status" if has_override
                  else "↩  Reset to Automatic Status (no override)",
            state="normal" if has_override else "disabled",
            command=lambda: self._reset_status_override(reg_number, iso_date)
        )

        selection = self._records_table.view.selection()
        if len(selection) > 1:
            menu.add_separator()
            menu.add_command(
                label=f"⚡  Apply to {len(selection)} selected rows...",
                state="disabled"
            )
            menu.add_separator()
            for code, name, color in self._status_options():
                if code == "-":
                    continue
                menu.add_command(
                    label=f"    {code}   —   {name} (bulk)",
                    command=lambda c=code: self._apply_status_to_selection(c),
                )

    def _open_stat_column_menu(self, event, values, reg_number, emp_name, iso_date, current_stat):
        """Context menu specialized for the STAT column: colored status picker + reset."""
        if not self._is_current_admin():
            Messagebox.show_error("You do not have permission to modify attendance records.", "Access Denied", parent=self)
            return
        menu = tk.Menu(self, tearoff=0)
        self._populate_status_menu(menu, reg_number, iso_date, current_stat)
        menu.add_separator()
        menu.add_command(
            label=f"👁  View Record Details  ({reg_number})",
            command=lambda: self._open_record_detail_card(values)
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _punch_slot_for_column(self, col_name):
        """Maps an attendance-grid punch column to (punch_type, slot_index)."""
        mapping = {
            "IN 1":  ("check_in",  1),
            "OUT 1": ("check_out", 1),
            "IN 2":  ("check_in",  2),
            "OUT 2": ("check_out", 2),
        }
        return mapping.get(col_name)

    def _open_punch_column_menu(self, event, values, reg_number, emp_name, iso_date, col_name):
        """Context menu for the punch time columns (IN 1 / OUT 1 / IN 2 / OUT 2).

        Right-clicking directly on a punch cell gives one-click access to the
        two operations the column needs: edit the time, or remove the punch.
        All changes go through the audited service methods.
        """
        if not self._punch_slot_for_column(col_name):
            return

        col_index = self._all_table_cols.index(col_name) if col_name in self._all_table_cols else None
        current_time = ""
        if col_index is not None and len(values) > col_index and values[col_index] not in ("-", "", None):
            current_time = str(values[col_index])

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label=f"✏️  Edit {col_name}...",
            command=lambda: self._open_quick_punch_dialog(
                reg_number=reg_number, emp_name=emp_name, iso_date=iso_date,
                col_name=col_name, current_time=current_time,
            )
        )
        menu.add_command(
            label=f"🗑  Remove {col_name} punch",
            state="normal" if current_time else "disabled",
            command=lambda: self._remove_punch_for_slot(
                reg_number=reg_number, iso_date=iso_date,
                col_name=col_name, current_time=current_time,
            )
        )
        menu.add_separator()
        menu.add_command(
            label=f"👁  View Record Details  ({reg_number})",
            command=lambda: self._open_record_detail_card(values)
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _open_quick_punch_dialog(self, reg_number, emp_name, iso_date, col_name, current_time=""):
        """Minimal single-field editor for a punch slot (IN/OUT 1/2).

        The current value is pre-filled so an update takes one edit + Enter.
        Saves go through ``add_manual_punch`` which upserts the matching slot
        and writes an audit-log entry, preserving data integrity.
        """
        slot = self._punch_slot_for_column(col_name)
        if not slot:
            return
        punch_type, slot_index = slot

        win = tk.Toplevel(self)
        win.title(f"Edit {col_name}")
        win.configure(bg=MAIN_BG)
        win.resizable(False, False)
        win.grab_set()
        win.transient(self)

        W, H = 340, 250
        self.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - W) // 2
        py = self.winfo_rooty() + (self.winfo_height() - H) // 2
        win.geometry(f"{W}x{H}+{px}+{py}")

        hdr = tk.Frame(win, bg=ACCENT_BLUE, height=42)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"✏️  EDIT {col_name}", font=("JetBrains Mono", 10, "bold"),
                 bg=ACCENT_BLUE, fg="#ffffff").pack(side=tk.LEFT, padx=12, pady=0)

        body = tk.Frame(win, bg=MAIN_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        tk.Label(body, text=f"{emp_name}  (REG {reg_number})  —  {iso_date}",
                 font=("Space Mono", 8), bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor=tk.W)

        tk.Label(body, text="Time (HH:MM):", font=("Space Mono", 9, "bold"),
                 bg=MAIN_BG, fg=TEXT_HIGH).pack(anchor=tk.W, pady=(8, 2))
        time_var = ttk.StringVar(value=current_time[:5] if len(current_time) >= 5 else current_time)
        entry = ttk.Entry(body, textvariable=time_var, width=12, font=("Space Mono", 11))
        entry.pack(anchor=tk.W, pady=2, ipady=2)

        tk.Label(body, text="Reason (required for audit):", font=("Space Mono", 8, "bold"),
                 bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(6, 2))
        reason_var = ttk.StringVar()
        reason_entry = ttk.Entry(body, textvariable=reason_var, width=30)
        reason_entry.pack(anchor=tk.W, pady=2, ipady=2)
        # Pre-fill the last-used reason so repeated corrections are faster
        # (still editable, still audited).
        if getattr(self, "_last_edit_reason", ""):
            reason_var.set(self._last_edit_reason)

        def _save():
            time_str = time_var.get().strip()
            if len(time_str) != 5 or ":" not in time_str:
                Messagebox.show_error("Please enter time in HH:MM format.", "Invalid Format", parent=self)
                return
            if not reason_var.get().strip():
                Messagebox.show_error("Please provide a reason for this modification.", "Missing Reason", parent=self)
                return
            self._transfer_status.configure(text=f"⏳ Saving {col_name}...", fg=ACCENT_BLUE)
            # Use the DAY_PROGRAM override path (set_punch_slot) instead of
            # add_manual_punch: on night-shift days the enriched view re-pairs
            # raw punches chronologically, so a raw-record edit never sticks
            # visually.  The override pins the slot verbatim — reliable.
            ok, msg = self.service.set_punch_slot(
                registration_number=reg_number,
                punch_date=iso_date,
                col_name=col_name,
                time_val=time_str,
                admin_name=self._current_admin_name(),
                reason=reason_var.get().strip(),
            )
            if ok:
                self._last_edit_reason = reason_var.get().strip()
                self._transfer_status.configure(text=f"✅ {msg}", fg=SUCCESS_EMERALD)
                win.destroy()
                self._deferred_reload_records()
            else:
                self._transfer_status.configure(text=f"❌ {msg}", fg=DANGER_ROSE)
                Messagebox.show_error(msg, "Error", parent=self)

        btn_frame = tk.Frame(win, bg=MAIN_BG)
        btn_frame.pack(fill=tk.X, padx=14, pady=(2, 10))
        ttk.Button(btn_frame, text="✅ Save", bootstyle=SUCCESS, command=_save, width=10).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="❌ Cancel", bootstyle=SECONDARY, command=win.destroy, width=10).pack(side=tk.RIGHT, padx=4)

        win.bind("<Return>", lambda e: _save())
        win.bind("<Escape>", lambda e: win.destroy())
        entry.focus_set()
        entry.select_range(0, "end")

    def _open_note_editor_dialog(self, reg_number, emp_name, iso_date, current_note=""):
        """Edits the NOTE column for an employee/day (DAY_NOTE override).

        The grid's NOTE column comes from ``AttendanceCorrectionLog`` rows with
        issue_type='DAY_NOTE'.  This dialog writes through
        ``save_note_correction`` (audited), then reloads the grid so the note
        shows up immediately.
        """
        if not self._is_current_admin():
            Messagebox.show_error("You do not have permission to modify attendance records.", "Access Denied", parent=self)
            return

        win = tk.Toplevel(self)
        win.title("Edit Note")
        win.configure(bg=MAIN_BG)
        win.resizable(False, False)
        win.grab_set()
        win.transient(self)

        W, H = 440, 330
        self.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - W) // 2
        py = self.winfo_rooty() + (self.winfo_height() - H) // 2
        win.geometry(f"{W}x{H}+{px}+{py}")

        hdr = tk.Frame(win, bg=ACCENT_BLUE, height=42)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="📝  EDIT NOTE", font=("JetBrains Mono", 10, "bold"),
                 bg=ACCENT_BLUE, fg="#ffffff").pack(side=tk.LEFT, padx=12, pady=0)

        body = tk.Frame(win, bg=MAIN_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        tk.Label(body, text=f"{emp_name}  (REG {reg_number})  —  {iso_date}",
                 font=("Space Mono", 8), bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor=tk.W)

        tk.Label(body, text="Note:", font=("Space Mono", 9, "bold"),
                 bg=MAIN_BG, fg=TEXT_HIGH).pack(anchor=tk.W, pady=(8, 2))
        note_text = tk.Text(body, width=46, height=5, font=("Space Mono", 9),
                            bg="#1E222C", fg="#E2E8F0", insertbackground="#E2E8F0",
                            relief="flat", highlightthickness=1, highlightbackground="#334155")
        note_text.pack(fill=tk.X, pady=2)
        note_text.insert("1.0", current_note if current_note and current_note != "-" else "")

        # Quick-pick from the predefined notes list (optional convenience).
        # NEVER let a failure here abort the dialog build — the note editor must
        # open even if the predefined-notes query errors (otherwise the whole
        # "add note" option appears dead).
        try:
            predefined = self.service.get_predefined_notes()
        except Exception:
            predefined = []
        if predefined:
            tk.Label(body, text="Quick note:", font=("Space Mono", 8, "bold"),
                     bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(6, 2))
            quick_var = ttk.StringVar()
            quick_cb = ttk.Combobox(body, textvariable=quick_var,
                                    values=[n["name"] for n in predefined],
                                    state="readonly", width=40)
            quick_cb.pack(anchor=tk.W, pady=2)
            quick_cb.bind("<<ComboboxSelected>>", lambda e: note_text.delete("1.0", "end") or note_text.insert("1.0", quick_var.get()))

        tk.Label(body, text="Reason (required for audit):", font=("Space Mono", 8, "bold"),
                 bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(6, 2))
        reason_var = ttk.StringVar()
        if getattr(self, "_last_edit_reason", ""):
            reason_var.set(self._last_edit_reason)
        reason_entry = ttk.Entry(body, textvariable=reason_var, width=44)
        reason_entry.pack(anchor=tk.W, pady=2, ipady=2)

        def _save():
            note = note_text.get("1.0", "end").strip()
            if not reason_var.get().strip():
                Messagebox.show_error("Please provide a reason for this modification.", "Missing Reason", parent=self)
                return
            self._transfer_status.configure(text="⏳ Saving note...", fg=ACCENT_BLUE)
            ok, msg = self.service.save_note_correction(
                reg_number=reg_number,
                shift_date=iso_date,
                note_text=note,
                admin_name=self._current_admin_name(),
            )
            if ok:
                self._last_edit_reason = reason_var.get().strip()
                self._transfer_status.configure(text=f"✅ Note updated", fg=SUCCESS_EMERALD)
                win.destroy()
                self._deferred_reload_records()
            else:
                self._transfer_status.configure(text=f"❌ {msg}", fg=DANGER_ROSE)
                Messagebox.show_error(msg, "Error", parent=self)

        btn_frame = tk.Frame(win, bg=MAIN_BG)
        btn_frame.pack(fill=tk.X, padx=14, pady=(2, 10))
        ttk.Button(btn_frame, text="✅ Save", bootstyle=SUCCESS, command=_save, width=10).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="❌ Cancel", bootstyle=SECONDARY, command=win.destroy, width=10).pack(side=tk.RIGHT, padx=4)

        # The hard-coded H (330px) clips the Save/Cancel buttons when the
        # quick-pick block renders (content requests ~370px). Re-fit the window
        # to the actual requested size so the validate buttons are ALWAYS visible.
        # Cosmetic only — never let a geometry error abort the dialog.
        try:
            win.update_idletasks()
            req_h = win.winfo_reqheight()
            if req_h > H:
                H = req_h + 8
                px = self.winfo_rootx() + (self.winfo_width() - W) // 2
                py = max(0, self.winfo_rooty() + (self.winfo_height() - H) // 2)
                win.geometry(f"{W}x{H}+{px}+{py}")
        except Exception:
            pass

        win.bind("<Control-Return>", lambda e: _save())
        win.bind("<Escape>", lambda e: win.destroy())
        note_text.focus_set()

    def _remove_punch_for_slot(self, reg_number, iso_date, col_name, current_time):
        """Removes one punch slot (IN/OUT 1/2) after a reason + confirmation.

        Deletion goes through ``delete_manual_punch`` which logs an audit
        entry before physically removing the record.
        """
        slot = self._punch_slot_for_column(col_name)
        if not slot:
            return
        punch_type, slot_index = slot

        reason = Querybox.get_string(
            prompt="Reason for removal (required for audit):",
            title=f"Remove {col_name}",
            parent=self,
            initialvalue="",
        )
        if reason is None or not reason.strip():
            Messagebox.show_error("Please provide a reason for this deletion.", "Missing Reason", parent=self)
            return

        ans = Messagebox.show_question(
            f"Remove {col_name} ({current_time}) for REG {reg_number} on {iso_date}?\n\n"
            "This deletes the punch record permanently (audit trail kept).",
            "Confirm Removal",
            buttons=["Cancel:secondary", "Remove:danger"],
            parent=self,
        )
        if ans != "Remove":
            return

        self._transfer_status.configure(text=f"⏳ Removing {col_name}...", fg=ACCENT_BLUE)
        ok, msg = self.service.delete_manual_punch(
            registration_number=reg_number,
            punch_date=iso_date,
            punch_type=punch_type,
            admin_name=self._current_admin_name(),
            reason=reason.strip(),
            slot_index=slot_index,
            target_time=current_time,
        )
        if ok:
            self._transfer_status.configure(text=f"✅ {msg}", fg=SUCCESS_EMERALD)
        else:
            self._transfer_status.configure(text=f"❌ {msg}", fg=DANGER_ROSE)
            Messagebox.show_error(msg, "Error", parent=self)
        self._deferred_reload_records()

    # ── Inline editor (true Excel-like cell editing) ──────────────────────
    #
    # An Entry widget is placed directly on top of the cell, covering it
    # exactly. The admin types the new time, presses Enter → commit, or
    # Escape → cancel. No popup dialog, no reason field. The reason is
    # auto-filled from the last edit or defaults to "Quick edit" so the
    # audit trail is kept without breaking the "type → Enter" flow.
    # ──────────────────────────────────────────────────────────────────────
    def _commit_inline_edit(self, col_name, iso_date, reg_number, time_val):
        """Commits an inline time edit (validates HH:MM, calls service)."""
        if not time_val:
            return
        if not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", time_val):
            if hasattr(self, "_transfer_status"):
                self._transfer_status.configure(text="❌ Format: HH:MM", fg=DANGER_ROSE)
            return
        reason = getattr(self, "_last_edit_reason", "") or "Quick edit"
        if not self._punch_slot_for_column(col_name):
            return
        self._transfer_status.configure(text=f"⏳ Saving {col_name}...", fg=ACCENT_BLUE)
        # DAY_PROGRAM override path — reliable even on night-shift days (the
        # enriched grid re-pairs raw punches, so raw-record edits don't stick).
        ok, msg = self.service.set_punch_slot(
            registration_number=reg_number,
            punch_date=iso_date,
            col_name=col_name,
            time_val=time_val,
            admin_name=self._current_admin_name(),
            reason=reason,
        )
        if ok:
            self._last_edit_reason = reason
            self._transfer_status.configure(text=f"✅ {msg}", fg=SUCCESS_EMERALD)
            self._deferred_reload_records()
        else:
            self._transfer_status.configure(text=f"❌ {msg}", fg=DANGER_ROSE)

    def _open_inline_editor(self, col_name, iso_date, reg_number, _emp_name,
                            initial_text="", current_time=""):
        """Places an Entry overlay directly on top of the armed cell.

        Type a time, press Enter → save. Press Esc → cancel.
        Tab commits and moves to the next punch column.
        """
        if not hasattr(self, "_records_table"):
            return
        view = self._records_table.view
        item = getattr(self, "_move_src_item", None)
        if not item:
            return
        # Remove any existing inline editor first.
        if self._inline_entry is not None:
            try:
                self._inline_entry.destroy()
            except Exception:
                pass
            self._inline_entry = None
        col_index = self._all_table_cols.index(col_name)
        bbox = view.bbox(item, column="#%d" % (col_index + 1))
        if not bbox:
            return
        x, y, w, h = bbox
        self._cancel_move_src()
        entry = tk.Entry(
            view, font=("Space Mono", 10, "bold"),
            bg="#2A2F3A", fg="#ffffff", insertbackground="#ffffff",
            highlightthickness=2, highlightcolor=ACCENT_BLUE,
            highlightbackground=ACCENT_BLUE, relief="flat", bd=0,
        )
        self._inline_entry = entry
        self._inline_col = col_name
        entry.place(x=x, y=y, width=w, height=h)
        if initial_text:
            entry.insert(0, initial_text)
        elif current_time:
            entry.insert(0, current_time)
        entry.select_range(0, "end")
        entry.focus_set()

        def _commit(event=None):
            val = entry.get().strip()
            if entry.winfo_exists():
                entry.destroy()
            self._inline_entry = None
            self._commit_inline_edit(col_name, iso_date, reg_number, val)

        def _cancel(event=None):
            if entry.winfo_exists():
                entry.destroy()
            self._inline_entry = None

        def _commit_and_navigate(delta=1):
            val = entry.get().strip()
            if entry.winfo_exists():
                entry.destroy()
            self._inline_entry = None
            self._commit_inline_edit(col_name, iso_date, reg_number, val)
            # Navigate to the next/prev column after save.
            self.after(60, lambda d=delta: self._navigate_inline_col(d))

        entry.bind("<Return>", _commit)
        entry.bind("<Escape>", _cancel)
        entry.bind("<Tab>", lambda e: _commit_and_navigate(1))
        entry.bind("<Shift-Tab>", lambda e: _commit_and_navigate(-1))

    def _navigate_inline_col(self, delta):
        """After an inline edit commit, re-arm the next/prev punch column."""
        col = getattr(self, "_inline_col", None)
        if col not in PUNCH_COLS:
            return
        item = getattr(self, "_move_src_item", None)
        if not item:
            return
        try:
            idx = PUNCH_COLS.index(col)
        except ValueError:
            return
        new_idx = idx + delta
        if 0 <= new_idx < len(PUNCH_COLS):
            self._arm_cell(item, PUNCH_COLS[new_idx])

    # ── Cell move (Excel-style click-to-select + click-to-drop) ────────────
    #
    # How it works:
    #   1st click on a non-empty punch cell (IN 1 / OUT 1 / IN 2 / OUT 2):
    #       → Arms that cell as the source.  The row is highlighted in amber.
    #         A hint appears in the status bar.  Escape cancels.
    #   2nd click on any other punch cell (same or different row/date):
    #       → Immediately opens the "Move Punch" confirmation dialog.
    #   Classic drag-hold (press + move + release) also works as a fallback.
    # ────────────────────────────────────────────────────────────────────────
    def _cancel_move_src(self):
        """Clears the pending source selection (amber highlight + status hint)."""
        if not hasattr(self, "_records_table"):
            return
        view = self._records_table.view
        # Remove amber highlight from the previously-armed row
        if self._move_src_item:
            try:
                current_tags = list(view.item(self._move_src_item, "tags") or [])
                if "move_src" in current_tags:
                    current_tags.remove("move_src")
                    view.item(self._move_src_item, tags=current_tags)
            except Exception:
                pass
        self._drag_src = None
        self._drag_moved = False
        self._move_src_item = None
        self._move_src_emp = ""
        view.configure(cursor="")
        _drag_dbg("cancel_move_src: source cleared")
        # Reset status bar hint if it was showing the move-mode message
        if hasattr(self, "_transfer_status"):
            try:
                current_text = self._transfer_status.cget("text")
                if "SELECTED" in current_text or "Escape" in current_text:
                    self._transfer_status.configure(text="", fg="#94A3B8")
            except Exception:
                pass

    def _on_drag_press(self, event):
        """Left-press on a punch cell.

        Two-phase Excel-style move:
          • If NO source is armed yet: arm this cell as the source (highlight it).
          • If a source IS already armed and this is a DIFFERENT punch cell:
            immediately trigger the confirmation dialog (2nd-click path).
        Classic drag-hold also works: press → move pointer → release.
        """
        try:
            self._drag_press_impl(event)
        except Exception as exc:
            _drag_dbg(f"press EXCEPTION: {exc!r}")
            raise

    def _drag_press_impl(self, event):
        try:
            ew = event.widget
        except AttributeError:
            ew = "<n/a>"
        _drag_dbg(f"press entered: widget={ew} x={getattr(event, 'x', None)!r} "
                  f"y={getattr(event, 'y', None)!r} "
                  f"table={self._records_table if hasattr(self, '_records_table') else None!r} "
                  f"drag_src={self._drag_src if hasattr(self, '_drag_src') else '<missing>'}")
        self._cancel_pending_tooltip()
        self._tooltip.hide()
        if not hasattr(self, "_records_table"):
            _drag_dbg("press no-op: _records_table missing")
            return
        view = self._records_table.view
        item = view.identify_row(event.y)
        _drag_dbg(f"press x={event.x} y={event.y} item={item!r}")
        if not item:
            # Clicked outside any row — cancel a pending source selection
            self._cancel_move_src()
            return
        values = view.item(item, "values")
        if not values:
            self._cancel_move_src()
            return
        if any("Subtotal" in str(v) for v in values) or "─" in str(values[0]):
            _drag_dbg(f"press ignored (subtotal row) item={item}")
            self._cancel_move_src()
            return

        col_name = self._col_name_at(event.x)
        _drag_dbg(f"press col_name_at(x={event.x}) = {col_name!r}")

        # ── 2nd-click path: source already armed ──────────────────────────
        if self._drag_src is not None:
            src = self._drag_src
            if col_name not in ("IN 1", "OUT 1", "IN 2", "OUT 2"):
                # Clicked a non-punch column → cancel
                self._cancel_move_src()
                return
            col_index = self._all_table_cols.index(col_name)
            target_cell = str(values[col_index]).strip() if len(values) > col_index else "-"
            reg_number  = str(values[2]).strip() if len(values) > 2 else "-"
            if not reg_number or reg_number == "-":
                self._cancel_move_src()
                return
            dst = {
                "reg":  reg_number,
                "date": self._parse_iso_date(str(values[0])),
                "col":  col_name,
                "time": target_cell if target_cell not in ("-", "", "None") else "-",
            }
            if (src["reg"], src["date"], src["col"]) == (dst["reg"], dst["date"], dst["col"]):
                # Re-clicked the source cell itself — stay armed, do nothing.
                # The user may have mis-clicked or is reconfirming the source
                # before picking a destination.  Cancelling here is confusing.
                _drag_dbg("press 2nd-click on same cell -> stay armed (no-op)")
                return
            _drag_dbg(f"press 2nd-click -> confirm src={src} dst={dst}")
            self._cancel_move_src()   # Clear highlight before dialog opens
            self._confirm_cell_move(src, dst)
            return

        # ── 1st-click path: arm a new source ─────────────────────────────
        if col_name not in ("IN 1", "OUT 1", "IN 2", "OUT 2"):
            return  # Clicked a non-punch column, nothing to arm

        col_index = self._all_table_cols.index(col_name)
        cell = str(values[col_index]).strip() if len(values) > col_index else "-"
        if cell in ("-", "", "None"):
            _drag_dbg(f"press ignored (empty cell) col={col_name} cell={cell!r}")
            return  # Empty cell — nothing to move

        reg_number = str(values[2]).strip() if len(values) > 2 else "-"
        if not reg_number or reg_number == "-":
            return

        self._drag_src = {
            "reg":  reg_number,
            "date": self._parse_iso_date(str(values[0])),
            "col":  col_name,
            "time": cell,
        }
        self._drag_moved = False
        self._move_src_item = item
        self._move_src_emp = str(values[3]).strip() if len(values) > 3 else ""

        # Highlight the source row in amber so the user can see what is armed
        try:
            current_tags = list(view.item(item, "tags") or [])
            if "move_src" not in current_tags:
                current_tags.append("move_src")
            view.item(item, tags=current_tags)
        except Exception:
            pass

        view.configure(cursor="fleur")
        # Give the grid keyboard focus so typing / shortcuts edit the cell.
        try:
            view.focus_set()
        except Exception:
            pass
        # Status bar hint (kept in sync by _update_move_hint)
        self._update_move_hint()
        _drag_dbg(f"press ARMED (1st-click) src={self._drag_src} item={item}")

    def _cancel_pending_tooltip(self):
        """Cancel any deferred tooltip show so stale popups never appear."""
        if self._tooltip_after_id:
            try:
                self.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = None

    def _on_drag_motion(self, event):
        """Pointer moved with button held -> flags the action as a classic drag."""
        if self._drag_src:
            self._drag_moved = True
            _drag_dbg(f"motion x={event.x} y={event.y} moved=True")
            # A drag is underway: keep the destination cells uncovered.
            self._cancel_pending_tooltip()
            self._tooltip.hide()
        else:
            _drag_dbg(f"motion ignored (no src) x={event.x} y={event.y}")

    def _on_drag_release(self, event):
        """Button-release handler for the classic drag-hold path.

        If the pointer actually moved (``_drag_moved`` is True) this acts as
        the drop target.  If the pointer did NOT move it means the user did a
        plain click — in that case the source selection stays armed for the
        2nd-click path handled by ``_on_drag_press``, so we do nothing here.
        """
        if not hasattr(self, "_records_table"):
            return
        view = self._records_table.view
        src   = self._drag_src
        moved = self._drag_moved

        if not src:
            _drag_dbg(f"release ignored (no src) moved={moved}")
            return

        if not moved:
            # Plain click (no pointer movement): leave source armed for 2nd click.
            _drag_dbg(f"release ignored (not moved, staying armed) src={src}")
            view.configure(cursor="")   # Restore cursor but keep amber highlight
            return

        # Classic drag-hold completed — clear source state unconditionally.
        self._cancel_move_src()

        item = view.identify_row(event.y)
        _drag_dbg(f"release (drag) x={event.x} y={event.y} item={item!r} src={src}")
        if not item:
            return
        values = view.item(item, "values")
        if not values:
            return
        if any("Subtotal" in str(v) for v in values) or "─" in str(values[0]):
            return

        col_name = self._col_name_at(event.x)
        _drag_dbg(f"release col_name_at(x={event.x}) = {col_name!r}")
        if col_name not in ("IN 1", "OUT 1", "IN 2", "OUT 2"):
            return

        col_index = self._all_table_cols.index(col_name)
        target_cell = str(values[col_index]).strip() if len(values) > col_index else "-"
        reg_number  = str(values[2]).strip() if len(values) > 2 else "-"
        if not reg_number or reg_number == "-":
            return

        dst = {
            "reg":  reg_number,
            "date": self._parse_iso_date(str(values[0])),
            "col":  col_name,
            "time": target_cell if target_cell not in ("-", "", "None") else "-",
        }
        if (src["reg"], src["date"], src["col"]) == (dst["reg"], dst["date"], dst["col"]):
            _drag_dbg(f"release ignored (same cell) dst={dst}")
            return

        _drag_dbg(f"release (drag) -> confirm src={src} dst={dst}")
        self._confirm_cell_move(src, dst)

    def _col_name_at(self, x):
        """Resolves the grid column name at a given x offset (0-based)."""
        try:
            col_id = self._records_table.view.identify_column(x)
            idx = int(col_id.lstrip("#")) - 1
            return self._all_table_cols[idx] if 0 <= idx < len(self._all_table_cols) else None
        except Exception:
            return None

    def _confirm_cell_move(self, src, dst):
        """Shows a reason dialog before executing the cell move."""
        _drag_dbg(f"confirm src={src} dst={dst}")
        src_slot = self._punch_slot_for_column(src["col"])
        dst_slot = self._punch_slot_for_column(dst["col"])
        if not src_slot or not dst_slot:
            _drag_dbg(f"confirm aborted (slots) src_slot={src_slot} dst_slot={dst_slot}")
            return

        win = tk.Toplevel(self)
        _drag_dbg(f"confirm dialog created {win}")
        win.title("Move Punch")
        win.configure(bg=MAIN_BG)
        win.resizable(False, False)
        win.grab_set()
        win.transient(self)

        W, H = 430, 285
        self.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - W) // 2
        py = self.winfo_rooty() + (self.winfo_height() - H) // 2
        win.geometry(f"{W}x{H}+{px}+{py}")

        hdr = tk.Frame(win, bg=ACCENT_BLUE, height=42)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="↔  MOVE PUNCH", font=("JetBrains Mono", 10, "bold"),
                 bg=ACCENT_BLUE, fg="#ffffff").pack(side=tk.LEFT, padx=12)

        body = tk.Frame(win, bg=MAIN_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        tk.Label(body, text=(
            f"Move  {src['time']}  ({src['col']})\n"
            f"  REG {src['reg']}  —  {src['date']}\n"
            f"→  {dst['col']}  of  REG {dst['reg']}  —  {dst['date']}"
        ), font=("Space Mono", 9), bg=MAIN_BG, fg=TEXT_HIGH, justify=tk.LEFT).pack(anchor=tk.W)

        tk.Label(body, text=(
            f"Target currently: {dst['time']}" if dst["time"] != "-"
            else "Target currently: (empty)"
        ), font=("Space Mono", 8), bg=MAIN_BG, fg=ACCENT_AMBER).pack(anchor=tk.W, pady=(4, 0))

        tk.Label(body, text="Reason (required for audit):", font=("Space Mono", 8, "bold"),
                 bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(10, 2))
        reason_var = ttk.StringVar()
        reason_entry = ttk.Entry(body, textvariable=reason_var, width=40)
        reason_entry.pack(anchor=tk.W, ipady=2)

        def _execute():
            _drag_dbg(f"dialog _execute: reason={reason_var.get().strip()!r}")
            if not reason_var.get().strip():
                _drag_dbg("dialog _execute: missing reason -> error shown")
                Messagebox.show_error("Please provide a reason for this move.", "Missing Reason", parent=win)
                return
            _drag_dbg("dialog _execute: confirmed -> calling _perform_cell_move")
            win.destroy()
            self._perform_cell_move(src, dst, reason_var.get().strip())

        btn_frame = tk.Frame(win, bg=MAIN_BG)
        btn_frame.pack(fill=tk.X, padx=14, pady=(2, 10))
        ttk.Button(btn_frame, text="✅ Move", bootstyle=SUCCESS, command=_execute, width=10).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="❌ Cancel", bootstyle=SECONDARY, command=win.destroy, width=10).pack(side=tk.RIGHT, padx=4)

        win.bind("<Return>", lambda e: _execute())
        win.bind("<Escape>", lambda e: win.destroy())
        reason_entry.focus_set()

    def _perform_cell_move(self, src, dst, reason):
        """Applies the move reliably via the DAY_PROGRAM override path.

        On night-shift days (e.g. schedule "18 -> 02") the enriched grid
        re-pairs raw punches chronologically, so the historical
        add_manual_punch + delete_manual_punch move executes but the grid
        re-pairs the records and the move *never sticks visually*.  Writing
        the DAY_PROGRAM override pins the exact slots verbatim (same
        deterministic mechanism as execution/move_punch_cli.py).
        """
        admin = self._current_admin_name()
        dst_punch_date = dst["date"]

        _drag_dbg(f"perform: src={src} dst={dst} dst_punch_date={dst_punch_date}")

        ok, msg = self.service.move_punch_slot(
            reg_number=src["reg"],
            src_date=src["date"],
            src_col=src["col"],
            dst_date=dst_punch_date,
            dst_col=dst["col"],
            admin_name=admin,
            reason=reason,
        )
        _drag_dbg(f"perform: move_punch_slot ok={ok} msg={msg!r}")
        if not ok:
            self._transfer_status.configure(text=f"❌ {msg}", fg=DANGER_ROSE)
            Messagebox.show_error(msg, "Error", parent=self)
            return
        self._transfer_status.configure(text=f"✅ Moved {src['time']} {src['col']} → {dst['col']}", fg=SUCCESS_EMERALD)
        _drag_dbg("perform: reloading records...")
        self._deferred_reload_records()

    # ── Keyboard editing (Excel-like fast correction) ──────────────────────
    #
    # Works on the armed punch cell (click to arm, like the cell-move flow):
    #   • type a time character            → edit dialog pre-filled with it
    #   • Enter / F2                       → edit dialog with current value
    #   • Tab / Shift+Tab                  → move the cursor to the next/prev
    #                                        punch column (IN1→OUT1→IN2→OUT2)
    #   • Ctrl+← / Ctrl+→ / Ctrl+↑ / Ctrl+↓→ move the VALUE to the adjacent
    #                                        column / row (audit dialog)
    #   • Delete                           → remove the punch (audit dialog)
    #   • Escape                           → cancel (existing binding)
    # ────────────────────────────────────────────────────────────────────────
    def _update_move_hint(self):
        """Refreshes the status-bar hint for the armed punch cell."""
        if not hasattr(self, "_transfer_status"):
            return
        try:
            src = self._drag_src
            if not src:
                self._transfer_status.configure(text="", fg="#94A3B8")
                return
            shown = src["time"] if src["time"] != "-" else "(empty)"
            self._transfer_status.configure(
                text=(
                    f"  SELECTED  {shown}  ({src['col']})  REG {src['reg']}  —  {src['date']}  —  "
                    "double-clic = edit  ·  tapez l'heure = éditer  ·  "
                    "2e clic / Ctrl+→ = déplacer  ·  Tab = colonne suivante  ·  "
                    "Del = retirer  ·  Esc = annuler"
                ),
                fg="#F59E0B",
            )
        except Exception:
            pass

    def _is_subtotal_row(self, item):
        """True when a treeview item is a subtotal/pad separator row."""
        try:
            values = self._records_table.view.item(item, "values")
            if not values:
                return True
            if any("Subtotal" in str(v) for v in values) or "─" in str(values[0]):
                return True
        except Exception:
            return True
        return False

    def _arm_cell(self, item, col_name, focus=True):
        """Arms any punch cell (empty or not) as the keyboard/move cursor.

        Reuses the same ``_drag_src``/``_move_src_item`` state as the
        click-to-move flow so every existing move/edit path works unchanged.
        Returns True on success.
        """
        if not hasattr(self, "_records_table"):
            return False
        view = self._records_table.view
        try:
            values = view.item(item, "values")
        except Exception:
            return False
        if not values:
            return False
        if any("Subtotal" in str(v) for v in values) or "─" in str(values[0]):
            return False
        col_index = self._all_table_cols.index(col_name) if col_name in self._all_table_cols else None
        if col_index is None:
            return False
        cell = str(values[col_index]).strip() if len(values) > col_index else "-"
        if cell in ("-", "", "None"):
            cell = "-"
        reg_number = str(values[2]).strip() if len(values) > 2 else "-"
        if not reg_number or reg_number == "-":
            return False

        if self._drag_src is not None and self._move_src_item != item:
            self._cancel_move_src()
        self._drag_src = {
            "reg":  reg_number,
            "date": self._parse_iso_date(str(values[0])),
            "col":  col_name,
            "time": cell,
        }
        self._drag_moved = False
        self._move_src_item = item
        self._move_src_emp = str(values[3]).strip() if len(values) > 3 else ""
        try:
            current_tags = list(view.item(item, "tags") or [])
            if "move_src" not in current_tags:
                current_tags.append("move_src")
            view.item(item, tags=current_tags)
        except Exception:
            pass
        view.configure(cursor="fleur")
        if focus:
            try:
                view.focus_set()
            except Exception:
                pass
        self._update_move_hint()
        _drag_dbg(f"arm_cell item={item} col={col_name} src={self._drag_src}")
        return True

    def _armed_punch_cell(self):
        """(src, item, col) of the armed cell if it is a punch column."""
        src = self._drag_src
        if not src or src.get("col") not in PUNCH_COLS:
            return None
        return (src, self._move_src_item, src["col"])

    def _on_punch_keypress(self, event):
        """Typing a time character on the armed cell opens the edit dialog."""
        if event.state & 0x4 or event.state & 0x20000:
            return  # Ctrl / Alt combos handled by the dedicated bindings
        if not event.char or not event.char.isprintable():
            return
        if event.char.isspace():
            return
        if not re.fullmatch(r"[0-9:.\-]", event.char):
            return
        armed = self._armed_punch_cell()
        if not armed:
            return
        src = armed[0]
        emp = getattr(self, "_move_src_emp", "")  # before _cancel_move_src clears it
        self._open_inline_editor(
            col_name=src["col"],
            iso_date=src["date"],
            reg_number=src["reg"],
            _emp_name=emp,
            initial_text=event.char,
        )
        return "break"

    def _on_punch_edit(self, event):
        """Enter / F2 → edit the armed punch cell (current value pre-filled)."""
        armed = self._armed_punch_cell()
        if not armed:
            return
        src = armed[0]
        current = src["time"] if src["time"] != "-" else ""
        emp = getattr(self, "_move_src_emp", "")  # before _cancel_move_src clears it
        self._open_inline_editor(
            col_name=src["col"],
            iso_date=src["date"],
            reg_number=src["reg"],
            _emp_name=emp,
            current_time=current,
        )
        return "break"

    def _on_punch_tab(self, event):
        """Tab / Shift+Tab navigates across IN1→OUT1→IN2→OUT2 (wraps rows)."""
        if not self._drag_src or not self._move_src_item:
            return
        view = self._records_table.view
        items = list(view.get_children())
        try:
            idx = PUNCH_COLS.index(self._drag_src["col"])
        except ValueError:
            return
        shift = -1 if (event.state & 0x1) else 1  # Shift bit
        item = self._move_src_item
        dst_idx = idx + shift
        if 0 <= dst_idx < len(PUNCH_COLS):
            if self._arm_cell(item, PUNCH_COLS[dst_idx]):
                return "break"
            return
        # Wrap to the previous/next data row, same side of the grid.
        if item not in items:
            return
        row_idx = items.index(item)
        target = row_idx + shift
        while 0 <= target < len(items):
            if not self._is_subtotal_row(items[target]):
                if self._arm_cell(items[target], PUNCH_COLS[0 if shift == 1 else -1]):
                    return "break"
                return
            target += shift
        return "break"

    def _on_punch_ctrl_arrow(self, event):
        """Ctrl+arrow moves the armed VALUE to the adjacent column/row.

        Reuses ``_confirm_cell_move`` (audit reason dialog) + the audited
        service move — exactly the same path as a drag & drop.
        """
        if not self._drag_src or self._drag_src["time"] == "-":
            return
        if not self._move_src_item:
            return
        src = self._drag_src
        view = self._records_table.view
        item = self._move_src_item
        dst = None
        keysym = event.keysym

        if keysym in ("Right", "Left"):
            try:
                idx = PUNCH_COLS.index(src["col"])
            except ValueError:
                return
            shift = 1 if keysym == "Right" else -1
            dst_idx = idx + shift
            if not (0 <= dst_idx < len(PUNCH_COLS)):
                return
            dst_col = PUNCH_COLS[dst_idx]
            values = view.item(item, "values")
            if not values:
                return
            col_index = self._all_table_cols.index(dst_col)
            target_cell = str(values[col_index]).strip() if len(values) > col_index else "-"
            if target_cell in ("-", "", "None"):
                target_cell = "-"
            reg_number = str(values[2]).strip() if len(values) > 2 else "-"
            dst = {
                "reg":  reg_number,
                "date": self._parse_iso_date(str(values[0])),
                "col":  dst_col,
                "time": target_cell,
            }
        elif keysym in ("Down", "Up"):
            items = list(view.get_children())
            if item not in items:
                return
            shift = 1 if keysym == "Down" else -1
            target = items.index(item) + shift
            while 0 <= target < len(items):
                if not self._is_subtotal_row(items[target]):
                    break
                target += shift
            else:
                return
            values = view.item(items[target], "values")
            if not values:
                return
            col_index = self._all_table_cols.index(src["col"])
            target_cell = str(values[col_index]).strip() if len(values) > col_index else "-"
            if target_cell in ("-", "", "None"):
                target_cell = "-"
            reg_number = str(values[2]).strip() if len(values) > 2 else "-"
            dst = {
                "reg":  reg_number,
                "date": self._parse_iso_date(str(values[0])),
                "col":  src["col"],
                "time": target_cell,
            }

        if dst is None:
            return
        if (src["reg"], src["date"], src["col"]) == (dst["reg"], dst["date"], dst["col"]):
            return
        _drag_dbg(f"ctrl-arrow move src={src} dst={dst}")
        self._cancel_move_src()
        self._confirm_cell_move(src, dst)
        return "break"

    def _on_punch_delete(self, event):
        """Delete removes the armed punch (audit dialog)."""
        armed = self._armed_punch_cell()
        if not armed:
            return
        src = armed[0]
        if src["time"] == "-":
            return
        self._cancel_move_src()
        self._remove_punch_for_slot(src["reg"], src["date"], src["col"], src["time"])
        return "break"

    def _set_status_for_date(self, reg_number, iso_date, new_status):
        """Applies a single status override for one employee/date with status feedback."""
        if not self._is_current_admin():
            Messagebox.show_error("You do not have permission to modify attendance records.", "Access Denied", parent=self)
            return
        self._transfer_status.configure(text=f"⏳ Saving status {new_status}...", fg=ACCENT_BLUE)
        try:
            ok, msg = self.service.save_status_correction(
                reg_number=reg_number, shift_date=iso_date,
                status_code=new_status, admin_name=self._current_admin_name()
            )
            if ok:
                self._transfer_status.configure(text=f"✅ {msg} ({new_status}).", fg=SUCCESS_EMERALD)
                self._deferred_reload_records()
            else:
                self._transfer_status.configure(text=f"❌ {msg}.", fg=DANGER_ROSE)
                Messagebox.show_error(msg, "Error", parent=self)
        except Exception as ex:
            self._transfer_status.configure(text=f"❌ {ex}.", fg=DANGER_ROSE)
            Messagebox.show_error(str(ex), "Error", parent=self)

    def _reset_status_override(self, reg_number, iso_date):
        """Removes the DAY_STATUS override so the day reverts to automatic computation."""
        if not self._is_current_admin():
            Messagebox.show_error("You do not have permission to reset statuses. Only administrators can perform this action.", "Access Denied", parent=self)
            return
        ok, msg = self.service.delete_status_correction(
            reg_number=reg_number, shift_date=iso_date, admin_name=self._current_admin_name()
        )
        if ok:
            self._transfer_status.configure(text=f"✅ {msg}.", fg=SUCCESS_EMERALD)
        else:
            self._transfer_status.configure(text=f"❌ {msg}.", fg=DANGER_ROSE)
        self._deferred_reload_records()

    def _open_status_picker_dialog(self, reg_number, emp_name, iso_date, current_stat):
        """Professional dialog with a grid of colored status buttons (generic menu path)."""
        if not self._is_current_admin():
            Messagebox.show_error("You do not have permission to modify attendance records.", "Access Denied", parent=self)
            return

        win = tk.Toplevel(self)
        win.title("Change Status")
        win.configure(bg=MAIN_BG)
        win.resizable(False, False)
        win.grab_set()
        win.transient(self)

        options = self._status_options()
        cols = 3
        rows = (len(options) + cols - 1) // cols
        W, H = 420, 80 + rows * 42 + 40
        self.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - W) // 2
        py = self.winfo_rooty() + (self.winfo_height() - H) // 2
        win.geometry(f"{W}x{H}+{px}+{py}")

        hdr = tk.Frame(win, bg=ACCENT_BLUE, height=46)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🎯  CHANGE STATUS", font=("JetBrains Mono", 10, "bold"),
                 bg=ACCENT_BLUE, fg="#ffffff").pack(side=tk.LEFT, padx=12, pady=0)

        body = tk.Frame(win, bg=MAIN_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        display = current_stat if current_stat not in ("-", "") else "Automatic"
        tk.Label(body, text=f"{emp_name}  (REG {reg_number})  —  {iso_date}",
                 font=("Space Mono", 8), bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor=tk.W)
        tk.Label(body, text=f"Current status: {display}",
                 font=("Space Mono", 9, "bold"), bg=MAIN_BG, fg=TEXT_HIGH).pack(anchor=tk.W, pady=(2, 8))

        grid = tk.Frame(body, bg=MAIN_BG)
        grid.pack(fill=tk.BOTH, expand=True)

        def _apply(code):
            self._set_status_for_date(reg_number, iso_date, code)
            win.destroy()

        for i, (code, name, color) in enumerate(options):
            r, c = divmod(i, cols)
            fg = self._text_color_for(color)
            tk.Button(grid, text=f"{code}\n{name}", font=("Space Mono", 8, "bold"),
                      bg=color, fg=fg, activebackground=color, activeforeground=fg,
                      relief=tk.FLAT, cursor="hand2", bd=0, padx=4, pady=2,
                      command=lambda c=code: _apply(c)
                      ).grid(row=r, column=c, sticky="nsew", padx=3, pady=3)

        for i in range(cols):
            grid.columnconfigure(i, weight=1)

        btn_frame = tk.Frame(win, bg=MAIN_BG)
        btn_frame.pack(fill=tk.X, padx=14, pady=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", bootstyle=SECONDARY, command=win.destroy, width=10).pack(side=tk.RIGHT)
        win.bind("<Escape>", lambda e: win.destroy())

    def _reset_schedule_override(self, reg_number, iso_date):
        """Removes the DAY_SCHEDULE override so the day reverts to automatic resolution."""
        if not self._is_current_admin():
            Messagebox.show_error("You do not have permission to reset schedules. Only administrators can perform this action.", "Access Denied", parent=self)
            return
        ok, msg = self.service.delete_schedule_correction(
            reg_number=reg_number, shift_date=iso_date, admin_name=self._current_admin_name()
        )
        if ok:
            self._transfer_status.configure(text=f"✅ {msg}.", fg=SUCCESS_EMERALD)
        else:
            self._transfer_status.configure(text=f"❌ {msg}.", fg=DANGER_ROSE)
        self._deferred_reload_records()

    def _open_change_schedule_dialog(self, reg_number, emp_name, iso_date, current_sched):
        """Opens a professional dialog that lets the user override the schedule for a single day."""
        if not self._is_current_admin():
            Messagebox.show_error("You do not have permission to modify attendance records.", "Access Denied", parent=self)
            return
        try:
            schedules = self.service.get_all_work_schedules()
        except Exception:
            Messagebox.show_warning("Could not load schedules from the database.", "Error", parent=self)
            return
        if not schedules:
            Messagebox.show_warning("No schedules found in the database.", "No Schedules")
            return

        sched_names = [s.name for s in schedules]
        sched_by_name = {s.name: s for s in schedules}
        # Only pre-select if current_sched is a valid known schedule name
        initial = current_sched if (current_sched and current_sched in sched_names) else ""

        win = tk.Toplevel(self)
        win.title("Change Schedule")
        win.configure(bg=MAIN_BG)
        win.resizable(False, False)
        win.grab_set()
        win.transient(self)

        W, H = 460, 340
        self.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - W) // 2
        py = self.winfo_rooty() + (self.winfo_height() - H) // 2
        win.geometry(f"{W}x{H}+{px}+{py}")

        # ── Header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg=ACCENT_BLUE, height=46)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🕒  CHANGE SCHEDULE", font=("JetBrains Mono", 10, "bold"),
                 bg=ACCENT_BLUE, fg="#ffffff").pack(side=tk.LEFT, padx=12, pady=0)

        # ── Body ─────────────────────────────────────────────────────────────
        body = tk.Frame(win, bg=MAIN_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        tk.Label(body, text=f"Employee:  {emp_name}  (REG {reg_number})",
                 font=("Space Mono", 8), bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor=tk.W)
        tk.Label(body, text=f"Date:  {iso_date}     •     Current: {current_sched}",
                 font=("Space Mono", 8), bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(1, 8))

        tk.Label(body, text="Select Schedule:", font=("Space Mono", 9, "bold"),
                 bg=MAIN_BG, fg=TEXT_HIGH).pack(anchor=tk.W)

        sched_var = ttk.StringVar(value=initial)
        cb = ttk.Combobox(body, textvariable=sched_var, values=sched_names, state="readonly", width=38)
        cb.pack(anchor=tk.W, pady=4, fill=tk.X)
        if initial:
            cb.set(initial)

        # Live preview of the selected schedule (times, break, hours, days)
        preview = tk.Label(body, text="", font=("Space Mono", 8), bg=MAIN_BG,
                           fg=ACCENT_BLUE, justify=tk.LEFT)
        preview.pack(anchor=tk.W, pady=(6, 0))

        def _fmt_sched(s):
            bs = s.break_start or "-"
            be = s.break_end or "-"
            days = s.days_of_week or "All days"
            minutes = int(getattr(s, "compte_minute", 0) or 0)
            return (f"  {s.start_time}  →  {s.end_time}    Break {bs}-{be}\n"
                    f"  {s.total_hours}h ({minutes} min)   •   {days}")

        def _refresh_preview(*_):
            s = sched_by_name.get(sched_var.get())
            if s:
                preview.configure(text=_fmt_sched(s), fg=ACCENT_BLUE)
            else:
                preview.configure(text="  Select a schedule to preview its times.", fg=TEXT_MUTED)

        cb.bind("<<ComboboxSelected>>", _refresh_preview)
        _refresh_preview()

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_frame = tk.Frame(win, bg=MAIN_BG)
        btn_frame.pack(fill=tk.X, padx=16, pady=(4, 12))

        def _save(event=None):
            chosen = sched_var.get().strip()
            if not chosen or chosen not in sched_names:
                Messagebox.show_warning("Please select a valid schedule from the list.", "No Selection", parent=win)
                return
            try:
                ok, msg = self.service.save_schedule_correction(
                    reg_number=reg_number,
                    shift_date=iso_date,
                    schedule_name=chosen,
                    admin_name=self._current_admin_name()
                )
                if ok:
                    self._transfer_status.configure(text=f"✅ {msg}.", fg=SUCCESS_EMERALD)
                    win.destroy()
                    self._deferred_reload_records()
                else:
                    Messagebox.show_error(msg, "Error", parent=win)
            except Exception as ex:
                Messagebox.show_error(str(ex), "Error", parent=win)

        ttk.Button(btn_frame, text="✅ Save", bootstyle=SUCCESS, command=_save, width=10).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(btn_frame, text="❌ Cancel", bootstyle=SECONDARY, command=win.destroy, width=10).pack(side=tk.RIGHT)
        win.bind("<Return>", _save)
        win.bind("<Escape>", lambda e: win.destroy())

    # ─── READ-ONLY DETAIL CARD ────────────────────────────────────────────────
    def _open_record_detail_card(self, values):
        """Opens a premium read-only detail popup for a selected attendance row.

        The gridview is fixed and cannot be modified inline.
        This card is purely informational — all edits are performed through
        the dedicated toolbar buttons (FIX / ADD PUNCH, RECALCULATE).
        """
        if not values or len(values) < 5:
            return

        # Map positional values to named fields
        cols = ["DATE", "DEPT", "REG", "EMPLOYEE", "ROLE", "STAT",
                "SCHED", "IN 1", "OUT 1", "IN 2", "OUT 2",
                "ATT.", "WORK", "DIFF", "NOTE", "MACH.", "SYNC"]
        data = {cols[i]: str(values[i]).strip() if i < len(values) else "-"
                for i in range(len(cols))}

        stat_code = data.get("STAT", "-") or "-"

        # Resolve status color from tag palette
        stat_color = self._status_colors.get(stat_code, ACCENT_BLUE) if hasattr(self, "_status_colors") else ACCENT_BLUE
        try:
            hex_c = stat_color.lstrip("#")
            if len(hex_c) == 6:
                r2, g2, b2 = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
                stat_fg = "#000000" if ((0.299 * r2 + 0.587 * g2 + 0.114 * b2) / 255) > 0.6 else "#ffffff"
            else:
                stat_fg = "#ffffff"
        except Exception:
            stat_fg = "#ffffff"

        # ── Window ──────────────────────────────────────────────────────────
        win = tk.Toplevel(self)
        win.title("Attendance Record — Detail View")
        win.configure(bg=MAIN_BG)
        win.resizable(False, False)
        win.grab_set()
        win.transient(self)

        W = 560
        H = 480
        self.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - W) // 2
        py = self.winfo_rooty() + (self.winfo_height() - H) // 2
        win.geometry(f"{W}x{H}+{px}+{py}")

        # ── Header strip ────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg=ACCENT_BLUE, height=52)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="📋  ATTENDANCE RECORD", font=("JetBrains Mono", 11, "bold"),
                 bg=ACCENT_BLUE, fg="#ffffff").pack(side=tk.LEFT, padx=14, pady=0)

        # Status badge on the right side of header
        badge = tk.Label(hdr, text=f"  {stat_code}  ",
                         font=("JetBrains Mono", 12, "bold"),
                         bg=stat_color, fg=stat_fg,
                         padx=8, pady=2, relief="flat")
        badge.pack(side=tk.RIGHT, padx=14, pady=10)

        # ── Employee identity row ────────────────────────────────────────────
        id_row = tk.Frame(win, bg=PANEL_BG, pady=8)
        id_row.pack(fill=tk.X, padx=0)

        tk.Label(id_row, text=data.get("EMPLOYEE", "-"),
                 font=("JetBrains Mono", 10, "bold"),
                 bg=PANEL_BG, fg=TEXT_HIGH).pack(side=tk.LEFT, padx=14)

        tk.Label(id_row, text=f"REG {data.get('REG', '-')}  |  {data.get('DEPT', '-')}",
                 font=("Space Mono", 8),
                 bg=PANEL_BG, fg=TEXT_MUTED).pack(side=tk.LEFT, padx=6)

        tk.Label(id_row, text=data.get("DATE", "-"),
                 font=("Space Mono", 9, "bold"),
                 bg=PANEL_BG, fg=ACCENT_AMBER).pack(side=tk.RIGHT, padx=14)

        tk.Frame(win, bg=BORDER_COLOR, height=1).pack(fill=tk.X)

        # ── Main content: two-column grid ────────────────────────────────────
        body = tk.Frame(win, bg=MAIN_BG, padx=16, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        LEFT_FIELDS = [
            ("Schedule",    data.get("SCHED", "-")),
            ("Role",        data.get("ROLE", "-")),
            ("Machine",     data.get("MACH.", "-")),
            ("Last Sync",   data.get("SYNC", "-")),
        ]
        RIGHT_FIELDS = [
            ("Attendance",  data.get("ATT.", "-")),
            ("Work Time",   data.get("WORK", "-")),
            ("Difference",  data.get("DIFF", "-")),
            ("Note",        data.get("NOTE", "-") or "—"),
        ]

        def _field(parent, label, value, col, row, diff_color=None):
            cell = tk.Frame(parent, bg=MAIN_BG)
            cell.grid(row=row, column=col, sticky="w", padx=(0, 24), pady=3)
            tk.Label(cell, text=label.upper(),
                     font=("Space Mono", 7), bg=MAIN_BG, fg=TEXT_MUTED,
                     anchor="w").pack(anchor="w")
            fg = diff_color or TEXT_HIGH
            tk.Label(cell, text=value or "—",
                     font=("JetBrains Mono", 9, "bold"), bg=MAIN_BG, fg=fg,
                     anchor="w").pack(anchor="w")

        for i, (lbl, val) in enumerate(LEFT_FIELDS):
            _field(body, lbl, val, col=0, row=i)
        for i, (lbl, val) in enumerate(RIGHT_FIELDS):
            diff_col = None
            if lbl == "Difference" and val not in ("-", "—", ""):
                diff_col = SUCCESS_EMERALD if val.startswith("+") else DANGER_ROSE
            _field(body, lbl, val, col=1, row=i, diff_color=diff_col)

        # ── Punch Timeline ───────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER_COLOR, height=1).pack(fill=tk.X, padx=16)
        tl_frame = tk.Frame(win, bg=MAIN_BG, pady=8)
        tl_frame.pack(fill=tk.X, padx=16)

        tk.Label(tl_frame, text="PUNCH TIMELINE",
                 font=("Space Mono", 7), bg=MAIN_BG, fg=TEXT_MUTED).pack(anchor="w")

        tl_row = tk.Frame(tl_frame, bg=MAIN_BG)
        tl_row.pack(fill=tk.X, pady=4)

        PUNCH_SLOTS = [
            ("IN 1",  data.get("IN 1",  "-"), "#3DDC84"),   # green
            ("OUT 1", data.get("OUT 1", "-"), ACCENT_AMBER), # amber
            ("IN 2",  data.get("IN 2",  "-"), "#3DDC84"),   # green
            ("OUT 2", data.get("OUT 2", "-"), ACCENT_AMBER), # amber
        ]
        for slot_lbl, slot_val, slot_color in PUNCH_SLOTS:
            slot = tk.Frame(tl_row, bg=PANEL_BG, padx=10, pady=6,
                            highlightbackground=slot_color if slot_val != "-" else BORDER_COLOR,
                            highlightthickness=1 if slot_val != "-" else 0)
            slot.pack(side=tk.LEFT, padx=4, fill=tk.Y)
            tk.Label(slot, text=slot_lbl,
                     font=("Space Mono", 7), bg=PANEL_BG,
                     fg=slot_color if slot_val != "-" else TEXT_MUTED).pack()
            tk.Label(slot, text=slot_val if slot_val != "-" else "—",
                     font=("JetBrains Mono", 9, "bold"), bg=PANEL_BG,
                     fg=TEXT_HIGH if slot_val != "-" else TEXT_MUTED).pack()

        # ── Footer buttons ───────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER_COLOR, height=1).pack(fill=tk.X)
        foot = tk.Frame(win, bg=PANEL_BG, pady=8)
        foot.pack(fill=tk.X)

        reg = data.get("REG", "-")

        ttk.Button(
            foot, text="📜  Audit Trail", bootstyle="secondary-outline",
            command=lambda: [win.destroy(), self.view_audit_for_employee(reg)]
        ).pack(side=tk.LEFT, padx=10)

        ttk.Button(
            foot, text="Close", bootstyle="dark",
            command=win.destroy
        ).pack(side=tk.RIGHT, padx=10)

        # Hint label
        tk.Label(foot,
                 text="Use  ✚ FIX / ADD PUNCH  or  ⟳ RECALCULATE  to modify records.",
                 font=("Space Mono", 7), bg=PANEL_BG, fg=TEXT_MUTED).pack(side=tk.LEFT, padx=6)

    # ─────────────────────────────────────────────────────────────────────────

    def _open_manual_punch_dialog_from_btn(self):
        """Wrapper to open the dialog from the explicit UI button, requiring a row selection."""
        sel = self._records_table.view.selection()
        if not sel:
            Messagebox.show_warning("Please select a record from the table first.", "Selection Required", parent=self)
            return
            
        values = self._records_table.view.item(sel[0], "values")
        
        date_str = values[0]
        iso_date = self._parse_iso_date(date_str)
        reg_number = values[2]
        emp_name = values[3]
        current_times = self._extract_current_times(values)
        
        self._open_manual_punch_dialog(reg_number, emp_name, iso_date, current_times)

    def _recalculate_attendance(self):
        """Recalculates attendance by analyzing punch patterns and auto-assigning schedules."""
        # Admin check
        is_admin = False
        if getattr(self.main_window, "current_user", None):
            if self.main_window.current_user.role == 'admin':
                is_admin = True
        if not is_admin:
            Messagebox.show_error(
                "You do not have permission to recalculate records. Please contact an administrator.",
                "Access Denied", parent=self)
            return

        # Get current filters
        emp_filter = self._filter_emp.get().strip()
        start_date = self._filter_from_de.entry.get().strip()
        end_date = self._filter_to_de.entry.get().strip()

        reg_numbers = []
        target_desc = ""

        if emp_filter:
            # Single Employee Extraction
            import re
            reg_match = re.search(r'\((\w+)\)', emp_filter) # Support alphanumeric
            if reg_match:
                reg_numbers.append(reg_match.group(1))
            elif emp_filter.isalnum():
                reg_numbers.append(emp_filter)
            else:
                reg_match_any = re.search(r"\(([^)]+)\)", emp_filter)
                if reg_match_any:
                    reg_numbers.append(reg_match_any.group(1).strip())
            
            if not reg_numbers:
                Messagebox.show_warning(
                    "Could not extract REG number from employee filter.\nFormat: 'Name (REG)'",
                    "Invalid Filter", parent=self)
                return
            target_desc = f"Employee {emp_filter}"
        else:
            # Bulk Extraction from visible Table
            if not self._records_table or not self._records_table.view.get_children():
                Messagebox.show_warning(
                    "Please search for employees first or select a specific employee to recalculate.",
                    "No Target Data", parent=self)
                return
            
            # Collect unique REG numbers from the REG column (index 2)
            seen_regs = set()
            for item_id in self._records_table.view.get_children():
                values = self._records_table.view.item(item_id, 'values')
                if values and len(values) > 2:
                    reg = str(values[2]).strip()
                    if reg and reg != "-":
                        seen_regs.add(reg)
            
            reg_numbers = list(seen_regs)
            if not reg_numbers:
                Messagebox.show_warning("No valid Registration Numbers found in current view.", "Bulk Error", parent=self)
                return
            
            target_desc = f"ALL {len(reg_numbers)} employees in current view"
        
        # Confirm with user
        ans = Messagebox.show_question(
            f"Recalculate attendance for:\n{target_desc}\n"
            f"Period: {start_date} to {end_date}?\n\n"
            f"This will analyze raw punch patterns and\n"
            f"auto-assign the closest matching schedule for each day.",
            "Confirm Recalculation",
            buttons=["Cancel:secondary", "Recalculate:primary"],
            parent=self
        )
        if ans != "Recalculate":
            return

        # Get admin name
        admin_name = "System"
        if self.main_window and self.main_window.current_user:
            admin_name = self.main_window.current_user.username

        # UI Setup for progress
        self._prog_frame.pack(side=tk.TOP, fill=tk.X, pady=3)

        self._progress_var.set(0)
        self._progress_pct_label.configure(text="0%")
        self._progress_eta_label.configure(text="Analyzing records...")

        
        # Run bulk recalculation in background
        self.task_manager.run_task(
            task_id="recalculate_attendance",
            name=f"🔄 Recalculating {len(reg_numbers)} employees",
            target=self._recalculate_attendance_bg,
            args=(reg_numbers, start_date, end_date, admin_name),
            on_progress=self._update_progress_ui,
            on_complete=self._finalize_recalculation_ui,
            on_error=self._on_recalculation_error
        )

    def _on_recalculation_error(self, err):
        """Handle errors during recalculation."""
        self.status_bar.set_status(f"Error: {err}", bootstyle=DANGER)
        Messagebox.show_error(f"Recalculation failed: {err}", "Critical Error")
        self.after(3000, lambda: self._safe_pack_forget("_prog_frame"))



    def _recalculate_attendance_bg(self, reg_numbers, start_date, end_date, admin_name, progress_callback=None):
        total_days = 0
        total_corrections = 0
        errors = []

        from contragest.core.database import SessionLocal
        from contragest.features.pointage.service import PointageService
        bg_session = SessionLocal()
        bg_service = PointageService(bg_session)

        try:
            for i, reg in enumerate(reg_numbers):
                try:
                    if progress_callback:
                        progress_callback(i + 1, len(reg_numbers), f"REG {reg}")

                    days, corrections, summary = bg_service.batch_recalculate(
                        registration_number=reg,
                        start_date=start_date,
                        end_date=end_date,
                        admin_name=admin_name,
                    )
                    total_days += days
                    total_corrections += corrections
                except Exception as e:
                    errors.append(f"REG {reg}: {str(e)}")
        finally:
            bg_session.close()

        return total_days, total_corrections, errors, len(reg_numbers)

    def _finalize_recalculation_ui(self, results):
        total_days, total_corrections, errors, count = results
        self.status_bar.set_status("Attendance Management Terminal Engaged")
        
        # Always refresh the grid with current filter state so the updated SCHED column
        # and recalculated values are immediately visible. Reset the loading guard first
        # so the reload is never silently skipped.
        self._loading_records = False
        self._load_recent_records()
        
        if not errors:
            msg = (
                f"\u2705 Recalculation complete.\n\n"
                f"Employees: {count}\n"
                f"Days processed: {total_days}\n"
                f"Corrections made: {total_corrections}"
            )
            Messagebox.show_info(msg, "Recalculation Complete", parent=self)
        elif total_corrections > 0:
            msg = (
                f"\u26a0\ufe0f Partial success \u2014 some employees failed.\n\n"
                f"Employees: {count}\n"
                f"Days processed: {total_days}\n"
                f"Corrections made: {total_corrections}\n\n"
                f"Errors ({len(errors)}):\n" + "\n".join(errors[:5])
            )
            Messagebox.show_warning(msg, "Recalculation Partial", parent=self)
        else:
            Messagebox.show_error(
                f"Recalculation failed for all targets:\n" + "\n".join(errors[:5]),
                "Recalculation Failed", parent=self
            )
        self._progress_var.set(100)
        self.after(3000, lambda: self._safe_pack_forget("_prog_frame"))



    def _extract_current_times(self, values):
        """Extract existing punch times from table row values (indices 7-10 after Status move)."""
        return {
            "Check In 1": values[7] if len(values) > 7 and values[7] != "-" else "",
            "Check Out 1": values[8] if len(values) > 8 and values[8] != "-" else "",
            "Check In 2": values[9] if len(values) > 9 and values[9] != "-" else "",
            "Check Out 2": values[10] if len(values) > 10 and values[10] != "-" else "",
        }

    def _open_manual_punch_dialog(self, reg_number, emp_name, date_str, current_times=None):
        # Admin check
        is_admin = False
        if getattr(self.main_window, "current_user", None):
            if self.main_window.current_user.role == 'admin':
                is_admin = True
                
        if not is_admin:
            Messagebox.show_error("You do not have permission to modify attendance records. Please contact an administrator.", "Access Denied", parent=self)
            return
            
        dlg = ManualPunchDialog(
            parent=self, 
            service=self.service, 
            reg_number=reg_number, 
            emp_name=emp_name, 
            date_str=date_str, 
            refresh_callback=self._deferred_reload_records,
            current_times=current_times
        )
        dlg.transient(self)
        dlg.grab_set()

    def _open_edit_employee_dialog(self, reg_number):
        from contragest.core.database import Employee
        from contragest.features.employee_manager.data_entry_form import DataEntryForm
        from ttkbootstrap.dialogs import Messagebox
        
        # Admin check
        is_admin = False
        if getattr(self.main_window, "current_user", None):
            if self.main_window.current_user.role == 'admin':
                is_admin = True
                
        if not is_admin:
            Messagebox.show_error("You do not have permission to modify employee records. Please contact an administrator.", "Access Denied", parent=self)
            return

        emp = self.service.session.query(Employee).filter_by(registration_number=reg_number).first()
        if not emp:
            Messagebox.show_error(f"Employee with REG NUMBER {reg_number} not found.", "Error", parent=self)
            return
            
        dlg = DataEntryForm(
            parent=self, 
            mode="edit", 
            employee_id=emp.id, 
            on_save_callback=self._load_recent_records
        )

    def _on_record_double_click(self, event):
        """Double-click behavior.

        • Punch column (IN 1 / OUT 1 / IN 2 / OUT 2): opens the quick-punch
          edit dialog for a fast time correction. Mouse-driven, so it works
          even when the treeview does not have keyboard focus.
        • Any other column: opens the read-only Detail Card popup.
        """
        try:
            item = self._records_table.view.identify_row(event.y)
            if not item:
                _drag_dbg(f"double-click ignored (no row) y={event.y}")
                return

            values = self._records_table.view.item(item, "values")
            if not values:
                _drag_dbg(f"double-click ignored (no values) item={item!r}")
                return

            reg_number = str(values[2]).strip() if len(values) > 2 else "-"
            formatted_date = str(values[0]).strip() if len(values) > 0 else "-"

            # Don't open popup for empty / pad rows
            if not reg_number or reg_number == "-" or not formatted_date or formatted_date == "-":
                _drag_dbg(f"double-click ignored (pad row) reg={reg_number!r} date={formatted_date!r}")
                return

            # Fast path: double-click directly on a punch cell → edit dialog.
            col_name = self._col_name_at(event.x)
            _drag_dbg(f"double-click item={item!r} col={col_name!r} reg={reg_number} date={formatted_date}")
            if col_name in ("IN 1", "OUT 1", "IN 2", "OUT 2"):
                col_index = self._all_table_cols.index(col_name)
                cell = str(values[col_index]).strip() if len(values) > col_index else "-"
                if cell in ("-", "", "None"):
                    cell = ""
                emp_name = str(values[3]).strip() if len(values) > 3 else ""
                iso_date = self._parse_iso_date(formatted_date)
                _drag_dbg(f"double-click opening dialog col={col_name} reg={reg_number} current_time={cell!r}")
                self._open_quick_punch_dialog(
                    reg_number=reg_number,
                    emp_name=emp_name,
                    iso_date=iso_date,
                    col_name=col_name,
                    current_time=cell,
                )
                return
            if col_name == "NOTE":
                current_note = str(values[14]).strip() if len(values) > 14 else "-"
                emp_name = str(values[3]).strip() if len(values) > 3 else ""
                iso_date = self._parse_iso_date(formatted_date)
                _drag_dbg(f"double-click NOTE editor reg={reg_number} note={current_note!r}")
                self._open_note_editor_dialog(
                    reg_number=reg_number,
                    emp_name=emp_name,
                    iso_date=iso_date,
                    current_note=current_note,
                )
                return
        except Exception as exc:
            _drag_dbg(f"double-click EXCEPTION: {exc!r}")

        self._open_record_detail_card(values)

    def _apply_status_to_selection(self, new_status):
        """Applies the selected status to all highlighted rows in the treeview."""
        if not new_status:
            return

        if not self._is_current_admin():
            Messagebox.show_error("You do not have permission to modify attendance records.", "Access Denied", parent=self)
            return

        selection = self._records_table.view.selection()
        if not selection:
            Messagebox.show_warning("Please select one or more records from the table to update their status.", "Selection Required", parent=self)
            return
            
        # Confirm action for multiple rows
        if len(selection) > 1:
            confirm = Messagebox.yesno(f"Are you sure you want to change the status to '{new_status}' for {len(selection)} records?", "Confirm Bulk Update", parent=self)
            if confirm != "yes":
                return

        admin_name = self._current_admin_name()
        
        success_count = 0
        error_msgs = []
        
        for item in selection:
            values = self._records_table.view.item(item, "values")
            if "─" in str(values[0]) or any("Subtotal" in str(v) for v in values):
                continue
            reg_number = values[2]
            iso_date = self._parse_iso_date(values[0])
            
            success, msg = self.service.save_status_correction(reg_number, iso_date, new_status, admin_name)
            if success:
                success_count += 1
            else:
                error_msgs.append(f"Reg {reg_number}: {msg}")
        
        if success_count > 0:
            self._deferred_reload_records()
        
        if error_msgs:
            error_text = "\n".join(error_msgs[:5]) + ("\n..." if len(error_msgs) > 5 else "")
            Messagebox.show_error(f"Updates completed with {len(error_msgs)} errors:\n{error_text}", "Update Partial Failure")

    def _apply_schedule_to_selection(self, new_schedule):
        """Applies the selected schedule to all highlighted rows in the treeview."""
        if not new_schedule:
            return

        if not self._is_current_admin():
            Messagebox.show_error("You do not have permission to modify attendance records.", "Access Denied", parent=self)
            return

        selection = self._records_table.view.selection()
        if not selection:
            Messagebox.show_warning("Please select one or more records from the table to update their schedule.", "Selection Required", parent=self)
            return

        # Confirm action for multiple rows
        if len(selection) > 1:
            confirm = Messagebox.yesno(f"Are you sure you want to change the schedule to '{new_schedule}' for {len(selection)} records?", "Confirm Bulk Update", parent=self)
            if confirm != "yes":
                return

        admin_name = self._current_admin_name()

        success_count = 0
        error_msgs = []

        for item in selection:
            values = self._records_table.view.item(item, "values")
            if "─" in str(values[0]) or any("Subtotal" in str(v) for v in values):
                continue
            reg_number = values[2]
            iso_date = self._parse_iso_date(values[0])

            success, msg = self.service.save_schedule_correction(reg_number, iso_date, new_schedule, admin_name)
            if success:
                success_count += 1
            else:
                error_msgs.append(f"Reg {reg_number}: {msg}")

        if success_count > 0:
            self._deferred_reload_records()

        if error_msgs:
            error_text = "\n".join(error_msgs[:5]) + ("\n..." if len(error_msgs) > 5 else "")
            Messagebox.show_error(f"Updates completed with {len(error_msgs)} errors:\n{error_text}", "Update Partial Failure")

    def _on_record_select(self, event):
        """Shows detailed raw logs in a tooltip when a row is selected."""
        sel = self._records_table.view.selection()
        if not sel:
            self._tooltip.hide()
            return
            
        item = sel[0]
        if item == self._tooltip.last_item:
            return
            
        self._tooltip.last_item = item
        values = self._records_table.view.item(item, "values")
        
        # values = [Date, Dept, Reg, Emp, Role, Status, Sched, In1, Out1, In2, Out2, Atten, Work, Diff, Note, Mach, Sync]
        date_str = values[0]
        iso_date = self._parse_iso_date(date_str)
        reg_number = values[2]
        emp_name = values[3]
        dept_name = values[1]
        
        # Fetch raw punches from service using ISO date for DB query
        raw_punches = self.service.get_raw_attendance_detail(reg_number, iso_date)
        
        if not raw_punches:
            self._tooltip.hide()
            return

        # Structured data for the modern tooltip design
        employee_info = {
            "name": emp_name,
            "reg_number": reg_number,
            "dept": dept_name,
            "date": date_str
        }
        
        # Get schedule active on this specific date for inference in detail view
        from contragest.core.database import Employee
        emp_obj = self.session.query(Employee).filter_by(registration_number=reg_number).first()
        sched_obj = None
        if emp_obj:
            sched_obj = self.service.get_schedule_for_date(emp_obj.id, iso_date)

        processed_punches = []
        for p in raw_punches:
            p_time = p.punch_time[11:19]
            # Use 'Mach 1' format as in reference image
            p_mach = f"Mach {p.machine_id}" if p.machine_id is not None else "N/A"
            p_type_tuple = self.service.guess_punch_type(p.punch_time, sched_obj)
            p_type_str = f"{p_type_tuple[0].title()} {p_type_tuple[1]}"
            processed_punches.append({
                "time": p_time,
                "machine": p_mach,
                "type": p_type_str
            })

        # Position tooltip near mouse click/selection, but DEFER the show:
        # mapping a topmost window while the mouse button is still held down
        # breaks the button's event routing on Windows and silently kills the
        # drag & drop cell move. The drag handlers cancel this pending show as
        # soon as the pointer actually moves.
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        self._cancel_pending_tooltip()
        self._tooltip_after_id = self.after(
            300, lambda: self._show_record_tooltip(item, x, y, employee_info, processed_punches)
        )

    def _show_record_tooltip(self, item, x, y, employee_info, punches):
        """Actually maps the tooltip (deferred from selection, so it never
        appears mid-press and breaks the drag & drop)."""
        self._tooltip_after_id = None
        try:
            if not self.winfo_exists():
                return
            sel = self._records_table.view.selection()
            if not sel or sel[0] != item:
                return
        except Exception:
            return
        self._tooltip.show(x, y, employee_info=employee_info, punches=punches)

    def _clear_filters(self):
        if hasattr(self, "_filter_emp"):
            self._filter_emp.set("")
            self._filter_dept.set("")
            self._filter_type.set(tr("all_types"))
            
            # Reset inline grid filters if they exist
            self._clear_inline_filters()
            
            self._populate_filter_dropdowns()
        self._load_recent_records()

    def _build_schedules_tab(self):
        parent = self._tab_schedules

        paned = ttk.Panedwindow(parent, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=YES)

        # ── Schedule List (Left) ──
        list_frame = ttk.LabelFrame(paned, text=f"📋 {tr('schedule_admin')}")
        paned.add(list_frame, weight=3) 

        self._sched_table_frame = ttk.Frame(list_frame)
        self._sched_table_frame.pack(fill=BOTH, expand=YES, padx=3, pady=3)
        self._sched_table = None

        # ── Schedule Form (Right) ──
        form_frame = ttk.LabelFrame(paned, text=f"📝 {tr('schedule_admin')} Settings")
        paned.add(form_frame, weight=2)
        
        self.selected_schedule_id = None
        self._sched_vars = {}
        
        # Actions Row
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=X, padx=6, pady=3)
        
        ttk.Button(btn_frame, text=f"➕ {tr('new')}", command=self._clear_schedule_form, bootstyle=SUCCESS, width=10).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text=f"💾 {tr('save')}", command=self._save_schedule, bootstyle=SUCCESS, width=10).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text=f"❌ {tr('delete')}", command=self._delete_schedule, bootstyle=DANGER, width=10).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text=f"🔄", command=self._clear_schedule_form, bootstyle=INFO, width=4).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text="Sync to ZK", command=self._sync_schedule_to_zk, bootstyle=PRIMARY, width=12).pack(side=LEFT, padx=1)
        
        ttk.Separator(form_frame, orient=HORIZONTAL).pack(fill=X, padx=3, pady=(1, 3))
        
        # 1. Basic Info
        basic_lf = ttk.LabelFrame(form_frame, text="Basic Info")
        basic_lf.pack(fill=X, padx=6, pady=3, ipadx=3, ipady=3)
        
        ttk.Label(basic_lf, text=tr("schedule_name")).grid(row=0, column=0, sticky=W, pady=1)
        self._sched_vars["name"] = ttk.StringVar()
        ttk.Entry(basic_lf, textvariable=self._sched_vars["name"]).grid(row=0, column=1, sticky=EW, pady=1, padx=(3, 1))
        
        ttk.Label(basic_lf, text="Color").grid(row=1, column=0, sticky=W, pady=1)
        self._sched_vars["color_hex"] = ttk.StringVar(value="#0055ff")
        
        color_frame = ttk.Frame(basic_lf)
        color_frame.grid(row=1, column=1, sticky=EW, pady=1, padx=(3, 1))
        self._color_lbl = ttk.Label(color_frame, width=3, background=self._sched_vars["color_hex"].get())
        self._color_lbl.pack(side=LEFT, padx=(1, 3))
        ttk.Button(color_frame, text="Pick", command=self._pick_color, bootstyle="outline-secondary").pack(side=LEFT)
        basic_lf.columnconfigure(1, weight=1)

        # 2. Timing
        time_lf = ttk.LabelFrame(form_frame, text="Timing")
        time_lf.pack(fill=X, padx=6, pady=3, ipadx=3, ipady=3)
        
        # Smart Timing Input
        ttk.Label(time_lf, text="Smart Timing", font=("Space Mono", 9, "bold")).grid(row=0, column=0, sticky=W, pady=(1, 3))
        self._smart_timing_var = ttk.StringVar()
        self._smart_ent = ttk.Entry(time_lf, textvariable=self._smart_timing_var, bootstyle=INFO)
        self._smart_ent.grid(row=0, column=1, columnspan=3, sticky=EW, pady=(1, 3), padx=(3, 1))
        self._smart_ent.bind("<KeyRelease>", self._on_smart_timing_key)
        
        # Tooltip-like helper
        ttk.Label(time_lf, text="e.g., 8-12 and 18-22", font=("Space Mono", 8, "italic"), foreground="gray").grid(row=1, column=1, columnspan=3, sticky=W, padx=(3, 1))
        
        ttk.Separator(time_lf, orient=HORIZONTAL).grid(row=2, column=0, columnspan=4, sticky=EW, pady=6)
        
        time_fields = [
            ("Start", "start_time", "08:00"), ("End", "end_time", "17:00"),
            ("Break In", "break_start", "12:00"), ("Break Out", "break_end", "13:00")
        ]
        for i, (lbl, key, def_val) in enumerate(time_fields):
            row_idx, col = divmod(i, 2)
            row = row_idx + 3
            ttk.Label(time_lf, text=lbl).grid(row=row, column=col*2, sticky=W, padx=(10 if col else 0, 5), pady=1)
            self._sched_vars[key] = ttk.StringVar(value=def_val)
            ent = ttk.Entry(time_lf, textvariable=self._sched_vars[key], width=8, justify="center", font=("Space Mono", 9, "bold"))
            ent.grid(row=row, column=col*2+1, pady=1)
            ent.bind("<KeyRelease>", self._on_time_entry_key)
        
        time_lf.columnconfigure(1, weight=1)
        time_lf.columnconfigure(3, weight=1)

        # 3. Punch Windows
        win_lf = ttk.LabelFrame(form_frame, text="Punch Windows (HH:MM)")
        win_lf.pack(fill=X, padx=6, pady=3, ipadx=3, ipady=3)
        
        win_fields = [
            ("In Range Start", "debut_pointage_entree", "00:00"), ("In Range End", "fin_pointage_entree", "23:59"),
            ("Out Range Start", "debut_pointage_sortie", "00:00"), ("Out Range End", "fin_pointage_sortie", "23:59")
        ]
        for i, (lbl, key, def_val) in enumerate(win_fields):
            row, col = divmod(i, 2)
            ttk.Label(win_lf, text=lbl).grid(row=row, column=col*2, sticky=W, padx=(10 if col else 0, 5), pady=1)
            self._sched_vars[key] = ttk.StringVar(value=def_val)
            ent = ttk.Entry(win_lf, textvariable=self._sched_vars[key], width=8, justify="center", font=("Space Mono", 9, "bold"))
            ent.grid(row=row, column=col*2+1, pady=1)
            ent.bind("<KeyRelease>", self._on_time_entry_key)

        # 4. Rules & Grace Periods
        rules_lf = ttk.LabelFrame(form_frame, text="Rules & Tolerances")
        rules_lf.pack(fill=X, padx=6, pady=3, ipadx=3, ipady=3)
        
        ttk.Label(rules_lf, text="Late Grace (mn)").grid(row=0, column=0, sticky=W, pady=1)
        self._sched_vars["retard_tolere_mn"] = ttk.IntVar(value=0)
        ttk.Spinbox(rules_lf, from_=0, to=120, textvariable=self._sched_vars["retard_tolere_mn"], width=5).grid(row=0, column=1, sticky=W, pady=1)
        
        ttk.Label(rules_lf, text="Early Leave Grace (mn)").grid(row=0, column=2, sticky=W, padx=(6, 3), pady=1)
        self._sched_vars["depart_avance_tolere_mn"] = ttk.IntVar(value=0)
        ttk.Spinbox(rules_lf, from_=0, to=120, textvariable=self._sched_vars["depart_avance_tolere_mn"], width=5).grid(row=0, column=3, sticky=W, pady=1)

        self._sched_vars["pointe_entree_obligatoire"] = ttk.BooleanVar(value=True)
        ttk.Checkbutton(rules_lf, text="Check-In Required", variable=self._sched_vars["pointe_entree_obligatoire"], bootstyle="round-toggle").grid(row=1, column=0, columnspan=2, sticky=W, pady=3)
        
        self._sched_vars["pointe_sortie_obligatoire"] = ttk.BooleanVar(value=True)
        ttk.Checkbutton(rules_lf, text="Check-Out Required", variable=self._sched_vars["pointe_sortie_obligatoire"], bootstyle="round-toggle").grid(row=1, column=2, columnspan=2, sticky=W, padx=(6, 1), pady=3)

        # 5. Calculation
        calc_lf = ttk.LabelFrame(form_frame, text="Calculation Settings")
        calc_lf.pack(fill=X, padx=6, pady=3, ipadx=3, ipady=3)
        
        ttk.Label(calc_lf, text="Day Multiplier").grid(row=0, column=0, sticky=W, pady=1)
        self._sched_vars["compte_journee"] = ttk.DoubleVar(value=1.0)
        ttk.Spinbox(calc_lf, from_=0.0, to=5.0, increment=0.5, textvariable=self._sched_vars["compte_journee"], width=5).grid(row=0, column=1, sticky=W, pady=1)
        
        ttk.Label(calc_lf, text="Total Hours").grid(row=0, column=2, sticky=W, padx=(6, 3), pady=1)
        self._sched_vars["total_hours"] = ttk.DoubleVar(value=8.0)
        ttk.Spinbox(calc_lf, from_=0.0, to=24.0, increment=0.5, textvariable=self._sched_vars["total_hours"], width=5,
                    command=self._on_total_hours_changed).grid(row=0, column=3, sticky=W, pady=1)
        # Bind keyboard edits too
        self._sched_vars["total_hours"].trace_add("write", lambda *_: self._on_total_hours_changed())

        ttk.Label(calc_lf, text="Total Minutes").grid(row=1, column=0, sticky=W, pady=1)
        self._sched_vars["compte_minute"] = ttk.IntVar(value=480)
        ttk.Spinbox(calc_lf, from_=0, to=1440, increment=30, textvariable=self._sched_vars["compte_minute"], width=5,
                    command=self._on_total_minutes_changed).grid(row=1, column=1, sticky=W, pady=1)
        self._sched_vars["compte_minute"].trace_add("write", lambda *_: self._on_total_minutes_changed())
        
    def _on_time_entry_key(self, event):
        if event.keysym in ("BackSpace", "Delete", "Left", "Right", "Tab", "Shift_L", "Shift_R"):
            return
        widget = event.widget
        val = widget.get()
        digits = ''.join(filter(str.isdigit, val))
        
        if len(digits) > 4:
            digits = digits[:4]
            
        formatted = ""
        if len(digits) >= 2:
            formatted = digits[:2] + ":" + digits[2:]
            if formatted.endswith(":"):
                pass  # Keep empty colon
        else:
            formatted = digits
            
        if val != formatted:
            widget.delete(0, 'end')
            widget.insert(0, formatted)

    def _on_total_hours_changed(self):
        """When Total Hours changes, auto-update Total Minutes = hours * 60."""
        if getattr(self, "_syncing_calc", False):
            return
        try:
            self._syncing_calc = True
            hours = self._sched_vars["total_hours"].get()
            self._sched_vars["compte_minute"].set(int(hours * 60))
        except Exception:
            pass
        finally:
            self._syncing_calc = False

    def _on_total_minutes_changed(self):
        """When Total Minutes changes, reverse-sync Total Hours = minutes / 60."""
        if getattr(self, "_syncing_calc", False):
            return
        try:
            self._syncing_calc = True
            minutes = self._sched_vars["compte_minute"].get()
            self._sched_vars["total_hours"].set(round(minutes / 60.0, 2))
        except Exception:
            pass
        finally:
            self._syncing_calc = False

    def _on_smart_timing_key(self, event):
        val = self._smart_timing_var.get()
        if not val or len(val) < 3:
            self._smart_ent.configure(bootstyle=INFO)
            return
            
        from contragest.logic.scheduling import EmployeeScheduleConfig
        try:
            mapping = EmployeeScheduleConfig.suggest_shift_mapping(val)
            if mapping:
                for k, v in mapping.items():
                    if k in self._sched_vars:
                        self._sched_vars[k].set(v)
                self._smart_ent.configure(bootstyle=SUCCESS)
                # Auto-calculate total minutes if we have start/end
                if "start_time" in mapping and "end_time" in mapping:
                    self._recalc_total_minutes()
            else:
                self._smart_ent.configure(bootstyle=DANGER)
        except Exception:
            self._smart_ent.configure(bootstyle=DANGER)

    def _recalc_total_minutes(self):
        try:
            from datetime import datetime
            fmt = "%H:%M"
            
            def parse_time(t):
                if not t or not t.strip(): return None
                try: return datetime.strptime(t.strip(), fmt)
                except: return None
                
            def min_between(s, e):
                d = (e - s).total_seconds() / 60
                if d < 0: d += 1440
                return d

            s_dt = parse_time(self._sched_vars["start_time"].get())
            e_dt = parse_time(self._sched_vars["end_time"].get())
            if not s_dt or not e_dt: return
            
            bs_dt = parse_time(self._sched_vars.get("break_start", ttk.StringVar()).get())
            be_dt = parse_time(self._sched_vars.get("break_end", ttk.StringVar()).get())
            
            if bs_dt and be_dt:
                if min_between(s_dt, bs_dt) >= min_between(s_dt, e_dt):
                    diff = min_between(s_dt, e_dt) + min_between(bs_dt, be_dt)
                else:
                    diff = max(0, min_between(s_dt, e_dt) - min_between(bs_dt, be_dt))
            else:
                diff = min_between(s_dt, e_dt)
                
            if diff > 0:
                self._sched_vars["compte_minute"].set(int(diff))
        except: pass

    def _pick_color(self):
        from ttkbootstrap.dialogs.colorchooser import ColorChooserDialog
        cd = ColorChooserDialog()
        cd.show()
        if cd.result:
            color = self._get_valid_color(cd.result.hex)
            self._sched_vars["color_hex"].set(color)
            self._color_lbl.configure(background=color)

    def _get_valid_color(self, color):
        """Ensures the color is a valid hex string starting with #."""
        if not color:
            return "#0055ff"
        color_str = str(color).strip()
        if color_str.startswith("#"):
            return color_str
        try:
            # If it's a numeric string (like '16715535'), convert to hex
            val = int(color_str)
            # Ensure it's 6 digits, lowercase hex
            return f"#{val & 0xFFFFFF:06x}"
        except (ValueError, TypeError):
            return color_str

    def _calculate_work_time_str(self, start, end, b_start, b_end):
        """Calculates net work time considering standard breaks and split-shifts (where break encodes session 2)."""
        from datetime import datetime
        fmt = "%H:%M"
        
        def parse_time(t):
            if not t or not t.strip(): return None
            try: return datetime.strptime(t.strip(), fmt)
            except: return None
            
        def min_between(s, e):
            d = (e - s).total_seconds() / 60
            if d < 0: d += 1440
            return d

        s_dt = parse_time(start)
        e_dt = parse_time(end)
        bs_dt = parse_time(b_start)
        be_dt = parse_time(b_end)
        
        if not s_dt or not e_dt:
            return "-"
            
        if bs_dt and be_dt:
            # Check for split shift: second session starts at break_start
            m_s_e = min_between(s_dt, e_dt)
            m_s_bs = min_between(s_dt, bs_dt)
            
            if m_s_bs >= m_s_e:
                # Split shift: total = (start->end) + (break_start->break_end)
                total_min = min_between(s_dt, e_dt) + min_between(bs_dt, be_dt)
            else:
                # Normal break subtraction
                m_brk = min_between(bs_dt, be_dt)
                total_min = max(0, min_between(s_dt, e_dt) - m_brk)
        else:
            total_min = min_between(s_dt, e_dt)
            
        hours = int(total_min // 60)
        minutes = int(total_min % 60)
        return f"{hours:02d}:{minutes:02d}"

    def _load_schedules(self):
        schedules = self.service.get_all_schedules()
        cols = ["ID", tr("schedule_name"), "Timing", "Work Time", "Check-In Window", "Check-Out Window", "Grace (In/Out)", "Multiplier"]
        rows = []
        for s in schedules:
            timing = f"{s.start_time} - {s.end_time}"
            work_time = self._calculate_work_time_str(s.start_time, s.end_time, s.break_start, s.break_end)
            in_win = f"{s.debut_pointage_entree} - {s.fin_pointage_entree}"
            out_win = f"{s.debut_pointage_sortie} - {s.fin_pointage_sortie}"
            grace = f"{s.retard_tolere_mn}m / {s.depart_avance_tolere_mn}m"
            rows.append((s.id, s.name, timing, work_time, in_win, out_win, grace, s.compte_journee))

        for w in self._sched_table_frame.winfo_children():
            w.destroy()

        self._sched_table = Tableview(
            master=self._sched_table_frame,
            coldata=cols,
            rowdata=rows,
            paginated=False,
            searchable=False,
            bootstyle="dark",
            autofit=True,
        )
        self._sched_table.pack(fill=BOTH, expand=YES)
        self._sched_table.view.bind("<<TreeviewSelect>>", self._on_schedule_select)

    def _on_schedule_select(self, event=None):
        if not self._sched_table:
            return
        sel = self._sched_table.view.selection()
        if not sel:
            return
        values = self._sched_table.view.item(sel[0], "values")
        self.selected_schedule_id = int(values[0])
        sched = self.service.session.query(WorkSchedule).get(self.selected_schedule_id)
        if sched:
            self._sched_vars["name"].set(sched.name)
            self._sched_vars["start_time"].set(sched.start_time)
            self._sched_vars["end_time"].set(sched.end_time)
            self._sched_vars["break_start"].set(sched.break_start or "")
            self._sched_vars["break_end"].set(sched.break_end or "")
            self._sched_vars["color_hex"].set(self._get_valid_color(sched.color_hex))
            self._color_lbl.configure(background=self._sched_vars["color_hex"].get())
            
            self._sched_vars["debut_pointage_entree"].set(sched.debut_pointage_entree or "00:00")
            self._sched_vars["fin_pointage_entree"].set(sched.fin_pointage_entree or "23:59")
            self._sched_vars["debut_pointage_sortie"].set(sched.debut_pointage_sortie or "00:00")
            self._sched_vars["fin_pointage_sortie"].set(sched.fin_pointage_sortie or "23:59")
            
            self._sched_vars["retard_tolere_mn"].set(sched.retard_tolere_mn or 0)
            self._sched_vars["depart_avance_tolere_mn"].set(sched.depart_avance_tolere_mn or 0)
            self._sched_vars["pointe_entree_obligatoire"].set(sched.pointe_entree_obligatoire)
            self._sched_vars["pointe_sortie_obligatoire"].set(sched.pointe_sortie_obligatoire)
            
            self._sched_vars["compte_journee"].set(sched.compte_journee or 1.0)
            self._sched_vars["total_hours"].set(sched.total_hours if sched.total_hours is not None else 8.0)
            self._sched_vars["compte_minute"].set(sched.compte_minute or 480)

    def _clear_schedule_form(self):
        self.selected_schedule_id = None
        # Reset all form variables to defaults or empty
        if hasattr(self, "_sched_vars"):
            self._sched_vars["name"].set("")
            self._sched_vars["start_time"].set("")
            self._sched_vars["end_time"].set("")
            self._sched_vars["break_start"].set("")
            self._sched_vars["break_end"].set("")
            
            # Reset smart timing helper
            if hasattr(self, "_smart_timing_var"):
                self._smart_timing_var.set("")
            
            # Reset defaults for other fields if they exist
            if "color_hex" in self._sched_vars: self._sched_vars["color_hex"].set("#0055ff")
            if "retard_tolere_mn" in self._sched_vars: self._sched_vars["retard_tolere_mn"].set(0)
            if "depart_avance_tolere_mn" in self._sched_vars: self._sched_vars["depart_avance_tolere_mn"].set(0)
            if "pointe_entree_obligatoire" in self._sched_vars: self._sched_vars["pointe_entree_obligatoire"].set(True)
            if "pointe_sortie_obligatoire" in self._sched_vars: self._sched_vars["pointe_sortie_obligatoire"].set(True)
            if "compte_journee" in self._sched_vars: self._sched_vars["compte_journee"].set(1.0)
            if "total_hours" in self._sched_vars: self._sched_vars["total_hours"].set(8.0)
            if "compte_minute" in self._sched_vars: self._sched_vars["compte_minute"].set(480)
            
            # Update UI indicators (like the color label)
            if hasattr(self, "_color_lbl"):
                self._color_lbl.config(background="#0055ff")
        
        # Unselect table
        if self._sched_table:
            self._sched_table.view.selection_remove(self._sched_table.view.selection())

    def _nav_first(self):
        if not self._sched_table or not self._sched_table.view.get_children(): return
        children = self._sched_table.view.get_children()
        self._sched_table.view.selection_set(children[0])
        self._sched_table.view.see(children[0])
        self._on_schedule_select()

    def _nav_prev(self):
        if not self._sched_table or not self._sched_table.view.get_children(): return
        children = self._sched_table.view.get_children()
        sel = self._sched_table.view.selection()
        if not sel:
            self._nav_first()
            return
        idx = children.index(sel[0])
        if idx > 0:
            self._sched_table.view.selection_set(children[idx - 1])
            self._sched_table.view.see(children[idx - 1])
            self._on_schedule_select()

    def _nav_next(self):
        if not self._sched_table or not self._sched_table.view.get_children(): return
        children = self._sched_table.view.get_children()
        sel = self._sched_table.view.selection()
        if not sel:
            self._nav_first()
            return
        idx = children.index(sel[0])
        if idx < len(children) - 1:
            self._sched_table.view.selection_set(children[idx + 1])
            self._sched_table.view.see(children[idx + 1])
            self._on_schedule_select()

    def _nav_last(self):
        if not self._sched_table or not self._sched_table.view.get_children(): return
        children = self._sched_table.view.get_children()
        self._sched_table.view.selection_set(children[-1])
        self._sched_table.view.see(children[-1])
        self._on_schedule_select()
        self._sched_vars["name"].set("")
        self._sched_vars["start_time"].set("08:00")
        self._sched_vars["end_time"].set("17:00")
        self._sched_vars["break_start"].set("12:00")
        self._sched_vars["break_end"].set("13:00")
        self._sched_vars["color_hex"].set("#0055ff")
        self._color_lbl.configure(background="#0055ff")
        self._sched_vars["debut_pointage_entree"].set("00:00")
        self._sched_vars["fin_pointage_entree"].set("23:59")
        self._sched_vars["debut_pointage_sortie"].set("00:00")
        self._sched_vars["fin_pointage_sortie"].set("23:59")
        self._sched_vars["retard_tolere_mn"].set(0)
        self._sched_vars["depart_avance_tolere_mn"].set(0)
        self._sched_vars["pointe_entree_obligatoire"].set(True)
        self._sched_vars["pointe_sortie_obligatoire"].set(True)
        self._sched_vars["compte_journee"].set(1.0)
        self._sched_vars["total_hours"].set(8.0)
        self._sched_vars["compte_minute"].set(480)

    def _save_schedule(self):
        data = { k: v.get() for k, v in self._sched_vars.items() }
        # Map back fields omitted from basic ui
        data["days_of_week"] = "Mon,Tue,Wed,Thu,Fri"
        # total_hours is now sourced from the form variable (no longer hardcoded)
        
        try:
            self.service.save_schedule(data, schedule_id=self.selected_schedule_id)
            Messagebox.show_info(tr("schedule_saved"), tr("success"))
            self._clear_schedule_form()
            self._load_schedules()
        except Exception as e:
            Messagebox.show_error(str(e), tr("error"))

    def _delete_schedule(self):
        if not self.selected_schedule_id:
            Messagebox.show_info(tr("no_selection"), tr("information"))
            return
        ans = Messagebox.show_question(
            tr("confirm_delete_schedule"), tr("confirmation"),
            buttons=["No:secondary", "Yes:danger"]
        )
        if ans == "Yes":
            self.service.delete_schedule(self.selected_schedule_id)
            Messagebox.show_info(tr("schedule_deleted"), tr("success"))
            self._clear_schedule_form()
            self._load_schedules()

    def _sync_schedule_to_zk(self):
        """Push all employees assigned to the selected schedule to every active ZK machine via TaskManager."""
        if not self.selected_schedule_id:
            Messagebox.show_warning("Please select a schedule from the list first.", "No Selection", parent=self)
            return

        from contragest.core.database import WorkSchedule, EmployeeSchedule, Employee, AttendanceMachine

        sched = self.service.session.query(WorkSchedule).get(self.selected_schedule_id)
        if not sched:
            Messagebox.show_error("Schedule not found.", "Error", parent=self)
            return

        sched_name = sched.name 
        seen_emp_ids = set()
        user_list = []
        for a in self.service.session.query(EmployeeSchedule).filter_by(schedule_id=self.selected_schedule_id).all():
            if a.employee_id in seen_emp_ids: continue
            seen_emp_ids.add(a.employee_id)
            emp = self.service.session.query(Employee).get(a.employee_id)
            if emp and emp.registration_number:
                try:
                    user_list.append({"uid": int(emp.registration_number), "name": f"{emp.first_name} {emp.last_name}"})
                except (ValueError, TypeError): pass

        machine_params = [
            {"name": m.name, "ip": m.ip_address, "port": m.port, "password": m.password or ""}
            for m in self.service.session.query(AttendanceMachine).filter_by(is_active=True).all()
        ]

        if not machine_params:
            Messagebox.show_warning("No active ZK machines configured.", "Sync Skipped", parent=self)
            return

        ans = Messagebox.show_question(
            f"Push {len(user_list)} employee(s) assigned to schedule '{sched_name}' to all active ZK machines?",
            "Confirm Sync to ZK", buttons=["Cancel:secondary", "Proceed:primary"], parent=self
        )
        if ans != "Proceed": return

        admin_name = self.main_window.current_user.username if getattr(self.main_window, "current_user", None) else "System"

        # ── Progress Dialog ──
        prog_dlg = ttk.Toplevel(self)
        prog_dlg.title("Syncing to ZK\u2026")
        prog_dlg.geometry("380x130")
        prog_dlg.resizable(False, False)
        prog_dlg.transient(self)
        prog_dlg.grab_set()

        ttk.Label(prog_dlg, text=f"\u27f3  Syncing schedule '{sched_name}' to ZK machines\u2026",
                  font=("Space Mono", 9, "bold")).pack(pady=(12, 4), padx=12)
        pvar = ttk.DoubleVar()
        pbar = ttk.Progressbar(prog_dlg, variable=pvar, maximum=100, bootstyle=PRIMARY)
        pbar.pack(fill=X, padx=12)
        plbl = ttk.Label(prog_dlg, text="Connecting\u2026", font=("Space Mono", 9))
        plbl.pack(pady=(4, 1))

        def _dlg_progress(pct, txt):
            pvar.set(pct)
            plbl.config(text=txt)

        self.task_manager.run_task(
            task_id="sync_schedule_zk",
            name=f"📡 Schedule Sync: {sched_name}",
            target=self._sync_schedule_bg,
            args=(machine_params, user_list),
            on_progress=_dlg_progress,
            on_complete=lambda res: self._after_sync_finalize(res, sched_name, admin_name, prog_dlg)
        )

    def _sync_schedule_bg(self, machine_params, user_list, progress_callback=None):
        """Background worker for schedule sync."""
        machine_results = []
        total_s, total_f = 0, 0
        total_m = len(machine_params)
        
        for i, mp in enumerate(machine_params):
            if progress_callback:
                progress_callback(i, total_m, f"Pushing to {mp['name']}...")
            
            res = {"machine": mp["name"], "success": 0, "failed": len(user_list), "error": None}
            try:
                s, f = self.service.connector.push_users_bulk(mp["ip"], mp["port"], mp["password"], user_list)
                res["success"], res["failed"] = s, f
                total_s += s
                total_f += f
            except Exception as e:
                res["error"] = str(e)
                total_f += len(user_list)
            machine_results.append(res)
        
        return total_s, total_f, machine_results

    def _after_sync_finalize(self, result, sched_name, admin_name, prog_dlg=None):
        """Finalizes UI and writes audit logs after schedule sync."""
        if prog_dlg:
            prog_dlg.grab_release()
            prog_dlg.destroy()

        total_s, total_f, machine_results = result
        
        from datetime import date, datetime
        from contragest.core.database import AttendanceCorrectionLog
        for r in machine_results:
            if not r["error"]:
                try:
                    self.service.session.add(AttendanceCorrectionLog(
                        reg_number="ALL", shift_date=date.today().isoformat(),
                        issue_type="SCHEDULE_SYNC", imputed_val=sched_name,
                        strategy="PUSH_TO_ZK", corrected_by=admin_name,
                        corrected_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        notes=f"Synced schedule '{sched_name}' to machine '{r['machine']}': {r['success']} pushed, {r['failed']} failed."
                    ))
                except Exception as ae: logger.warning(f"Audit log failed for {r['machine']}: {ae}")
        
        try: self.service.session.commit()
        except Exception as ce:
            self.service.session.rollback()
            logger.warning(f"Audit commit failed: {ce}")

        lines = [f"Schedule: {sched_name}\n"]
        for r in machine_results:
            icon = "✅" if not r["error"] else "❌"
            detail = f"Error: {r['error']}" if r["error"] else f"{r['success']} pushed, {r['failed']} failed"
            lines.append(f"{icon}  {r['machine']}:  {detail}")
        lines.append(f"\nTotal:  ✅ {total_s} pushed  ❌ {total_f} failed")
        
        self._transfer_status.configure(text=f"✅ {sched_name} Sync Complete.", fg=SUCCESS_EMERALD)
        Messagebox.show_info("\n".join(lines), "Sync Complete", parent=self)
        self.master.after(4000, lambda: self._safe_pack_forget("_prog_frame"))

    # ── Machine Time Sync ─────────────────────────────────────────────────

    def _sync_machine_time(self):
        """Read each active machine's clock and sync to PC time if needed."""
        from contragest.core.database import AttendanceMachine
        machines = self.service.session.query(AttendanceMachine).filter_by(is_active=True).all()
        if not machines:
            Messagebox.show_warning("No active ZK machines configured.", "Sync Time", parent=self)
            return

        ans = Messagebox.show_question(
            f"Sync time on {len(machines)} active machine(s) to PC time?",
            "Confirm Time Sync",
            buttons=["Cancel:secondary", "Proceed:primary"],
            parent=self
        )
        if ans != "Proceed":
            return

        self._prog_frame.pack(fill=X, padx=6, pady=(1, 6))
        self._transfer_status.configure(text=f"Syncing time on {len(machines)} machine(s)...", fg=ACCENT_BLUE)

        self.task_manager.run_task(
            task_id="sync_machine_time",
            name="Clock Sync",
            target=self._sync_machine_time_bg,
            args=([{"id": m.id, "name": m.name} for m in machines],),
            on_progress=self._update_progress_ui,
            on_complete=self._on_sync_time_complete,
            on_error=lambda err: self._on_sync_time_complete({"success": False, "message": str(err)})
        )

    def _sync_machine_time_bg(self, machine_list, progress_callback=None):
        """Background worker: iterate active machines, sync time on each."""
        from datetime import datetime
        results = []
        total = len(machine_list)
        for i, m in enumerate(machine_list):
            if progress_callback:
                progress_callback(i, total, f"[{i+1}/{total}] {m['name']}...")
            try:
                res = self.service.sync_machine_time(m["id"])
                res["machine_name"] = m["name"]
                results.append(res)
            except Exception as e:
                results.append({"machine_name": m["name"], "success": False,
                                "message": str(e)})
            if progress_callback:
                progress_callback(i + 1, total,
                                  f"[{i+1}/{total}] {m['name']}: {results[-1].get('message','')[:60]}")
        return results

    def _on_sync_time_complete(self, results):
        """Finalize UI after time sync completes."""
        if not isinstance(results, list):
            results = [results]
        lines = ["Machine Time Sync Results:\n"]
        ok = err = synced = 0
        for r in results:
            if r.get("success"):
                ok += 1
                if r.get("synced"):
                    synced += 1
            else:
                err += 1
            icon = "   OK" if r.get("success") else "ERROR"
            msg = r.get("message", "No message")
            lines.append(f"  {icon}  {r.get('machine_name', '?'):20s}  {msg[:80]}")
        lines.append(f"\n  OK: {ok}  |  Synced: {synced}  |  Errors: {err}")

        status = "Time sync complete"
        if err:
            status += f" ({err} error(s))"
            color = DANGER_ROSE
        elif synced:
            status += f" ({synced} machine(s) synced)"
            color = SUCCESS_EMERALD
        else:
            status += " (all OK, no sync needed)"
            color = SUCCESS_EMERALD

        self._transfer_status.configure(text=f"{status}", fg=color)
        self.after(5000, lambda: self._safe_pack_forget("_prog_frame"))
        for r in results:
            icon = "✅" if r.get("success") else "❌"
            detail = r.get("message", "No message")
            if r.get("synced"):
                detail += " (synced)"
            
            # Format and display the machine time and PC time
            pc_t = r.get("pc_time_iso", "")
            mach_t = r.get("machine_time_iso", "")
            if pc_t and mach_t:
                try:
                    pc_time_str = pc_t.split("T")[1][:8]
                    mach_time_str = mach_t.split("T")[1][:8]
                    detail = f"Clock={mach_time_str} | PC={pc_time_str} | {detail}"
                except Exception:
                    pass
            self._log_machine(f"🕒 {icon} {r.get('machine_name', '?')}: {detail}")
        Messagebox.show_info("\n".join(lines), "Time Sync Complete", parent=self)

    # ── Machine Reboot ────────────────────────────────────────────────────

    def _reboot_machine(self):
        """Confirm and reboot the currently selected machine."""
        if not self.selected_machine_id:
            Messagebox.show_warning("Select a machine first.", "No Selection")
            return
        machine = self.service.get_machine(self.selected_machine_id)
        if not machine:
            return
        ans = Messagebox.show_question(
            f"Send restart command to '{machine.name}' ({machine.ip_address})?",
            "Confirm Reboot",
            buttons=["Cancel:secondary", "Proceed:danger"],
            parent=self
        )
        if ans != "Proceed":
            return

        self._prog_frame.pack(fill=X, padx=6, pady=(1, 6))
        self._transfer_status.configure(
            text=f"Rebooting {machine.name} ({machine.ip_address})...", fg=ACCENT_BLUE)

        self.task_manager.run_task(
            task_id="reboot_machine",
            name="Machine Reboot",
            target=self._reboot_machine_bg,
            args=(self.selected_machine_id,),
            on_complete=self._on_reboot_complete,
            on_error=lambda err: self._on_reboot_complete(
                {"success": False, "machine_name": machine.name,
                 "message": str(err)})
        )

    def _reboot_machine_bg(self, machine_id, progress_callback=None):
        """Background worker for machine reboot."""
        if progress_callback:
            progress_callback(50, 100, "Sending restart command...")
        result = self.service.reboot_machine(machine_id)
        if progress_callback:
            progress_callback(100, 100, result.get("message", "Done"))
        return result

    def _on_reboot_complete(self, result):
        """Finalize UI after reboot completes."""
        ok = result.get("success", False)
        name = result.get("machine_name", "?")
        msg = result.get("message", "No message")

        icon = "✅" if ok else "❌"
        self._log_machine(f"🔄 {icon} {name}: {msg}")
        self._transfer_status.configure(
            text=f"{'✅' if ok else '❌'} Reboot {'succeeded' if ok else 'failed'}: {msg[:60]}",
            fg=SUCCESS_EMERALD if ok else DANGER_ROSE)
        self.after(5000, lambda: self._safe_pack_forget("_prog_frame"))

        if ok:
            Messagebox.show_info(f"'{name}': {msg}", "Reboot Complete", parent=self)
        else:
            Messagebox.show_error(f"'{name}': {msg}", "Reboot Failed", parent=self)

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB - STATUS OF DAYS
    # ═══════════════════════════════════════════════════════════════════════

    def _build_status_days_tab(self):
        parent = self._tab_status_days

        paned = ttk.Panedwindow(parent, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=YES)

        # ── List (Left) ──
        list_frame = ttk.LabelFrame(paned, text="📋 Status of Days")
        paned.add(list_frame, weight=3) 

        self._status_table_frame = ttk.Frame(list_frame)
        self._status_table_frame.pack(fill=BOTH, expand=YES, padx=3, pady=3)
        self._status_table = None

        # ── Form (Right) ──
        form_frame = ttk.LabelFrame(paned, text="📝 Status Settings")
        paned.add(form_frame, weight=2)
        
        self.selected_status_id = None
        self._status_vars = {}
        
        # Actions Row
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=X, padx=6, pady=3)
        
        ttk.Button(btn_frame, text=f"➕ {tr('new')}", command=self._clear_status_form, bootstyle=SUCCESS, width=10).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text=f"💾 {tr('save')}", command=self._save_day_status, bootstyle=SUCCESS, width=10).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text=f"❌ {tr('delete')}", command=self._delete_day_status, bootstyle=DANGER, width=10).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text=f"🔄", command=self._load_day_statuses, bootstyle=INFO, width=4).pack(side=LEFT, padx=1)
        
        ttk.Separator(form_frame, orient=HORIZONTAL).pack(fill=X, padx=3, pady=(1, 3))
        
        # ── Form Fields ──
        basic_lf = ttk.LabelFrame(form_frame, text="Basic Info")
        basic_lf.pack(fill=X, padx=6, pady=3, ipadx=3, ipady=3)
        
        ttk.Label(basic_lf, text="Name").grid(row=0, column=0, sticky=W, pady=1)
        self._status_vars["name"] = ttk.StringVar()
        ttk.Entry(basic_lf, textvariable=self._status_vars["name"]).grid(row=0, column=1, sticky=EW, pady=1, padx=(3, 1))

        ttk.Label(basic_lf, text="Code").grid(row=1, column=0, sticky=W, pady=1)
        self._status_vars["code"] = ttk.StringVar()
        ttk.Entry(basic_lf, textvariable=self._status_vars["code"]).grid(row=1, column=1, sticky=EW, pady=1, padx=(3, 1))

        ttk.Label(basic_lf, text="Color").grid(row=2, column=0, sticky=W, pady=1)
        self._status_vars["color_hex"] = ttk.StringVar(value="#ffffff")
        
        color_frame = ttk.Frame(basic_lf)
        color_frame.grid(row=2, column=1, sticky=EW, pady=1, padx=(3, 1))
        self._status_color_lbl = ttk.Label(color_frame, width=3, background=self._status_vars["color_hex"].get())
        self._status_color_lbl.pack(side=LEFT, padx=(1, 3))
        ttk.Button(color_frame, text="Pick", command=self._pick_status_color, bootstyle="outline-secondary").pack(side=LEFT)
        basic_lf.columnconfigure(1, weight=1)

        # ── Rules ──
        rules_lf = ttk.LabelFrame(form_frame, text="⚙️ Calculation Rules")
        rules_lf.pack(fill=X, padx=6, pady=3, ipadx=5, ipady=5)

        rule_info = ttk.Label(rules_lf, text="Define how this status affects the attendance balance.", font=("Segoe UI", 8, "italic"), bootstyle="secondary")
        rule_info.grid(row=0, column=0, columnspan=2, sticky=W, pady=(0, 5))

        self._status_vars["is_worked_day"] = ttk.BooleanVar(value=True)
        is_worked_cb = ttk.Checkbutton(
            rules_lf, 
            text="Consider as Worked Day", 
            variable=self._status_vars["is_worked_day"], 
            bootstyle="round-toggle"
        )
        is_worked_cb.grid(row=1, column=0, columnspan=2, sticky=W, pady=5)
        ToolTip(is_worked_cb, text="If enabled, this day is expected to have 8h (or scheduled) work.\nIf disabled (e.g. Repos), expected work time is 0h.")

        ttk.Label(rules_lf, text="Time Multiplier (Coeff)").grid(row=2, column=0, sticky=W, pady=5)
        self._status_vars["coefficient"] = ttk.DoubleVar(value=1.0)
        coeff_spin = ttk.Spinbox(
            rules_lf, 
            from_=0.0, to=5.0, 
            increment=0.5, 
            textvariable=self._status_vars["coefficient"], 
            width=8,
            bootstyle="info"
        )
        coeff_spin.grid(row=2, column=1, sticky=W, pady=5, padx=5)
        ToolTip(coeff_spin, text="Multiply attendance time by this factor.\ne.g. 1.0 = Normal, 2.0 = Double time on Holidays.")

        self._load_day_statuses()

    def _pick_status_color(self):
        from ttkbootstrap.dialogs.colorchooser import ColorChooserDialog
        cd = ColorChooserDialog()
        cd.show()
        if cd.result:
            color = self._get_valid_color(cd.result.hex)
            self._status_vars["color_hex"].set(color)
            self._status_color_lbl.configure(background=color)

    def _load_day_statuses(self):
        from contragest.core.database import DayStatus
        statuses = self.service.get_all_day_statuses()
        cols = ["ID", "Name", "Code", "Color", "Worked", "Coeff"]
        rows = []
        for s in statuses:
            worked_display = "✅ Yes" if s.is_worked_day else "❌ No"
            coeff_display = f"x{s.coefficient:.1f}"
            rows.append((s.id, s.name, s.code, s.color_hex, worked_display, coeff_display))

        for w in self._status_table_frame.winfo_children():
            w.destroy()

        self._status_table = Tableview(
            master=self._status_table_frame,
            coldata=cols,
            rowdata=rows,
            paginated=False,
            searchable=False,
            bootstyle="dark",
            autofit=True,
        )
        self._status_table.pack(fill=BOTH, expand=YES)
        
        # Apply color tags for immediate visual reference
        for item in self._status_table.view.get_children():
            vals = self._status_table.view.item(item, "values")
            color = vals[3] if len(vals) > 3 else "#ffffff"
            
            # Dynamic foreground color for contrast
            fg = "#ffffff"
            try:
                c = color.lstrip('#')
                if len(c) == 6:
                    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                    if ((0.299*r + 0.587*g + 0.114*b)/255) > 0.6: fg = "#000000"
            except: pass
            
            self._status_table.view.tag_configure(item, background=color, foreground=fg)
            self._status_table.view.item(item, tags=(item,))

        self._status_table.view.bind("<<TreeviewSelect>>", self._on_status_select)

    def _on_status_select(self, event=None):
        if not self._status_table: return
        sel = self._status_table.view.selection()
        if not sel: return
        values = self._status_table.view.item(sel[0], "values")
        self.selected_status_id = int(values[0])
        from contragest.core.database import DayStatus
        status = self.service.session.query(DayStatus).get(self.selected_status_id)
        if status:
            self._status_vars["name"].set(status.name)
            self._status_vars["code"].set(status.code)
            self._status_vars["color_hex"].set(self._get_valid_color(status.color_hex))
            self._status_color_lbl.configure(background=self._status_vars["color_hex"].get())
            self._status_vars["is_worked_day"].set(status.is_worked_day)
            self._status_vars["coefficient"].set(status.coefficient)

    def _clear_status_form(self):
        self.selected_status_id = None
        self._status_vars["name"].set("")
        self._status_vars["code"].set("")
        self._status_vars["color_hex"].set("#ffffff")
        self._status_color_lbl.configure(background="#ffffff")
        self._status_vars["is_worked_day"].set(True)
        self._status_vars["coefficient"].set(1.0)

    def _save_day_status(self):
        data = { k: v.get() for k, v in self._status_vars.items() }
        if not data["name"] or not data["code"]:
            Messagebox.show_error("Name and Code are required.", "Error")
            return
        try:
            self.service.save_day_status(data, status_id=self.selected_status_id)
            Messagebox.show_info("Status saved.", "Success")
            self._clear_status_form()
            self._load_day_statuses()
        except Exception as e:
            Messagebox.show_error(str(e), "Error")

    def _delete_day_status(self):
        if not self.selected_status_id:
            Messagebox.show_info("Please select a status first.", "Information")
            return
        ans = Messagebox.show_question("Are you sure you want to delete this status?", "Confirmation", buttons=["No:secondary", "Yes:danger"])
        if ans == "Yes":
            self.service.delete_day_status(self.selected_status_id)
            Messagebox.show_info("Status deleted.", "Success")
            self._clear_status_form()
            self._load_day_statuses()

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB - NOTE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def _build_notes_tab(self):
        parent = self._tab_notes

        paned = ttk.Panedwindow(parent, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=YES)

        # ── List (Left) ──
        list_frame = ttk.LabelFrame(paned, text="📋 Predefined Notes")
        paned.add(list_frame, weight=3) 

        self._notes_table_frame = ttk.Frame(list_frame)
        self._notes_table_frame.pack(fill=BOTH, expand=YES, padx=3, pady=3)
        self._notes_table = None

        # ── Form (Right) ──
        form_frame = ttk.LabelFrame(paned, text="📝 Note Settings")
        paned.add(form_frame, weight=2)
        
        self.selected_note_id = None
        self._note_vars = {}
        
        # Actions Row
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=X, padx=6, pady=3)
        
        ttk.Button(btn_frame, text=f"➕ {tr('new')}", command=self._clear_note_form, bootstyle=SUCCESS, width=10).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text=f"💾 {tr('save')}", command=self._save_predefined_note, bootstyle=SUCCESS, width=10).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text=f"❌ {tr('delete')}", command=self._delete_predefined_note, bootstyle=DANGER, width=10).pack(side=LEFT, padx=1)
        ttk.Button(btn_frame, text=f"🔄", command=self._load_predefined_notes, bootstyle=INFO, width=4).pack(side=LEFT, padx=1)
        
        ttk.Separator(form_frame, orient=HORIZONTAL).pack(fill=X, padx=3, pady=(1, 3))
        
        # ── Form Fields ──
        basic_lf = ttk.LabelFrame(form_frame, text="Note Info")
        basic_lf.pack(fill=X, padx=6, pady=3, ipadx=3, ipady=3)
        
        ttk.Label(basic_lf, text="Name").grid(row=0, column=0, sticky=W, pady=1)
        self._note_vars["name"] = ttk.StringVar()
        ttk.Entry(basic_lf, textvariable=self._note_vars["name"]).grid(row=0, column=1, sticky=EW, pady=1, padx=(3, 1))

        ttk.Label(basic_lf, text="Color").grid(row=2, column=0, sticky=W, pady=1)
        self._note_vars["color_hex"] = ttk.StringVar(value="#ffffff")
        
        color_frame = ttk.Frame(basic_lf)
        color_frame.grid(row=2, column=1, sticky=EW, pady=1, padx=(3, 1))
        self._note_color_lbl = ttk.Label(color_frame, width=3, background=self._note_vars["color_hex"].get())
        self._note_color_lbl.pack(side=LEFT, padx=(1, 3))
        ttk.Button(color_frame, text="Pick", command=self._pick_note_color, bootstyle="outline-secondary").pack(side=LEFT)
        basic_lf.columnconfigure(1, weight=1)

        self._load_predefined_notes()

    def _pick_note_color(self):
        from ttkbootstrap.dialogs.colorchooser import ColorChooserDialog
        cd = ColorChooserDialog()
        cd.show()
        if cd.result:
            color = self._get_valid_color(cd.result.hex)
            self._note_vars["color_hex"].set(color)
            self._note_color_lbl.configure(background=color)

    def _load_predefined_notes(self):
        notes = self.service.get_predefined_notes()
        cols = ["ID", "Name", "Color"]
        rows = []
        for n in notes:
            rows.append((n.get("id"), n.get("name"), n.get("color_hex")))

        for w in self._notes_table_frame.winfo_children():
            w.destroy()

        self._notes_table = Tableview(
            master=self._notes_table_frame,
            coldata=cols,
            rowdata=rows,
            paginated=False,
            searchable=False,
            bootstyle="dark",
            autofit=True,
        )
        self._notes_table.pack(fill=BOTH, expand=YES)
        self._notes_table.view.bind("<<TreeviewSelect>>", self._on_note_select)

    def _on_note_select(self, event=None):
        if not self._notes_table: return
        sel = self._notes_table.view.selection()
        if not sel: return
        values = self._notes_table.view.item(sel[0], "values")
        self.selected_note_id = int(values[0])
        from contragest.core.database import PredefinedNote
        note = self.service.session.query(PredefinedNote).get(self.selected_note_id)
        if note:
            self._note_vars["name"].set(note.name)
            self._note_vars["color_hex"].set(self._get_valid_color(note.color_hex))
            self._note_color_lbl.configure(background=self._note_vars["color_hex"].get())

    def _clear_note_form(self):
        self.selected_note_id = None
        self._note_vars["name"].set("")
        self._note_vars["color_hex"].set("#ffffff")
        self._note_color_lbl.configure(background="#ffffff")

    def _save_predefined_note(self):
        data = { "id": self.selected_note_id, "name": self._note_vars["name"].get(), "color_hex": self._note_vars["color_hex"].get() }
        if not data["name"]:
            Messagebox.show_error("Name is required.", "Error")
            return
        try:
            self.service.save_predefined_note(data)
            Messagebox.show_info("Note saved.", "Success")
            self._clear_note_form()
            self._load_predefined_notes()
        except Exception as e:
            Messagebox.show_error(str(e), "Error")

    def _delete_predefined_note(self):
        if not self.selected_note_id:
            Messagebox.show_info("Please select a note first.", "Information")
            return
        ans = Messagebox.show_question("Are you sure you want to delete this note?", "Confirmation", buttons=["No:secondary", "Yes:danger"])
        if ans == "Yes":
            self.service.delete_predefined_note(self.selected_note_id)
            Messagebox.show_info("Note deleted.", "Success")
            self._clear_note_form()
            self._load_predefined_notes()

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 5 - Audit Logs
    # ═══════════════════════════════════════════════════════════════════════

    def _build_audit_tab(self):
        parent = self._tab_audit
        
        from ttkbootstrap.widgets import DateEntry
        filter_frame = ttk.LabelFrame(parent, text="🔍 Filters")
        filter_frame.pack(fill=X, padx=3, pady=6)

        f_row = ttk.Frame(filter_frame)
        f_row.pack(fill=X, pady=3)
        
        ttk.Label(f_row, text="📅 From:").pack(side=LEFT, padx=3)
        self._audit_from_de = DateEntry(f_row, startdate=None, dateformat='%Y-%m-%d')
        self._audit_from_de.pack(side=LEFT, padx=3)
        self._audit_from_de.entry.delete(0, END)

        ttk.Label(f_row, text="📅 To:").pack(side=LEFT, padx=(6, 3))
        self._audit_to_de = DateEntry(f_row, startdate=None, dateformat='%Y-%m-%d')
        self._audit_to_de.pack(side=LEFT, padx=3)
        self._audit_to_de.entry.delete(0, END)

        ttk.Label(f_row, text="🆔 REG:").pack(side=LEFT, padx=(6, 3))
        self._audit_reg = ttk.StringVar()
        ttk.Entry(f_row, textvariable=self._audit_reg, width=15).pack(side=LEFT, padx=3)
        
        ttk.Label(f_row, text="🏷️ Strategy:").pack(side=LEFT, padx=(6, 3))
        self._audit_strategy = ttk.StringVar(value="All")
        ttk.Combobox(f_row, textvariable=self._audit_strategy, values=["All", "MANUAL", "SCHEDULE", "HISTORY", "UNRESOLVED"], state="readonly", width=12).pack(side=LEFT, padx=3)
        
        ttk.Button(f_row, text="✅ Apply", bootstyle=PRIMARY, command=self._load_audit_logs).pack(side=RIGHT, padx=3)
        ttk.Button(f_row, text="🔄 Clear", bootstyle=SECONDARY, command=self._clear_audit_filters).pack(side=RIGHT, padx=3)

        records_frame = ttk.LabelFrame(parent, text="📋 Correction & Manual Logs")
        records_frame.pack(fill=BOTH, expand=YES, pady=3)

        self._audit_table_frame = ttk.Frame(records_frame)
        self._audit_table_frame.pack(fill=BOTH, expand=YES)
        self._audit_table = None
        
        self._load_audit_logs()

    def _clear_audit_filters(self):
        self._audit_from_de.entry.delete(0, END)
        self._audit_to_de.entry.delete(0, END)
        self._audit_reg.set("")
        self._audit_strategy.set("All")
        self._load_audit_logs()

    def _load_audit_logs(self):
        date_from = self._audit_from_de.entry.get().strip() or None
        date_to = self._audit_to_de.entry.get().strip() or None
        reg_filter = self._audit_reg.get().strip() or None
        strategy = self._audit_strategy.get()

        logs = self.service.get_correction_logs(
            start_date=date_from,
            end_date=date_to,
            reg_filter=reg_filter,
            strategy_filter=strategy,
            limit=500
        )

        cols = ["DATE", "EMPLOYEE", "REG", "ISSUE TYPE", "CORRECTION", "STRATEGY", "BY", "TIMESTAMP", "NOTES"]
        rows = [
            (
                l["shift_date"], l["employee"], l["reg_number"], l["issue_type"],
                l["correction"], l["strategy"], l["corrected_by"], l["corrected_at"][:16] if l["corrected_at"] else "-", l["notes"]
            ) for l in logs
        ]

        for w in self._audit_table_frame.winfo_children():
            w.destroy()

        self._audit_table = Tableview(
            master=self._audit_table_frame,
            coldata=cols,
            rowdata=rows,
            paginated=True,
            pagesize=30,
            searchable=True,
            bootstyle="dark",
            autofit=True,
        )
        self._audit_table.pack(fill=BOTH, expand=YES)

    def view_audit_for_employee(self, reg_number):
        self.notebook.select(self._tab_audit)
        self._clear_audit_filters()
        self._audit_reg.set(reg_number)
        self._load_audit_logs()

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 8 - Analytics & Reports
    # ═══════════════════════════════════════════════════════════════════════

    def _build_analytics_tab(self):
        parent = self._tab_analytics
        parent.configure(background=MAIN_BG)
        
        # 1. Header with branding
        header_frame = tk.Frame(parent, background=MAIN_BG)
        header_frame.pack(fill=X, pady=(1, 12))
        
        # Logo container
        self._analytics_logo_lbl = tk.Label(header_frame, background=MAIN_BG)
        self._analytics_logo_lbl.pack(side=tk.LEFT, padx=6)
        self._load_analytics_logo()
        
        # Center Title
        title_vbox = tk.Frame(header_frame, background=MAIN_BG)
        title_vbox.pack(side=tk.LEFT, expand=tk.YES)
        tk.Label(title_vbox, text="TIME & ATTENDANCE MANAGEMENT", font=("Space Mono", 14, "bold"), fg=TEXT_HIGH, bg=MAIN_BG).pack()
        tk.Label(title_vbox, text="DEPARTMENTAL ATTENDANCE SUMMARY", font=("Space Mono", 10), fg=TEXT_MUTED, bg=MAIN_BG).pack()
        
        # Metadata
        meta_vbox = tk.Frame(header_frame, background=MAIN_BG)
        meta_vbox.pack(side=tk.RIGHT, padx=6)
        self._meta_created_lbl = tk.Label(meta_vbox, text="Created on: --", font=("Space Mono", 9), fg=TEXT_MUTED, bg=MAIN_BG)
        self._meta_created_lbl.pack(anchor=tk.E)
        self._meta_range_lbl = tk.Label(meta_vbox, text="Report Range: --", font=("Space Mono", 9), fg=TEXT_MUTED, bg=MAIN_BG)
        self._meta_range_lbl.pack(anchor=tk.E)
        
        # 2. Main Content (Table)
        self._analytics_table_frame = tk.Frame(parent, background=MAIN_BG)
        self._analytics_table_frame.pack(fill=tk.BOTH, expand=tk.YES)
        
        # 3. Graphical Component (Chart)
        self._chart_frame = tk.LabelFrame(
            parent, text="📊 Attendance Trends by Department", 
            bg=PANEL_BG, fg=TEXT_MUTED, font=("Space Mono", 9, "bold"),
            highlightbackground=BORDER_COLOR, highlightthickness=1
        )
        self._chart_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=6)
        
        self._chart_canvas = tk.Canvas(self._chart_frame, height=220, bg=PANEL_BG, highlightthickness=0)
        self._chart_canvas.pack(fill=tk.X, expand=tk.YES)
        
        # Action Bar
        ctrl_frame = tk.Frame(parent, background=MAIN_BG)
        ctrl_frame.pack(fill=tk.X, pady=6)
        ttk.Button(ctrl_frame, text="🔄 REFRESH ANALYTICS", bootstyle=SUCCESS, command=self._update_analytics_gui).pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl_frame, text="📄 EXPORT PDF", bootstyle=DANGER, command=self._export_pdf).pack(side=tk.LEFT, padx=3)

    def _load_analytics_logo(self):
        """Dynamic logo loading for the analytics tab summary."""
        from contragest.core.database import SessionLocal, AppConfig
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            logo_path = config.company_logo_path if config and config.company_logo_path else None
            
            if logo_path and os.path.exists(logo_path):
                img = Image.open(logo_path)
                img.thumbnail((120, 120))
                self._analytics_logo_img = ImageTk.PhotoImage(img)
                self._analytics_logo_lbl.configure(image=self._analytics_logo_img)
            else:
                # Fallback
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                for ext in ["png", "jpg"]:
                    fallback = os.path.join(base_dir, "assets", f"company_logo.{ext}")
                    if os.path.exists(fallback):
                        img = Image.open(fallback)
                        img.thumbnail((120, 120))
                        self._analytics_logo_img = ImageTk.PhotoImage(img)
                        self._analytics_logo_lbl.configure(image=self._analytics_logo_img)
                        break
        except Exception as e:
            logger.error(f"Error loading analytics logo: {e}")
        finally:
            session.close()

    def _update_analytics_gui(self):
        """Refresh departmental summary with visual feedback."""
        if not self.winfo_exists():
            return
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            start_date = self._filter_from_de.entry.get() if hasattr(self, "_filter_from_de") else ""
            end_date = self._filter_to_de.entry.get() if hasattr(self, "_filter_to_de") else ""
            if not start_date or not end_date:
                today = datetime.now().strftime("%Y-%m-%d")
                start_date = today; end_date = today
            self._meta_created_lbl.configure(text=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self._meta_range_lbl.configure(text=f"Report Range: {start_date} to {end_date}")
            recap = self.service.get_department_summary(start_date, end_date)
            for w in self._analytics_table_frame.winfo_children(): w.destroy()
            if not recap:
                ttk.Label(self._analytics_table_frame, text="No attendance records found.", font=("Space Mono", 10, "italic")).pack(pady=30)
                if hasattr(self, "_chart_canvas") and self._chart_canvas.winfo_exists():
                    self._chart_canvas.delete("all")
                self.config(cursor=""); return
            cols = list(recap[0].keys()); rows = [list(r.values()) for r in recap]
            self._analytics_table = Tableview(master=self._analytics_table_frame, coldata=cols, rowdata=rows, paginated=False, searchable=True, bootstyle="dark", autofit=True)
            self._analytics_table.pack(fill=tk.BOTH, expand=tk.YES)
            self.after(100, lambda: self._draw_department_chart(recap))
            self.config(cursor="")
        except Exception as e:
            logger.error(f"Error refreshing analytics: {e}")
            self.config(cursor="")


    def _draw_department_chart(self, recap):
        """Draws a themed departmental attendance bar chart."""
        if not hasattr(self, "_chart_canvas") or not self._chart_canvas.winfo_exists(): return
        self._chart_canvas.delete("all")
        
        w = self._chart_canvas.winfo_width()
        h = self._chart_canvas.winfo_height()
        if w < 100: w = 1100 
        if h < 50: h = 220
        
        padding_x = 80
        padding_y = 40
        chart_w = w - padding_x * 2
        chart_h = h - padding_y * 1.5
        
        # Scaling logic
        try:
            max_val = max([float(r.get("Total", r.get("Total presence", 0))) for r in recap] + [1])
        except (ValueError, TypeError):
            max_val = 1
            
        num_depts = len(recap)
        bar_width = min(60, (chart_w / max(1, num_depts)) * 0.7)
        spacing = (chart_w / max(1, num_depts))
        
        for i, r in enumerate(recap):
            dept = r.get("Departement", r.get("DEPARTMENT", "-"))
            total = r.get("Total", r.get("Total presence", 0))
            
            x0 = padding_x + i * spacing + (spacing - bar_width) / 2
            try: y_val = (float(total) / max_val) * chart_h
            except: y_val = 0
            
            y0 = h - padding_y - y_val
            
            # Draw Bar (Modern Accents)
            self._chart_canvas.create_rectangle(x0, y0, x0 + bar_width, h - padding_y, fill=ACCENT_BLUE, outline="")
            
            # X-Axis Labels (Rotated for fit)
            label_text = str(dept)[:12] + ".." if len(str(dept)) > 12 else str(dept)
            self._chart_canvas.create_text(x0 + bar_width/2, h - padding_y + 15, text=label_text, font=("Space Mono", 8, "bold"), fill=TEXT_MUTED, angle=45, anchor=tk.NW)
            
            # Value Callouts
            if total > 0:
                self._chart_canvas.create_text(x0 + bar_width/2, y0 - 12, text=str(total), font=("JetBrains Mono", 9, "bold"), fill=TEXT_HIGH)

        # Baseline (Themed)
        self._chart_canvas.create_line(padding_x - 10, h - padding_y, w - padding_x + 10, h - padding_y, fill=BORDER_COLOR, width=2)

    # ── Calendar Tab Implementation ───────────────────────────────────────
    #  Premium OLED Canvas Calendar – Nebula Midnight Design System
    #  Canvas-based rendering for pixel-perfect cells with hover/today/holiday states

    # ── Design constants local to calendar ───────────────────────────────
    _CAL_BG         = "#0A1120"   # Deep void background (darker than MAIN_BG)
    _CAL_CELL_NORM  = "#111827"   # Normal day cell background
    _CAL_CELL_WE    = "#0D1520"   # Weekend cell (slightly dimmer)
    _CAL_CELL_TODAY = "#0D2240"   # Today highlight fill
    _CAL_CELL_HOL   = "#1A1200"   # Holiday fill (deep amber tint)
    _CAL_RING_TODAY = "#7DD3FC"   # Today ring (primary sky-blue)
    _CAL_HOL_AMBER  = "#F59E0B"   # Holiday text/ring
    _CAL_HOL_GLOW   = "#3D2800"   # Holiday hover glow fill
    _CAL_HOVER      = "#1C2A3A"   # Hover fill for normal days
    _CAL_GRID_LINE  = "#1E293B"   # Cell border/separator
    _CAL_WE_TEXT    = "#64748B"   # Weekend day number muted
    _CAL_NORM_TEXT  = "#CBD5E1"   # Normal day number
    _CAL_DOT_HOL    = "#F59E0B"   # Holiday dot
    _CAL_HDR_BG     = "#0F172A"   # Header row bg
    _CAL_HDR_TEXT   = "#475569"   # Header day names
    _CAL_HDR_WE     = "#334155"   # Header weekend

    # Cell geometry
    _CELL_W  = 88
    _CELL_H  = 80
    _CELL_PAD = 3   # Gap between cells
    _HDR_H   = 32   # Header row height
    _CANVAS_PADX = 12
    _CANVAS_PADY = 8

    def _build_calendar_tab(self):
        """Builds a premium OLED canvas-based calendar for public holiday management."""
        import calendar
        from datetime import date as dt_date

        self._calendar_year  = dt_date.today().year
        self._calendar_month = dt_date.today().month
        self._cal_hover_item = None   # Track hovered canvas cell
        self._cal_cell_map   = {}     # Maps canvas item-id -> date_str / holiday_obj

        # ── Main horizontal split ──────────────────────────────────────────
        outer = tk.Frame(self._tab_calendar, bg=self._CAL_BG)
        outer.pack(fill=BOTH, expand=YES)

        left_col = tk.Frame(outer, bg=self._CAL_BG)
        left_col.pack(side=LEFT, fill=BOTH, expand=YES, padx=(16, 8), pady=12)

        right_col = tk.Frame(outer, bg=MAIN_BG, width=340)
        right_col.pack(side=RIGHT, fill=Y, padx=(4, 12), pady=12)
        right_col.pack_propagate(False)

        # ── Left: Navigation bar ───────────────────────────────────────────
        nav = tk.Frame(left_col, bg=self._CAL_BG)
        nav.pack(fill=X, pady=(0, 10))

        # Prev / Next buttons (minimal ghost style)
        btn_cfg = dict(bg=self._CAL_BG, fg="#7DD3FC", activebackground="#1C2A3A",
                       activeforeground="#7DD3FC", relief="flat", bd=0,
                       font=("JetBrains Mono", 14, "bold"), cursor="hand2", padx=8, pady=2)
        tk.Button(nav, text="◂", command=self._prev_calendar_month, **btn_cfg).pack(side=LEFT)
        tk.Button(nav, text="▸", command=self._next_calendar_month, **btn_cfg).pack(side=LEFT, padx=(2,0))

        self._cal_title_var = tk.StringVar()
        tk.Label(
            nav, textvariable=self._cal_title_var, bg=self._CAL_BG, fg="#F1F5F9",
            font=("Plus Jakarta Sans", 15, "bold"), anchor="w"
        ).pack(side=LEFT, padx=14)

        # Add Holiday button on the right of nav
        add_btn = tk.Button(
            nav, text="+ Add Holiday",
            bg="#1A0E00", fg=self._CAL_HOL_AMBER, activebackground="#2D1A00",
            activeforeground=self._CAL_HOL_AMBER, relief="flat", bd=1,
            highlightbackground=self._CAL_HOL_AMBER, highlightthickness=1,
            font=("Plus Jakarta Sans", 9, "bold"), cursor="hand2", padx=10, pady=4,
            command=self._open_holiday_dialog
        )
        add_btn.pack(side=RIGHT, padx=4)

        # Import from Web button
        import_btn = tk.Button(
            nav, text="🌐 Import from Web",
            bg="#0D1E2A", fg="#38BDF8", activebackground="#1E293B",
            activeforeground="#38BDF8", relief="flat", bd=1,
            highlightbackground="#38BDF8", highlightthickness=1,
            font=("Plus Jakarta Sans", 9, "bold"), cursor="hand2", padx=10, pady=4,
            command=self._open_import_holidays_dialog
        )
        import_btn.pack(side=RIGHT, padx=4)

        # ── Left: Canvas calendar grid ─────────────────────────────────────
        # Canvas size: 7 cols × max 6 rows + 1 header
        canvas_w = 7 * (self._CELL_W + self._CELL_PAD) + self._CELL_PAD + self._CANVAS_PADX * 2
        canvas_h = 6 * (self._CELL_H + self._CELL_PAD) + self._CELL_PAD + self._HDR_H + self._CANVAS_PADY * 2

        self._cal_canvas = tk.Canvas(
            left_col, bg=self._CAL_BG, highlightthickness=0,
            width=canvas_w, height=canvas_h
        )
        self._cal_canvas.pack(fill=BOTH, expand=YES)

        # Bind mouse events
        self._cal_canvas.bind("<Motion>",   self._cal_on_hover)
        self._cal_canvas.bind("<Leave>",    self._cal_on_leave)
        self._cal_canvas.bind("<Button-1>", self._cal_on_click)

        # ── Right panel ────────────────────────────────────────────────────
        # Stats card at top
        self._cal_stats_frame = tk.Frame(right_col, bg=PANEL_BG)
        self._cal_stats_frame.pack(fill=X, padx=2, pady=(2, 8))

        # Section title
        tk.Label(
            right_col, text="HOLIDAY REGISTRY",
            bg=MAIN_BG, fg="#475569",
            font=("Plus Jakarta Sans", 8, "bold"), anchor="w"
        ).pack(fill=X, padx=6, pady=(0, 4))

        self._holiday_list_frame = tk.Frame(right_col, bg=MAIN_BG)
        self._holiday_list_frame.pack(fill=BOTH, expand=YES, padx=2)

        # Hint label
        tk.Label(
            right_col,
            text="Double-click a row to edit or delete",
            bg=MAIN_BG, fg="#334155",
            font=("Plus Jakarta Sans", 8, "italic")
        ).pack(anchor="w", padx=6, pady=(4, 2))

        # Initial render
        self._refresh_calendar_view()

    # ── Canvas rendering helpers ───────────────────────────────────────────

    def _cal_draw_cell(
        self, col, row, day, date_str, is_today, is_holiday, is_weekend, holiday_obj
    ):
        """Draw a single day cell on the canvas at grid (col, row)."""
        px = self._CANVAS_PADX + col * (self._CELL_W + self._CELL_PAD)
        py = self._CANVAS_PADY + self._HDR_H + row * (self._CELL_H + self._CELL_PAD)
        x2, y2 = px + self._CELL_W, py + self._CELL_H

        c = self._cal_canvas

        # ── Cell background ──
        if is_holiday:
            fill = self._CAL_CELL_HOL
        elif is_today:
            fill = self._CAL_CELL_TODAY
        elif is_weekend:
            fill = self._CAL_CELL_WE
        else:
            fill = self._CAL_CELL_NORM

        rect = c.create_rectangle(
            px, py, x2, y2,
            fill=fill, outline=self._CAL_GRID_LINE, width=1
        )

        # ── Today ring ──
        if is_today:
            ring = c.create_rectangle(
                px + 2, py + 2, x2 - 2, y2 - 2,
                fill="", outline=self._CAL_RING_TODAY, width=2
            )
        else:
            ring = None

        # ── Holiday top accent bar ──
        accent = None
        if is_holiday:
            accent = c.create_rectangle(
                px + 1, py + 1, x2 - 1, py + 4,
                fill=self._CAL_HOL_AMBER, outline=""
            )

        # ── Day number ──
        if is_holiday:
            num_color = self._CAL_HOL_AMBER
            num_font  = ("JetBrains Mono", 15, "bold")
        elif is_today:
            num_color = self._CAL_RING_TODAY
            num_font  = ("JetBrains Mono", 15, "bold")
        elif is_weekend:
            num_color = self._CAL_WE_TEXT
            num_font  = ("JetBrains Mono", 14, "normal")
        else:
            num_color = self._CAL_NORM_TEXT
            num_font  = ("JetBrains Mono", 14, "normal")

        num = c.create_text(
            px + 12, py + 14,
            text=str(day), fill=num_color, font=num_font, anchor="nw"
        )

        # ── Holiday name (short) ──
        hol_txt = None
        if is_holiday and holiday_obj:
            short_name = holiday_obj.name[:13] + "…" if len(holiday_obj.name) > 14 else holiday_obj.name
            hol_txt = c.create_text(
                px + self._CELL_W // 2, py + self._CELL_H - 18,
                text=short_name, fill="#D97706",
                font=("Plus Jakarta Sans", 7, "bold"), anchor="center"
            )

        # ── Holiday dot ──
        dot = None
        if is_holiday:
            dot = c.create_oval(
                px + self._CELL_W // 2 - 3, py + self._CELL_H - 8,
                px + self._CELL_W // 2 + 3, py + self._CELL_H - 2,
                fill=self._CAL_DOT_HOL, outline=""
            )

        # Register all drawn items to the cell map for hover/click
        items = [rect, ring, accent, num, hol_txt, dot]
        items = [i for i in items if i is not None]
        cell_info = {"date_str": date_str, "holiday_obj": holiday_obj,
                     "fill": fill, "rect": rect, "items": items,
                     "is_today": is_today, "is_holiday": is_holiday, "is_weekend": is_weekend}
        for item in items:
            self._cal_cell_map[item] = cell_info

    def _cal_on_hover(self, event):
        """Highlight the cell under the cursor."""
        if not getattr(self, "_cal_canvas", None) or not self._cal_canvas.winfo_exists():
            return
        item = self._cal_canvas.find_closest(event.x, event.y)
        if not item:
            return
        item = item[0]
        info = self._cal_cell_map.get(item)
        if info is None:
            self._cal_reset_hover()
            return
        rect = info["rect"]
        if rect == getattr(self, "_cal_hovered_rect", None):
            return   # Same cell, no update
        self._cal_reset_hover()
        self._cal_hovered_rect = rect
        hover_fill = self._CAL_HOL_GLOW if info["is_holiday"] else self._CAL_HOVER
        self._cal_canvas.itemconfigure(rect, fill=hover_fill)
        self._cal_canvas.config(cursor="hand2")

    def _cal_on_leave(self, event):
        if not getattr(self, "_cal_canvas", None) or not self._cal_canvas.winfo_exists():
            return
        self._cal_reset_hover()
        self._cal_canvas.config(cursor="")

    def _cal_reset_hover(self):
        if not getattr(self, "_cal_canvas", None) or not self._cal_canvas.winfo_exists():
            return
        rect = getattr(self, "_cal_hovered_rect", None)
        if rect and rect in self._cal_canvas.find_all():
            info = self._cal_cell_map.get(rect)
            if info:
                self._cal_canvas.itemconfigure(rect, fill=info["fill"])
        self._cal_hovered_rect = None

    def _cal_on_click(self, event):
        if not getattr(self, "_cal_canvas", None) or not self._cal_canvas.winfo_exists():
            return
        item = self._cal_canvas.find_closest(event.x, event.y)
        if not item:
            return
        info = self._cal_cell_map.get(item[0])
        if info:
            self._day_clicked(info["date_str"], info["holiday_obj"])

    # ── Core refresh ──────────────────────────────────────────────────────

    def _refresh_calendar_view(self):
        import calendar
        from datetime import date as dt_date

        # Reset canvas and cell map
        self._cal_canvas.delete("all")
        self._cal_cell_map.clear()
        self._cal_hovered_rect = None

        # ── Title ──
        MONTH_NAMES_FR = ["","Janvier","Février","Mars","Avril","Mai","Juin",
                          "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        self._cal_title_var.set(
            f"{MONTH_NAMES_FR[self._calendar_month].upper()}  {self._calendar_year}"
        )

        # ── Header row (day names) ──
        DAY_LABELS = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
        for col, label in enumerate(DAY_LABELS):
            is_we = col >= 5
            cx = self._CANVAS_PADX + col * (self._CELL_W + self._CELL_PAD) + self._CELL_W // 2
            cy = self._CANVAS_PADY + self._HDR_H // 2
            self._cal_canvas.create_text(
                cx, cy, text=label,
                fill=self._CAL_HDR_WE if is_we else self._CAL_HDR_TEXT,
                font=("Plus Jakarta Sans", 9, "bold"), anchor="center"
            )

        # ── Load holidays ──
        month_str = f"{self._calendar_year}-{self._calendar_month:02d}"
        from contragest.core.database import PublicHoliday
        h_list = self.service.session.query(PublicHoliday).filter(
            PublicHoliday.date.like(f"{month_str}-%")
        ).all()
        h_dict = {h.date: h for h in h_list}

        today_iso = dt_date.today().isoformat()

        # ── Draw cells ──
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(self._calendar_year, self._calendar_month)

        for r_idx, week in enumerate(month_days):
            for c_idx, day in enumerate(week):
                if day == 0:
                    continue
                date_str   = f"{self._calendar_year}-{self._calendar_month:02d}-{day:02d}"
                is_today   = (date_str == today_iso)
                is_holiday = date_str in h_dict
                is_weekend = c_idx >= 5
                self._cal_draw_cell(
                    col=c_idx, row=r_idx, day=day,
                    date_str=date_str, is_today=is_today,
                    is_holiday=is_holiday, is_weekend=is_weekend,
                    holiday_obj=h_dict.get(date_str)
                )

        # Subtle horizontal line under header
        lx2 = self._CANVAS_PADX + 7 * (self._CELL_W + self._CELL_PAD) - self._CELL_PAD
        self._cal_canvas.create_line(
            self._CANVAS_PADX, self._CANVAS_PADY + self._HDR_H - 2,
            lx2, self._CANVAS_PADY + self._HDR_H - 2,
            fill="#1E293B", width=1
        )

        # Refresh right panel
        self._refresh_holiday_list()

    def _refresh_holiday_list(self):
        """Rebuild the right-side stats card + holiday table."""
        # ── Stats card ──
        for w in self._cal_stats_frame.winfo_children():
            w.destroy()

        all_holidays = self.service.get_public_holidays(self._calendar_year)
        month_count  = sum(
            1 for h in all_holidays
            if h.date.startswith(f"{self._calendar_year}-{self._calendar_month:02d}-")
        )
        year_count   = len(all_holidays)

        stats_inner = tk.Frame(self._cal_stats_frame, bg=PANEL_BG)
        stats_inner.pack(fill=X, padx=6, pady=6)

        def _stat_chip(parent, value, label, color):
            chip = tk.Frame(parent, bg="#0F172A", padx=12, pady=6)
            chip.pack(side=LEFT, padx=4, pady=4)
            tk.Label(chip, text=str(value), bg="#0F172A", fg=color,
                     font=("JetBrains Mono", 18, "bold")).pack()
            tk.Label(chip, text=label, bg="#0F172A", fg="#475569",
                     font=("Plus Jakarta Sans", 7, "normal")).pack()

        month_names_short = ["","Jan","Fév","Mar","Avr","Mai","Jun",
                             "Jul","Aoû","Sep","Oct","Nov","Déc"]
        _stat_chip(stats_inner, month_count,
                   f"CE MOIS ({month_names_short[self._calendar_month]})",
                   self._CAL_HOL_AMBER)
        _stat_chip(stats_inner, year_count,
                   f"TOTAL {self._calendar_year}", "#7DD3FC")

        # ── Holiday list ──
        for w in self._holiday_list_frame.winfo_children():
            w.destroy()

        cols = ["Date", "Nom du Jour Férié", "Description"]
        rows = [[h.date, h.name, h.description or ""] for h in all_holidays]

        table = Tableview(
            master=self._holiday_list_frame, coldata=cols, rowdata=rows,
            paginated=False, searchable=True, bootstyle="dark", autofit=True
        )
        table.pack(fill=BOTH, expand=YES)
        table.view.bind("<Double-1>", lambda e: self._on_holiday_table_double_click(table))

    def _on_holiday_table_double_click(self, table):
        selection = table.view.selection()
        if not selection:
            return
        vals    = table.view.item(selection[0], "values")
        h_date  = vals[0]
        from contragest.core.database import PublicHoliday
        holiday = self.service.session.query(PublicHoliday).filter_by(date=h_date).first()
        if holiday:
            self._open_holiday_dialog(holiday)

    def _day_clicked(self, date_str, holiday_obj=None):
        self._open_holiday_dialog(holiday_obj, initial_date=date_str)

    def _prev_calendar_month(self):
        self._calendar_month -= 1
        if self._calendar_month < 1:
            self._calendar_month = 12
            self._calendar_year -= 1
        self._refresh_calendar_view()

    def _next_calendar_month(self):
        self._calendar_month += 1
        if self._calendar_month > 12:
            self._calendar_month = 1
            self._calendar_year += 1
        self._refresh_calendar_view()

    def _open_holiday_dialog(self, holiday_obj=None, initial_date=None):
        """Premium dark dialog for adding / editing a public holiday."""
        # ── Window setup ──
        dialog = tk.Toplevel(self)
        dialog.title("")
        dialog.geometry("420x330")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg="#080F1E")
        dialog.overrideredirect(False)

        # ── Dark card container ──
        card = tk.Frame(dialog, bg=PANEL_BG, padx=24, pady=20)
        card.pack(fill=BOTH, expand=YES, padx=1, pady=1)

        # ── Header ──
        is_edit  = holiday_obj is not None
        hdr_text = "MODIFIER LE JOUR FÉRIÉ" if is_edit else "AJOUTER UN JOUR FÉRIÉ"
        tk.Label(
            card, text=hdr_text, bg=PANEL_BG,
            fg=self._CAL_HOL_AMBER if is_edit else self._CAL_RING_TODAY,
            font=("Plus Jakarta Sans", 11, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))

        # ── Field builder ──
        field_cfg = dict(bg=PANEL_BG, fg="#94A3B8", font=("Plus Jakarta Sans", 8, "bold"), anchor="w")
        entry_cfg = dict(
            bg="#0F172A", fg="#F1F5F9",
            insertbackground="#7DD3FC",
            relief="flat", bd=0,
            font=("JetBrains Mono", 10),
            highlightthickness=1, highlightbackground="#1E293B",
            highlightcolor="#7DD3FC"
        )

        def make_field(row_idx, label, var):
            tk.Label(card, text=label, **field_cfg).grid(
                row=row_idx, column=0, sticky="w", pady=(0, 2)
            )
            ent = tk.Entry(card, textvariable=var, width=32, **entry_cfg)
            ent.grid(row=row_idx + 1, column=0, columnspan=2, sticky="ew", pady=(0, 12), ipady=6)
            return ent

        date_var = tk.StringVar(value=(
            holiday_obj.date if holiday_obj
            else (initial_date or datetime.now().strftime("%Y-%m-%d"))
        ))
        name_var = tk.StringVar(value=holiday_obj.name if holiday_obj else "")
        desc_var = tk.StringVar(value=(holiday_obj.description or "") if holiday_obj else "")

        make_field(1, "DATE  (YYYY-MM-DD)", date_var)
        make_field(3, "NOM DU JOUR FÉRIÉ",  name_var)
        make_field(5, "DESCRIPTION  (optionnel)", desc_var)

        card.columnconfigure(0, weight=1)

        # ── Action buttons ──
        btn_row = tk.Frame(card, bg=PANEL_BG)
        btn_row.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        def _mk_btn(parent, text, bg, fg, cmd, side=RIGHT):
            b = tk.Button(
                parent, text=text, command=cmd,
                bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
                relief="flat", bd=0, font=("Plus Jakarta Sans", 9, "bold"),
                cursor="hand2", padx=14, pady=6
            )
            b.pack(side=side, padx=3)
            return b

        def save_action():
            d    = date_var.get().strip()
            n    = name_var.get().strip()
            desc = desc_var.get().strip()
            if not d or not n:
                Messagebox.show_warning("La date et le nom sont requis.", "Champs manquants", parent=dialog)
                return
            try:
                datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                Messagebox.show_warning("Format de date invalide. Utilisez YYYY-MM-DD.", "Erreur", parent=dialog)
                return
            try:
                data = {"date": d, "name": n, "description": desc}
                self.service.save_public_holiday(
                    data, holiday_id=holiday_obj.id if holiday_obj else None
                )
                self._refresh_calendar_view()
                dialog.destroy()
            except Exception as exc:
                Messagebox.show_error(f"Erreur base de données : {exc}", "Erreur", parent=dialog)

        def delete_action():
            if not holiday_obj:
                return
            confirm = Messagebox.show_question(
                f"Supprimer '{holiday_obj.name}' ?", "Confirmer la suppression", parent=dialog
            )
            if confirm == "Yes":
                try:
                    self.service.delete_public_holiday(holiday_obj.id)
                    self._refresh_calendar_view()
                    dialog.destroy()
                except Exception as exc:
                    Messagebox.show_error(f"Erreur : {exc}", "Erreur", parent=dialog)

        _mk_btn(btn_row, "Enregistrer", "#064E3B", "#10B981", save_action, RIGHT)
        _mk_btn(btn_row, "Annuler",    "#1E293B", "#94A3B8", dialog.destroy, RIGHT)
        if is_edit:
            _mk_btn(btn_row, "Supprimer", "#3B0D0D", "#EF4444", delete_action, LEFT)

    def _open_import_holidays_dialog(self):
        """Premium dark dialog for importing public holidays from the web."""
        # ── Window setup ──
        dialog = tk.Toplevel(self)
        dialog.title("")
        dialog.geometry("400x260")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg="#080F1E")

        # ── Dark card container ──
        card = tk.Frame(dialog, bg=PANEL_BG, padx=24, pady=20)
        card.pack(fill=BOTH, expand=YES, padx=1, pady=1)

        # ── Header ──
        tk.Label(
            card, text="🌐 IMPORTATION DE JOURS FÉRIÉS", bg=PANEL_BG,
            fg="#38BDF8", font=("Plus Jakarta Sans", 11, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))

        # ── Field builder ──
        field_cfg = dict(bg=PANEL_BG, fg="#94A3B8", font=("Plus Jakarta Sans", 8, "bold"), anchor="w")
        entry_cfg = dict(
            bg="#0F172A", fg="#F1F5F9",
            insertbackground="#7DD3FC",
            relief="flat", bd=0,
            font=("JetBrains Mono", 10),
            highlightthickness=1, highlightbackground="#1E293B",
            highlightcolor="#7DD3FC"
        )

        def make_field(row_idx, label, var):
            tk.Label(card, text=label, **field_cfg).grid(
                row=row_idx, column=0, sticky="w", pady=(0, 2)
            )
            ent = tk.Entry(card, textvariable=var, width=32, **entry_cfg)
            ent.grid(row=row_idx + 1, column=0, columnspan=2, sticky="ew", pady=(0, 12), ipady=6)
            return ent

        year_var = tk.StringVar(value=str(self._calendar_year))
        country_var = tk.StringVar(value="TN")

        make_field(1, "ANNÉE (YYYY)", year_var)
        make_field(3, "CODE PAYS (ex: TN, FR, US)", country_var)

        card.columnconfigure(0, weight=1)

        # ── Action buttons ──
        btn_row = tk.Frame(card, bg=PANEL_BG)
        btn_row.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        def _mk_btn(parent, text, bg, fg, cmd, side=RIGHT):
            b = tk.Button(
                parent, text=text, command=cmd,
                bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
                relief="flat", bd=0, font=("Plus Jakarta Sans", 9, "bold"),
                cursor="hand2", padx=14, pady=6
            )
            b.pack(side=side, padx=3)
            return b

        def import_action():
            yr_str = year_var.get().strip()
            cc_str = country_var.get().strip()
            if not yr_str or not cc_str:
                Messagebox.show_warning("L'année et le code pays sont requis.", "Champs manquants", parent=dialog)
                return
            try:
                yr = int(yr_str)
            except ValueError:
                Messagebox.show_warning("L'année doit être un nombre valide.", "Erreur", parent=dialog)
                return

            # Display "importing..." status inside the button
            btn_import.configure(text="Importation...", state=tk.DISABLED)
            dialog.update()

            try:
                # Run the import via pointage service
                count, err = self.service.bulk_import_public_holidays(yr, cc_str)
                if err:
                    Messagebox.show_error(f"Erreur d'importation : {err}", "Erreur", parent=dialog)
                else:
                    Messagebox.show_info(f"Importation réussie de {count} jours fériés.", "Succès", parent=dialog)
                    self._refresh_calendar_view()
                    dialog.destroy()
            except Exception as exc:
                Messagebox.show_error(f"Erreur inattendue : {exc}", "Erreur", parent=dialog)
            finally:
                try:
                    btn_import.configure(text="Importer", state=tk.NORMAL)
                except:
                    pass

        btn_import = _mk_btn(btn_row, "Importer", "#0284C7", "#F1F5F9", import_action, RIGHT)
        _mk_btn(btn_row, "Annuler",    "#1E293B", "#94A3B8", dialog.destroy, RIGHT)

    # ── Cleanup ───────────────────────────────────────────────────────────

    def after(self, ms, func=None, *args):
        """Override after() to auto-track timer IDs for cleanup on destroy."""
        timer_id = super().after(ms, func, *args) if func else super().after(ms, func)
        if func:
            pending = getattr(self, "_pending_timers", None)
            if pending is not None:
                pending.add(timer_id)
        return timer_id

    def after_cancel(self, timer_id):
        """Override after_cancel to remove from tracking set."""
        pending = getattr(self, "_pending_timers", None)
        if pending is not None:
            pending.discard(timer_id)
        super().after_cancel(timer_id)

    def _safe_pack_forget(self, attr_name):
        """Forget a frame by attribute name if it still exists."""
        if self.winfo_exists():
            frame = getattr(self, attr_name, None)
            if frame and frame.winfo_exists():
                frame.pack_forget()

    def destroy(self):
        try:
            if hasattr(self, "session") and self.session:
                self.session.close()
        except Exception:
            pass
        # Cancel all pending after() timers to prevent TclErrors on destroyed widgets
        for timer_id in list(getattr(self, "_pending_timers", set())):
            try:
                self.after_cancel(timer_id)
            except Exception:
                pass
        self._pending_timers = set()
        super().destroy()

    def __del__(self):
        try:
            if hasattr(self, "session") and self.session:
                self.session.close()
        except Exception:
            pass
