import tkinter as tk
import ttkbootstrap as ttk
from tkinter import messagebox
from typing import Optional, Dict, Any
import re
import os
import sys

# Ensure correct path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from contragest.core.database import SessionLocal, WorkSchedule
from contragest.features.pointage.service import PointageService
from contragest.core.i18n import tr

class ScheduleQuickAddDialog(ttk.Toplevel):
    """A standalone dialog to quickly add/edit a WorkSchedule."""
    
    def __init__(self, parent, schedule_id: Optional[int] = None, on_save_callback=None):
        super().__init__(parent)
        self.schedule_id = schedule_id
        self.on_save_callback = on_save_callback
        
        self.title(tr("add_schedule") if not schedule_id else tr("edit_schedule"))
        self.geometry("400x500")
        self.resizable(False, False)
        self.grab_set()
        
        self.session = SessionLocal()
        self.service = PointageService(self.session)
        
        self.vars = {
            "name": tk.StringVar(),
            "start_time": tk.StringVar(value="08:00"),
            "end_time": tk.StringVar(value="17:00"),
            "break_start": tk.StringVar(value="12:00"),
            "break_end": tk.StringVar(value="13:00"),
            "total_hours": tk.StringVar(value="8.0"),
            "color_hex": tk.StringVar(value="#0055ff")
        }
        
        if self.schedule_id:
            self._load_data()
            
        self._build_ui()
        self.center_window()

    def _load_data(self):
        sched = self.session.query(WorkSchedule).get(self.schedule_id)
        if sched:
            self.vars["name"].set(sched.name or "")
            self.vars["start_time"].set(sched.start_time or "08:00")
            self.vars["end_time"].set(sched.end_time or "17:00")
            self.vars["break_start"].set(sched.break_start or "12:00")
            self.vars["break_end"].set(sched.break_end or "13:00")
            self.vars["total_hours"].set(str(sched.total_hours or 8.0))
            self.vars["color_hex"].set(sched.color_hex or "#0055ff")

    def _build_ui(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Name
        ttk.Label(container, text=tr("schedule_name")).pack(fill=tk.X, pady=(0, 2))
        ttk.Entry(container, textvariable=self.vars["name"]).pack(fill=tk.X, pady=(0, 10))
        
        # Grid for times
        times_fr = ttk.Frame(container)
        times_fr.pack(fill=tk.X)
        
        fields = [
            (tr("start_time"), "start_time", 0, 0),
            (tr("end_time"), "end_time", 0, 1),
            (tr("break_start"), "break_start", 1, 0),
            (tr("break_end"), "break_end", 1, 1),
        ]
        
        for lbl, var_key, r, c in fields:
            f = ttk.Frame(times_fr)
            f.grid(row=r, column=c, sticky="ew", padx=2, pady=5)
            ttk.Label(f, text=lbl, font=("Helvetica", 8)).pack(anchor="w")
            ttk.Entry(f, textvariable=self.vars[var_key], width=12).pack(fill=tk.X)
            
        times_fr.columnconfigure(0, weight=1)
        times_fr.columnconfigure(1, weight=1)
        
        # Total Hours
        ttk.Label(container, text=tr("total_hours")).pack(fill=tk.X, pady=(10, 2))
        ttk.Entry(container, textvariable=self.vars["total_hours"]).pack(fill=tk.X)
        
        # Spacing
        ttk.Frame(container, height=20).pack()
        
        # Buttons
        btn_fr = ttk.Frame(container)
        btn_fr.pack(fill=tk.X, side=tk.BOTTOM)
        
        ttk.Button(btn_fr, text=tr("cancel"), bootstyle="secondary-outline", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_fr, text=tr("save"), bootstyle="success", command=self._on_save).pack(side=tk.RIGHT, padx=5)

    def _on_save(self):
        data = {k: v.get() for k, v in self.vars.items()}
        try:
            # Validation
            if not data["name"].strip():
                messagebox.showerror(tr("error"), tr("required_field_missing").replace("{field}", tr("schedule_name")))
                return
                
            time_pattern = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")
            for t_field in ["start_time", "end_time", "break_start", "break_end"]:
                if data[t_field] and not time_pattern.match(data[t_field]):
                    messagebox.showerror(tr("error"), f"Invalid format for {t_field} (Use HH:MM)")
                    return
            
            # Additional fields required by pointage_service.save_schedule
            data["days_of_week"] = "Mon,Tue,Wed,Thu,Fri,Sat,Sun"
            
            self.service.save_schedule(data, schedule_id=self.schedule_id)
            if self.on_save_callback:
                self.on_save_callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror(tr("error"), str(e))

    def center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        
    def destroy(self):
        if hasattr(self, 'session'):
            self.session.close()
        super().destroy()
