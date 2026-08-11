import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import time
import math
from datetime import date

# Database Integration
from contragest.core.database import SessionLocal, Employee, AttendanceRecord, Department
from contragest.core.gui_utils import DesignTokens

class ChronosDashboard(ttk.Toplevel):
    def __init__(self, parent=None):
        super().__init__(master=parent, title="Chronometer Live")
        self.geometry("1400x900+50+50")
        self.resizable(True, True)
        self.state('zoomed')
        
        # Object Pool for High-Performance Rendering without Flickering
        self.card_pool = []
        self.header_pool = []
        
        # Color Palette matched to Nebula Midnight
        self.c_bg_main = DesignTokens.BG_APP
        self.c_bg_card = DesignTokens.SURFACE
        self.c_text_primary = DesignTokens.TEXT
        self.c_text_muted = DesignTokens.TEXT_MUTED
        self.c_header_lift = DesignTokens.PRIMARY
        
        self.c_green = DesignTokens.SUCCESS
        self.c_orange = DesignTokens.WARNING
        self.c_coral = DesignTokens.DANGER
        
        self.configure(bg=self.c_bg_main)
        
        # Build Top Logo Header
        self.header_fr = tk.Frame(self, bg=self.c_bg_main, height=60)
        self.header_fr.pack(side="top", fill="x", padx=12, pady=6)
        
        self.logo_lbl = tk.Label(self.header_fr, bg=self.c_bg_main)
        self.logo_lbl.pack(side="left", padx=(1, 9))
        self._load_logo()

        tk.Label(self.header_fr, text="CHRONOMETER", font=("Space Mono", 14, "bold"), 
                 bg=self.c_bg_main, fg=self.c_green).pack(side="left")
        tk.Label(self.header_fr, text="LIVE MONITORING", font=("Space Mono", 10), 
                 bg=self.c_bg_main, fg=self.c_text_muted).pack(side="left", padx=9, pady=(3, 1))

        # Fetch Real Data
        self.sync_realtime_data()

        # Body Grid Container (Rows: Feed and Status Bar)
        self.body = tk.Frame(self, bg=self.c_bg_main)
        self.body.pack(side="top", fill="both", expand=True, padx=1, pady=1)
        
        # Configure layout (Feed takes all space, KPI stays at bottom)
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        self.body.rowconfigure(1, weight=0)
        
        self.col_top = tk.Frame(self.body, bg=self.c_bg_main)
        self.col_top.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 6))
        
        self.col_bottom = tk.Frame(self.body, bg="#E7E5E4")
        self.col_bottom.grid(row=1, column=0, sticky="ew")

        # Build Inner Sections
        self.build_kpis(self.col_bottom)
        self.build_feed(self.col_top)
        
        # Bind resize for mathematical non-scrolling grid calculations
        self.col_top.bind("<Configure>", self._on_screen_resize)
        self._last_resize_w = 0
        self._last_resize_h = 0
        
        # Trigger periodic raw sync updates
        self.after(500, self.periodic_ui_refresh)
        
        # Animation states
        self._pulse_state = True
        self._animate_pulses()

    def _animate_pulses(self):
        """Creates a heartbeat/flashing effect for status labels"""
        self._pulse_state = not self._pulse_state
        
        # ACTIVE Colors (Deep Forest Pulses)
        # Pulse between accessible Green and Dark Green
        act_bg = "#10B981" if self._pulse_state else "#064E3B"
        act_fg = "#ECFDF5" if self._pulse_state else "#34D399"
        
        # INACTIVE Colors (Deep Maroon / Dark Red Pulses)
        # Pulse between accessible Red and Deep Red
        inact_bg = "#EF4444" if self._pulse_state else "#450A0A"
        inact_fg = "#FEF2F2" if self._pulse_state else "#F87171"
        
        # Update all visible cards in pool
        for card in self.card_pool:
            # Check if card is currently assigned in grid (forget means hidden)
            if card["frame"].winfo_manager() == "": continue
            
            status = card["status"].cget("text").upper()
            if "INACTIVE" in status or "CLOCKED" in status:
                card["status"].config(bg=inact_bg, fg=inact_fg)
            elif "ACTIVE" in status:
                card["status"].config(bg=act_bg, fg=act_fg)
                
        # Schedule next pulse (1 second interval)
        self.after(1000, self._animate_pulses)

    def _load_logo(self):
        """Dynamic logo loading for Chronos."""
        from contragest.core.database import SessionLocal, AppConfig
        import os
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            if config and config.company_logo_path and os.path.exists(config.company_logo_path):
                img = Image.open(config.company_logo_path)
                img.thumbnail((45, 45))
                self.logo_img = ImageTk.PhotoImage(img)
                self.logo_lbl.config(image=self.logo_img)
        except: pass
        finally: session.close()

    def sync_realtime_data(self):
        """Fetch live stats leveraging PointageService for accurate schedule-matched data."""
        session = SessionLocal()
        from contragest.features.pointage.service import PointageService
        service = PointageService(session)
        try:
            today_str = date.today().strftime("%Y-%m-%d")
            self.last_sync_time = time.strftime("%H:%M:%S")

            # Emps
            active_emps = session.query(Employee).filter(Employee.is_archived == False).all()
            self.total_employees = len(active_emps)

            # Get enriched data for today
            records = service.get_attendance_records_enriched(start_date=today_str, end_date=today_str)
            
            self.present_count = 0
            self.late_count = 0
            self.departments_data = {}
            
            for r in records:
                # Extract strings
                ci = r["check_in"]
                co = r["check_out"]
                ci2 = r["check_in_2"]
                co2 = r["check_out_2"]

                # Basic active check
                has_ci = ci != "-"
                has_co = co != "-"
                has_ci2 = ci2 != "-"
                has_co2 = co2 != "-"
                is_auto = r.get("is_auto", False)
                
                status = "INACTIVE"
                if is_auto:
                    status = "ACTIVE"
                elif (has_ci and not has_co) or (has_ci2 and not has_co2):
                    status = "ACTIVE"
                elif has_ci or has_co or has_ci2 or has_co2:
                    status = "CLOCKED OUT"
                    
                if status == "ACTIVE":
                    self.present_count += 1
                    
                color = self.c_green if status == "ACTIVE" else self.c_text_muted
                
                # Format detailed hover string
                # Actual
                in_str = "--:--"
                if has_ci: in_str = ci[:5]
                elif has_ci2: in_str = ci2[:5]
                
                out_str = "--:--"
                if has_co2: out_str = co2[:5]
                elif has_co: out_str = co[:5]
                
                # Planned
                s_in = r.get('sched_in', "-")[:5]
                s_out = r.get('sched_out', "-")[:5]
                s_name = r.get('schedule', "-")
                
                # Check Tardiness
                if has_ci and s_in != "-":
                    try:
                        if ci[:5] > s_in:
                            self.late_count += 1
                    except:
                        pass
                
                sub = f" ACTUAL: {in_str} ➔ {out_str}\n SCHEDULE: {s_name} ({s_in} ➔ {s_out})"
                
                dept_name = str(r['department'] or "UNASSIGNED").upper()
                name = str(r['employee']).upper()
                
                r_role = str(r['role_title'])
                role = "" if r_role == "-" else r_role.upper()
                
                reg_number = r.get('reg_number', '')
                
                if dept_name not in self.departments_data:
                    self.departments_data[dept_name] = []
                self.departments_data[dept_name].append((reg_number, name, role, status, color, sub))

            self.absent_count = max(0, self.total_employees - self.present_count)
            
            if self.total_employees > 0:
                self.present_pct = int((self.present_count / self.total_employees) * 100)
                self.absent_pct = int((self.absent_count / self.total_employees) * 100)
            else:
                self.present_pct = 0
                self.absent_pct = 0
                
            if self.present_count > 0:
                self.tardiness_pct = int((self.late_count / self.present_count) * 100)
            else:
                self.tardiness_pct = 0
            
            if hasattr(self, 'dept_cb'):
                all_depts = ["All Departments"] + sorted(list(self.departments_data.keys()))
                current_vals = list(self.dept_cb['values'])
                if current_vals != all_depts:
                    self.dept_cb['values'] = all_depts
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Chronos Sync Error: {e}")
            self.total_employees = 0
            self.present_pct = 0
            self.absent_pct = 0
            self.present_count = 0
            self.absent_count = 0
            self.tardiness_pct = 0
            self.late_count = 0
            self.departments_data = {}
        finally:
            session.close()

    def periodic_ui_refresh(self):
        """Update values dynamically if screen remains open."""
        self.sync_realtime_data()
        
        # 1. Update KPIs
        self.kpi_lbl_present_pct.config(text=f"{self.present_pct}%")
        self.kpi_lbl_present_cnt.config(text=f"● {self.present_count} active / {self.total_employees} Total")
        
        self.kpi_lbl_absent_pct.config(text=f"{self.absent_pct}%")
        self.kpi_lbl_absent_cnt.config(text=f"{self.absent_count} Off-site")
        
        self.kpi_lbl_tardiness_pct.config(text=f"{self.tardiness_pct}%")
        
        # 2. Rebuild feed only if search is empty to not disrupt typing
        if not self.search_var.get().strip():
            self._render_math_grid()
            
        self.after(30000, self.periodic_ui_refresh)

    def _update_clock(self):
        """Update the dynamic clock and sync display every second."""
        if hasattr(self, 'lbl_clock') and self.lbl_clock.winfo_exists():
            current_time = time.strftime("%A, %d %b %Y\n%H:%M:%S")
            self.lbl_clock.config(text=current_time)
            
            sync_t = getattr(self, "last_sync_time", "--:--:--")
            self.lbl_sync.config(text=f"Last Sync: {sync_t}")
            
        self.after(1000, self._update_clock)

    def build_kpis(self, parent):
        kpi_container = tk.Frame(parent, bg="#E7E5E4")
        kpi_container.pack(fill="x", pady=1)
        
        for i in range(4):
            kpi_container.columnconfigure(i, weight=1, uniform="kpiGrp")

        # 1. LIVE WORKFORCE (Neon Cyan)
        f1 = tk.Frame(kpi_container, bg="#083344", padx=12, pady=7)
        f1.grid(row=0, column=0, sticky="nsew", padx=(1, 1), pady=1)
        tk.Label(f1, text="LIVE WORKFORCE", font=("Space Mono", 9, "bold"), fg="#67E8F9", bg="#083344").pack(anchor="w")
        
        v1_fr = tk.Frame(f1, bg="#083344")
        v1_fr.pack(anchor="w", pady=(1, 1))
        self.kpi_lbl_present_pct = tk.Label(v1_fr, text=f"{self.present_pct}%", font=("Space Mono", 19, "bold"), fg="#CFFAFE", bg="#083344")
        self.kpi_lbl_present_pct.pack(side="left")
        tk.Label(v1_fr, text=" PRESENT", font=("Space Mono", 9, "bold"), fg="#A5F3FC", bg="#083344").pack(side="left", anchor="s", pady=3)
        
        self.kpi_lbl_present_cnt = tk.Label(f1, text=f"● {self.present_count} active / {self.total_employees} Total", font=("Space Mono", 9), fg="#22D3EE", bg="#083344")
        self.kpi_lbl_present_cnt.pack(anchor="w", pady=(1, 1))

        # 2. OUT OF OFFICE (Neon Magenta)
        f2 = tk.Frame(kpi_container, bg="#4A044E", padx=12, pady=7)
        f2.grid(row=0, column=1, sticky="nsew", padx=1, pady=1)
        tk.Label(f2, text="OUT OF OFFICE", font=("Space Mono", 9, "bold"), fg="#00A6F4", bg="#4A044E").pack(anchor="w")
        
        v2_fr = tk.Frame(f2, bg="#4A044E")
        v2_fr.pack(anchor="w", pady=(1, 1))
        self.kpi_lbl_absent_pct = tk.Label(v2_fr, text=f"{self.absent_pct}%", font=("Space Mono", 19, "bold"), fg="#FAE8FF", bg="#4A044E")
        self.kpi_lbl_absent_pct.pack(side="left")
        tk.Label(v2_fr, text=" ABSENT", font=("Space Mono", 9, "bold"), fg="#F5D0FE", bg="#4A044E").pack(side="left", anchor="s", pady=3)
        
        self.kpi_lbl_absent_cnt = tk.Label(f2, text=f"{self.absent_count} Off-site", font=("Space Mono", 9), fg="#F0ABFC", bg="#4A044E")
        self.kpi_lbl_absent_cnt.pack(anchor="w", pady=(1, 1))

        # 3. TARDINESS INDEX (Neon Fuchsia)
        f3 = tk.Frame(kpi_container, bg="#4C0519", padx=12, pady=7)
        f3.grid(row=0, column=2, sticky="nsew", padx=1, pady=1)
        tk.Label(f3, text="TARDINESS", font=("Space Mono", 9, "bold"), fg="#FB7185", bg="#4C0519").pack(anchor="w")
        
        v3_fr = tk.Frame(f3, bg="#4C0519")
        v3_fr.pack(anchor="w", pady=(1, 1))
        self.kpi_lbl_tardiness_pct = tk.Label(v3_fr, text=f"{self.tardiness_pct}%", font=("Space Mono", 19, "bold"), fg="#FFE4E6", bg="#4C0519")
        self.kpi_lbl_tardiness_pct.pack(side="left")
        tk.Label(v3_fr, text=" LATE", font=("Space Mono", 9, "bold"), fg="#FECDD3", bg="#4C0519").pack(side="left", anchor="s", pady=3)
        
        tk.Label(f3, text="Trend improving from yesterday", font=("Space Mono", 9), fg="#FDA4AF", bg="#4C0519").pack(anchor="w", pady=(1, 1))

        # 4. SYSTEM STATUS (Dynamic Violet)
        sys_f = tk.Frame(kpi_container, bg="#2E1065", padx=12, pady=7)
        sys_f.grid(row=0, column=3, sticky="nsew", padx=(1, 1), pady=1)
        tk.Label(sys_f, text="SYSTEM STATUS", font=("Space Mono", 9, "bold"), fg="#A78BFA", bg="#2E1065").pack(anchor="w")
        
        self.lbl_clock = tk.Label(sys_f, text="", font=("Space Mono", 10, "bold"), fg="#EDE9FE", bg="#2E1065", justify="left")
        self.lbl_clock.pack(anchor="w", pady=(1, 1))
        
        self.lbl_sync = tk.Label(sys_f, text="Sync: --:--:--", font=("Space Mono", 9), fg="#C4B5FD", bg="#2E1065")
        self.lbl_sync.pack(anchor="w")
        
        self._update_clock()

    def build_feed(self, parent):
        feed_container = tk.Frame(parent, bg=self.c_bg_card)
        feed_container.pack(fill="both", expand=True)
        
        # Header
        head_fr = tk.Frame(feed_container, bg=self.c_bg_card, pady=1, padx=1)
        head_fr.pack(fill="x", pady=(1, 6))
        
        tk.Label(head_fr, text="Live Activity Feed", font=("Space Mono", 10, "bold"), fg=self.c_text_primary, bg=self.c_bg_card, justify="center").pack(side="left", expand=False)
        
        btn_fr = tk.Frame(head_fr, bg=self.c_bg_card)
        btn_fr.pack(side="right")
        
        # --- Filters Section ---
        filters_fr = tk.Frame(btn_fr, bg=self.c_bg_card)
        filters_fr.pack(side="left", padx=6)
        
        # Status Filter
        self.status_filter_var = tk.StringVar(value="All Statuses")
        self.status_cb = ttk.Combobox(filters_fr, textvariable=self.status_filter_var, values=["All Statuses", "ACTIVE", "CLOCKED OUT", "INACTIVE"], state="readonly", width=15)
        self.status_cb.pack(side="left", padx=3)
        self.status_cb.bind("<<ComboboxSelected>>", lambda e: self.after(20, self._apply_search))
        
        # Department Filter
        self.dept_filter_var = tk.StringVar(value="All Departments")
        self.dept_cb = ttk.Combobox(filters_fr, textvariable=self.dept_filter_var, state="readonly", width=20)
        if hasattr(self, 'departments_data'):
            self.dept_cb['values'] = ["All Departments"] + sorted(list(self.departments_data.keys()))
        self.dept_cb.pack(side="left", padx=3)
        self.dept_cb.bind("<<ComboboxSelected>>", lambda e: self.after(20, self._apply_search))
        
        # Sticky Search Input inside Header
        search_wrap = tk.Frame(btn_fr, bg=self.c_header_lift, padx=6, pady=3)
        search_wrap.pack(side="left", padx=9)
        tk.Label(search_wrap, text="🔍", bg=self.c_header_lift, fg=self.c_text_muted).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_ent = tk.Entry(search_wrap, textvariable=self.search_var, bg=self.c_header_lift, fg=self.c_text_primary, bd=0, insertbackground="black", font=("Space Mono", 9), width=20)
        self.search_ent.pack(side="left", padx=(3, 1))
        
        # Debounced Search Binding
        self._search_timer = None
        self.search_ent.bind("<KeyRelease>", self._on_search_key)

        # Single Interface Container (High Density, Non-Scrolling)
        self.feed_list_container = tk.Frame(feed_container, bg=self.c_bg_main)
        self.feed_list_container.pack(fill="both", expand=True)
        self.grid_container = self.feed_list_container

    def _on_screen_resize(self, event):
        if abs(event.width - self._last_resize_w) > 50 or abs(event.height - self._last_resize_h) > 50:
            self._last_resize_w = event.width
            self._last_resize_h = event.height
            self._render_math_grid()

    def _on_search_key(self, event):
        if self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(300, self._apply_search)

    def _apply_search(self):
        self._render_math_grid()

    def _get_flattened_sorted_data(self):
        query = self.search_var.get().lower().strip()
        dept_filter = self.dept_filter_var.get() if hasattr(self, 'dept_filter_var') else "All Departments"
        status_filter = self.status_filter_var.get() if hasattr(self, 'status_filter_var') else "All Statuses"
        
        flat_list = []
        for dept_name, employees in getattr(self, 'departments_data', {}).items():
            if dept_filter != "All Departments" and dept_name != dept_filter:
                continue
                
            for emp in employees:
                status = emp[3]
                if status_filter != "All Statuses" and status != status_filter:
                    continue
                    
                if query:
                    if query not in emp[1].lower() and query not in emp[2].lower() and query not in dept_name.lower():
                        continue
                flat_list.append((dept_name, *emp))
                
        # Primary Sort by Object Type (Status Level), Secondary by Department
        def sort_key(item):
            status = item[4]
            if status == "ACTIVE": s_val = 0
            elif status == "CLOCKED OUT": s_val = 1
            else: s_val = 2
            return (s_val, item[0], item[2])
            
        flat_list.sort(key=sort_key)
        return flat_list

    def _get_or_create_card(self, index):
        """Virtual DOM Object Pool Pattern - Optimized for Ultra-High Density"""
        if index < len(self.card_pool):
            return self.card_pool[index]
            
        # Remove border thickness to save space
        item_btn = tk.Frame(self.grid_container, bg=DesignTokens.SURFACE, highlightthickness=1, highlightbackground=DesignTokens.PRIMARY)
        item_btn.columnconfigure(0, weight=1)
        
        # Row 0: COMBINED Status + Dept
        top_fr = tk.Frame(item_btn, bg=self.c_bg_card)
        top_fr.grid(row=0, column=0, columnspan=2, sticky="ew", pady=0)
        
        lbl_status = tk.Label(top_fr, text="", font=("Space Mono", 7, "bold"), padx=4, pady=0)
        lbl_status.pack(side="left", padx=(2, 4))
        
        lbl_dept = tk.Label(top_fr, text="", font=("Space Mono", 5), fg=self.c_text_muted, bg=self.c_bg_card)
        lbl_dept.pack(side="left", fill="x")
        
        # Row 1: NAME (Primary)
        lbl_name = tk.Label(item_btn, text="", font=("Space Mono", 8, "bold"), fg=self.c_text_primary, bg=self.c_bg_card, anchor="w")
        lbl_name.grid(row=1, column=0, sticky="ew", padx=6, pady=0)
        
        # Row 2: ROLE (Subtext)
        lbl_role = tk.Label(item_btn, text="", font=("Space Mono", 6), fg="#A5F3FC", bg=self.c_bg_card, anchor="w")
        lbl_role.grid(row=2, column=0, sticky="ew", padx=6, pady=0)
        
        # Column 1: PHOTO AVATAR
        lbl_photo = tk.Label(item_btn, bg=self.c_bg_card)
        lbl_photo.grid(row=1, column=1, rowspan=2, sticky="nse", padx=(0, 4))
        
        obj = {
            "frame": item_btn,
            "status": lbl_status,
            "dept": lbl_dept,
            "name": lbl_name,
            "role": lbl_role,
            "photo": lbl_photo,
            "top_fr": top_fr,
            "sub_text": "",
            "photo_path": None
        }
        
        def on_click(e):
            self.show_hover_notification(e, obj["sub_text"])
            
        def on_photo_click(e):
            if obj.get("photo_path"):
                self.show_photo_zoom(e, obj["photo_path"], obj["name"].cget("text"))
            else:
                on_click(e)
            
        for w in (item_btn, lbl_status, lbl_dept, lbl_name, lbl_role, top_fr):
            w.bind("<Button-1>", on_click)
            w.config(cursor="hand2")
            
        lbl_photo.bind("<Button-1>", on_photo_click)
        lbl_photo.bind("<Enter>", lambda e: lbl_photo.config(cursor="plus" if obj.get("photo_path") else "hand2"))
            
        self.card_pool.append(obj)
        return obj
        
    def show_photo_zoom(self, event, photo_path, emp_name):
        if not photo_path: return
        if hasattr(self, "_zoom_popup") and getattr(self._zoom_popup, "winfo_exists", lambda: False)():
            self._zoom_popup.destroy()
            
        self._zoom_popup = tk.Toplevel(self)
        self._zoom_popup.wm_overrideredirect(True)
        
        from PIL import Image, ImageTk
        try:
            img = Image.open(photo_path).convert("RGBA")
            img.thumbnail((200, 240), Image.Resampling.LANCZOS)
            self._zoom_img_cache = ImageTk.PhotoImage(img)
            
            fr = tk.Frame(self._zoom_popup, bg="#38BDF8", bd=2)
            fr.pack()
            
            lbl_title = tk.Label(fr, text=emp_name, font=("Space Mono", 10, "bold"), bg="#0F172A", fg="#BAE6FD", pady=3)
            lbl_title.pack(fill="x")
            
            lbl_zoomed = tk.Label(fr, image=self._zoom_img_cache, bg="#0F172A")
            lbl_zoomed.pack(padx=1, pady=(0, 1))
            
            # Position near cursor
            w = img.width + 4
            h = img.height + 35
            
            # Keep within screen bounds
            scr_w, scr_h = self.winfo_screenwidth(), self.winfo_screenheight()
            x = min(max(0, event.x_root - w//2), scr_w - w)
            y = min(event.y_root + 15, scr_h - h - 10)
            
            self._zoom_popup.geometry(f"{w}x{h}+{x}+{y}")
            self._zoom_popup.attributes('-topmost', True)
            
            # Auto-dismiss conditions
            self._zoom_popup.bind("<Leave>", lambda e: self._zoom_popup.destroy() if getattr(self._zoom_popup, "winfo_exists", lambda: False)() else None)
            self._zoom_popup.bind("<Button-1>", lambda e: self._zoom_popup.destroy() if getattr(self._zoom_popup, "winfo_exists", lambda: False)() else None)
            lbl_zoomed.bind("<Button-1>", lambda e: self._zoom_popup.destroy() if getattr(self._zoom_popup, "winfo_exists", lambda: False)() else None)
            
            self.after(4000, lambda: self._zoom_popup.destroy() if getattr(self._zoom_popup, "winfo_exists", lambda: False)() else None)
        except Exception as e:
            print(f"Error zooming photo: {e}")
            if getattr(self._zoom_popup, "winfo_exists", lambda: False)():
                self._zoom_popup.destroy()

    def show_hover_notification(self, event, text):
        if not text: return
        if hasattr(self, "_hover_popup") and getattr(self._hover_popup, "winfo_exists", lambda: False)():
            self._hover_popup.destroy()
            
        self._hover_popup = tk.Toplevel(self)
        self._hover_popup.wm_overrideredirect(True)
        self._hover_popup.geometry(f"+{event.x_root + 15}+{event.y_root + 15}")
        self._hover_popup.attributes('-topmost', True)
        
        fr = tk.Frame(self._hover_popup, bg="#38BDF8")
        fr.pack()
        tk.Label(fr, text=text, font=("JetBrains Mono", 9, "bold"), bg="#0F172A", fg="#BAE6FD", padx=9, pady=6, justify="left").pack(padx=1, pady=1)
        
        # Increased stay duration for multiline reading
        self.after(5000, lambda p=self._hover_popup: p.destroy() if getattr(p, "winfo_exists", lambda: False)() else None)
        self._hover_popup.bind("<Button-1>", lambda e: self._hover_popup.destroy())
        
    def _get_or_create_header(self, index):
        if index < len(self.header_pool):
            return self.header_pool[index]
            
        hdr_frame = tk.Frame(self.grid_container)
        lbl = tk.Label(hdr_frame, font=("Space Mono", 9, "bold"), fg="#F8FAFC")
        lbl.pack(fill="both", expand=True, padx=2, pady=1)
        
        obj = {"frame": hdr_frame, "label": lbl}
        self.header_pool.append(obj)
        return obj

    def _render_math_grid(self):
        """Recalculates rows and columns to perfectly fill without scroll"""
        width = self.feed_list_container.winfo_width()
        height = self.feed_list_container.winfo_height()
        if width <= 10 or height <= 10:
            return
            
        all_items = self._get_flattened_sorted_data()
        total_items = len(all_items)
        
        if total_items == 0:
            for c in self.card_pool: c["frame"].grid_forget()
            for h in self.header_pool: h["frame"].grid_forget()
            return
            
        # Group mathematically to insert headers
        groups = {}
        for item in all_items:
            status = item[4]
            if status not in groups: groups[status] = []
            groups[status].append(item)
            
        num_headers = len(groups)
        header_height_estimate = 20
        available_height = height - (num_headers * header_height_estimate)
        
        # Calculate optimal grid to fill screen
        ratio = max(0.1, width / max(1, available_height))
        cols = math.ceil(math.sqrt(total_items * ratio * 2.0))
        cols = max(6, min(10, cols))
        
        # Reset grid weights
        for c in range(30):
            self.grid_container.columnconfigure(c, weight=0, uniform="")
            self.grid_container.rowconfigure(c, weight=0, uniform="")
            
        for c in range(cols):
            self.grid_container.columnconfigure(c, weight=1, uniform="c")
            
        # Hide all existing elements cleanly
        for c in self.card_pool: c["frame"].grid_forget()
        for h in self.header_pool: h["frame"].grid_forget()
        
        current_row = 0
        card_idx = 0
        hdr_idx = 0
        
        for status, items in groups.items():
            if status == "ACTIVE": bg_hdr = "#083344"; bg_fg = "#22D3EE"
            elif status == "CLOCKED OUT": bg_hdr = "#4C0519"; bg_fg = "#FB7185"
            else: bg_hdr = DesignTokens.PRIMARY; bg_fg = DesignTokens.SECONDARY
            
            # Place Header
            hdr = self._get_or_create_header(hdr_idx)
            hdr_idx += 1
            hdr["frame"].config(bg=bg_hdr)
            hdr["label"].config(text=f"━ {status} ({len(items)}) ━", bg=bg_hdr, fg=bg_fg)
            hdr["frame"].grid(row=current_row, column=0, columnspan=cols, sticky="ew", pady=(2, 1))
            self.grid_container.rowconfigure(current_row, weight=0)
            current_row += 1
            
            # Place Items
            for i, item in enumerate(items):
                dept_name, reg_number, name, role, i_status, color, sub = item
                r = current_row + (i // cols)
                c_idx = i % cols
                
                card = self._get_or_create_card(card_idx)
                card_idx += 1
                
                if i_status == "ACTIVE": pill_bg = "#083344"; pill_fg = "#22D3EE"
                elif i_status == "CLOCKED OUT": pill_bg = "#4C0519"; pill_fg = "#FB7185"
                else: pill_bg = DesignTokens.PRIMARY; pill_fg = DesignTokens.SECONDARY
                
                card["status"].config(text=i_status, bg=pill_bg, fg=pill_fg)
                card["dept"].config(text=f"• {dept_name.upper()}")
                
                cw = (width // cols) - 45 # Make room for avatar without stretch
                card["name"].config(text=name.upper(), wraplength=cw)
                card["role"].config(text=role.upper(), wraplength=cw)
                card["sub_text"] = sub
                
                # Fetch and render the photo
                if not hasattr(self, '_photo_cache'):
                    self._photo_cache = {}
                
                photo_found = False
                import os
                from PIL import Image, ImageTk
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                photos_dir = os.path.join(base_dir, "assets", "photos")
                clean_reg = str(reg_number).lstrip('0') if str(reg_number).isdigit() else str(reg_number)
                
                for ext in ['.jpg', '.jpeg', '.png']:
                    p = os.path.join(photos_dir, f"reg_{clean_reg}{ext}")
                    if os.path.exists(p):
                        try:
                            if p not in self._photo_cache:
                                img = Image.open(p).convert("RGBA")
                                # LANCZOS ensures high quality micro-resizing
                                img.thumbnail((24, 24), Image.Resampling.LANCZOS)
                                self._photo_cache[p] = ImageTk.PhotoImage(img)
                            
                            card["photo"].config(image=self._photo_cache[p], text="")
                            card["photo_path"] = p
                            photo_found = True
                            break
                        except Exception: pass
                        
                if not photo_found:
                    card["photo_path"] = None
                    initial_letter = name[0].upper() if name else "?"
                    card["photo"].config(image="", text=initial_letter, font=("Space Mono", 12, "bold"), fg="#38BDF8")
                    
                card["frame"].grid(row=r, column=c_idx, sticky="nsew", padx=2, pady=2, ipadx=4, ipady=2)
                
            current_row += math.ceil(len(items) / cols)
            
        # Add a weight=1 spacer at the very bottom to absorb extra space 
        # instead of stretching the cards vertically when items are few.
        self.grid_container.rowconfigure(current_row, weight=1)
            
if __name__ == "__main__":
    app = ttk.Window()
    app.withdraw() # Hide root
    ChronosDashboard(app)
    app.mainloop()
