import os
import tkinter as tk
from tkinter import ttk
from ttkbootstrap.dialogs import Messagebox
from typing import Callable, Any
from PIL import Image, ImageTk


class AuthLoginWindow(tk.Frame):
    def __init__(self, master, auth_service: Any, on_success: Callable[[Any], None], title="Login"):
        super().__init__(master)
        self.auth_service = auth_service
        self.on_success = on_success
        self.master = master
        
        # If master is Toplevel or Tk, set title
        if isinstance(master, (tk.Tk, tk.Toplevel)):
            master.title(title)
        
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.logo_img = None # Reference to photoimage

        self._create_widgets()

    def _create_widgets(self):
        # Container
        container = ttk.Frame(self, padding=20)
        container.pack(expand=True, fill='both')

        # Company Logo
        self._load_logo(container)

        # Title
        ttk.Label(container, text="Login", font=("Helvetica", 16, "bold")).pack(pady=10)

        # Username
        ttk.Label(container, text="Username").pack(anchor='w')
        usernames = self.auth_service.get_all_usernames()
        self.username_combo = ttk.Combobox(container, textvariable=self.username_var, values=usernames, state="readonly")
        self.username_combo.pack(fill='x', pady=(0, 10))
        self.username_combo.bind("<Return>", lambda e: self._do_login())
        if usernames:
            self.username_combo.current(0)

        # Password
        ttk.Label(container, text="Password").pack(anchor='w')
        password_entry = ttk.Entry(container, textvariable=self.password_var, show="*")
        password_entry.pack(fill='x', pady=(0, 10))
        password_entry.bind("<Return>", lambda e: self._do_login())
        
        # Auto-focus the password entry
        password_entry.focus_set()

        # Login button
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill='x', pady=10)
        ttk.Button(btn_frame, text="Login", command=self._do_login).pack(fill='x')

        # Action links
        links_frame = ttk.Frame(container)
        links_frame.pack(fill='x', pady=(5, 0))

        forgot_btn = ttk.Button(
            links_frame, text="Forgot Password?",
            command=self._open_password_reset,
            cursor="hand2",
        )
        forgot_btn.pack(side='left', padx=(0, 10))

        activate_btn = ttk.Button(
            links_frame, text="Activate Account",
            command=self._open_activation,
            cursor="hand2",
        )
        activate_btn.pack(side='right')

    def _do_login(self):
        username = self.username_var.get()
        password = self.password_var.get()
        
        if not username or not password:
            Messagebox.show_error("Please enter both username and password.", "Error")
            return

        user, msg = self.auth_service.authenticate_user(username, password)
        if user:
            self.on_success(user)
        else:
            Messagebox.show_error(msg, "Login Failed")

    def _open_password_reset(self):
        from .password_reset import PasswordResetDialog
        PasswordResetDialog(self.winfo_toplevel(), self.auth_service)

    def _open_activation(self):
        from .activation import ActivationDialog
        # Pre-fill username if entered
        username = self.username_var.get().strip()
        ActivationDialog(self.winfo_toplevel(), self.auth_service, prefill_username=username)

    def _load_logo(self, parent):
        from contragest.core.database import SessionLocal, AppConfig
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            if config and config.company_logo_path and os.path.exists(config.company_logo_path):
                img = Image.open(config.company_logo_path)
                img.thumbnail((120, 120)) # Larger for login
                self.logo_img = ImageTk.PhotoImage(img)
                ttk.Label(parent, image=self.logo_img).pack(pady=(0, 15))
        except Exception as e:
            print(f"Error loading logo in LoginUI: {e}")
        finally:
            session.close()
