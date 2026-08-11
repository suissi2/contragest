"""
Department Manager Dialog - CRUD management of organizational departments.

Displays a hierarchical Treeview of departments and provides add, rename,
and delete operations with relational integrity safety checks.
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox, Querybox
from contragest.core.database import SessionLocal
from contragest.features.employee_manager.service import EmployeeService
from contragest.core.i18n import tr


class DepartmentManagerDialog(ttk.Toplevel):
    """Small dialog for managing the department hierarchy."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title(tr("department_manager"))
        self.geometry("500x620")
        self.resizable(False, False)
        self.grab_set()

        self.session = SessionLocal()
        self.service = EmployeeService(self.session)
        self.selected_dept_id = None
        self._pointage_machines = {}   # display_name -> machine_id

        self._build_ui()
        self._refresh_tree()
        self._refresh_machine_combo()
        self.center_window()

    # ------------------------------------------------------------------ #
    #  UI
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # Header
        header = ttk.Frame(self, bootstyle="info")
        header.pack(fill=X)
        ttk.Label(
            header, text=f"  🏢  {tr('department_manager')}",
            font=("Helvetica", 13, "bold"),
            bootstyle="inverse-info", padding=(15, 8)
        ).pack(side=LEFT)

        # ── Machine Import Panel ──────────────────────────────────────────
        machine_frame = ttk.LabelFrame(self, text=f"🖥️ {tr('import_to_machine')}")
        machine_frame.pack(fill=X, padx=10, pady=(8, 0))

        ttk.Label(machine_frame, text=f"{tr('machine_name')}:", font=("Helvetica", 10)).pack(side=LEFT, padx=(0, 6))

        self._machine_var = ttk.StringVar()
        self._machine_combo = ttk.Combobox(
            machine_frame, textvariable=self._machine_var,
            width=28, state="readonly"
        )
        self._machine_combo.pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            machine_frame, text="🔄", bootstyle=INFO, width=3,
            command=self._refresh_machine_combo
        ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            machine_frame,
            text=f"🔃 {tr('import_depts_to_machine')}",
            bootstyle=SUCCESS,
            command=self._import_to_machine
        ).pack(side=LEFT)

        # Treeview
        tree_frame = ttk.Frame(self, padding=10)
        tree_frame.pack(fill=BOTH, expand=YES)

        self.tree = ttk.Treeview(tree_frame, selectmode="browse", show="tree headings")
        self.tree["columns"] = ("employees",)
        self.tree.heading("#0", text=tr("department"), anchor=W)
        self.tree.heading("employees", text=tr("employees_count"), anchor=CENTER)
        self.tree.column("#0", width=300, anchor=W)
        self.tree.column("employees", width=120, anchor=CENTER)

        scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Action buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=X)

        ttk.Button(
            btn_frame, text=f"➕ {tr('add_department')}",
            bootstyle="success", command=self._add_department
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame, text=f"✏️ {tr('rename_department')}",
            bootstyle="warning", command=self._rename_department
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame, text=f"🗑️ {tr('delete_department')}",
            bootstyle="danger", command=self._delete_department
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame, text=f"❌ {tr('close')}",
            bootstyle="secondary-outline", command=self.destroy
        ).pack(side=RIGHT, padx=5)

    # ------------------------------------------------------------------ #
    #  Machine combo helpers
    # ------------------------------------------------------------------ #

    def _refresh_machine_combo(self):
        """Populate the machine combobox from the pointage service."""
        try:
            from contragest.features.pointage.service import PointageService
            svc = PointageService(self.session)
            machines = svc.get_all_machines()
            self._pointage_machines = {
                f"{m.name} ({m.ip_address})": m.id for m in machines
            }
            self._machine_combo["values"] = list(self._pointage_machines.keys())
            if self._pointage_machines:
                self._machine_combo.current(0)
        except Exception:
            self._pointage_machines = {}

    def _get_selected_machine_id(self):
        key = self._machine_var.get()
        return self._pointage_machines.get(key)

    # ------------------------------------------------------------------ #
    #  Import to machine
    # ------------------------------------------------------------------ #

    def _import_to_machine(self):
        """Push all departments to the selected pointage machine."""
        mid = self._get_selected_machine_id()
        if not mid:
            Messagebox.show_warning(tr("select_machine_first"), tr("information"))
            return

        try:
            from contragest.features.pointage.service import PointageService
            svc = PointageService(self.session)
            synced, failed = svc.push_all_departments_to_machine(mid)
            msg = tr("dept_sync_saved").replace("{count}", str(synced))
            if failed:
                msg += f"\n({failed} {tr('error').lower()}s)"
            Messagebox.show_info(msg, tr("success"))
        except Exception as e:
            Messagebox.show_error(
                tr("import_machine_failed").replace("{error}", str(e)),
                tr("error")
            )

    # ------------------------------------------------------------------ #
    #  Data loading
    # ------------------------------------------------------------------ #

    def _refresh_tree(self):
        """Reload the entire department tree from the database."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        top_depts = self.service.get_department_hierarchy()
        for dept in top_depts:
            self._insert_dept_node("", dept)

    def _insert_dept_node(self, parent_iid, dept):
        """Recursively insert a department and its children into the treeview."""
        emp_count = len(dept.employees) if dept.employees else 0
        iid = self.tree.insert(
            parent_iid, "end",
            text=f"  📁  {dept.name}",
            values=(emp_count,),
            tags=(str(dept.id),)
        )
        if dept.children:
            for child in dept.children:
                self._insert_dept_node(iid, child)

    # ------------------------------------------------------------------ #
    #  Selection
    # ------------------------------------------------------------------ #

    def _on_select(self, event):
        selection = self.tree.selection()
        if selection:
            tags = self.tree.item(selection[0], "tags")
            self.selected_dept_id = int(tags[0]) if tags else None
        else:
            self.selected_dept_id = None

    def _get_selected_name(self):
        selection = self.tree.selection()
        if selection:
            return self.tree.item(selection[0], "text").strip().replace("📁", "").strip()
        return None

    # ------------------------------------------------------------------ #
    #  CRUD operations
    # ------------------------------------------------------------------ #

    def _add_department(self):
        """Add a new department, optionally as a child of the selected one."""
        name = Querybox.get_string(
            prompt=tr("enter_department_name"),
            title=tr("add_department")
        )
        if not name or not name.strip():
            return

        name = name.strip() # Added .strip() here
        parent_id = self.selected_dept_id  # None if nothing selected → top-level
        try:
            self.service.create_department(name, parent_id)
            self._refresh_tree()
            Messagebox.show_info(
                tr("department_added", name=name),
                tr("success")
            )
        except Exception as e:
            Messagebox.show_error(str(e), tr("error"))

    def _rename_department(self):
        """Rename the currently selected department."""
        if not self.selected_dept_id:
            Messagebox.show_warning(tr("select_department_first"), tr("no_selection"))
            return

        current_name = self._get_selected_name()
        new_name = Querybox.get_string(
            prompt=tr("enter_new_name"),
            title=tr("rename_department"),
            initialvalue=current_name
        )
        if not new_name or not new_name.strip():
            return

        try:
            dept = self.session.query(
                __import__('contragest.core.database', fromlist=['Department']).Department
            ).get(self.selected_dept_id)
            if dept:
                self.service.update_department(self.selected_dept_id, new_name.strip(), dept.parent_id)
                self._refresh_tree()
                Messagebox.show_info(
                    tr("department_renamed", old=current_name, new=new_name.strip()),
                    tr("success")
                )
        except Exception as e:
            Messagebox.show_error(str(e), tr("error"))

    def _delete_department(self):
        """Delete the currently selected department with safety checks."""
        if not self.selected_dept_id:
            Messagebox.show_warning(tr("select_department_first"), tr("no_selection"))
            return

        dept_name = self._get_selected_name()
        confirm = Messagebox.okcancel(
            tr("confirm_delete_department", name=dept_name),
            tr("confirmation")
        )
        if not confirm:
            return

        try:
            self.service.delete_department(self.selected_dept_id)
            self._refresh_tree()
            self.selected_dept_id = None
            Messagebox.show_info(
                tr("department_deleted", name=dept_name),
                tr("success")
            )
        except ValueError as e:
            Messagebox.show_error(str(e), tr("error"))
        except Exception as e:
            Messagebox.show_error(str(e), tr("error"))

    # ------------------------------------------------------------------ #
    #  Utilities
    # ------------------------------------------------------------------ #

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
