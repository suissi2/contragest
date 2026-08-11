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
        # We assume self is embedded inside AuthApp which fills the window.
        self.configure(bg="#06021A") # Deep AI Violet bg
        
        # Center container
        container = tk.Frame(self, bg="#1A0A3A", padx=40, pady=40, 
                             highlightbackground="#4B1D8C", highlightthickness=2)
        container.place(relx=0.5, rely=0.5, anchor="center", width=420)
        
        # Logo
        self._load_logo(container)
        
        # Title
        tk.Label(container, text="SYSTEM LOGIN", font=("Inter", 14, "bold"), 
                 bg="#1A0A3A", fg="#E8E6FF").pack(pady=(0, 25))
                 
        # Username
        tk.Label(container, text="USERNAME", font=("Inter", 9, "bold"), 
                 bg="#1A0A3A", fg="#8B82B5").pack(anchor='w', pady=(0, 5))
        
        usernames = self.auth_service.get_all_usernames()
        self.username_combo = ttk.Combobox(container, textvariable=self.username_var, values=usernames, state="normal", font=("Inter", 11))
        self.username_combo.pack(fill='x', pady=(0, 20))
        self.username_combo.bind("<Return>", lambda e: self._do_login())
        if usernames:
            self.username_combo.current(0)
            
        # Password
        tk.Label(container, text="PASSWORD", font=("Inter", 9, "bold"), 
                 bg="#1A0A3A", fg="#8B82B5").pack(anchor='w', pady=(0, 5))
                 
        password_entry = ttk.Entry(container, textvariable=self.password_var, show="•", font=("Inter", 11))
        password_entry.pack(fill='x', pady=(0, 30))
        password_entry.bind("<Return>", lambda e: self._do_login())
        password_entry.focus_set()
        
        # Login Button
        btn_login = tk.Button(container, text="SECURE ACCESS", font=("Inter", 10, "bold"),
                              bg="#06B6D4", fg="#FFFFFF", activebackground="#D946EF", 
                              activeforeground="#FFFFFF", bd=0, cursor="hand2",
                              command=self._do_login, pady=10)
        btn_login.pack(fill='x', pady=(0, 20))
        
        # Links
        links_frame = tk.Frame(container, bg="#1A0A3A")
        links_frame.pack(fill='x')
        
        lbl_forgot = tk.Label(links_frame, text="Forgot Password?", font=("Inter", 9), 
                              bg="#1A0A3A", fg="#8B82B5", cursor="hand2")
        lbl_forgot.pack(side="left")
        lbl_forgot.bind("<Button-1>", lambda e: self._open_password_reset())
        lbl_forgot.bind("<Enter>", lambda e: lbl_forgot.config(fg="#06B6D4"))
        lbl_forgot.bind("<Leave>", lambda e: lbl_forgot.config(fg="#8B82B5"))
        
        lbl_activate = tk.Label(links_frame, text="Activate Account", font=("Inter", 9), 
                                bg="#1A0A3A", fg="#8B82B5", cursor="hand2")
        lbl_activate.pack(side="right")
        lbl_activate.bind("<Button-1>", lambda e: self._open_activation())
        lbl_activate.bind("<Enter>", lambda e: lbl_activate.config(fg="#D946EF"))
        lbl_activate.bind("<Leave>", lambda e: lbl_activate.config(fg="#8B82B5"))

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
                
                # Dark Mode Optimization: Try to convert dark logos or just resize
                img.thumbnail((140, 140)) # Slightly larger for premium centered look
                self.logo_img = ImageTk.PhotoImage(img)
                ttk.Label(parent, image=self.logo_img, background="#1A0A3A").pack(pady=(0, 20))
        except Exception as e:
            print(f"Error loading logo in LoginUI: {e}")
        finally:
            session.close()
