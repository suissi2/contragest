"""
Employee Archive Panel - Displays archived employees with reinstate / permanent-delete actions.
This panel is password-gated before opening (same daily formula as contract deletion).
"""
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox, Querybox
from ttkbootstrap.tableview import Tableview
from contragest.core.database import SessionLocal
from contragest.features.employee_manager.service import EmployeeService
from datetime import datetime


from contragest.core.gui_utils import calculate_daily_password


class EmployeeArchivePanel(ttk.Toplevel):
    """Password-protected panel for viewing and managing archived employees."""

    def __init__(self, parent, on_reinstate_callback=None):
        super().__init__(parent)
        self.title("🗂️ Employee Archive")
        self.geometry("1100x600")
        self.on_reinstate_callback = on_reinstate_callback

        self.session = SessionLocal()
        self.service = EmployeeService(self.session)

        # Internal cache: {archive table row id → employee db id}
        self._emp_id_map: dict[str, int] = {}

        self._build_ui()
        self._load_archived_employees()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────
        header = ttk.Frame(self, bootstyle="warning")
        header.pack(fill=X)
        ttk.Label(
            header,
            text="🗂️   EMPLOYEE ARCHIVE",
            font=("Helvetica", 13, "bold"),
            bootstyle="inverse-warning"
        ).pack(side=LEFT, padx=15, pady=8)
        ttk.Label(
            header,
            text="Archived employees are hidden from all active views but their data is preserved.",
            font=("Helvetica", 9, "italic"),
            bootstyle="inverse-warning"
        ).pack(side=LEFT, padx=5, pady=8)

        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = ttk.Frame(self, bootstyle="light")
        toolbar.pack(fill=X, padx=10, pady=6)

        ttk.Button(
            toolbar, text="♻️  Reinstate Employee",
            bootstyle="success", command=self._reinstate_selected
        ).pack(side=LEFT, padx=4, ipady=3)

        ttk.Button(
            toolbar, text="🗑️  Delete Permanently",
            bootstyle="danger-outline", command=self._hard_delete_selected
        ).pack(side=LEFT, padx=4, ipady=3)

        ttk.Button(
            toolbar, text="🔄  Refresh",
            bootstyle="secondary-outline", command=self._load_archived_employees
        ).pack(side=LEFT, padx=4, ipady=3)

        ttk.Button(
            toolbar, text="✖  Close",
            bootstyle="secondary", command=self.destroy
        ).pack(side=RIGHT, padx=4, ipady=3)

        # ── Table container ───────────────────────────────────────────────
        self._table_frame = ttk.Frame(self)
        self._table_frame.pack(fill=BOTH, expand=YES, padx=10, pady=(0, 10))

    def _load_archived_employees(self):
        """Fetch archived employees and populate the table."""
        for widget in self._table_frame.winfo_children():
            widget.destroy()
        self._emp_id_map.clear()

        employees = self.service.get_all_archived_employees()
        self._employees_cache = employees

        cols = [
            {"text": "REG NUMBER", "stretch": True},
            {"text": "LAST NAME", "stretch": True},
            {"text": "FIRST NAME", "stretch": True},
            {"text": "DEPARTMENT", "stretch": True},
            {"text": "ROLE", "stretch": True},
            {"text": "ARCHIVED ON", "stretch": True},
            {"text": "REASON", "stretch": True}
        ]
        
        rows = []
        for emp in employees:
            dept = emp.dept_obj.name if emp.dept_obj else (emp.department or "-")
            archived_on = emp.archived_at.strftime("%Y-%m-%d") if emp.archived_at else "-"
            rows.append((
                emp.registration_number or "-",
                emp.last_name,
                emp.first_name,
                dept,
                emp.role_title or "-",
                archived_on,
                emp.archive_reason or "-",
            ))

        self._table = Tableview(
            master=self._table_frame,
            coldata=cols,
            rowdata=rows,
            paginated=True,
            pagesize=20,
            searchable=True,
            bootstyle=WARNING,
            autofit=True,
        )
        # Enable multi-selection (Ctrl/Shift+Click)
        self._table.view.configure(selectmode="extended")
        self._table.pack(fill=BOTH, expand=YES)

        # Build a robust lookup map: (RegNumber, LastName, FirstName) -> DB ID
        self._lookup_map = {}
        for emp in employees:
            key = (
                str(emp.registration_number or "-").strip(),
                str(emp.last_name or "").strip().upper(),
                str(emp.first_name or "").strip().upper()
            )
            self._lookup_map[key] = emp.id

    def _get_selected_employee_ids(self) -> List[int]:
        """Resolves the selected employees' DB IDs from the current Tableview selection."""
        selection = self._table.view.selection()
        if not selection:
            Messagebox.show_warning("Please select at least one employee from the list.", "No Selection")
            return []

        emp_ids = []
        for iid in selection:
            values = self._table.view.item(iid).get("values", [])
            if not values or len(values) < 3:
                continue

            # Extract Reg#, Last, First from table values
            key = (
                str(values[0]).strip(),         # REG NUMBER
                str(values[1]).strip().upper(), # LAST NAME
                str(values[2]).strip().upper()  # FIRST NAME
            )
            eid = self._lookup_map.get(key)
            if eid:
                emp_ids.append(eid)
        
        return emp_ids

    def _reinstate_selected(self):
        """Reinstate selected archived employees back to active status."""
        emp_ids = self._get_selected_employee_ids()
        if not emp_ids:
            return

        count = len(emp_ids)
        if count == 1:
            emp = self.session.query(__import__(
                'contragest.core.database', fromlist=['Employee']
            ).Employee).get(emp_ids[0])
            name = f"'{emp.last_name} {emp.first_name}'" if emp else f"ID {emp_ids[0]}"
        else:
            name = f"{count} selected employees"

        ans = Messagebox.show_question(
            f"Reinstate {name}?\n\n"
            "They will reappear in all active employee lists.",
            "Confirm Reinstatement",
            buttons=["No:secondary", "Yes:success"]
        )
        if ans != "Yes":
            return

        if self.service.bulk_reinstate_employees(emp_ids):
            Messagebox.show_info(
                f"✅ {name} {'has' if count==1 else 'have'} been reinstated successfully.",
                "Reinstated"
            )
            self._load_archived_employees()
            if self.on_reinstate_callback:
                self.on_reinstate_callback()
        else:
            Messagebox.show_error("Could not reinstate employees. Please try again.", "Error")

    def _hard_delete_selected(self):
        """Permanently and irreversibly delete the selected archived employees."""
        emp_ids = self._get_selected_employee_ids()
        if not emp_ids:
            return

        count = len(emp_ids)
        if count == 1:
            emp = self.session.query(__import__(
                'contragest.core.database', fromlist=['Employee']
            ).Employee).get(emp_ids[0])
            name = f"'{emp.last_name} {emp.first_name}'" if emp else f"ID {emp_ids[0]}"
        else:
            name = f"{count} selected employees"

        # Double confirm
        ans = Messagebox.show_question(
            f"⚠️  PERMANENTLY DELETE {name}?\n\n"
            "This action is IRREVERSIBLE. All associated contracts and\n"
            "attendance records will also be deleted.",
            "Confirm Permanent Deletion",
            buttons=["Cancel:secondary", "Delete:danger"]
        )
        if ans != "Delete":
            return

        # Password gate
        correct_pwd = calculate_daily_password()
        pwd_input = Querybox.get_string(
            prompt="Enter today's deletion password to confirm:",
            title="🔐 Password Required",
            parent=self,
            initialvalue=""
        )
        if pwd_input is None:
            return
        if pwd_input != correct_pwd:
            Messagebox.show_error("Incorrect password. Deletion aborted.", "Authentication Failed")
            return

        try:
            success_count = 0
            for eid in emp_ids:
                self.service.delete_employee(eid)
                success_count += 1
            
            Messagebox.show_info(
                f"🗑️  {success_count} employees have been permanently deleted.",
                "Deleted"
            )
            self._load_archived_employees()
            if self.on_reinstate_callback:
                self.on_reinstate_callback()
        except Exception as e:
            self.session.rollback()
            Messagebox.show_error(f"Deletion failed: {e}", "Error")

    def destroy(self):
        try:
            if hasattr(self, "session"):
                self.session.close()
        except Exception:
            pass
        super().destroy()
