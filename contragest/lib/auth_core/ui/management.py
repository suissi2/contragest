
import tkinter as tk
from tkinter import ttk, simpledialog
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.constants import *
from typing import Any, Optional, List, Callable
from datetime import datetime
from functools import wraps
from contragest.features.auth.service import AuthService


class UserManagementPanel(tk.Frame):
    """Comprehensive user management panel with search, filter, sort, and full CRUD."""

    # Column configuration: (column_id, heading, width, anchor)
    COLUMNS = [
        ("id",       "ID",        50,  "center"),
        ("username", "Username",  140, "w"),
        ("email",    "Email",     200, "w"),
        ("role",     "Role",      90,  "center"),
        ("status",   "Status",    100, "center"),
        ("auto_login","Auto-Login",90,  "center"),
        ("created",  "Created",   110, "center"),
    ]

    def __init__(self, master, auth_service: Any, current_user: Any):
        super().__init__(master)
        self.auth_service = auth_service
        self.current_user = current_user
        self._all_users: List[Any] = []
        self._sort_col = "username"
        self._sort_reverse = False
        self._filter_mode = "all"  # all, active, inactive, admin

        self._create_widgets()
        self.load_users()

    # ═══════════════════════════════════════════════════════════
    #  Widget Construction
    # ═══════════════════════════════════════════════════════════

    def _create_widgets(self):
        # ── Search & Filter Bar ────────────────────────────────
        search_frame = ttk.Frame(self)
        search_frame.pack(fill="x", padx=5, pady=(5, 2))

        ttk.Label(search_frame, text="🔍").pack(side="left", padx=(0, 4))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        # Role filter dropdown
        ttk.Label(search_frame, text="Role:").pack(side="left", padx=(0, 4))
        self.role_filter_var = tk.StringVar(value="All")
        role_combo = ttk.Combobox(
            search_frame, textvariable=self.role_filter_var,
            values=["All", "admin", "user"],
            state="readonly", width=10,
        )
        role_combo.pack(side="left", padx=(0, 8))
        role_combo.bind("<<ComboboxSelected>>", self._on_filter_changed)

        # Status filter dropdown
        ttk.Label(search_frame, text="Status:").pack(side="left", padx=(0, 4))
        self.status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(
            search_frame, textvariable=self.status_filter_var,
            values=["All", "Active", "Inactive"],
            state="readonly", width=10,
        )
        status_combo.pack(side="left", padx=(0, 8))
        status_combo.bind("<<ComboboxSelected>>", self._on_filter_changed)

        # Refresh button in filter bar
        ttk.Button(search_frame, text="🔄 Refresh", command=self.load_users, bootstyle="info").pack(side="left", padx=(4, 0))

        # ── Action Toolbar ─────────────────────────────────────
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=5, pady=4)

        actions = [
            ("➕ Add User",       self._show_add_user_dialog, "success"),
            ("✏️ Edit Role",      self._show_edit_role_dialog, "primary"),
            ("🛡️ Details",        self._show_permissions_dialog, "info"),
            ("🗑️ Delete",         self._do_delete_user, "danger"),
            ("🔓 Unlock",         self._do_unlock_user, "warning"),
            ("🔑 Reset Pwd",      self._show_reset_password_dialog, "danger"),
            ("⏻ Toggle Status",  self._do_toggle_status, "secondary"),
            ("⚡ Auto-Login",     self._do_toggle_auto_login, "success"),
            ("↻ Refresh",        self.load_users, "info"),
        ]
        for text, cmd, style in actions:
            ttk.Button(toolbar, text=text, command=cmd, bootstyle=style).pack(side="left", padx=2)

        # ── Treeview with Scrollbar ────────────────────────────
        tree_frame = ttk.Frame(self)
        tree_frame.pack(expand=True, fill="both", padx=5, pady=(2, 2))

        col_ids = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings", selectmode="browse")

        for col_id, heading, width, anchor in self.COLUMNS:
            self.tree.heading(col_id, text=heading, command=lambda c=col_id: self._on_heading_click(c))
            self.tree.column(col_id, width=width, anchor=anchor, minwidth=40)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", expand=True, fill="both")
        scrollbar.pack(side="right", fill="y")

        # Row tags for coloring
        self.tree.tag_configure("active",   foreground="#2ecc71")
        self.tree.tag_configure("inactive", foreground="#e74c3c")
        self.tree.tag_configure("admin",    foreground="#3498db")

        # Context menu
        self._context_menu = tk.Menu(self.tree, tearoff=0)
        self._context_menu.add_command(label="✏️ Edit Role",      command=self._show_edit_role_dialog)
        self._context_menu.add_command(label="🛡️ Permission Details", command=self._show_permissions_dialog)
        self._context_menu.add_command(label="⏻ Toggle Status",  command=self._do_toggle_status)
        self._context_menu.add_command(label="⚡ Toggle Auto-Login", command=self._do_toggle_auto_login)
        self._context_menu.add_command(label="🔓 Unlock Account", command=self._do_unlock_user)
        self._context_menu.add_command(label="🔑 Reset Password", command=self._show_reset_password_dialog)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="🗑️ Delete User",    command=self._do_delete_user)

        self.tree.bind("<Button-3>", self._on_right_click)

        # ── Stats Bar ──────────────────────────────────────────
        self.stats_var = tk.StringVar(value="Loading...")
        stats_bar = ttk.Frame(self)
        stats_bar.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Label(stats_bar, textvariable=self.stats_var, font=("Helvetica", 9)).pack(side="left")

    # ═══════════════════════════════════════════════════════════
    #  Data Loading & Display
    # ═══════════════════════════════════════════════════════════

    def load_users(self):
        """Reload all users from backend and refresh display."""
        # Reset all filters
        self.search_var.set("")
        self.role_filter_var.set("All")
        self.status_filter_var.set("All")
        
        self._local_auto_id = self.auth_service.get_local_auto_login_id()
        self._all_users = self.auth_service.get_all_users()
        self._refresh_tree()

    def _refresh_tree(self):
        """Reapply filter, sort, and repopulate the Treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        users = self._apply_filter(self._all_users)
        users = self._apply_sort(users)

        for u in users:
            # Format values
            role_display = "🔵 Admin" if (u.role or "").lower() == "admin" else "User"
            status_display = "✅ Active" if u.is_active else "🔴 Inactive"
            auto_login_display = "⚡ Yes (Local)" if u.id == getattr(self, '_local_auto_id', None) else "No"
            created = ""
            if hasattr(u, "created_at") and u.created_at:
                if isinstance(u.created_at, datetime):
                    created = u.created_at.strftime("%Y-%m-%d")
                else:
                    created = str(u.created_at)[:10]

            # Pick tag
            if (u.role or "").lower() == "admin":
                tag = "admin"
            elif u.is_active:
                tag = "active"
            else:
                tag = "inactive"

            self.tree.insert("", "end", iid=str(u.id), values=(
                u.id, u.username, u.email, role_display, status_display, auto_login_display, created,
            ), tags=(tag,))

        self._update_stats(users)

    def _apply_filter(self, users: list) -> list:
        filtered = users
        
        # Apply Role filter
        role_mode = self.role_filter_var.get()
        if role_mode != "All":
            filtered = [u for u in filtered if (u.role or "").lower() == role_mode.lower()]
        
        # Apply Status filter
        status_mode = self.status_filter_var.get()
        if status_mode == "Active":
            filtered = [u for u in filtered if u.is_active]
        elif status_mode == "Inactive":
            filtered = [u for u in filtered if not u.is_active]
        
        return filtered

    def _apply_sort(self, users: list) -> list:
        key_map = {
            "id":       lambda u: u.id or 0,
            "username": lambda u: (u.username or "").lower(),
            "email":    lambda u: (u.email or "").lower(),
            "role":     lambda u: (u.role or "").lower(),
            "status":   lambda u: (1 if u.is_active else 0),
            "created":  lambda u: (u.created_at or datetime.min),
        }
        key = key_map.get(self._sort_col, key_map["username"])
        try:
            return sorted(users, key=key, reverse=self._sort_reverse)
        except Exception:
            return users

    def _update_stats(self, displayed_users: list):
        total = len(self._all_users)
        active = sum(1 for u in self._all_users if u.is_active)
        inactive = total - active
        shown = len(displayed_users)
        filter_text = f" (showing {shown})" if shown != total else ""
        self.stats_var.set(f"{total} users total  •  {active} active  •  {inactive} inactive{filter_text}")

    # ═══════════════════════════════════════════════════════════
    #  Event Handlers
    # ═══════════════════════════════════════════════════════════

    def _on_search_changed(self, *_args):
        self.load_users()

    def _on_filter_changed(self, _event=None):
        self._refresh_tree()

    def _on_heading_click(self, col_id: str):
        if self._sort_col == col_id:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col_id
            self._sort_reverse = False

        # Update heading indicators
        for cid, heading, _, _ in self.COLUMNS:
            suffix = ""
            if cid == col_id:
                suffix = " ▼" if self._sort_reverse else " ▲"
            self.tree.heading(cid, text=heading + suffix)

        self._refresh_tree()

    def _on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self._context_menu.tk_popup(event.x_root, event.y_root)

    # ═══════════════════════════════════════════════════════════
    #  Selected User Helper
    # ═══════════════════════════════════════════════════════════

    def _get_selected(self) -> Optional[tuple]:
        """Return (user_id, username) of selected row, or None."""
        sel = self.tree.selection()
        if not sel:
            Messagebox.show_warning("No Selection", "Please select a user first.", parent=self.winfo_toplevel())
            return None
        item = self.tree.item(sel[0])
        vals = item["values"]
        return int(vals[0]), str(vals[1])

    # ═══════════════════════════════════════════════════════════
    #  Actions
    # ═══════════════════════════════════════════════════════════

    @AuthService.require_permission('User Management', 'edit')
    def _do_toggle_status(self):
        sel = self._get_selected()
        if not sel:
            return
        user_id, username = sel

        # Get current status from tree
        item = self.tree.item(self.tree.selection()[0])
        status_text = str(item["values"][4]).lower()
        current_active = "inactive" not in status_text and "active" in status_text

        if current_active:
            if not Messagebox.yesno(
                "Confirm Deactivation",
                f"Deactivate account '{username}'?\nThey will not be able to log in.",
                parent=self.winfo_toplevel(),
            ):
                return

        new_status = not current_active
        success, msg = self.auth_service.activate_account_direct(user_id, new_status, self.current_user.id)
        if success:
            self.load_users()
        else:
            Messagebox.show_error("Error", msg, parent=self.winfo_toplevel())

    @AuthService.require_permission('User Management', 'edit')
    def _do_toggle_auto_login(self):
        sel = self._get_selected()
        if not sel:
            return
        user_id, username = sel

        success, msg = self.auth_service.toggle_auto_login(user_id, self.current_user.id)
        if success:
            self.load_users()
            Messagebox.show_info("Success", msg, parent=self.winfo_toplevel())
        else:
            Messagebox.show_error("Error", msg, parent=self.winfo_toplevel())

    @AuthService.require_permission('User Management', 'delete')
    def _do_delete_user(self):
        sel = self._get_selected()
        if not sel:
            return
        user_id, username = sel

        if not Messagebox.yesno(
            "Confirm Deletion",
            f"Permanently delete user '{username}'?\nThis action cannot be undone.",
            icon="warning",
            parent=self.winfo_toplevel(),
        ):
            return

        success, msg = self.auth_service.delete_user(user_id, self.current_user.id)
        if success:
            self.load_users()
            Messagebox.show_info("Deleted", msg, parent=self.winfo_toplevel())
        else:
            Messagebox.show_error("Error", msg, parent=self.winfo_toplevel())

    @AuthService.require_permission('User Management', 'edit')
    def _do_unlock_user(self):
        sel = self._get_selected()
        if not sel:
            return
        user_id, username = sel

        success, msg = self.auth_service.unlock_user(user_id, self.current_user.id)
        if success:
            self.load_users()
            Messagebox.show_info("Unlocked", msg, parent=self.winfo_toplevel())
        else:
            Messagebox.show_info("Info", msg, parent=self.winfo_toplevel())

    # ═══════════════════════════════════════════════════════════
    #  Dialog: Add User
    # ═══════════════════════════════════════════════════════════

    @AuthService.require_permission('User Management', 'add')
    def _show_add_user_dialog(self):
        dlg = tk.Toplevel(self.winfo_toplevel())
        dlg.title("Add New User")
        dlg.resizable(False, False)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        container = ttk.Frame(dlg, padding=20)
        container.pack(expand=True, fill="both")

        ttk.Label(container, text="➕ Add New User", font=("Helvetica", 13, "bold")).pack(pady=(0, 10))

        feedback_var = tk.StringVar()
        feedback_label = ttk.Label(container, textvariable=feedback_var, wraplength=340)
        feedback_label.pack(pady=(0, 6))

        fields = {}
        for label_text in ["Username", "Email", "Password", "Confirm Password"]:
            ttk.Label(container, text=label_text).pack(anchor="w")
            var = tk.StringVar()
            show = "*" if "Password" in label_text else ""
            ttk.Entry(container, textvariable=var, show=show).pack(fill="x", pady=(0, 6))
            fields[label_text] = var

        # Role selector
        ttk.Label(container, text="Role").pack(anchor="w")
        role_var = tk.StringVar(value="user")
        role_frame = ttk.Frame(container)
        role_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(role_frame, text="User", variable=role_var, value="user").pack(side="left", padx=(0, 15))
        ttk.Radiobutton(role_frame, text="Admin", variable=role_var, value="admin").pack(side="left")

        # Password strength
        strength_label = ttk.Label(container, text="", font=("Helvetica", 9))
        strength_label.pack(anchor="w")

        def update_strength(*_):
            pwd = fields["Password"].get()
            if not pwd:
                strength_label.configure(text="")
                return
            score = sum([
                len(pwd) >= 8,
                any(c.isupper() for c in pwd),
                any(c.islower() for c in pwd),
                any(c.isdigit() for c in pwd),
                len(pwd) >= 12,
            ])
            labels = {0: ("Very weak", "#e74c3c"), 1: ("Weak", "#e67e22"), 2: ("Fair", "#f1c40f"),
                      3: ("Good", "#27ae60"), 4: ("Strong", "#2ecc71"), 5: ("Very strong", "#1abc9c")}
            text, color = labels.get(score, ("", "#888"))
            bar = "█" * score + "░" * (5 - score)
            strength_label.configure(text=f"{bar}  {text}", foreground=color)

        fields["Password"].trace_add("write", update_strength)

        def do_add():
            username = fields["Username"].get().strip()
            email = fields["Email"].get().strip()
            pwd = fields["Password"].get()
            confirm = fields["Confirm Password"].get()

            if not all([username, email, pwd, confirm]):
                feedback_var.set("All fields are required.")
                feedback_label.configure(foreground="#e74c3c")
                return
            if pwd != confirm:
                feedback_var.set("Passwords do not match.")
                feedback_label.configure(foreground="#e74c3c")
                return

            try:
                user = self.auth_service.register_user(username, email, pwd)
                # If admin selected a different role
                if role_var.get() != user.role:
                    self.auth_service.update_user_role(user.id, role_var.get(), self.current_user.id)
                Messagebox.show_info("Success", f"User '{username}' created.\nActivation email sent.", parent=dlg)
                dlg.destroy()
                self.load_users()
            except ValueError as e:
                feedback_var.set(str(e))
                feedback_label.configure(foreground="#e74c3c")
            except Exception as e:
                feedback_var.set(f"Error: {e}")
                feedback_label.configure(foreground="#e74c3c")

        ttk.Button(container, text="Create User", command=do_add).pack(fill="x", pady=(8, 0))

        # Center dialog
        dlg.update_idletasks()
        w, h = 380, 480
        x = (dlg.winfo_screenwidth() // 2) - (w // 2)
        y = (dlg.winfo_screenheight() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    # ═══════════════════════════════════════════════════════════
    #  Dialog: Edit Role
    # ═══════════════════════════════════════════════════════════

    @AuthService.require_permission('User Management', 'edit')
    def _show_edit_role_dialog(self):
        sel = self._get_selected()
        if not sel:
            return
        user_id, username = sel

        # Get current role from tree
        item = self.tree.item(self.tree.selection()[0])
        current_role = "admin" if "admin" in str(item["values"][3]).lower() else "user"

        dlg = tk.Toplevel(self.winfo_toplevel())
        dlg.title("Edit Role")
        dlg.resizable(False, False)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        container = ttk.Frame(dlg, padding=20)
        container.pack(expand=True, fill="both")

        ttk.Label(container, text="✏️ Edit Role", font=("Helvetica", 13, "bold")).pack(pady=(0, 10))
        ttk.Label(container, text=f"User: {username}", font=("Helvetica", 11)).pack(pady=(0, 8))
        ttk.Label(container, text=f"Current role: {current_role}").pack(pady=(0, 10))

        role_var = tk.StringVar(value=current_role)
        role_frame = ttk.Frame(container)
        role_frame.pack(fill="x", pady=(0, 12))
        ttk.Radiobutton(role_frame, text="User", variable=role_var, value="user").pack(side="left", padx=(0, 20))
        ttk.Radiobutton(role_frame, text="Admin", variable=role_var, value="admin").pack(side="left")

        def do_save():
            new_role = role_var.get()
            if new_role == current_role:
                dlg.destroy()
                return
            success, msg = self.auth_service.update_user_role(user_id, new_role, self.current_user.id)
            if success:
                dlg.destroy()
                self.load_users()
                Messagebox.show_info("Success", msg, parent=self.winfo_toplevel())
            else:
                Messagebox.show_error("Error", msg, parent=dlg)

        ttk.Button(container, text="Save", command=do_save).pack(fill="x")

        dlg.update_idletasks()
        w, h = 300, 230
        x = (dlg.winfo_screenwidth() // 2) - (w // 2)
        y = (dlg.winfo_screenheight() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    # ═══════════════════════════════════════════════════════════
    #  Dialog: Admin Reset Password
    # ═══════════════════════════════════════════════════════════

    @AuthService.require_permission('User Management', 'edit')
    def _show_reset_password_dialog(self):
        sel = self._get_selected()
        if not sel:
            return
        user_id, username = sel

        dlg = tk.Toplevel(self.winfo_toplevel())
        dlg.title("Reset Password")
        dlg.resizable(False, False)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        container = ttk.Frame(dlg, padding=20)
        container.pack(expand=True, fill="both")

        ttk.Label(container, text="🔑 Reset Password", font=("Helvetica", 13, "bold")).pack(pady=(0, 8))
        ttk.Label(container, text=f"User: {username}", font=("Helvetica", 11)).pack(pady=(0, 4))

        ttk.Label(
            container,
            text="⚠️ The user will need to use the new password to log in.",
            wraplength=320, foreground="#e67e22",
        ).pack(pady=(0, 10))

        feedback_var = tk.StringVar()
        feedback_label = ttk.Label(container, textvariable=feedback_var, wraplength=320)
        feedback_label.pack(pady=(0, 6))

        ttk.Label(container, text="New Password").pack(anchor="w")
        pwd_var = tk.StringVar()
        ttk.Entry(container, textvariable=pwd_var, show="*").pack(fill="x", pady=(0, 6))

        ttk.Label(container, text="Confirm Password").pack(anchor="w")
        confirm_var = tk.StringVar()
        ttk.Entry(container, textvariable=confirm_var, show="*").pack(fill="x", pady=(0, 6))

        # Strength
        strength_label = ttk.Label(container, text="", font=("Helvetica", 9))
        strength_label.pack(anchor="w", pady=(0, 6))

        def update_strength(*_):
            pwd = pwd_var.get()
            if not pwd:
                strength_label.configure(text="")
                return
            score = sum([
                len(pwd) >= 8,
                any(c.isupper() for c in pwd),
                any(c.islower() for c in pwd),
                any(c.isdigit() for c in pwd),
                len(pwd) >= 12,
            ])
            labels = {0: ("Very weak", "#e74c3c"), 1: ("Weak", "#e67e22"), 2: ("Fair", "#f1c40f"),
                      3: ("Good", "#27ae60"), 4: ("Strong", "#2ecc71"), 5: ("Very strong", "#1abc9c")}
            text, color = labels.get(score, ("", "#888"))
            bar = "█" * score + "░" * (5 - score)
            strength_label.configure(text=f"{bar}  {text}", foreground=color)

        pwd_var.trace_add("write", update_strength)

        def do_reset():
            pwd = pwd_var.get()
            confirm = confirm_var.get()
            if not pwd:
                feedback_var.set("Password is required.")
                feedback_label.configure(foreground="#e74c3c")
                return
            if pwd != confirm:
                feedback_var.set("Passwords do not match.")
                feedback_label.configure(foreground="#e74c3c")
                return

            if not Messagebox.yesno(
                "Confirm Reset",
                f"Reset password for '{username}'?",
                parent=dlg,
            ):
                return

            success, msg = self.auth_service.admin_reset_password(user_id, pwd, self.current_user.id)
            if success:
                dlg.destroy()
                Messagebox.show_info("Success", msg, parent=self.winfo_toplevel())
            else:
                feedback_var.set(msg)
                feedback_label.configure(foreground="#e74c3c")

        ttk.Button(container, text="Reset Password", command=do_reset).pack(fill="x", pady=(4, 0))

        dlg.update_idletasks()
        w, h = 380, 380
        x = (dlg.winfo_screenwidth() // 2) - (w // 2)
        y = (dlg.winfo_screenheight() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    # ═══════════════════════════════════════════════════════════
    #  Dialog: Permission Matrix
    # ═══════════════════════════════════════════════════════════

    @AuthService.require_permission('User Management', 'edit')
    def _show_permissions_dialog(self):
        sel = self._get_selected()
        if not sel:
            return
        user_id, username = sel

        # Get the role_id from the object if possible, or use simple lookup
        # For simplicity in this reusable UI, we'll fetch roles from service
        roles = self.auth_service.get_roles()
        
        # Determine the user's role_name from the tree
        item = self.tree.item(self.tree.selection()[0])
        role_display = str(item["values"][3]).replace("🔵 ", "")
        
        role_obj = next((r for r in roles if r.name.lower() == role_display.lower()), None)
        if not role_obj:
            Messagebox.show_error("Error", "Role object not found in database.", parent=self.winfo_toplevel())
            return

        dlg = tk.Toplevel(self.winfo_toplevel())
        dlg.title(f"Permissions: {role_obj.name}")
        dlg.geometry("700x600")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        container = ttk.Frame(dlg, padding=10)
        container.pack(fill=BOTH, expand=YES)

        ttk.Label(container, text=f"🛡️ Granular Permissions for Role: {role_obj.name}", font=("Helvetica", 12, "bold")).pack(pady=10)
        
        from .permissions import PermissionMatrixUI
        matrix = PermissionMatrixUI(container)
        matrix.pack(fill=BOTH, expand=YES, pady=5)
        
        # Load existing permissions
        matrix.set_permissions(role_obj.permissions)

        def do_save():
            new_perms = matrix.get_permissions()
            success, msg = self.auth_service.update_role_permissions(role_obj.id, new_perms, self.current_user.id)
            if success:
                Messagebox.show_info("Success", "Permissions updated successfully.", parent=dlg)
                dlg.destroy()
            else:
                Messagebox.show_error("Error", msg, parent=dlg)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=X, pady=10)
        ttk.Button(btn_frame, text="Save Permissions", command=do_save, bootstyle=SUCCESS).pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy, bootstyle=SECONDARY).pack(side=RIGHT, padx=5)

        # Center dialog
        dlg.update_idletasks()
        w, h = 700, 600
        x = (dlg.winfo_screenwidth() // 2) - (w // 2)
        y = (dlg.winfo_screenheight() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
