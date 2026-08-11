
import tkinter as tk
from tkinter import ttk
from ttkbootstrap.dialogs import Messagebox
from typing import Any


class PasswordResetDialog(tk.Toplevel):
    """Two-step password reset dialog: request OTP → enter new password."""

    def __init__(self, master, auth_service: Any):
        super().__init__(master)
        self.auth_service = auth_service
        self.title("Password Reset")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.email_var = tk.StringVar()
        self.otp_var = tk.StringVar()
        self.new_password_var = tk.StringVar()
        self.confirm_password_var = tk.StringVar()
        self._cooldown_seconds = 0
        self._cooldown_job = None

        self._step = 1
        self._create_widgets()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        w, h = 440, 420
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _create_widgets(self):
        # Main container
        self.container = ttk.Frame(self, padding=25)
        self.container.pack(expand=True, fill="both")

        # Header
        ttk.Label(
            self.container, text="🔑  Password Reset",
            font=("Helvetica", 15, "bold"),
        ).pack(pady=(0, 12))

        # Feedback
        self.feedback_var = tk.StringVar()
        self.feedback_label = ttk.Label(
            self.container, textvariable=self.feedback_var, wraplength=380, justify="center",
        )
        self.feedback_label.pack(pady=(0, 8))

        # Step frames
        self.step1_frame = ttk.Frame(self.container)
        self.step2_frame = ttk.Frame(self.container)

        self._build_step1()
        self._build_step2()
        self._show_step(1)

    # ── Step 1: Request reset code ──────────────────────────────
    def _build_step1(self):
        f = self.step1_frame

        ttk.Label(
            f, text="Enter your email to receive a reset code.",
            wraplength=380, justify="center",
        ).pack(pady=(0, 12))

        ttk.Label(f, text="Email Address").pack(anchor="w")
        ttk.Entry(f, textvariable=self.email_var).pack(fill="x", pady=(0, 14))

        self.send_btn = ttk.Button(f, text="Send Reset Code", command=self._do_request)
        self.send_btn.pack(fill="x")

    # ── Step 2: Enter OTP + new password ────────────────────────
    def _build_step2(self):
        f = self.step2_frame

        ttk.Label(f, text="Reset Code").pack(anchor="w")
        ttk.Entry(f, textvariable=self.otp_var, font=("Courier", 14), justify="center").pack(fill="x", pady=(0, 8))

        ttk.Label(f, text="New Password").pack(anchor="w")
        ttk.Entry(f, textvariable=self.new_password_var, show="*").pack(fill="x", pady=(0, 8))

        ttk.Label(f, text="Confirm Password").pack(anchor="w")
        ttk.Entry(f, textvariable=self.confirm_password_var, show="*").pack(fill="x", pady=(0, 6))

        # Password strength bar
        self.strength_frame = ttk.Frame(f)
        self.strength_frame.pack(fill="x", pady=(0, 4))
        self.strength_label = ttk.Label(self.strength_frame, text="", font=("Helvetica", 9))
        self.strength_label.pack(anchor="w")

        # Track password changes for live strength feedback
        self.new_password_var.trace_add("write", self._update_strength)

        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(8, 0))

        ttk.Button(btn_row, text="Reset Password", command=self._do_reset).pack(fill="x", pady=(0, 5))

        self.resend_reset_btn = ttk.Button(btn_row, text="Resend Code", command=self._do_resend)
        self.resend_reset_btn.pack(fill="x", pady=(0, 5))

        ttk.Button(btn_row, text="← Back", command=lambda: self._show_step(1)).pack(fill="x")

    def _show_step(self, step: int):
        self._step = step
        self.step1_frame.pack_forget()
        self.step2_frame.pack_forget()
        self.feedback_var.set("")

        if step == 1:
            self.step1_frame.pack(expand=True, fill="both")
        else:
            self.step2_frame.pack(expand=True, fill="both")

    # ── Actions ─────────────────────────────────────────────────
    def _do_request(self):
        email = self.email_var.get().strip()
        if not email or "@" not in email:
            self._show_feedback("Please enter a valid email address.", error=True)
            return

        success, msg = self.auth_service.request_password_reset(email)
        self._show_feedback(msg, error=not success)

        if success:
            self._start_cooldown(self.send_btn, 60)
            # Move to step 2 after a brief pause so user reads the message
            self.after(1200, lambda: self._show_step(2))

    def _do_reset(self):
        email = self.email_var.get().strip()
        otp = self.otp_var.get().strip()
        new_pwd = self.new_password_var.get()
        confirm = self.confirm_password_var.get()

        if not otp or len(otp) != 6 or not otp.isdigit():
            self._show_feedback("Please enter the 6-digit code.", error=True)
            return

        if new_pwd != confirm:
            self._show_feedback("Passwords do not match.", error=True)
            return

        if not new_pwd:
            self._show_feedback("Please enter a new password.", error=True)
            return

        success, msg = self.auth_service.reset_password(email, otp, new_pwd)

        if success:
            self._show_feedback(msg, error=False)
            Messagebox.show_info(msg, "Success", parent=self)
            self.destroy()
        else:
            self._show_feedback(msg, error=True)

    def _do_resend(self):
        email = self.email_var.get().strip()
        if not email:
            self._show_feedback("Email is required.", error=True)
            return

        success, msg = self.auth_service.request_password_reset(email)
        self._show_feedback(msg, error=not success)
        if success:
            self._start_cooldown(self.resend_reset_btn, 60)

    # ── Password strength indicator ────────────────────────────
    def _update_strength(self, *_args):
        pwd = self.new_password_var.get()
        if not pwd:
            self.strength_label.configure(text="")
            return

        score = 0
        if len(pwd) >= 8:
            score += 1
        if any(c.isupper() for c in pwd):
            score += 1
        if any(c.islower() for c in pwd):
            score += 1
        if any(c.isdigit() for c in pwd):
            score += 1
        if len(pwd) >= 12:
            score += 1

        levels = {
            0: ("Very weak", "#e74c3c"),
            1: ("Weak", "#e67e22"),
            2: ("Fair", "#f1c40f"),
            3: ("Good", "#27ae60"),
            4: ("Strong", "#2ecc71"),
            5: ("Very strong", "#1abc9c"),
        }
        label, color = levels.get(score, ("", "#888"))
        bar = "█" * score + "░" * (5 - score)
        self.strength_label.configure(text=f"{bar}  {label}", foreground=color)

    # ── Cooldown helper ─────────────────────────────────────────
    def _start_cooldown(self, button, seconds: int):
        self._cooldown_seconds = seconds
        self._cooldown_btn = button
        button.configure(state="disabled")
        self._tick_cooldown()

    def _tick_cooldown(self):
        if self._cooldown_seconds > 0:
            self._cooldown_btn.configure(text=f"Resend Code ({self._cooldown_seconds}s)")
            self._cooldown_seconds -= 1
            self._cooldown_job = self.after(1000, self._tick_cooldown)
        else:
            self._cooldown_btn.configure(text="Resend Code", state="normal")
            self._cooldown_job = None

    def _show_feedback(self, msg: str, error: bool = True):
        self.feedback_var.set(msg)
        color = "#e74c3c" if error else "#2ecc71"
        self.feedback_label.configure(foreground=color)

    def destroy(self):
        if self._cooldown_job:
            self.after_cancel(self._cooldown_job)
        super().destroy()
