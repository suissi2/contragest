import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tableview import Tableview
from contragest.core.database import SessionLocal, WorkSchedule
from contragest.features.pointage.service import PointageService
from contragest.core.i18n import tr
from contragest.core.gui_utils import DesignTokens
import re

class MasterScheduleManager(ttk.Toplevel):
    """
    A lightweight, dedicated manager for work schedules.
    Provides full CRUD operations without the overhead of the attendance terminal.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"🕒 {tr('schedule_admin')}")
        self.geometry("1100x700")
        self.resizable(True, True)
        self.grab_set()

        self.session = SessionLocal()
        self.service = PointageService(self.session)
        self.selected_schedule_id = None
        self._sched_vars = {}

        self._build_ui()
        self._load_schedules()
        self.center_window()

    def _build_ui(self):
        main_container = ttk.Frame(self, padding=10)
        main_container.pack(fill=BOTH, expand=YES)

        paned = ttk.Panedwindow(main_container, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=YES)

        # ── Left Panel: List ──
        list_frame = ttk.LabelFrame(paned, text=f"📋 {tr('schedule_admin')}")
        paned.add(list_frame, weight=3)

        self._table_container = ttk.Frame(list_frame)
        self._table_container.pack(fill=BOTH, expand=YES, padx=5, pady=5)
        self._table = None

        # ── Right Panel: Form ──
        form_outer = ttk.Frame(paned)
        paned.add(form_outer, weight=2)
        
        # Scrollable form container
        canvas = tk.Canvas(form_outer, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(form_outer, orient=VERTICAL, command=canvas.yview)
        self.form_inner = ttk.Frame(canvas, padding=10)
        
        self.form_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.form_inner, anchor="nw", width=420)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        self._build_form(self.form_inner)

    def _build_form(self, parent):
        # Actions
        btn_fr = ttk.Frame(parent)
        btn_fr.pack(fill=X, pady=(0, 10))
        
        ttk.Button(btn_fr, text=f"➕ {tr('new')}", command=self._clear_form, bootstyle=SUCCESS).pack(side=LEFT, padx=2)
        ttk.Button(btn_fr, text=f"💾 {tr('save')}", command=self._save_schedule, bootstyle=SUCCESS).pack(side=LEFT, padx=2)
        ttk.Button(btn_fr, text=f"❌ {tr('delete')}", command=self._delete_schedule, bootstyle=DANGER).pack(side=LEFT, padx=2)

        ttk.Separator(parent, orient=HORIZONTAL).pack(fill=X, pady=5)

        # 1. Basic Info
        lf_basic = ttk.LabelFrame(parent, text="Basic Info")
        lf_basic.pack(fill=X, pady=5)
        
        inner_basic = ttk.Frame(lf_basic, padding=10)
        inner_basic.pack(fill=X)
        
        ttk.Label(inner_basic, text=tr("schedule_name")).pack(anchor=W)
        self._sched_vars["name"] = tk.StringVar()
        ttk.Entry(inner_basic, textvariable=self._sched_vars["name"]).pack(fill=X, pady=(2, 10))

        # 2. Timing
        lf_time = ttk.LabelFrame(parent, text="Timing")
        lf_time.pack(fill=X, pady=5)
        
        inner_time = ttk.Frame(lf_time, padding=10)
        inner_time.pack(fill=X)
        
        time_fields = [
            ("Start", "start_time", "08:00"), ("End", "end_time", "17:00"),
            ("Break In", "break_start", "12:00"), ("Break Out", "break_end", "13:00")
        ]
        grid = ttk.Frame(inner_time)
        grid.pack(fill=X)
        
        for i, (lbl, key, def_val) in enumerate(time_fields):
            r, c = divmod(i, 2)
            f = ttk.Frame(grid)
            f.grid(row=r, column=c, sticky="ew", padx=2, pady=2)
            ttk.Label(f, text=lbl, font=("Helvetica", 8)).pack(anchor=W)
            self._sched_vars[key] = tk.StringVar(value=def_val)
            ent = ttk.Entry(f, textvariable=self._sched_vars[key], justify="center", font=("Courier", 10, "bold"))
            ent.pack(fill=X)
            ent.bind("<KeyRelease>", self._on_time_key)
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)

        # 3. Calculation
        lf_calc = ttk.LabelFrame(parent, text="Calculation")
        lf_calc.pack(fill=X, pady=5)
        
        inner_calc = ttk.Frame(lf_calc, padding=10)
        inner_calc.pack(fill=X)
        
        ttk.Label(inner_calc, text="Total Hours").pack(anchor=W)
        self._sched_vars["total_hours"] = tk.DoubleVar(value=8.0)
        ttk.Spinbox(inner_calc, from_=0, to=24, increment=0.5, textvariable=self._sched_vars["total_hours"]).pack(fill=X, pady=(2, 5))

    def _load_schedules(self):
        for child in self._table_container.winfo_children():
            child.destroy()
            
        schedules = self.session.query(WorkSchedule).order_by(WorkSchedule.name).all()
        cols = ["ID", "SCHEDULE NAME", "Timing", "Work Time"]
        rows = []
        for s in schedules:
            timing = f"{s.start_time or ''} - {s.end_time or ''}"
            rows.append((s.id, s.name, timing, f"{s.total_hours or 0}h"))
            
        self._table = Tableview(
            master=self._table_container,
            coldata=cols,
            rowdata=rows,
            paginated=False,
            searchable=True,
            bootstyle=PRIMARY,
            autofit=True
        )
        self._table.pack(fill=BOTH, expand=YES)
        self._table.view.bind("<<TreeviewSelect>>", self._on_select)

    def _on_select(self, _=None):
        sel = self._table.view.selection()
        if not sel: return
        item = self._table.view.item(sel[0])
        val = item['values']
        self.selected_schedule_id = int(val[0])
        
        sched = self.session.query(WorkSchedule).get(self.selected_schedule_id)
        if sched:
            self._sched_vars["name"].set(sched.name or "")
            self._sched_vars["start_time"].set(sched.start_time or "08:00")
            self._sched_vars["end_time"].set(sched.end_time or "17:00")
            self._sched_vars["break_start"].set(sched.break_start or "12:00")
            self._sched_vars["break_end"].set(sched.break_end or "13:00")
            self._sched_vars["total_hours"].set(sched.total_hours or 8.0)

    def _clear_form(self):
        self.selected_schedule_id = None
        if "name" in self._sched_vars:
            self._sched_vars["name"].set("")
        for k in ["start_time", "end_time", "break_start", "break_end"]:
            if k in self._sched_vars:
                self._sched_vars[k].set("")
        if "total_hours" in self._sched_vars:
            self._sched_vars["total_hours"].set(8.0)
        
        if self._table:
            self._table.view.selection_remove(self._table.view.selection())

    def _save_schedule(self):
        data = {k: v.get() for k, v in self._sched_vars.items()}
        if not data["name"]:
            Messagebox.show_error("Name is required", "Error")
            return
            
        try:
            self.service.save_schedule(data, self.selected_schedule_id)
            Messagebox.show_info("Schedule Saved", "Success")
            self._load_schedules()
        except Exception as e:
            Messagebox.show_error(str(e), "Error")

    def _delete_schedule(self):
        if not self.selected_schedule_id: return
        if Messagebox.show_question("Delete this schedule?", "Confirm") == "Yes":
            self.service.delete_schedule(self.selected_schedule_id)
            self._clear_form()
            self._load_schedules()

    def _on_time_key(self, event):
        val = event.widget.get()
        digits = ''.join(filter(str.isdigit, val))[:4]
        if len(digits) >= 2:
            formatted = digits[:2] + ":" + digits[2:]
            if val != formatted:
                event.widget.delete(0, tk.END)
                event.widget.insert(0, formatted)

    def center_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"+{x}+{y}")

    def destroy(self):
        self.session.close()
        super().destroy()
