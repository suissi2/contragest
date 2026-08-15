import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tableview import Tableview
from ttkbootstrap.scrolled import ScrolledFrame
from contragest.core.i18n import tr
from contragest.core.database import SessionLocal, Employee, Department, AttendanceRecord
from contragest.core.gui_utils import DesignTokens, apply_premium_style
from sqlalchemy import func
import threading
from datetime import date
from contragest.core.logging import setup_logger

logger = setup_logger("hr_dashboard")

class HRDashboard(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill=BOTH, expand=YES, padx=6, pady=6)
        self._polling = False  
        self._is_fetching = False    # Concurrency guard
        self._polling_after_id = None # Task tracker
        self._reset_expansion = False  
        self._cache_punches = []        # cached 7-tuples for log tree
        self._cache_records = []        # cached enriched dicts for dept stats
        self._cache_filters = {}        # filter params used for cache
        self._cache_loaded = False
        self._machine_sync_after_id = None
        
        self._setup_ui()
        self._populate_filter_dropdowns()
        
        # Increase dropdown list font for better readability
        self.option_add("*TCombobox*Listbox.font", ("Space Mono", 11))
        
        self.start_polling()
        self._schedule_machine_sync()

    def _setup_ui(self):
        # Premium Design System Initialization
        style = ttk.Style()
        apply_premium_style(style)
        
        style.configure('Main.TFrame', background=DesignTokens.BG_APP)
        self.configure(style='Main.TFrame')
        
        style.configure('Header.TFrame', background=DesignTokens.BG_APP)
        style.configure('Header.TLabel', background=DesignTokens.BG_APP, foreground=DesignTokens.PRIMARY)
        style.configure('Card.TLabelframe', background=DesignTokens.SURFACE, bordercolor=DesignTokens.SECONDARY, padding=DesignTokens.CARD_PADDING)
        style.configure('Card.TLabelframe.Label', background=DesignTokens.SURFACE, foreground=DesignTokens.PRIMARY, font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY + 2, 'bold'))

        # Header Bar
        header_frame = ttk.Frame(self, style='Header.TFrame')
        header_frame.pack(fill=X, pady=(1, 12))
        
        header_content = ttk.Frame(header_frame, style='Header.TFrame', padding=(12, 6))
        header_content.pack(fill=X)

        ttk.Label(header_content, text="👔 HR MANAGEMENT HUB", 
                  font=(DesignTokens.FONT_PRIMARY, 11, "bold"), style='Header.TLabel').pack(side=LEFT)
        
        # Status and Metrics Badges in Header
        status_group = ttk.Frame(header_content, style='Header.TFrame')
        status_group.pack(side=RIGHT, anchor=E)

        self.lbl_last_update = ttk.Label(status_group, text="Updated: --:--:--", font=(DesignTokens.FONT_PRIMARY, 9), foreground=DesignTokens.TEXT_MUTED)
        self.lbl_last_update.pack(side=RIGHT, padx=(9, 1))

        self.lbl_status = ttk.Label(status_group, text=" ● LIVE ", font=(DesignTokens.FONT_PRIMARY, 9, "bold"), bootstyle="success-inverse")
        self.lbl_status.pack(side=RIGHT, padx=6)

        self._records_count_label = ttk.Label(status_group, text="Total Records: 0", font=(DesignTokens.FONT_PRIMARY, 9, "bold"), bootstyle="info-inverse")
        self._records_count_label.pack(side=RIGHT, padx=9)

        # Paned Window for split layout
        pane = ttk.Panedwindow(self, orient=HORIZONTAL)
        pane.pack(fill=BOTH, expand=YES)

        # Left Panel (Department Summary Card)
        self.left_panel = ttk.Labelframe(pane, text="🏢 Department Summary", style="Card.TLabelframe")
        pane.add(self.left_panel, weight=1)

        dept_header = ttk.Frame(self.left_panel)
        dept_header.pack(fill=X, pady=(1, 6))
        
        self.btn_refresh_dept = ttk.Button(
            dept_header, 
            text=" 🔄 Refresh ", 
            bootstyle="secondary-outline",
            width=10,
            cursor="hand2",
            command=self.on_refresh
        )
        self.btn_refresh_dept.pack(side=RIGHT)
        
        self.lbl_total_employees = ttk.Label(self.left_panel, text="Total Employees: 0", font=("Space Mono", 10, "bold"), bootstyle=INFO)
        self.lbl_total_employees.pack(anchor=W, pady=(1, 12))
        
        # Department Summary Treeview
        style.configure('Treeview', rowheight=28, font=("Space Mono", 10))
        style.configure('Treeview.Heading', font=("Space Mono", 10, "bold"))

        self.dept_cols = ["Ratio", "Presence %"]
        self.dept_tree = ttk.Treeview(self.left_panel, columns=self.dept_cols, show="tree headings", height=15)
        self.dept_tree.heading("#0", text="Department / Employee")
        self.dept_tree.heading("Ratio", text="Ratio")
        self.dept_tree.heading("Presence %", text="Presence %")
        self.dept_tree.column("#0", stretch=YES, width=220)
        self.dept_tree.column("Ratio", anchor=CENTER, width=90)
        self.dept_tree.column("Presence %", anchor=CENTER, width=110)

        dept_scroll = ttk.Scrollbar(self.left_panel, orient=VERTICAL, command=self.dept_tree.yview)
        self.dept_tree.configure(yscrollcommand=dept_scroll.set)
        
        self.dept_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        dept_scroll.pack(side=RIGHT, fill=Y)

        # Right Panel (Recent Logs Card)
        self.right_panel = ttk.Labelframe(pane, text="⏱️ Real-Time Attendance Log", style="Card.TLabelframe")
        pane.add(self.right_panel, weight=3)

        # Filters - Redesigned 2-Row Layout
        from ttkbootstrap.widgets import DateEntry
        filter_frame = ttk.Labelframe(self.right_panel, text="🔍 Search & Filters", style="Card.TLabelframe")
        filter_frame.pack(fill=X, pady=(1, 9))

        self._filter_emp = ttk.StringVar()
        self._filter_reg = ttk.StringVar()
        self._filter_dept = ttk.StringVar()
        self._filter_type = ttk.StringVar(value=tr("all_types"))

        # Row 1: Department & Employee
        f_row1 = ttk.Frame(filter_frame)
        f_row1.pack(fill=X, pady=(1, 6))

        ttk.Label(f_row1, text="🏢 Department:", font=("Space Mono", 9, "bold")).pack(side=LEFT, padx=(3, 3))
        self._cb_dept = ttk.Combobox(f_row1, textvariable=self._filter_dept, width=35)
        self._cb_dept.pack(side=LEFT, padx=3)
        self._cb_dept.bind("<<ComboboxSelected>>", self._on_dept_selected)

        ttk.Label(f_row1, text="👤 Employee Name:", font=("Space Mono", 9, "bold")).pack(side=LEFT, padx=(12, 3))
        self._cb_emp = ttk.Combobox(f_row1, textvariable=self._filter_emp, state="readonly", width=63)
        self._cb_emp.pack(side=LEFT, padx=3)

        # Row 2: Type, Dates, Actions
        f_row2 = ttk.Frame(filter_frame)
        f_row2.pack(fill=X)

        ttk.Label(f_row2, text="🏷️ Punch Type:", font=("Space Mono", 9, "bold")).pack(side=LEFT, padx=(3, 3))
        cb = ttk.Combobox(f_row2, textvariable=self._filter_type, state="normal", width=15,
                          values=[tr("all_types"), tr("check_in_type"), tr("check_out_type")])
        cb.pack(side=LEFT, padx=3)
        cb.bind("<<ComboboxSelected>>", lambda e: self._trigger_fetch_immediate())

        today = date.today()
        ttk.Label(f_row2, text="📅 From Date:", font=("Space Mono", 9, "bold")).pack(side=LEFT, padx=(12, 3))
        self._filter_from_de = DateEntry(f_row2, startdate=today, dateformat='%Y-%m-%d', width=12)
        self._filter_from_de.pack(side=LEFT, padx=3)

        ttk.Label(f_row2, text="📅 To Date:", font=("Space Mono", 9, "bold")).pack(side=LEFT, padx=(12, 3))
        self._filter_to_de = DateEntry(f_row2, startdate=today, dateformat='%Y-%m-%d', width=12)
        self._filter_to_de.pack(side=LEFT, padx=3)

        ttk.Button(f_row2, text="✅ Filter", bootstyle="primary", command=self._trigger_fetch_immediate, width=10).pack(side=RIGHT, padx=3)
        ttk.Button(f_row2, text="🔄 Clear", bootstyle="secondary", command=self._clear_filters, width=10).pack(side=RIGHT, padx=3)
        
        self._cb_reg = ttk.Combobox(f_row2, textvariable=self._filter_reg) # Hidden helper
        
        # Performance: Debounce Real-time filtering for Employee Name
        self._after_id = None
        self._cb_emp.bind("<<ComboboxSelected>>", lambda e: self._trigger_fetch_immediate())

        # Optimized Attendance Log Treeview
        style.configure('Log.Treeview', rowheight=28, font=("Space Mono", 9))
        style.configure('Log.Treeview.Heading', font=("Space Mono", 10, "bold"))
        
        self.log_cols = ["Time", "Employee", "REG. NUMBER", "Department", "Schedule", "Machine", "Type"]
        self.log_tree = ttk.Treeview(self.right_panel, columns=self.log_cols, show="headings", height=15, style='Log.Treeview')
        
        for col in self.log_cols:
            self.log_tree.heading(col, text=col)
            self.log_tree.column(col, anchor=CENTER, width=110)
        
        self.log_tree.column("Time", anchor=W, width=180)
        self.log_tree.column("Employee", anchor=W, width=250)
        self.log_tree.column("Department", anchor=W, width=180)
        self.log_tree.column("Schedule", anchor=CENTER, width=130)

        # Unified Status Coloring
        self.log_tree.tag_configure('in', foreground="#059669", font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY, 'bold')) # Emerald Green
        self.log_tree.tag_configure('out', foreground=DesignTokens.WARNING, font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY, 'bold')) # Amber

        # Add scrollbar to log tree
        log_scroll = ttk.Scrollbar(self.right_panel, orient=VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=log_scroll.set)
        
        self.log_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        log_scroll.pack(side=RIGHT, fill=Y)

        self.log_tree.bind("<Double-1>", self._on_record_double_click)

    def _open_edit_employee_dialog(self, reg_number):
        from contragest.core.database import Employee
        from contragest.features.employee_manager.data_entry_form import DataEntryForm
        from ttkbootstrap.dialogs import Messagebox
        
        session = SessionLocal()
        try:
            emp = session.query(Employee).filter_by(registration_number=reg_number).first()
            if not emp:
                Messagebox.show_error(f"Employee with REG NUMBER {reg_number} not found.", "Error", parent=self)
                return
                
            emp_id = emp.id
        finally:
            session.close()
            
        dlg = DataEntryForm(
            parent=self, 
            mode="edit", 
            employee_id=emp_id, 
            on_save_callback=self._trigger_fetch_immediate
        )

    def _on_record_double_click(self, event):
        """Extracts REG number from the row and opens the Edit Employee dialog if the user clicked the REG NUMBER column."""
        sel = self.log_tree.selection()
        if not sel:
            return
            
        values = self.log_tree.item(sel[0], "values")
        # Columns: ["Time", "Employee", "REG. NUMBER", "Department", "Schedule", "Machine", "Type"]
        # REG NUMBER is at index 2
        reg_number = values[2]
        
        # Don't try to open if reg is empty or "-"
        if not reg_number or reg_number == "-":
            return
            
        col = self.log_tree.identify_column(event.x)
        
        # If the clicked column is REG. NUMBER (col #3)
        if col == '#3':
            self._open_edit_employee_dialog(reg_number)


    def _populate_filter_dropdowns(self, department_name=None):
        """Fetches unique values from DB to populate the search comboboxes with autocomplete."""
        session = SessionLocal()
        try:
            from contragest.features.pointage.service import PointageService
            svc = PointageService(session)
            vals = svc.get_filter_dropdown_values(department_name=department_name)
            
            self._filter_full_lists = {
                "employees": vals.get("employees", []),
                "reg_numbers": vals.get("reg_numbers", []),
                "departments": vals.get("departments", [])
            }

            if hasattr(self, "_cb_emp"):
                self._cb_emp.configure(values=self._filter_full_lists["employees"])

            if hasattr(self, "_cb_reg"):
                self._cb_reg.configure(values=self._filter_full_lists["reg_numbers"])
                self._cb_reg.bind("<KeyRelease>", lambda e: self._on_combobox_key(e, self._cb_reg, self._filter_full_lists["reg_numbers"]))
                self._cb_reg.bind("<ButtonPress-1>", lambda e: self._on_combobox_click(self._cb_reg, self._filter_full_lists["reg_numbers"]))
                
            if hasattr(self, "_cb_dept"):
                # Always show all departments in the primary filter
                if not department_name:
                    self._cb_dept.configure(values=self._filter_full_lists["departments"])
                    self._cb_dept.bind("<KeyRelease>", lambda e: self._on_combobox_key(e, self._cb_dept, self._filter_full_lists["departments"]))
                    self._cb_dept.bind("<ButtonPress-1>", lambda e: self._on_combobox_click(self._cb_dept, self._filter_full_lists["departments"]))
        finally:
            session.close()

    def _on_dept_selected(self, event=None):
        """When a department is selected, filter employee and reg dropdowns."""
        dept = self._filter_dept.get().strip()
        # Reset employee/reg filters when department changes to avoid invalid combinations
        self._filter_emp.set("")
        self._filter_reg.set("")
        # Re-populate dropdowns with department filter applied
        self._populate_filter_dropdowns(department_name=dept if dept else None)
        # Filter log from cache (instant)
        self._trigger_fetch_immediate()

    def _on_combobox_key(self, event, combobox, full_list):
        if event.keysym in ('Up', 'Down', 'Return', 'Left', 'Right', 'Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R'):
            return
            
        typed_text = combobox.get().lower()
        if not typed_text:
            combobox.configure(values=full_list)
        else:
            filtered = [item for item in full_list if typed_text in str(item).lower()]
            combobox.configure(values=filtered)
            
        combobox.after("idle", lambda: combobox.event_generate('<Down>'))
        
    def _on_combobox_click(self, combobox, full_list):
        if not combobox.get():
            combobox.configure(values=full_list)

    def _clear_filters(self):
        self._filter_emp.set("")
        self._filter_reg.set("")
        self._filter_dept.set("")
        self._filter_type.set(tr("all_types"))
        today_str = date.today().strftime('%Y-%m-%d')
        self._filter_from_de.entry.delete(0, END)
        self._filter_from_de.entry.insert(0, today_str)
        self._filter_to_de.entry.delete(0, END)
        self._filter_to_de.entry.insert(0, today_str)
        self._populate_filter_dropdowns()
        self._trigger_fetch_immediate()

    def set_reg_filter(self, reg_number):
        """Sets the registration number filter and triggers an immediate refresh."""
        if hasattr(self, "_filter_reg"):
            self._filter_reg.set(reg_number)
            self._trigger_fetch_immediate()

    def on_refresh(self):
        """Dedicated refresh that also resets expansion states."""
        # Instant acknowledgment: Always reset expansion and show a flicker
        self._reset_expansion = True
        
        if hasattr(self, "lbl_status"):
            # Flicker effect: Turn success temporarily to warning to show click worked
            self.lbl_status.configure(bootstyle="warning-inverse")
            self.after(200, lambda: self.lbl_status.configure(bootstyle="success-inverse" if not self._is_fetching else "warning-inverse"))
            
        self._trigger_fetch_immediate()

    def _run_machine_sync(self):
        """Sync attendance machines in background (separate from filter path)."""
        def _sync():
            session = SessionLocal()
            try:
                from contragest.features.pointage.service import PointageService
                from contragest.core.database import AttendanceMachine
                svc = PointageService(session)
                machines = session.query(AttendanceMachine).filter_by(is_active=True).all()
                new_total = 0
                for m in machines:
                    try:
                        count, _ = svc.download_attendance(m.id)
                        new_total += count
                    except Exception as e:
                        logger.warning(f"Machine sync error for {m.name}: {e}")
                logger.debug(f"Background machine sync complete ({new_total} new records)")
                # New records arrived → refresh the grid immediately
                if new_total > 0 and self.winfo_exists():
                    self.after(0, self._trigger_fetch_immediate)
            except Exception as e:
                logger.warning(f"Background machine sync error: {e}")
            finally:
                session.close()
        threading.Thread(target=_sync, daemon=True).start()
        self._schedule_machine_sync()

    def _schedule_machine_sync(self):
        """Schedule next machine sync (every 30s for near-real-time)."""
        if self._machine_sync_after_id:
            self.after_cancel(self._machine_sync_after_id)
        self._machine_sync_after_id = self.after(30000, self._run_machine_sync)

    def _update_log_tree(self, log_data):
        """Update the log treeview with given data (runs on main thread)."""
        if not self.winfo_exists():
            return
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        for row in log_data:
            row_l = list(row)
            t_str = str(row_l[6]).lower()
            if "in" in t_str:
                row_l[6] = "🟢 " + str(row_l[6])
                tags = ('in',)
            elif "out" in t_str:
                row_l[6] = "🔴 " + str(row_l[6])
                tags = ('out',)
            else:
                tags = ()
            self.log_tree.insert("", END, values=row_l, tags=tags)
        if hasattr(self, "_records_count_label"):
            self._records_count_label.config(text=f"Total Rows: {len(log_data)}")

    def _normalize_date(self, s):
        """Parse date string to YYYY-MM-DD format."""
        from datetime import datetime
        if not s:
            return ""
        s = s.strip()
        for fmt in ("%Y-%m-%d", "%Y %m %d", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except:
                continue
        return ""

    def _trigger_fetch_immediate(self):
        """Immediately starts a refresh of the attendance log, canceling scheduled debounce."""
        if not self.winfo_exists():
            return
            
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        # Try cache first for fast filter-only changes
        if self._cache_loaded:
            try:
                d_from = self._normalize_date(self._filter_from_de.entry.get().strip()) if hasattr(self, "_filter_from_de") else ""
                d_to = self._normalize_date(self._filter_to_de.entry.get().strip()) if hasattr(self, "_filter_to_de") else ""
                cached_d_from = self._cache_filters.get("d_from", "")
                cached_d_to = self._cache_filters.get("d_to", "")

                if d_from == cached_d_from and d_to == cached_d_to:
                    emp = self._filter_emp.get().strip() if hasattr(self, "_filter_emp") else ""
                    reg = self._filter_reg.get().strip() if hasattr(self, "_filter_reg") else ""
                    dept = self._filter_dept.get().strip() if hasattr(self, "_filter_dept") else ""
                    p_raw = self._filter_type.get() if hasattr(self, "_filter_type") else tr("all_types")
                    if p_raw == tr("check_in_type"): p_type = "check_in"
                    elif p_raw == tr("check_out_type"): p_type = "check_out"
                    else: p_type = None

                    # Check scope compatibility with cache
                    cf_dept = self._cache_filters.get("dept", "")
                    cf_emp = self._cache_filters.get("emp", "")
                    cf_reg = self._cache_filters.get("reg", "")

                    can_use_cache = True
                    # Widening: cache was filtered but user removed filter
                    if (cf_dept and not dept) or (cf_emp and not emp) or (cf_reg and not reg):
                        can_use_cache = False
                    # Different scope: cache has one value, user selected another
                    if dept and cf_dept and dept.lower() != cf_dept.lower():
                        can_use_cache = False
                    if emp and cf_emp and emp.lower() != cf_emp.lower():
                        can_use_cache = False
                    if reg and cf_reg and reg.lower() != cf_reg.lower():
                        can_use_cache = False

                    if can_use_cache:
                        filtered = list(self._cache_punches)
                        if emp:
                            # Combobox shows "NAME (REG)", cache has just "NAME"
                            clean_emp = emp.split('(')[0].strip().lower()
                            filtered = [p for p in filtered if clean_emp in p[1].lower()]
                        if reg:
                            filtered = [p for p in filtered if reg.lower() in str(p[2]).lower()]
                        if dept:
                            filtered = [p for p in filtered if dept.lower() in p[3].lower()]
                        if p_type:
                            target = p_type.lower().replace("-", "_")
                            filtered = [p for p in filtered if target in p[6].lower().replace("-", "_")]
                        self._update_log_tree(filtered)
                        return
            except Exception as e:
                logger.warning(f"Cache filter failed, falling back to DB: {e}")

        if self._is_fetching:
            logger.info("Sync already in progress (Immediate). Trigger ignored.")
            return

        # Date Validation (Robust)
        def parse_date_robust(s):
            if not s: return None
            s = s.strip()
            for fmt in ("%Y-%m-%d", "%Y %m %d", "%Y/%m/%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(s, fmt)
                except:
                    continue
            return None

        try:
            d_from_str = self._filter_from_de.entry.get().strip() if hasattr(self, "_filter_from_de") else ""
            d_to_str = self._filter_to_de.entry.get().strip() if hasattr(self, "_filter_to_de") else ""
            
            if d_from_str and d_to_str:
                from datetime import datetime
                d_from_obj = parse_date_robust(d_from_str)
                d_to_obj = parse_date_robust(d_to_str)
                
                if d_from_obj and d_to_obj and d_to_obj < d_from_obj:
                    from ttkbootstrap.dialogs import Messagebox
                    Messagebox.show_warning(
                        "The 'To Date' cannot be earlier than the 'From Date'.\nPlease select a valid date range.",
                        "Invalid Date Range"
                    )
                    return
        except Exception as e:
            logger.warning(f"Date validation error: {e}")

        self._is_fetching = True
        
        # Flash status
        if hasattr(self, "lbl_status"):
            self.lbl_status.configure(bootstyle="warning-inverse")

        threading.Thread(target=self._fetch_data_thread, daemon=True).start()

    def _fetch_data_thread(self):
        """Fetches data from DB in a background thread."""
        session = SessionLocal()
        try:
            # Read filter states properly from UI variables.
            from datetime import datetime, timedelta
            from contragest.features.pointage.service import PointageService
            svc = PointageService(session)
            
            emp = self._filter_emp.get().strip() if hasattr(self, "_filter_emp") else ""
            reg = self._filter_reg.get().strip() if hasattr(self, "_filter_reg") else ""
            dept = self._filter_dept.get().strip() if hasattr(self, "_filter_dept") else ""
            
            p_type = self._filter_type.get() if hasattr(self, "_filter_type") else tr("all_types")
            if p_type == tr("check_in_type"): p_type = "check_in"
            elif p_type == tr("check_out_type"): p_type = "check_out"
            else: p_type = None

            d_from = self._filter_from_de.entry.get().strip() if hasattr(self, "_filter_from_de") else ""
            d_to = self._filter_to_de.entry.get().strip() if hasattr(self, "_filter_to_de") else ""
            
            def parse_date_robust(s):
                if not s: return ""
                # Handle common separators like space, dash, or slash
                s = s.strip()
                for fmt in ("%Y-%m-%d", "%Y %m %d", "%Y/%m/%d", "%d/%m/%Y"):
                    try:
                        dt = datetime.strptime(s, fmt)
                        return dt.strftime("%Y-%m-%d")
                    except:
                        continue
                return ""

            d_from = parse_date_robust(d_from)
            d_to = parse_date_robust(d_to)

            # 1. Fetch grouped records for Department Summary (presence stats)
            records = svc.get_attendance_records_enriched(
                name_filter=emp,
                reg_filter=reg,
                dept_filter=dept,
                start_date=d_from,
                end_date=d_to
            )

            # 2. Build Department Summary (stats_data) exactly from the filtered Log
            # 2. Build Department Summary (stats_data) with normalization
            dept_unique_emps = {} # Keyed by UPPER department name
            unassigned_emps = set()
            
            for r in records:
                emp_name = r["employee"]
                d_raw = str(r["department"] or "").strip().upper()
                
                valid = False
                if p_type == "check_out" and r["check_out"] != "-": valid = True
                elif p_type == "check_in" and r["check_in"] != "-": valid = True
                elif not p_type and (r["check_in"] != "-" or r["check_out"] != "-"): valid = True
                
                if valid:
                    if d_raw and d_raw not in ("-", "-", ""):
                        if d_raw not in dept_unique_emps:
                            dept_unique_emps[d_raw] = set()
                        dept_unique_emps[d_raw].add(emp_name)
                    else:
                        unassigned_emps.add(emp_name)
                    
            # 3. Fetch Total Employee Counts per Department (Normalized & Active Only)
            from contragest.core.database import Employee, Department
            
            # Count ACTIVE employees with a formal Department ID link
            linked_counts = session.query(Department.name, func.count(Employee.id)).join(
                Employee, Employee.department_id == Department.id
            ).filter(Employee.is_archived == False).group_by(Department.name).all()
            
            dept_totals = {name.strip().upper(): count for name, count in linked_counts}
            
            # Add counts for ACTIVE employees using only the legacy department string field
            legacy_counts = session.query(Employee.department, func.count(Employee.id)).filter(
                Employee.department_id == None,
                Employee.is_archived == False
            ).group_by(Employee.department).all()
            
            for l_name, l_count in legacy_counts:
                if l_name:
                    l_norm = l_name.strip().upper()
                    dept_totals[l_norm] = dept_totals.get(l_norm, 0) + l_count
                
            # 4. Build List of All Departments (Formal + Legacy)
            all_dept_names = {d[0].strip().upper(): d[0] for d in session.query(Department.name).all()}
            
            # Add names found in the legacy department column
            legacy_names = session.query(func.distinct(Employee.department)).filter(
                Employee.department != None, 
                Employee.department != ""
            ).all()
            for (l_name,) in legacy_names:
                l_upper = l_name.strip().upper()
                if l_upper not in all_dept_names:
                    all_dept_names[l_upper] = l_name
            
            # Sort names for display
            sorted_depts = sorted(all_dept_names.items(), key=lambda x: x[0])
            
            stats_data = []
            for d_upper, d_display in sorted_depts:
                present_list = dept_unique_emps.get(d_upper, [])
                total_in_dept = dept_totals.get(d_upper, 0)
                
                # Only show if there's someone in it or it's a formal department
                if total_in_dept > 0 or d_upper in {d[0].strip().upper() for d in session.query(Department.name).all()}:
                    stats_data.append({
                        "name": d_display, 
                        "employees": sorted(list(present_list)),
                        "present_count": len(present_list),
                        "total_count": total_in_dept
                    })

            if unassigned_emps:
                stats_data.append({
                    "name": "Unassigned", 
                    "employees": sorted(list(unassigned_emps)), 
                    "present_count": len(unassigned_emps),
                    "total_count": len(unassigned_emps)
                })

            grand_total_present = sum(s["present_count"] for s in stats_data)
            grand_total_emps = session.query(Employee).filter(Employee.is_archived == False).count()

            # 3. Fetch RAW punches for the "Real-Time Attendance Log" view to show ALL activity
            raw_punches = svc.get_attendance_records(
                name_filter=emp,
                reg_filter=reg,
                dept_filter=dept,
                start_date=d_from,
                end_date=d_to,
                punch_type=None, # Fetch all types to correctly apply inference filter
                limit=1000
            )

            log_data = []
            for p in raw_punches:
                # Skip entries with no employee linkage and no registration ID
                if not p.employee_id and not p.zk_user_id:
                    continue
                # Skip entries with empty or missing punch_time
                if not p.punch_time or not p.punch_time.strip():
                    continue

                # Enrich with Employee info
                emp_obj = p.employee
                f_name = f"{emp_obj.first_name} {emp_obj.last_name}" if emp_obj else f"REG {p.zk_user_id}"
                reg_num = emp_obj.registration_number if emp_obj else p.zk_user_id
                
                # Department
                d_name = "-"
                if emp_obj:
                    if emp_obj.dept_obj: d_name = emp_obj.dept_obj.name
                    elif emp_obj.department: d_name = emp_obj.department
                    
                # Schedule (Check active assignments for the specific date).
                # Use the service's authoritative resolver so the Real-Time Log
                # matches the enriched grid: it covers BOTH fixed
                # (EmployeeSchedule) and rotating (EmployeeRotation) schedules,
                # unlike the old code that only scanned emp_obj.assignments.
                s_name = "-"
                sched_obj = None
                p_date = None
                try:
                    # Robust parsing for ISO or space-separated timestamps
                    if "T" in p.punch_time:
                        p_date = datetime.fromisoformat(p.punch_time.replace('Z', '+00:00')).date()
                    else:
                        p_date = datetime.strptime(p.punch_time.split()[0], "%Y-%m-%d").date()
                except:
                    pass

                if emp_obj and p_date:
                    sched_obj = svc.resolve_employee_schedule(
                        employee_id=emp_obj.id,
                        reg_str=str(emp_obj.registration_number or ""),
                        target_date=p_date,
                        punch_time=p.punch_time,
                    )
                    if sched_obj:
                        s_name = sched_obj.name
                
                # Use inference logic to differentiate IN/OUT (since machines often label everything as check_in)
                # If machine says check_out, we honor it, otherwise we help it guess.
                inferred_type, _ = svc.guess_punch_type(p.punch_time, sched_obj)
                type_str = "Check-In" if inferred_type == "check_in" else "Check-Out"
                if p.punch_type and p.punch_type.lower() == "check_out":
                    type_str = "Check-Out"

                # Filter by inferred type if requested
                if p_type:
                    # Normalize both for comparison (check_in vs Check-In)
                    t_match = type_str.lower().replace("-", "_")
                    if t_match != p_type.lower():
                        continue

                # Format time
                try:
                    dt = datetime.fromisoformat(p.punch_time.replace('Z', '+00:00'))
                    formatted_dt = dt.strftime("%d/%m/%Y %H:%M:%S")
                except:
                    formatted_dt = p.punch_time
                    
                log_data.append((
                    formatted_dt,
                    f_name,
                    reg_num or "-",
                    d_name,
                    s_name,
                    p.machine.name if p.machine else "-",
                    type_str
                ))

            # Populate cache for client-side filtering
            self._cache_punches = list(log_data)
            self._cache_records = list(records)
            self._cache_filters = {"emp": emp, "reg": reg, "dept": dept, "p_type": p_type, "d_from": d_from, "d_to": d_to}
            self._cache_loaded = True

            # Schedule UI update
            if self.winfo_exists() and self._polling:
                self.after(0, lambda: self._update_ui(stats_data, log_data, grand_total_present, grand_total_emps))

        except Exception as e:
            logger.error(f"Error fetching HR dashboard data: {e}")
            if "disk I/O error" in str(e).lower():
                # Backoff: wait 60s if network is unstable
                if self.winfo_exists() and self._polling:
                    self.after(0, lambda: self.lbl_status.configure(text=" ● OFFLINE ", bootstyle="danger-inverse"))
                    self.after(0, lambda: self.lbl_last_update.config(text="Network Error - Retrying in 60s"))
                    self.after(60000, self._trigger_fetch)
                    return
        finally:
            self._is_fetching = False  # Always reset flag
            session.close()

    def _update_ui(self, stats_data, log_data, total_present=0, total_emps=0):
        """Updates UI components (runs on main thread)."""
        if not self.winfo_exists():
            return

        import datetime
        self.lbl_last_update.config(text=f"Last updated: {datetime.datetime.now().strftime('%H:%M:%S')}")

        if hasattr(self, "lbl_total_employees"):
            pct = (total_present / total_emps * 100) if total_emps > 0 else 0
            self.lbl_total_employees.config(text=f"Total Presence: {total_present} / {total_emps} ({pct:.1f}%)")
            
        # Update Progress Bar if it exists (for a WOW factor)
        if not hasattr(self, "_presence_bar"):
            # Create a premium summary frame at the top if not exists
            summary_frame = ttk.Frame(self.left_panel)
            summary_frame.pack(after=self.lbl_total_employees, fill=X, pady=(1, 12))
            
            self._presence_bar = ttk.Progressbar(
                summary_frame, 
                orient=HORIZONTAL, 
                length=200, 
                mode='determinate', 
                bootstyle=SUCCESS
            )
            self._presence_bar.pack(fill=X, side=TOP)
        
        pct = (total_present / total_emps * 100) if total_emps > 0 else 0
        self._presence_bar['value'] = pct
        
        # Color based on health
        if pct < 30: self._presence_bar.configure(bootstyle=DANGER)
        elif pct < 70: self._presence_bar.configure(bootstyle=WARNING)
        else: self._presence_bar.configure(bootstyle=SUCCESS)

        # Update Department Summary Treeview
        # 1. Save state: expansion and selection
        expanded_depts = set()
        selected_text = ""
        
        if not self._reset_expansion:
            # Handle selection persistence
            selected_item = self.dept_tree.selection()
            if selected_item:
                selected_text = self.dept_tree.item(selected_item[0], "text")
                
            # Handle expansion persistence
            for item in self.dept_tree.get_children():
                if self.dept_tree.item(item, "open"):
                    expanded_depts.add(self.dept_tree.item(item, "text"))
        else:
            # We are resetting, so consume the flag
            self._reset_expansion = False
        
        # 2. Rebuild tree
        for item in self.dept_tree.get_children():
            self.dept_tree.delete(item)

        for i, stat in enumerate(stats_data):
            dept_name = str(stat["name"]).upper()
            present_c = stat["present_count"]
            total_c = stat["total_count"]
            emps = stat.get("employees", [])
            
            # Row styling tag (striping)
            row_tag = 'even' if i % 2 == 0 else 'odd'
            
            # Display stats like "5 / 12"
            stats_str = f"{present_c} / {total_c}"
            pct_val = (present_c / total_c * 100) if total_c > 0 else 0
            pct_str = f"{pct_val:.1f}%"
            presence_status = "Present" if present_c > 0 else "None"
            
            # Insert department as parent
            parent_id = self.dept_tree.insert(
                "", 
                END, 
                text=dept_name, 
                values=(stats_str, pct_str),
                tags=('dept', row_tag)
            )
            
            # Restore expansion if it was open before
            if dept_name in expanded_depts:
                self.dept_tree.item(parent_id, open=True)
            
            # Restore selection if this was the selected department
            if dept_name == selected_text:
                self.dept_tree.selection_set(parent_id)
            
            # Insert employees as children
            for emp in emps:
                emp_display = f"  • {emp}" # Cleaner bullet point
                child_id = self.dept_tree.insert(
                    parent_id, 
                    END, 
                    text=emp_display, 
                    values=("Present",), # Use a cleaner status for individuals
                    tags=('emp', row_tag)
                )
                # Restore selection if this was the selected employee
                if emp_display == selected_text:
                    self.dept_tree.selection_set(child_id)

        # Configure Treeview tags for premium look & striping
        style = ttk.Style()
        style.configure('Treeview', rowheight=DesignTokens.TABLE_ROW_HEIGHT, font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY))
        style.configure('Treeview.Heading', font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY, "bold"), foreground=DesignTokens.PRIMARY, background=DesignTokens.SECONDARY)

        self.dept_tree.tag_configure('dept', font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY, "bold"), background=DesignTokens.SECONDARY, foreground=DesignTokens.PRIMARY)
        self.dept_tree.tag_configure('emp', font=(DesignTokens.FONT_PRIMARY, DesignTokens.FONT_SIZE_BODY), foreground=DesignTokens.TEXT)
        self.dept_tree.tag_configure('even', background=DesignTokens.SURFACE)
        self.dept_tree.tag_configure('odd', background=DesignTokens.BG_APP)

        # Update Log Tree
        self._update_log_tree(log_data)

        # Schedule next poll (10s interval for Real-Time feel)
        if self._polling:
            if self._polling_after_id:
                self.after_cancel(self._polling_after_id)
            self._polling_after_id = self.after(10000, self._trigger_fetch)

    def _trigger_fetch(self):
        """High-level fetch trigger with concurrency security."""
        if not self._polling or not self.winfo_exists():
            return
            
        if self._is_fetching:
            logger.info("Sync already in progress. Skipping redundant trigger.")
            return

        # Cancel any pending 'after' to prevent stacking
        if self._polling_after_id:
            self.after_cancel(self._polling_after_id)
            self._polling_after_id = None

        self._is_fetching = True
        
        # Flash the status indicator
        if hasattr(self, "lbl_status"):
            self.lbl_status.configure(bootstyle="warning-inverse")
            
        threading.Thread(target=self._fetch_data_thread, daemon=True).start()

    def start_polling(self):
        """Starts the auto-refresh loop if not already running."""
        if not self._polling:
            self._polling = True
            logger.info("HRDashboard: Starting auto-polling.")
            if hasattr(self, "lbl_status"):
                self.lbl_status.configure(bootstyle="success-inverse", text=" ● LIVE ")
            self._trigger_fetch()

    def stop_polling(self):
        """Stops the polling loop and cancels pending tasks."""
        self._polling = False
        if self._polling_after_id:
            self.after_cancel(self._polling_after_id)
            self._polling_after_id = None
        if self._machine_sync_after_id:
            self.after_cancel(self._machine_sync_after_id)
            self._machine_sync_after_id = None

    def destroy(self):
        self.stop_polling()
        super().destroy()
