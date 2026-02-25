
import tkinter as tk
from tkinter import ttk
from ttkbootstrap.dialogs import Messagebox
from typing import Any, Optional


class ActivationDialog(tk.Toplevel):
    """Account activation dialog with OTP entry and resend functionality."""

    def __init__(self, master, auth_service: Any, prefill_username: str = ""):
        super().__init__(master)
        self.auth_service = auth_service
        self.title("Account Activation")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.username_var = tk.StringVar(value=prefill_username)
        self.otp_var = tk.StringVar()
        self._cooldown_seconds = 0
        self._cooldown_job = None

        self._create_widgets()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        w, h = 420, 340
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _create_widgets(self):
        container = ttk.Frame(self, padding=25)
        container.pack(expand=True, fill="both")

        # Header
        ttk.Label(
            container, text="🔐  Activate Account",
            font=("Helvetica", 15, "bold"),
        ).pack(pady=(0, 12))

        ttk.Label(
            container,
            text="Enter the 6-digit code sent to your email.",
            wraplength=350, justify="center",
        ).pack(pady=(0, 14))

        # Username
        ttk.Label(container, text="Username").pack(anchor="w")
        ttk.Entry(container, textvariable=self.username_var).pack(fill="x", pady=(0, 8))

        # OTP
        ttk.Label(container, text="Activation Code").pack(anchor="w")
        otp_entry = ttk.Entry(container, textvariable=self.otp_var, font=("Courier", 14), justify="center")
        otp_entry.pack(fill="x", pady=(0, 10))

        # Feedback label
        self.feedback_var = tk.StringVar()
        self.feedback_label = ttk.Label(container, textvariable=self.feedback_var, wraplength=350)
        self.feedback_label.pack(pady=(0, 6))

        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(5, 0))

        ttk.Button(btn_frame, text="Verify", command=self._do_activate).pack(fill="x", pady=(0, 5))

        self.resend_btn = ttk.Button(btn_frame, text="Resend Code", command=self._do_resend)
        self.resend_btn.pack(fill="x")

    def _do_activate(self):
        username = self.username_var.get().strip()
        otp = self.otp_var.get().strip()

        if not username:
            self._show_feedback("Please enter your username.", error=True)
            return
        if not otp or len(otp) != 6 or not otp.isdigit():
            self._show_feedback("Please enter a valid 6-digit code.", error=True)
            return

        success, msg = self.auth_service.activate_account(username, otp)

        if success:
            self._show_feedback(msg, error=False)
            Messagebox.show_info(msg, "Success", parent=self)
            self.destroy()
        else:
            self._show_feedback(msg, error=True)

    def _do_resend(self):
        username = self.username_var.get().strip()
        if not username:
            self._show_feedback("Please enter your username.", error=True)
            return

        success, msg = self.auth_service.resend_activation_otp(username)
        self._show_feedback(msg, error=not success)

        if success:
            self._start_cooldown(60)

    def _start_cooldown(self, seconds: int):
        self._cooldown_seconds = seconds
        self.resend_btn.configure(state="disabled")
        self._tick_cooldown()

    def _tick_cooldown(self):
        if self._cooldown_seconds > 0:
            self.resend_btn.configure(text=f"Resend Code ({self._cooldown_seconds}s)")
            self._cooldown_seconds -= 1
            self._cooldown_job = self.after(1000, self._tick_cooldown)
        else:
            self.resend_btn.configure(text="Resend Code", state="normal")
            self._cooldown_job = None

    def _show_feedback(self, msg: str, error: bool = True):
        self.feedback_var.set(msg)
        color = "#e74c3c" if error else "#2ecc71"
        self.feedback_label.configure(foreground=color)

    def destroy(self):
        if self._cooldown_job:
            self.after_cancel(self._cooldown_job)
        super().destroy()
