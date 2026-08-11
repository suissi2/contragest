"""
Employee Data Entry Form - Rich tabbed form for add/edit employee records.

Supports two modes:
  - mode="add"  → empty form for new employee entry
  - mode="edit" → pre-populated form for editing an existing employee

Features:
  - 4 tabs: Identity, Professional, Contact, Documents & Salary
  - Real-time field validation with visual indicators
  - Autocomplete department combobox
  - Photo upload and preview
  - RBAC enforcement via AuthService
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets import DateEntry
from contragest.core.database import SessionLocal, Employee, Department
from contragest.features.employee_manager.service import EmployeeService
from contragest.core.i18n import tr
from tkinter import filedialog
from PIL import Image, ImageTk
from datetime import datetime, date
import os
from contragest.core.status_bar import StatusLabel
import re
import shutil
from contragest.features.pointage.service import PointageService
from contragest.core.database import WorkSchedule, EmployeeSchedule
from contragest.core.logging import setup_logger
from contragest.features.employee_manager.schedule_quick_add import ScheduleQuickAddDialog

logger = setup_logger("employee_manager_form")


# --------------------------------------------------------------------------- #
#  Constants
# --------------------------------------------------------------------------- #

CIVILITY_OPTIONS = ["MR.", "MS.", "MRS."]
MATRIMONIAL_OPTIONS = ["SINGLE", "MARRIED", "DIVORCED", "WIDOWED"]
PRIVILEGE_OPTIONS = ["STANDARD", "VIP", "EXECUTIVE"]
NATIONALITY_OPTIONS = [
    "MOROCCAN", "FRENCH", "AMERICAN", "BRITISH", "GERMAN",
    "SPANISH", "ITALIAN", "CANADIAN", "BELGIAN", "DUTCH",
    "TUNISIAN", "ALGERIAN", "EGYPTIAN", "SAUDI", "EMIRATI",
    "TURKISH", "CHINESE", "JAPANESE", "INDIAN", "BRAZILIAN",
    "OTHER"
]

WEEKDAY_OPTIONS = ["NONE", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

class DataEntryForm(ttk.Toplevel):
    """Professional tabbed form for adding / editing an employee record."""

    def __init__(self, parent, mode="add", employee_id=None, on_save_callback=None):
        """
        Args:
            parent: Parent widget.
            mode: "add" or "edit".
            employee_id: Required when mode="edit".
            on_save_callback: Called after successful save to refresh parent.
        """
        super().__init__(parent)
        self.mode = mode
        self.employee_id = employee_id
        self.on_save_callback = on_save_callback

        self.title(tr("data_entry_title") if mode == "add" else tr("edit_employee_title"))
        self.geometry("820x700")
        self.resizable(False, False)
        self.grab_set()

        # DB session & service
        self.session = SessionLocal()
        self.service = EmployeeService(self.session)

        # Photo state
        self.photo_path_var = ttk.StringVar()
        self._photo_image = None  # Keep reference to prevent GC

        # Load departments and schedules for comboboxes before building UI
        self.pointage_service = PointageService(self.session)
        self.department_list = self.service.get_all_departments()
        self.schedule_list = self.session.query(WorkSchedule).order_by(WorkSchedule.name).all()

        # Add Persistent Status Bar (Reserve bottom area before UI build)
        # Check if parent has current_user (common in MainWindow/EmployeeManagerWindow)
        user = getattr(parent, 'current_user', None)
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status(tr("data_entry_title") if mode == "add" else tr("edit_employee_title"))

        # Build UI
        self._build_header()
        self._build_notebook()
        self._build_action_bar()

        # If editing, pre-populate
        if mode == "edit" and employee_id:
            self._populate_from_employee(employee_id)

        self.center_window()

    # ------------------------------------------------------------------ #
    #  Layout builders
    # ------------------------------------------------------------------ #

    def _build_header(self):
        """Top banner with icon and title."""
        header = ttk.Frame(self, bootstyle="primary")
        header.pack(fill=X)

        icon = "➕" if self.mode == "add" else "✏️"
        title_text = tr("data_entry_title") if self.mode == "add" else tr("edit_employee_title")
        ttk.Label(
            header, text=f"  {icon}  {title_text}",
            font=("Helvetica", 14, "bold"),
            bootstyle="inverse-primary",
            padding=(15, 10)
        ).pack(side=LEFT)

    def _build_notebook(self):
        """Create the 4-tab notebook."""
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=YES, padx=15, pady=10)

        # --- Tab 1: Identity --- #
        self.identity_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.identity_frame, text=f"  👤 {tr('identity_tab')}  ")
        self._build_identity_tab()

        # --- Tab 2: Professional --- #
        self.professional_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.professional_frame, text=f"  💼 {tr('professional_tab')}  ")
        self._build_professional_tab()

        # --- Tab 3: Contact --- #
        self.contact_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.contact_frame, text=f"  📞 {tr('contact_tab')}  ")
        self._build_contact_tab()

        # --- Tab 4: Documents & Salary --- #
        self.documents_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.documents_frame, text=f"  📄 {tr('documents_tab')}  ")
        self._build_documents_tab()

    def _build_action_bar(self):
        """Bottom bar with Save / Export / Cancel buttons."""
        bar = ttk.Frame(self, padding=10)
        bar.pack(fill=X, side=BOTTOM)

        ttk.Button(
            bar, text=f"❌ {tr('cancel')}", bootstyle="secondary-outline",
            command=self.destroy, padding=(20, 8)
        ).pack(side=RIGHT, padx=5)

        self._export_btn = ttk.Button(
            bar, text=f"📲 {tr('export_employee')}", bootstyle="warning",
            command=self._on_export, padding=(20, 8)
        )
        self._export_btn.pack(side=RIGHT, padx=5)

        ttk.Button(
            bar, text=f"💾 {tr('save')}", bootstyle="success",
            command=self._on_save, padding=(20, 8)
        ).pack(side=RIGHT, padx=5)

        # Status label for export feedback
        self._export_status = ttk.Label(bar, text="", font=("Helvetica", 9))
        self._export_status.pack(side=LEFT, padx=10)

    # ------------------------------------------------------------------ #
    #  Tab 1 - Identity
    # ------------------------------------------------------------------ #

    def _build_identity_tab(self):
        parent = self.identity_frame

        # Two-column layout: left = fields, right = photo
        left = ttk.Frame(parent)
        left.pack(side=LEFT, fill=BOTH, expand=YES)

        right = ttk.Frame(parent, padding=(20, 0, 0, 0))
        right.pack(side=RIGHT, fill=Y)

        # Civility
        self.civility_var = ttk.StringVar()
        self._add_combobox_row(left, tr("civility"), self.civility_var, CIVILITY_OPTIONS)

        # Registration Number
        self.reg_num_var = ttk.StringVar()
        self._add_entry_row(left, tr("registration_number"), self.reg_num_var)

        # First Name *
        self.first_name_var = ttk.StringVar()
        self._add_entry_row(left, f"{tr('first_name')} *", self.first_name_var, required=True)

        # Last Name *
        self.last_name_var = ttk.StringVar()
        self._add_entry_row(left, f"{tr('last_name')} *", self.last_name_var, required=True)

        # Date of Birth
        dob_row = ttk.Frame(left)
        dob_row.pack(fill=X, pady=5)
        ttk.Label(dob_row, text=tr("dob"), width=20, anchor=W).pack(side=LEFT)
        self.dob_entry = DateEntry(dob_row, dateformat="%Y-%m-%d", width=18)
        self.dob_entry.pack(side=LEFT, fill=X, expand=YES)
        self.dob_entry.entry.delete(0, "end")  # Start empty

        # Nationality
        self.nationality_var = ttk.StringVar()
        self._add_combobox_row(left, tr("nationality"), self.nationality_var, NATIONALITY_OPTIONS)

        # Matrimonial Status
        self.matrimonial_var = ttk.StringVar()
        self._add_combobox_row(left, tr("matrimonial_status"), self.matrimonial_var, MATRIMONIAL_OPTIONS)

        # Children Count
        children_row = ttk.Frame(left)
        children_row.pack(fill=X, pady=5)
        ttk.Label(children_row, text=tr("children_count"), width=20, anchor=W).pack(side=LEFT)
        self.children_spin = ttk.Spinbox(children_row, from_=0, to=20, width=6)
        self.children_spin.pack(side=LEFT)
        self.children_spin.set(0)

        # --- Photo panel (right side) ---
        ttk.Label(right, text=tr("photo"), font=("Helvetica", 10, "bold")).pack(pady=(0, 5))
        self.photo_label = ttk.Label(
            right, text="NO PHOTO", width=18,
            relief="groove", anchor=CENTER,
            padding=5
        )
        self.photo_label.pack(pady=5)
        self.photo_label.configure(image="")  # placeholder

        ttk.Button(
            right, text=f"📁 {tr('browse')}", bootstyle="info-outline",
            command=self._pick_photo
        ).pack(pady=5)

    # ------------------------------------------------------------------ #
    #  Tab 2 - Professional
    # ------------------------------------------------------------------ #

    def _build_professional_tab(self):
        parent = self.professional_frame

        # Department (autocomplete combobox)
        dept_row = ttk.Frame(parent)
        dept_row.pack(fill=X, pady=5)
        ttk.Label(dept_row, text=tr("department"), width=20, anchor=W).pack(side=LEFT)

        self.dept_var = ttk.StringVar()
        self.dept_var.set("HR")  # Default department value

        self.dept_combo = ttk.Combobox(
            dept_row, 
            textvariable=self.dept_var,
            values=[d.name for d in self.department_list]
        )
        self.dept_combo.pack(side=LEFT, fill=X, expand=YES)
        self.dept_combo.bind("<KeyRelease>", self._on_dept_key)

        # Small button to open Department Manager
        ttk.Button(
            dept_row, text="⚙️", bootstyle="secondary-outline", width=3,
            command=self._open_department_manager
        ).pack(side=LEFT, padx=(5, 0))


        # Role Title
        self.role_title_var = ttk.StringVar()
        self._add_entry_row(parent, tr("role_title"), self.role_title_var)

        # Multi-Schedule Selection
        sched_head = ttk.Frame(parent)
        sched_head.pack(fill=X, pady=(10, 2))
        ttk.Label(sched_head, text="AUTHORIZED SCHEDULES", font=("Helvetica", 10, "bold")).pack(side=LEFT)
        ttk.Button(sched_head, text="+", bootstyle="secondary-outline", width=3,
                   command=self._open_schedules_interface).pack(side=RIGHT)
        
        # Scrollable frame for schedule checkboxes
        sched_frame_outer = ttk.Frame(parent, relief="groove", padding=5)
        sched_frame_outer.pack(fill=X, pady=5)
        
        canvas = ttk.Canvas(sched_frame_outer, height=100)
        scrollbar = ttk.Scrollbar(sched_frame_outer, orient=VERTICAL, command=canvas.yview)
        self.sched_list_inner = ttk.Frame(canvas)
        
        self.sched_list_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.sched_list_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=X, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        self.schedule_checkboxes = {} # name -> (var, obj)
        self._refresh_schedule_list_ui()

        # Effective Date for Schedule
        eff_row = ttk.Frame(parent)
        eff_row.pack(fill=X, pady=5)
        ttk.Label(eff_row, text="SCHED. EFFECTIVE DATE", width=20, anchor=W).pack(side=LEFT)
        self.sched_eff_date_entry = DateEntry(eff_row, dateformat="%Y-%m-%d", width=18)
        self.sched_eff_date_entry.pack(side=LEFT, fill=X, expand=YES)
        self.sched_eff_date_entry.entry.delete(0, "end")
        self.sched_eff_date_entry.entry.insert(0, date.today().strftime("%Y-%m-%d"))
        
        # Reload checkboxes when date changes to allow editing historical sets
        self.sched_eff_date_entry.entry.bind("<FocusOut>", lambda e: self._refresh_sched_checkboxes_for_date())

        # Privilege
        self.privilege_var = ttk.StringVar()
        self._add_combobox_row(parent, tr("privilege"), self.privilege_var, PRIVILEGE_OPTIONS)

        # Weekly Day Off
        self.weekly_day_off_var = ttk.StringVar()
        self.weekly_day_off_var.set("NONE")
        self._add_combobox_row(parent, "WEEKLY DAY OFF", self.weekly_day_off_var, WEEKDAY_OPTIONS)

        # Auto Punch
        auto_row = ttk.Frame(parent)
        auto_row.pack(fill=X, pady=5)
        ttk.Label(auto_row, text="AUTO PUNCH", width=20, anchor=W).pack(side=LEFT)
        self.is_auto_punch_var = ttk.BooleanVar()
        ttk.Checkbutton(auto_row, text="Enable automatic clock-in/out", variable=self.is_auto_punch_var, bootstyle="round-toggle").pack(side=LEFT)

        # Hire Date
        hire_row = ttk.Frame(parent)
        hire_row.pack(fill=X, pady=5)
        ttk.Label(hire_row, text=tr("hire_date"), width=20, anchor=W).pack(side=LEFT)
        self.hire_date_entry = DateEntry(hire_row, dateformat="%Y-%m-%d", width=18)
        self.hire_date_entry.pack(side=LEFT, fill=X, expand=YES)
        self.hire_date_entry.entry.delete(0, "end")

        # Exit Date
        exit_row = ttk.Frame(parent)
        exit_row.pack(fill=X, pady=5)
        ttk.Label(exit_row, text=tr("exit_date"), width=20, anchor=W).pack(side=LEFT)
        self.exit_date_entry = DateEntry(exit_row, dateformat="%Y-%m-%d", width=18)
        self.exit_date_entry.pack(side=LEFT, fill=X, expand=YES)
        self.exit_date_entry.entry.delete(0, "end")

    # ------------------------------------------------------------------ #
    #  Tab 3 - Contact
    # ------------------------------------------------------------------ #

    def _build_contact_tab(self):
        parent = self.contact_frame

        # Email
        self.email_var = ttk.StringVar()
        self._add_entry_row(parent, tr("email"), self.email_var)

        # Mobile Phone
        self.mobile_var = ttk.StringVar()
        self._add_entry_row(parent, tr("mobile_phone"), self.mobile_var)

        # Office Phone
        self.office_phone_var = ttk.StringVar()
        self._add_entry_row(parent, tr("office_phone"), self.office_phone_var)

        # Address (multiline)
        addr_row = ttk.Frame(parent)
        addr_row.pack(fill=X, pady=5)
        ttk.Label(addr_row, text=tr("address"), width=20, anchor=W).pack(side=LEFT, anchor=N)
        self.address_text = ttk.Text(addr_row, height=4, width=40)
        self.address_text.pack(side=LEFT, fill=X, expand=YES)

    # ------------------------------------------------------------------ #
    #  Tab 4 - Documents & Salary
    # ------------------------------------------------------------------ #

    def _build_documents_tab(self):
        parent = self.documents_frame

        # ID Card Number
        self.id_card_var = ttk.StringVar()
        self._add_entry_row(parent, tr("id_card_number"), self.id_card_var)

        # Passport
        self.passport_var = ttk.StringVar()
        self._add_entry_row(parent, tr("passport"), self.passport_var)

        # CNSS
        self.cnss_var = ttk.StringVar()
        self._add_entry_row(parent, tr("cnss"), self.cnss_var)

        # Separator
        ttk.Separator(parent).pack(fill=X, pady=10)

        # Gross Salary
        self.gross_salary_var = ttk.StringVar()
        self._add_entry_row(parent, tr("gross_salary"), self.gross_salary_var)

        # Net Salary
        self.net_salary_var = ttk.StringVar()
        self._add_entry_row(parent, tr("net_salary"), self.net_salary_var)

    # ------------------------------------------------------------------ #
    #  Helpers - Row builders
    # ------------------------------------------------------------------ #

    def _add_entry_row(self, parent, label_text, variable, required=False):
        """Create a label + entry row."""
        row = ttk.Frame(parent)
        row.pack(fill=X, pady=5)
        ttk.Label(row, text=label_text, width=20, anchor=W).pack(side=LEFT)
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side=LEFT, fill=X, expand=YES)

        if required:
            # Real-time validation indicator
            indicator = ttk.Label(row, text="●", foreground="red", font=("Helvetica", 12))
            indicator.pack(side=LEFT, padx=5)
            variable.trace_add("write", lambda *_: indicator.configure(
                foreground="green" if variable.get().strip() else "red"
            ))
        return entry

    def _add_combobox_row(self, parent, label_text, variable, values):
        """Create a label + combobox row."""
        row = ttk.Frame(parent)
        row.pack(fill=X, pady=5)
        ttk.Label(row, text=label_text, width=20, anchor=W).pack(side=LEFT)
        combo = ttk.Combobox(row, textvariable=variable, values=values, state="readonly")
        combo.pack(side=LEFT, fill=X, expand=YES)
        return combo

    # ------------------------------------------------------------------ #
    #  Department autocomplete
    # ------------------------------------------------------------------ #

    def _load_departments(self):
        """Reload all departments from DB and update the Combobox."""
        depts = self.service.get_all_departments()
        self.department_list = depts
        if hasattr(self, 'dept_combo'):
            self.dept_combo["values"] = [d.name for d in depts]
        return depts

    def _on_dept_key(self, event):
        """Filter department dropdown as user types."""
        typed = self.dept_var.get().lower()
        if not typed:
            self.dept_combo["values"] = [d.name for d in self.department_list]
            return
        filtered = [d.name for d in self.department_list if typed in d.name.lower()]
        self.dept_combo["values"] = filtered
        self.dept_combo.event_generate("<Down>")  # Open dropdown

    def _open_department_manager(self):
        """Open the Department Manager dialog and refresh dropdown on close."""
        from contragest.features.employee_manager.department_manager import DepartmentManagerDialog
        dialog = DepartmentManagerDialog(self)
        self.wait_window(dialog)
        # Refresh departments after manager closes
        self.department_list = self._load_departments()

    # ------------------------------------------------------------------ #
    #  Photo handling
    # ------------------------------------------------------------------ #

    def _pick_photo(self):
        """Open file dialog for photo selection and show preview."""
        path = filedialog.askopenfilename(
            title=tr("browse"),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if not path:
            return

        self.photo_path_var.set(path)
        self._show_photo_preview(path)

    def _show_photo_preview(self, path):
        """Display a thumbnail preview of the selected photo."""
        try:
            img = Image.open(path)
            img.thumbnail((130, 160))
            self._photo_image = ImageTk.PhotoImage(img)
            self.photo_label.configure(image=self._photo_image, text="")
        except Exception as e:
            self.photo_label.configure(text="ERROR", image="")
            print(f"Photo preview error: {e}")

    # ------------------------------------------------------------------ #
    #  Pre-populate (edit mode)
    # ------------------------------------------------------------------ #

    def _populate_from_employee(self, emp_id):
        """Load employee data from DB and fill all form fields."""
        self.employee_id = emp_id
        emp = self.service.get_employee_full(emp_id)
        if not emp:
            Messagebox.show_error(tr("error"), "Employee not found.")
            self.destroy()
            return

        # Identity
        self.civility_var.set(emp.civility or "")
        self.reg_num_var.set(emp.registration_number or "")
        self.first_name_var.set(emp.first_name or "")
        self.last_name_var.set(emp.last_name or "")
        if emp.dob:
            self.dob_entry.entry.delete(0, "end")
            self.dob_entry.entry.insert(0, emp.dob.strftime("%Y-%m-%d"))
        self.nationality_var.set(emp.nationality or "")
        self.matrimonial_var.set(emp.matrimonial_status or "")
        self.children_spin.set(emp.children_count or 0)
        if emp.photo_path and os.path.exists(emp.photo_path):
            self.photo_path_var.set(emp.photo_path)
            self._show_photo_preview(emp.photo_path)

        # Professional
        if emp.dept_obj:
            self.dept_var.set(emp.dept_obj.name)

        self.role_title_var.set(emp.role_title or "")
        
        # Load Schedules (all matching the latest effective date)
        latest_assignment = (
            self.session.query(EmployeeSchedule)
            .filter_by(employee_id=emp_id)
            .order_by(EmployeeSchedule.effective_date.desc(), EmployeeSchedule.id.desc())
            .first()
        )
        if latest_assignment:
            eff = latest_assignment.effective_date
            self.sched_eff_date_entry.entry.delete(0, "end")
            self.sched_eff_date_entry.entry.insert(0, eff.strftime("%Y-%m-%d"))
            
            # Check all schedules assigned to this date
            all_at_date = self.session.query(EmployeeSchedule).filter_by(
                employee_id=emp_id, 
                effective_date=eff
            ).all()
            assigned_names = {a.schedule.name for a in all_at_date}
            
            for name, (v_obj, _) in self.schedule_checkboxes.items():
                v_obj.set(name in assigned_names)
        else:
            for v_obj, _ in self.schedule_checkboxes.values():
                v_obj.set(False)
            
        self.privilege_var.set(emp.privilege or "")
        self.is_auto_punch_var.set(getattr(emp, "is_auto_punch", False))
        self.weekly_day_off_var.set(getattr(emp, "weekly_day_off", "NONE") or "NONE")
        if emp.hire_date:
            self.hire_date_entry.entry.delete(0, "end")
            self.hire_date_entry.entry.insert(0, emp.hire_date.strftime("%Y-%m-%d"))
        if emp.exit_date:
            self.exit_date_entry.entry.delete(0, "end")
            self.exit_date_entry.entry.insert(0, emp.exit_date.strftime("%Y-%m-%d"))
        else:
            self.exit_date_entry.entry.delete(0, "end")

        # Contact
        self.email_var.set(emp.email or "")
        self.mobile_var.set(emp.mobile_phone or "")
        self.office_phone_var.set(emp.office_phone or "")
        if emp.address:
            self.address_text.insert("1.0", emp.address)

        # Documents & Salary
        self.id_card_var.set(emp.id_card_number or "")
        self.passport_var.set(emp.passport or "")
        self.cnss_var.set(emp.cnss or "")
        self.gross_salary_var.set(emp.gross_salary or "")
        self.net_salary_var.set(emp.net_salary or "")

    # ------------------------------------------------------------------ #
    #  Validation
    # ------------------------------------------------------------------ #

    def _validate(self):
        """Validate required fields and data formats. Returns list of errors."""
        errors = []

        # Required: first_name, last_name
        if not self.first_name_var.get().strip():
            errors.append(tr("required_field_missing", field=tr("first_name")))
        if not self.last_name_var.get().strip():
            errors.append(tr("required_field_missing", field=tr("last_name")))

        # Email format (if provided)
        email = self.email_var.get().strip()
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append(tr("invalid_email"))

        # Salary numeric check
        for var, label in [(self.gross_salary_var, tr("gross_salary")),
                           (self.net_salary_var, tr("net_salary"))]:
            val = var.get().strip()
            if val:
                try:
                    float(val.replace(",", "."))
                except ValueError:
                    errors.append(tr("invalid_number", field=label))

        return errors

    # ------------------------------------------------------------------ #
    #  Save
    # ------------------------------------------------------------------ #

    def _resolve_department_id(self):
        """Resolve department name to department_id."""
        dept_name = self.dept_var.get().strip()
        if not dept_name:
            return None
        # Robust resolution: strip both sides and use case-insensitive match
        for d in self.department_list:
            if d.name.strip().lower() == dept_name.lower():
                return d.id
        return None

    def _parse_date(self, date_entry):
        """Safely parse a DateEntry value to a date object."""
        val = date_entry.entry.get().strip()
        if not val:
            return None
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _copy_photo_to_assets(self, source_path):
        """Copy selected photo to assets/photos/ directory and return new path."""
        if not source_path or not os.path.exists(source_path):
            return None
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        photos_dir = os.path.join(base_dir, "assets", "photos")
        os.makedirs(photos_dir, exist_ok=True)
        ext = os.path.splitext(source_path)[1]
        filename = f"emp_{self.first_name_var.get().lower()}_{self.last_name_var.get().lower()}{ext}"
        dest = os.path.join(photos_dir, filename)
        try:
            shutil.copy2(source_path, dest)
            return dest
        except Exception:
            return source_path  # Fallback to original path

    def _collect_data(self):
        """Collect all form data into a kwargs dict for the service."""
        photo_path = self._copy_photo_to_assets(self.photo_path_var.get()) if self.photo_path_var.get() else None

        return {
            "first_name": self.first_name_var.get().strip(),
            "last_name": self.last_name_var.get().strip(),
            "email": self.email_var.get().strip() or None,
            "civility": self.civility_var.get() or None,
            "registration_number": self.reg_num_var.get().strip() or None,
            "dob": self._parse_date(self.dob_entry),
            "nationality": self.nationality_var.get() or None,
            "matrimonial_status": self.matrimonial_var.get() or None,
            "children_count": int(self.children_spin.get() or 0),
            "photo_path": photo_path,
            "department_id": self._resolve_department_id(),

            "role_title": self.role_title_var.get().strip() or None,
            "privilege": self.privilege_var.get() or None,
            "is_auto_punch": self.is_auto_punch_var.get(),
            "weekly_day_off": self.weekly_day_off_var.get() if self.weekly_day_off_var.get() != "NONE" else None,
            "hire_date": self._parse_date(self.hire_date_entry),
            "exit_date": self._parse_date(self.exit_date_entry),
            "mobile_phone": self.mobile_var.get().strip() or None,
            "office_phone": self.office_phone_var.get().strip() or None,
            "address": self.address_text.get("1.0", "end-1c").strip() or None,
            "id_card_number": self.id_card_var.get().strip() or None,
            "passport": self.passport_var.get().strip() or None,
            "cnss": self.cnss_var.get().strip() or None,
            "gross_salary": self.gross_salary_var.get().strip() or None,
            "net_salary": self.net_salary_var.get().strip() or None,
        }

    def _save_schedule_assignment(self, emp_id):
        if not emp_id:
            return
            
        try:
            eff_date = self._parse_date(self.sched_eff_date_entry) or date.today()
            
            # Get list of checked schedules
            selected_scheds = [obj for v_obj, obj in self.schedule_checkboxes.values() if v_obj.get()]
            
            # First, remove any assignments for this SPECIFIC employee and EXACT date 
            # that are NOT in the selection (clean up unchecks)
            selected_ids = [s.id for s in selected_scheds]
            existing = self.session.query(EmployeeSchedule).filter_by(
                employee_id=emp_id, 
                effective_date=eff_date
            ).all()
            
            for e in existing:
                if e.schedule_id not in selected_ids:
                    self.session.delete(e)
            
            # Now add/ensure all selected ones
            for s in selected_scheds:
                self.pointage_service.assign_schedule(emp_id, s.id, effective_date=eff_date, commit=False)
                
            self.session.commit()
            logger.info(f"Schedules saved for employee {emp_id} at date {eff_date}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving schedule assignment for employee {emp_id}: {e}")
            raise  # Re-raise to be caught by _save_employee_data

    def _refresh_sched_checkboxes_for_date(self):
        """Update checkboxes based on the currently selected effective date in the entry."""
        emp_id = getattr(self, "employee_id", None)
        if not emp_id: return
            
        try:
            eff_date = self._parse_date(self.sched_eff_date_entry)
            if not eff_date: return
            
            # Find the latest effective date <= the chosen date
            from sqlalchemy import func
            sub_q = self.session.query(func.max(EmployeeSchedule.effective_date))\
                .filter(EmployeeSchedule.employee_id == emp_id)\
                .filter(EmployeeSchedule.effective_date <= eff_date)
            
            actual_eff = sub_q.scalar()
            
            # Reset all
            for v_obj, _ in self.schedule_checkboxes.values():
                v_obj.set(False)
                
            if actual_eff:
                all_at_date = self.session.query(EmployeeSchedule).filter_by(
                    employee_id=emp_id, 
                    effective_date=actual_eff
                ).all()
                assigned_names = {a.schedule.name for a in all_at_date}
                for name, (v_obj, _) in self.schedule_checkboxes.items():
                    v_obj.set(name in assigned_names)
        except Exception as e:
            logger.error(f"Error refreshing checkboxes: {e}")

    def _save_employee_data(self):
        """Validate, save, and return the employee id. Returns None on failure."""
        errors = self._validate()
        if errors:
            Messagebox.show_error("\n".join(errors), tr("validation_error"))
            return None

        data = self._collect_data()

        try:
            if self.mode == "add":
                emp = self.service.add_employee(
                    first_name=data.pop("first_name"),
                    last_name=data.pop("last_name"),
                    email=data.pop("email"),
                    role_title=data.pop("role_title"),
                    department_id=data.pop("department_id"),
                    registry_num=data.pop("registration_number"),
                    **data
                )
                self.employee_id = emp.id
                self.mode = "edit"  # Switch to edit mode after first save
                self._save_schedule_assignment(emp.id)
                return emp.id
            else:
                self.service.update_employee(self.employee_id, **data)
                self._save_schedule_assignment(self.employee_id)
                return self.employee_id
        except Exception as e:
            logger.error(f"Failed to save employee data: {e}")
            Messagebox.show_error(str(e), tr("error"))
            return None

    def _on_save(self):
        """Validate and save (add or update) with enhanced error tracking."""
        try:
            logger.info(f"Initiating save for employee (ID: {self.employee_id}, Mode: {self.mode})")
            emp_id = self._save_employee_data()
            if emp_id is None:
                logger.warning("Save aborted: _save_employee_data returned None.")
                return

            logger.info(f"Save successful for employee {emp_id}. Displaying confirmation.")
            Messagebox.show_info(
                tr("employee_added") if self.mode == "add" else tr("employee_updated"),
                tr("success")
            )

            if self.on_save_callback:
                logger.info("Executing on_save_callback (UI refresh)...")
                try:
                    self.on_save_callback()
                    logger.info("UI refresh callback completed.")
                except Exception as cb_err:
                    logger.error(f"UI refresh callback failed: {cb_err}")
                    import traceback
                    logger.error(traceback.format_exc())

            logger.info("Destroying DataEntryForm.")
            self.destroy()
        except Exception as e:
            logger.error(f"CRITICAL ERROR in _on_save: {e}")
            import traceback
            logger.error(traceback.format_exc())
            Messagebox.show_error(f"Application Error during save: {e}\n\nPlease check logs.", "Critical Error")

    def _on_export(self):
        """Save the employee, then export to all active terminals."""
        emp_id = self._save_employee_data()
        if emp_id is None:
            return

        # Check registration number
        reg = self.reg_num_var.get().strip()
        if not reg:
            Messagebox.show_warning(tr("no_reg_number"), tr("information"))
            return

        # Show in-progress feedback
        self._export_status.configure(text=tr("export_in_progress"), foreground="orange")
        self._export_btn.configure(state="disabled")

        # Trigger background export with callback
        from contragest.features.pointage.sync_bus import sync_bus
        sync_bus.publish_employee_export(
            employee_id=emp_id,
            callback=self._export_callback,
            tk_root=self
        )

    def _export_callback(self, success, message):
        """Callback invoked on main thread after export completes."""
        try:
            self._export_btn.configure(state="normal")
        except Exception:
            return  # Window was closed

        if success:
            parts = message.split("|")
            name = parts[1] if len(parts) > 1 else ""
            count = parts[2] if len(parts) > 2 else "0"
            msg = tr("export_success").replace("{NAME}", name).replace("{COUNT}", count)
            self._export_status.configure(text="✅", foreground="green")
            Messagebox.show_info(msg, tr("success"))
        else:
            parts = message.split("|")
            name = parts[1] if len(parts) > 1 else ""
            error = parts[2] if len(parts) > 2 else message
            msg = tr("export_failed").replace("{NAME}", name).replace("{ERROR}", error)
            self._export_status.configure(text="❌", foreground="red")
            Messagebox.show_error(msg, tr("error"))

        if self.on_save_callback:
            self.on_save_callback()

    # ------------------------------------------------------------------ #
    #  Utilities
    # ------------------------------------------------------------------ #

    def _open_schedules_interface(self):
        """Open the dedicated Master Schedule Manager."""
        from contragest.features.employee_manager.master_schedule_manager import MasterScheduleManager
        dialog = MasterScheduleManager(self.winfo_toplevel())
        self.wait_window(dialog)
        if self.winfo_exists():
            self._refresh_schedule_list_ui()

    def _refresh_schedule_list_ui(self):
        """Reload all schedules from DB and rebuild the checkbox list."""
        # 1. Save current states
        states = {name: var.get() for name, (var, _) in self.schedule_checkboxes.items()}
        
        # 2. Clear old widgets
        for child in self.sched_list_inner.winfo_children():
            child.destroy()
            
        # 3. Reload data
        self.schedule_list = self.session.query(WorkSchedule).order_by(WorkSchedule.name).all()
        
        # 4. Rebuild
        self.schedule_checkboxes = {}
        for s in self.schedule_list:
            v_obj = ttk.BooleanVar(value=states.get(s.name, False))
            cb = ttk.Checkbutton(self.sched_list_inner, text=s.name, variable=v_obj, bootstyle="round-toggle")
            cb.pack(anchor=W, padx=5, pady=2)
            self.schedule_checkboxes[s.name] = (v_obj, s)

    def center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def destroy(self):
        try:
            if hasattr(self, 'session'):
                self.session.close()
        except Exception:
            pass
        super().destroy()
