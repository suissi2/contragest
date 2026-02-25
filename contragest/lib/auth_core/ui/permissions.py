
import tkinter as tk
from tkinter import ttk
from ttkbootstrap.constants import *
from typing import List, Dict, Any

class PermissionMatrixUI(ttk.Frame):
    """
    A matrix of screens vs actions with checkboxes.
    Used to define granular permissions for a role.
    """
    ACTIONS = ['view', 'add', 'edit', 'delete']
    SCREENS = [
        'Dashboard',
        'Employees',
        'Contracts',
        'Reports',
        'Settings',
        'Company',
        'User Management',
        'Mouchard'
    ]

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._vars = {} # (screen, action) -> BooleanVar
        self._create_widgets()

    def _create_widgets(self):
        # Table Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=X, pady=(0, 5))
        
        ttk.Label(header_frame, text="Screens / Modules", font=("Helvetica", 10, "bold"), width=25).pack(side=LEFT, padx=5)
        for action in self.ACTIONS:
            ttk.Label(header_frame, text=action.capitalize(), font=("Helvetica", 10, "bold"), width=10, anchor=CENTER).pack(side=LEFT, padx=5)

        ttk.Separator(self, orient=HORIZONTAL).pack(fill=X, pady=5)

        # Scrollable area for rows
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient=VERTICAL, command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Matrix Rows
        for i, screen in enumerate(self.SCREENS):
            row = ttk.Frame(self.scroll_frame)
            row.pack(fill=X, pady=2)
            
            # Alternate row background for readability
            if i % 2 == 0:
                row.configure(bootstyle=LIGHT)
            
            ttk.Label(row, text=screen, width=25, font=("Helvetica", 10)).pack(side=LEFT, padx=5)
            
            for action in self.ACTIONS:
                var = tk.BooleanVar(value=False)
                self._vars[(screen, action)] = var
                cb = ttk.Checkbutton(row, variable=var, bootstyle="round-toggle")
                cb.pack(side=LEFT, padx=25) # Centered roughly under label

    def get_permissions(self) -> List[Dict[str, Any]]:
        """Returns the matrix state as a list for the service."""
        perms = []
        for screen in self.SCREENS:
            perms.append({
                'screen': screen,
                'can_view': self._vars[(screen, 'view')].get(),
                'can_add': self._vars[(screen, 'add')].get(),
                'can_edit': self._vars[(screen, 'edit')].get(),
                'can_delete': self._vars[(screen, 'delete')].get(),
            })
        return perms

    def set_permissions(self, permissions: List[Any]):
        """Sets the matrix state from a list of Permission models."""
        # Reset first
        for var in self._vars.values():
            var.set(False)
            
        # Map by screen name for easy lookup
        perm_map = {p.screen_name: p for p in permissions}
        
        for screen in self.SCREENS:
            if screen in perm_map:
                p = perm_map[screen]
                self._vars[(screen, 'view')].set(p.can_view)
                self._vars[(screen, 'add')].set(p.can_add)
                self._vars[(screen, 'edit')].set(p.can_edit)
                self._vars[(screen, 'delete')].set(p.can_delete)
