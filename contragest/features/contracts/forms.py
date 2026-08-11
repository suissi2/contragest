import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import os
import shutil
from PIL import Image, ImageTk
from tkinter import filedialog
from contragest.core.database import SessionLocal, AppConfig, Employee, Contract, ContractHistory
from contragest.core.i18n import tr, get_lang_manager
from contragest.core.status_bar import StatusLabel

class SettingsForm(ttk.Toplevel):
    def __init__(self, parent, refresh_callback=None, initial_tab='application'):
        super().__init__(parent)
        self.title(tr("settings"))
        # Increase height to accommodate all fields and buttons
        self.geometry("480x800")
        self.center_window()
        self.refresh_callback = refresh_callback
        self.initial_tab = initial_tab
        
        self.session = SessionLocal()
        self.config = self.session.query(AppConfig).first()
        
        # Logo related
        self.temp_logo_path = None
        self.logo_image = None
        
        # Load current language into manager just in case (though main should handle it)
        get_lang_manager().load_language(self.config.language or "en")
        
        # Add Persistent Status Bar (Bottom) - Reserve before any notebook expansion
        user = getattr(parent, 'current_user', None)
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status("Application Settings")

        self.create_widgets()
    
    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def create_widgets(self):
        ttk.Label(self, text=tr("configuration"), font=("Helvetica", 12, "bold")).pack(pady=10)
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=YES, padx=10, pady=5)
        
        self.tab_app = ttk.Frame(self.notebook, padding=10)
        
        self.notebook.add(self.tab_app, text="🛠️ Application")
        
        # --- APPLICATION TAB ---
        
        # Language Selector
        ttk.Label(self.tab_app, text=tr("language") + ":").pack(anchor=W, padx=10)
        self.lang_var = ttk.StringVar(value=self.config.language or "en")
        self.lang_combo = ttk.Combobox(self.tab_app, textvariable=self.lang_var, values=["en", "fr", "ar"], state="readonly")
        self.lang_combo.pack(fill=X, padx=10, pady=5)
        
        # Threshold
        ttk.Label(self.tab_app, text="Alert Threshold (Days):").pack(anchor=W, padx=10)
        self.days_var = ttk.StringVar(value=str(self.config.alert_threshold_days))
        ttk.Entry(self.tab_app, textvariable=self.days_var).pack(fill=X, padx=10, pady=5)
        
        # Alert Time Selectors
        ttk.Label(self.tab_app, text="Alert Time:").pack(anchor=W, padx=10)
        time_frame = ttk.Frame(self.tab_app)
        time_frame.pack(fill=X, padx=10, pady=5)

        # Current value splitting
        default_time = self.config.alert_time or "09:00"
        try:
            h_val = default_time.split(":")[0]
            m_val = default_time.split(":")[1]
        except:
            h_val, m_val = "09", "00"

        self.hour_var = ttk.StringVar(value=h_val)
        self.min_var = ttk.StringVar(value=m_val)

        # Hour selector (00-23)
        ttk.Label(time_frame, text="HH:").pack(side=LEFT)
        self.hour_spin = ttk.Spinbox(time_frame, from_=0, to=23, width=3, textvariable=self.hour_var, format="%02.0f")
        self.hour_spin.pack(side=LEFT, padx=5)

        # Minute selector (00-59)
        ttk.Label(time_frame, text="MM:").pack(side=LEFT, padx=(5, 0))
        self.min_spin = ttk.Spinbox(time_frame, from_=0, to=59, width=3, textvariable=self.min_var, format="%02.0f")
        self.min_spin.pack(side=LEFT, padx=5)

        # SMTP Server
        ttk.Label(self.tab_app, text=tr("smtp_server") + ":").pack(anchor=W, padx=10)
        self.smtp_server_var = ttk.StringVar(value=self.config.smtp_server)
        ttk.Entry(self.tab_app, textvariable=self.smtp_server_var).pack(fill=X, padx=10, pady=5)

        # SMTP Port
        ttk.Label(self.tab_app, text=tr("smtp_port") + ":").pack(anchor=W, padx=10)
        self.smtp_port_var = ttk.StringVar(value=str(self.config.smtp_port))
        ttk.Entry(self.tab_app, textvariable=self.smtp_port_var).pack(fill=X, padx=10, pady=5)
        
        # SMTP User
        ttk.Label(self.tab_app, text=tr("smtp_user") + ":").pack(anchor=W, padx=10)
        self.smtp_user_var = ttk.StringVar(value=self.config.smtp_user or "")
        ttk.Entry(self.tab_app, textvariable=self.smtp_user_var).pack(fill=X, padx=10, pady=5)
        
        # SMTP Password
        ttk.Label(self.tab_app, text=tr("smtp_password") + ":").pack(anchor=W, padx=10)
        pass_frame = ttk.Frame(self.tab_app)
        pass_frame.pack(fill=X, padx=10, pady=5)
        self.smtp_pass_var = ttk.StringVar(value=self.config.smtp_password or "")
        ttk.Entry(pass_frame, textvariable=self.smtp_pass_var, show="*").pack(side=LEFT, fill=X, expand=True)
        ttk.Button(pass_frame, text="?", command=self.open_gmail_help, bootstyle="link-info", width=2).pack(side=LEFT, padx=5)

        # SMTP SSL Verify
        self.ssl_verify_var = ttk.BooleanVar(value=getattr(self.config, 'smtp_ssl_verify', True))
        ttk.Checkbutton(self.tab_app, text=tr("verify_ssl"), variable=self.ssl_verify_var, bootstyle="round-toggle").pack(anchor=W, padx=10, pady=5)
        
        # Automatic Alerts Toggle
        self.alerts_enabled_var = ttk.BooleanVar(value=getattr(self.config, 'automatic_alerts_enabled', True))
        ttk.Checkbutton(self.tab_app, text="Enable Automatic Startup Alerts", variable=self.alerts_enabled_var, bootstyle="round-toggle").pack(anchor=W, padx=10, pady=5)

        # Notification Email
        ttk.Label(self.tab_app, text="Notify To (Email):").pack(anchor=W, padx=10)
        self.notify_email_var = ttk.StringVar(value=self.config.notification_email or "")
        ttk.Entry(self.tab_app, textvariable=self.notify_email_var).pack(fill=X, padx=10, pady=5)

        # Database Tab
        self.tab_db = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_db, text="🗄️ Database")
        self._build_db_tab()

    def _build_db_tab(self):
        """Builds the SQLite Database configuration tab."""
        from contragest.core.database import DB_PATH

        # ── Section 1: Database File ─────────────────────────────────────
        file_group = ttk.Labelframe(self.tab_db, text="📁 Database File", padding=10)
        file_group.pack(fill=X, pady=(0, 10))

        ttk.Label(file_group, text="Active Database:", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky=W, pady=2)
        from contragest.core.database import DB_PATH, _active_db_path
        active_path = _active_db_path or DB_PATH
        ttk.Label(file_group, text=active_path, foreground="gray", wraplength=380, font=("Helvetica", 8)).grid(row=1, column=0, columnspan=2, sticky=W, padx=5)

        ttk.Label(file_group, text="Custom Path:").grid(row=2, column=0, sticky=W, pady=(10, 2))
        path_row = ttk.Frame(file_group)
        path_row.grid(row=3, column=0, columnspan=2, sticky=EW, pady=2)
        file_group.columnconfigure(0, weight=1)

        self.db_path_var = ttk.StringVar(value=getattr(self.config, 'db_custom_path', None) or "")
        ttk.Entry(path_row, textvariable=self.db_path_var).pack(side=LEFT, fill=X, expand=True)
        ttk.Button(path_row, text="📂 Browse", cursor="hand2", bootstyle="outline-secondary",
                   command=self._browse_db_path).pack(side=LEFT, padx=(5, 0))
        ttk.Button(path_row, text="✖ Reset", cursor="hand2", bootstyle="outline-danger",
                   command=lambda: self.db_path_var.set("")).pack(side=LEFT, padx=(3, 0))

        ttk.Label(file_group, text="⚠️  Changing the path requires a restart to take effect.",
                  font=("Helvetica", 8, "italic"), foreground="orange").grid(row=4, column=0, columnspan=2, sticky=W, pady=(5, 0))

        # ── Section 2: Performance ───────────────────────────────────────
        perf_group = ttk.Labelframe(self.tab_db, text="⚡ Performance Pragmas", padding=10)
        perf_group.pack(fill=X, pady=(0, 10))

        ttk.Label(perf_group, text="Journal Mode:").grid(row=0, column=0, sticky=W, pady=4, padx=5)
        self.db_journal_var = ttk.StringVar(value=getattr(self.config, 'db_journal_mode', None) or "WAL")
        jm_combo = ttk.Combobox(perf_group, textvariable=self.db_journal_var, state="readonly",
                                values=["WAL", "DELETE", "MEMORY", "TRUNCATE", "PERSIST"])
        jm_combo.grid(row=0, column=1, sticky=EW, pady=4, padx=5)

        ttk.Label(perf_group, text="Cache Size (KB):").grid(row=1, column=0, sticky=W, pady=4, padx=5)
        self.db_cache_var = ttk.IntVar(value=getattr(self.config, 'db_cache_size_kb', None) or 2000)
        ttk.Spinbox(perf_group, from_=256, to=32768, increment=256, textvariable=self.db_cache_var, width=8).grid(row=1, column=1, sticky=W, pady=4, padx=5)

        ttk.Label(perf_group, text="Auto-Vacuum:").grid(row=2, column=0, sticky=W, pady=4, padx=5)
        self.db_autovac_var = ttk.BooleanVar(value=bool(getattr(self.config, 'db_auto_vacuum', False)))
        ttk.Checkbutton(perf_group, variable=self.db_autovac_var, bootstyle="round-toggle").grid(row=2, column=1, sticky=W, pady=4, padx=5)
        perf_group.columnconfigure(1, weight=1)

        # ── Section 3: Maintenance ───────────────────────────────────────
        maint_group = ttk.Labelframe(self.tab_db, text="🛠️ Maintenance", padding=10)
        maint_group.pack(fill=X, pady=(0, 10))

        btn_row = ttk.Frame(maint_group)
        btn_row.pack(fill=X, pady=5)

        ttk.Button(btn_row, text="📋 Integrity Check", cursor="hand2",
                   command=self._db_integrity_check, bootstyle="info-outline").pack(side=LEFT, padx=5)
        ttk.Button(btn_row, text="📦 Backup Now", cursor="hand2",
                   command=self._db_backup, bootstyle="warning-outline").pack(side=LEFT, padx=5)
        ttk.Button(btn_row, text="🔄 WAL Checkpoint", cursor="hand2",
                   command=self._db_wal_checkpoint, bootstyle="secondary-outline").pack(side=LEFT, padx=5)

        # Info row
        ttk.Label(maint_group,
                  text="Backups are saved alongside the database file with a timestamp suffix.",
                  font=("Helvetica", 8, "italic"), foreground="gray", wraplength=400).pack(anchor=W, padx=5)

        # ── Save DB Settings button ──────────────────────────────────────
        ttk.Button(self.tab_db, text="💾 Save Database Settings", cursor="hand2",
                   command=self._save_db_settings, bootstyle="success").pack(pady=15)

        # --- GLOBAL ACTION BUTTONS ---
        
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="📡 " + tr("test_connection"), command=self.test_email, bootstyle=INFO).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="💾 " + tr("save_settings"), command=self.save_settings, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        
        # Test Trigger Button
        ttk.Button(self, text="🧪 Set Test Alert (2 min)", command=self.prepare_test_alert, bootstyle="outline-warning").pack(pady=(0, 10))

    def _browse_db_path(self):
        """Open a file dialog to choose a custom SQLite DB file path."""
        path = filedialog.asksaveasfilename(
            title="Select or Create SQLite Database File",
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("SQLite Database", "*.sqlite"), ("All Files", "*.*")],
            parent=self
        )
        if path:
            if not path.lower().endswith(('.db', '.sqlite')):
                Messagebox.show_warning("Please choose a file with a .db or .sqlite extension.", "Invalid File Type")
                return
            self.db_path_var.set(path)

    def _get_active_db_path(self):
        """Returns the currently active DB file path."""
        from contragest.core.database import DB_PATH, _active_db_path
        return _active_db_path or DB_PATH

    def _db_integrity_check(self):
        """Runs PRAGMA integrity_check on the active database and shows the result."""
        from contragest.core.database import engine, DB_PATH, _active_db_path
        from sqlalchemy import text
        db_path = _active_db_path or DB_PATH
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA integrity_check")).fetchall()
            first_line = result[0][0] if result else "No result"
            if first_line == "ok":
                Messagebox.show_info(
                    f"\u2705 Database integrity check passed!\n\nResult: {first_line}\nFile: {db_path}",
                    "Integrity Check \u2014 OK"
                )
            else:
                detail = "\n".join(row[0] for row in result[:10])
                Messagebox.show_error(
                    f"\u26a0\ufe0f Database integrity issues found:\n\n{detail}\n\nFile: {db_path}",
                    "Integrity Check \u2014 Issues Found"
                )
        except Exception as e:
            Messagebox.show_error(f"Failed to run integrity check:\n{e}", "Error")

    def _db_backup(self):
        """Copies the active DB file to a timestamped backup in the same directory."""
        import sqlite3
        from datetime import datetime
        from contragest.core.database import engine
        db_path = self._get_active_db_path()
        if not os.path.exists(db_path):
            Messagebox.show_error(f"Database file not found:\n{db_path}", "Backup Error")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.replace(".db", f"_backup_{timestamp}.db")
        if ".db" not in backup_path:  # Edge case: extension not .db
            backup_path = db_path + f"_backup_{timestamp}.bak"
        try:
            # Use sqlite3.backup() via SQLAlchemy's underlying connection for safety
            with engine.connect() as conn:
                source_conn = conn.connection.connection # Get the raw sqlite3 connection
                dest_conn = sqlite3.connect(backup_path)
                with dest_conn:
                    source_conn.backup(dest_conn)
                dest_conn.close()
            Messagebox.show_info(
                f"\u2705 Backup created successfully!\n\nFile: {backup_path}",
                "Backup Complete"
            )
        except Exception as e:
            Messagebox.show_error(f"Backup failed:\n{e}", "Backup Error")

    def _db_wal_checkpoint(self):
        """Runs a full WAL checkpoint to flush the write-ahead log."""
        from contragest.core.database import engine
        from sqlalchemy import text
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA wal_checkpoint(FULL)")).fetchone()
            # result = (busy, log, checkpointed)
            if result:
                Messagebox.show_info(
                    f"\u2705 WAL Checkpoint completed!\n\n"
                    f"  Pages logged: {result[1]}\n"
                    f"  Pages checkpointed: {result[2]}\n"
                    f"  Busy: {'Yes' if result[0] else 'No'}",
                    "WAL Checkpoint"
                )
            else:
                Messagebox.show_info("WAL checkpoint ran with no output.", "WAL Checkpoint")
        except Exception as e:
            Messagebox.show_error(f"WAL checkpoint failed:\n{e}", "Error")

    def _save_db_settings(self):
        """Saves the SQLite database configuration to AppConfig.
        
        PRAGMAs (journal_mode, cache_size, auto_vacuum) are applied automatically
        on every new SQLAlchemy connection via the event listener in database.py.
        No raw sqlite3 connection is opened here to avoid locking conflicts.
        """
        from contragest.core.database import DB_PATH

        custom_path = self.db_path_var.get().strip()
        journal_mode = self.db_journal_var.get()
        cache_size_kb = self.db_cache_var.get()
        auto_vacuum = self.db_autovac_var.get()

        # --- Validate custom path ---
        if custom_path:
            if not custom_path.lower().endswith(('.db', '.sqlite')):
                Messagebox.show_warning("The database file must have a .db or .sqlite extension.", "Validation Error")
                return
            parent_dir = os.path.dirname(custom_path) or "."
            if not os.path.isdir(parent_dir):
                Messagebox.show_error(f"Directory does not exist:\n{parent_dir}", "Validation Error")
                return
                
            # Check write permissions on the directory
            try:
                test_file = os.path.join(parent_dir, ".db_write_test")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                Messagebox.show_error(
                    f"You do not have write permissions for directory:\n{parent_dir}\n\n"
                    "SQLite requires write access to the folder to create temporary files (WAL/Journal). "
                    "Please choose a different folder (e.g. your Documents or a new subfolder).",
                    "Permission Denied"
                )
                return
                
            # Check write permissions on the DB file itself
            import sqlite3
            try:
                _test = sqlite3.connect(custom_path)
                if os.path.exists(custom_path):
                    _test.execute("CREATE TABLE IF NOT EXISTS _permission_test (id INT)")
                    _test.execute("DROP TABLE IF EXISTS _permission_test")
                _test.close()
            except sqlite3.OperationalError as e:
                Messagebox.show_error(
                    f"The database file itself is read-only:\n{custom_path}\n\n"
                    f"Detail: {e}\n\n"
                    "Please check the file properties in Windows and disable 'Read-Only'.",
                    "Permission Denied"
                )
                return

        # --- Validate cache size ---
        try:
            cache_size_kb = int(cache_size_kb)
            if not (256 <= cache_size_kb <= 32768):
                raise ValueError()
        except (ValueError, TypeError):
            Messagebox.show_warning("Cache size must be a number between 256 and 32768 KB.", "Validation Error")
            return

        original_path = getattr(self.config, 'db_custom_path', None) or DB_PATH
        path_changed = (custom_path or DB_PATH) != original_path

        try:
            # Only persist values - PRAGMAs are applied automatically at connection time
            self.config.db_custom_path = custom_path or None
            self.config.db_journal_mode = journal_mode
            self.config.db_cache_size_kb = cache_size_kb
            self.config.db_auto_vacuum = auto_vacuum
            self.session.commit()

            if path_changed:
                Messagebox.show_info(
                    "Database path has been updated.\n\n"
                    "⚠️ Please restart the application for the new path to take effect.",
                    "Restart Required"
                )
            else:
                Messagebox.show_info(
                    "Database settings saved!\n\n"
                    "Performance pragmas will be applied on next connection.",
                    "✅ Saved"
                )
        except Exception as e:
            self.session.rollback()
            Messagebox.show_error(f"Failed to save database settings:\n{e}", "Error")

    def test_email(self):
        # Create a temp config object to test with current form values
        from contragest.core.email_service import EmailService
        
        class MockConfig:
            pass
        
        # Validate Integers
        try:
            port = int(self.smtp_port_var.get())
        except ValueError:
            Messagebox.show_error("SMTP Port must be a number.", "Validation Error")
            return
            
        temp_config = MockConfig()
        temp_config.smtp_server = self.smtp_server_var.get()
        temp_config.smtp_port = port
        temp_config.smtp_user = self.smtp_user_var.get()
        temp_config.smtp_password = self.smtp_pass_var.get()
        temp_config.smtp_ssl_verify = self.ssl_verify_var.get()
        temp_config.automatic_alerts_enabled = self.alerts_enabled_var.get()
        # config.notification_email not strictly needed for connection test, but good for send test
        
        try:
            service = EmailService(temp_config)
            server = service.connect()
            server.quit()
            Messagebox.show_info("Connection successful! SMTP settings are valid.", "Connection Test")
        except Exception as e:
            Messagebox.show_error(f"Connection Failed:\n{e}", "Connection Test Failed")

    def open_gmail_help(self):
        import webbrowser
        webbrowser.open("https://support.google.com/accounts/answer/185833?hl=en")

    def save_settings(self):
        try:
            old_lang = self.config.language
            new_lang = self.lang_var.get()
            
            # Build time string from HH and MM selectors
            h = f"{int(self.hour_var.get()):02d}"
            m = f"{int(self.min_var.get()):02d}"
            new_alert_time = f"{h}:{m}"
            
            # Validation: Ensure SMTP Server is not an email address
            smtp_server = self.smtp_server_var.get().strip()
            if "@" in smtp_server:
                Messagebox.show_error(
                    "The SMTP Server must be a hostname (e.g., mail.saphirpalace.com.tn), not an email address.",
                    "Validation Error"
                )
                return

            # Reset daily alert lock if time has changed, allowing for easier testing
            if new_alert_time != self.config.alert_time:
                print(f"DEBUG: Alert time changed from {self.config.alert_time} to {new_alert_time}. Resetting daily alert lock.")
                self.config.last_alert_date = None
            
            self.config.alert_time = new_alert_time
            self.config.alert_threshold_days = int(self.days_var.get())
            self.config.smtp_server = self.smtp_server_var.get()
            self.config.smtp_port = int(self.smtp_port_var.get())
            self.config.smtp_user = self.smtp_user_var.get()
            self.config.smtp_password = self.smtp_pass_var.get()
            self.config.smtp_ssl_verify = self.ssl_verify_var.get()
            self.config.automatic_alerts_enabled = self.alerts_enabled_var.get()
            self.config.notification_email = self.notify_email_var.get()
            self.config.language = new_lang
            
            # Validation is mostly handled by Spinboxes, but let's confirm format
            try:
                datetime.strptime(self.config.alert_time, "%H:%M")
            except ValueError:
                raise ValueError("Invalid Hour or Minute selection.")

            self.session.commit()
            
            if old_lang != new_lang:
                 Messagebox.show_info("Language changed. Please restart the application.", "Restart Required")
            else:
                 Messagebox.show_info("Settings saved successfully!", "Success")
            
            if self.refresh_callback:
                self.refresh_callback()
                 
            self.destroy()
        except ValueError:
            Messagebox.show_error("Invalid input. Please check numbers.", "Error")
        except Exception as e:
            Messagebox.show_error(f"Error saving settings: {e}", "Error")
        finally:
            self.session.close()

    def prepare_test_alert(self):
        """Automatically sets alert time to +2 mins and resets last_alert_date for testing."""
        try:
            # 1. Update Form Variables
            future = datetime.now() + timedelta(minutes=2)
            future_time = future.strftime("%H:%M")
            
            self.hour_var.set(future.strftime("%H"))
            self.min_var.set(future.strftime("%M"))
            self.alerts_enabled_var.set(True)
            
            # 2. Update Database Object
            self.config.alert_time = future_time
            self.config.automatic_alerts_enabled = True
            # Reset last_alert_date to yesterday to ensure it triggers today
            self.config.last_alert_date = (datetime.now() - timedelta(days=1)).date()
            
            # 3. Commit
            self.session.commit()
            
            Messagebox.show_info(
                f"Test alert scheduled for {future_time}.\n\n"
                "The system will verify this EXACT time automatically.\n"
                "Please keep the app open.", 
                "Test Ready"
            )
            
            if self.refresh_callback:
                self.refresh_callback()
                
            self.destroy()
        except Exception as e:
            Messagebox.show_error(f"Error preparing test alert: {e}", "Error")


from contragest.core.layout import pack_start, pack_end, get_anchor_start, get_anchor_end

class ContractForm(ttk.Toplevel):
    def __init__(self, parent, contract_id=None, user=None, refresh_callback=None, pre_employee_id=None):
        """
        Args:
            parent: Parent widget.
            contract_id: If set, edit existing contract.
            user: Current logged-in user.
            refresh_callback: Called after save to refresh parent views.
            pre_employee_id: If set, pre-select this employee (used from Employee Manager).
        """
        super().__init__(parent)
        self.title(tr("contract_info"))
        self.geometry("550x700")
        self.refresh_callback = refresh_callback
        self.contract_id = contract_id
        self.user = user
        self.pre_employee_id = pre_employee_id
        self.session = SessionLocal()
        
        # Period variables for bidirectional sync
        self._sync_lock = False
        self.period_years_var = ttk.IntVar(value=0)
        self.period_months_var = ttk.IntVar(value=0)
        self.period_days_var = ttk.IntVar(value=0)
        
        # Add traces for period fields
        self.period_years_var.trace_add("write", self._on_period_change)
        self.period_months_var.trace_add("write", self._on_period_change)
        self.period_days_var.trace_add("write", self._on_period_change)
        
        # Employee data cache
        self.employees_cache = []
        self.selected_employee_id = None
        
        # Add Persistent Status Bar (Bottom) - Reserve before any widget build
        # 'user' is passed as argument
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status("Contract Administration")

        self.create_widgets()
        self._load_employees()
        
        if contract_id:
            self.load_data()
        elif pre_employee_id:
            self._select_employee_by_id(pre_employee_id)

    def create_widgets(self):
        # Container for better padding
        main_container = ttk.Frame(self, padding=20)
        main_container.pack(fill=BOTH, expand=YES)

        anchor_start = get_anchor_start()
        anchor_end = get_anchor_end()

        # ── Employee Selection Section ──────────────────────────────────
        emp_group = ttk.Labelframe(main_container, text=tr("employee_info"), padding=15)
        emp_group.pack(fill=X, pady=(0, 15))
        
        # Employee search combobox
        search_row = ttk.Frame(emp_group)
        search_row.pack(fill=X, pady=5)
        pack_start(ttk.Label(search_row, text=tr("employee") + ":", width=12))
        
        self.emp_search_var = ttk.StringVar()
        self.emp_combo = ttk.Combobox(search_row, textvariable=self.emp_search_var)
        self.emp_combo.pack(side=LEFT, fill=X, expand=YES, padx=5)
        self.emp_combo.bind("<KeyRelease>", self._on_emp_search)
        self.emp_combo.bind("<<ComboboxSelected>>", self._on_emp_selected)
        
        # New Employee button
        ttk.Button(
            search_row, text="➕", bootstyle="success-outline", width=3,
            command=self._open_new_employee
        ).pack(side=LEFT, padx=(2, 0))
        
        # Employee context info (read-only)
        self.emp_info_frame = ttk.Frame(emp_group)
        self.emp_info_frame.pack(fill=X, pady=(5, 0))
        
        self.emp_dept_var = ttk.StringVar()
        self.emp_func_var = ttk.StringVar()
        
        info_row1 = ttk.Frame(self.emp_info_frame)
        info_row1.pack(fill=X, pady=2)
        pack_start(ttk.Label(info_row1, text=tr("department") + ":", width=16, foreground="gray"))
        ttk.Label(info_row1, textvariable=self.emp_dept_var, foreground="gray").pack(side=LEFT, padx=5)
        
        info_row2 = ttk.Frame(self.emp_info_frame)
        info_row2.pack(fill=X, pady=2)
        pack_start(ttk.Label(info_row2, text=tr("role_title") + ":", width=16, foreground="gray"))
        ttk.Label(info_row2, textvariable=self.emp_func_var, foreground="gray").pack(side=LEFT, padx=5)
        
        # Selection indicator
        self.emp_status_var = ttk.StringVar(value="")
        self.emp_status_label = ttk.Label(emp_group, textvariable=self.emp_status_var, font=("Helvetica", 9))
        self.emp_status_label.pack(anchor=W, pady=(5, 0))

        # Hidden fields for edit mode backward compatibility  
        self.fname_var = ttk.StringVar()
        self.lname_var = ttk.StringVar()

        # ── Contract Info Section ───────────────────────────────────────
        contract_group = ttk.Labelframe(main_container, text=tr("contract_info"), padding=15)
        contract_group.pack(fill=X)
        
        # Type
        row3 = ttk.Frame(contract_group)
        row3.pack(fill=X, pady=5)
        pack_start(ttk.Label(row3, text=tr("type") + ":", width=16))
        self.type_var = ttk.StringVar()
        types = ["CDI", "CDD", "Stage", "Freelance"]
        combo = ttk.Combobox(row3, textvariable=self.type_var, values=types, state="readonly")
        pack_end(combo, expand=True, fill=X, padx=5)
        combo.current(0)
        
        # Start Date
        row4 = ttk.Frame(contract_group)
        row4.pack(fill=X, pady=5)
        pack_start(ttk.Label(row4, text=tr("start_date") + ":", width=16))
        self.start_date_var = ttk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.start_date_entry = ttk.DateEntry(row4, dateformat="%Y-%m-%d")
        self.start_date_entry.entry.configure(textvariable=self.start_date_var)
        self.start_date_var.trace_add("write", self._update_duration)
        pack_end(self.start_date_entry, expand=True, fill=X, padx=5)
        
        # ── Period Configuration (Year, Month, Days) ────────────────────
        
        # YEAR
        row_py = ttk.Frame(contract_group)
        row_py.pack(fill=X, pady=5)
        pack_start(ttk.Label(row_py, text=tr("YEAR_LABEL") + ":", width=16))
        self.period_years_spin = ttk.Spinbox(row_py, from_=0, to=50, textvariable=self.period_years_var)
        pack_end(self.period_years_spin, expand=True, fill=X, padx=5)

        # MONTH
        row_pm = ttk.Frame(contract_group)
        row_pm.pack(fill=X, pady=5)
        pack_start(ttk.Label(row_pm, text=tr("MONTH_LABEL") + ":", width=16))
        self.period_months_spin = ttk.Spinbox(row_pm, from_=0, to=11, textvariable=self.period_months_var)
        pack_end(self.period_months_spin, expand=True, fill=X, padx=5)

        # DAYS
        row_pd = ttk.Frame(contract_group)
        row_pd.pack(fill=X, pady=5)
        pack_start(ttk.Label(row_pd, text=tr("DAY_LABEL") + ":", width=16))
        self.period_days_spin = ttk.Spinbox(row_pd, from_=0, to=31, textvariable=self.period_days_var)
        pack_end(self.period_days_spin, expand=True, fill=X, padx=5)
        
        # End Date
        row5 = ttk.Frame(contract_group)
        row5.pack(fill=X, pady=5)
        pack_start(ttk.Label(row5, text=tr("end_date") + ":", width=16))
        
        self.has_end_date = ttk.BooleanVar(value=False)
        self.end_date_var = ttk.StringVar()
        self.end_date_entry = ttk.DateEntry(row5, dateformat="%Y-%m-%d")
        self.end_date_entry.entry.configure(textvariable=self.end_date_var)
        self.end_date_var.trace_add("write", self._update_duration)
        
        def toggle_end_date():
            if self.has_end_date.get():
                self.end_date_entry.configure(state="normal")
            else:
                self.end_date_entry.configure(state="disabled")
            self._update_duration()
                
        check = ttk.Checkbutton(row5, variable=self.has_end_date, command=toggle_end_date, bootstyle="round-toggle")
        pack_end(check, padx=5)
        pack_end(self.end_date_entry, expand=True, fill=X, padx=5)
        
        # Duration
        row6 = ttk.Frame(contract_group)
        row6.pack(fill=X, pady=5)
        pack_start(ttk.Label(row6, text=tr("duration") + ":", width=16))
        self.duration_var = ttk.StringVar(value="-")
        # Bold and Info colored for visibility
        ttk.Label(row6, textvariable=self.duration_var, font=("Helvetica", 9, "bold"), bootstyle="info").pack(side=LEFT, padx=5)


        toggle_end_date() # Initial state
        self._update_duration() # Initialize duration display

        # Buttons
        button_frame = ttk.Frame(main_container)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="💾 " + tr("save"), command=self.save_contract, bootstyle=SUCCESS, width=15).pack(side=LEFT, padx=10, ipady=5)
        
        if self.contract_id:
             ttk.Button(button_frame, text="📜 " + tr("view_history"), command=self.view_history, bootstyle=SECONDARY, width=15).pack(side=LEFT, padx=10, ipady=5)

    # ------------------------------------------------------------------ #
    #  Employee search & selection
    # ------------------------------------------------------------------ #

    def _load_employees(self):
        """Load only active employees into cache and populate combobox."""
        self.employees_cache = self.session.query(Employee)\
            .filter(Employee.is_archived == False)\
            .order_by(Employee.last_name, Employee.first_name).all()
        display_list = [f"{e.last_name} {e.first_name} (ID:{e.id}) - {e.role_title}" for e in self.employees_cache]
        self.emp_combo["values"] = display_list

    def _on_emp_search(self, event):
        """Filter employee dropdown as user types."""
        typed = self.emp_search_var.get().lower()
        if not typed:
            self.emp_combo["values"] = [f"{e.last_name} {e.first_name} (ID:{e.id}) - {e.role_title}" for e in self.employees_cache]
            return
        filtered = [
            f"{e.last_name} {e.first_name} (ID:{e.id}) - {e.role_title}"
            for e in self.employees_cache
            if typed in e.last_name.lower() or typed in e.first_name.lower()
               or typed in str(e.id) or typed in (e.role_title or "").lower()
        ]
        self.emp_combo["values"] = filtered
        if filtered:
            self.emp_combo.event_generate("<Down>")

    def _on_emp_selected(self, event=None):
        """Handle employee selection from combobox."""
        selection = self.emp_search_var.get()
        # Extract ID from "LastName FirstName (ID:123) - Role"
        try:
            id_part = selection.split("(ID:")[1].split(")")[0]
            emp_id = int(id_part)
            self._select_employee_by_id(emp_id)
        except (IndexError, ValueError):
            self.selected_employee_id = None
            self._update_emp_context(None)

    def _select_employee_by_id(self, emp_id):
        """Select and display an employee by their ID."""
        emp = None
        for e in self.employees_cache:
            if e.id == emp_id:
                emp = e
                break
        if not emp:
            emp = self.session.query(Employee).get(emp_id)
        
        if emp:
            self.selected_employee_id = emp.id
            self.emp_search_var.set(f"{emp.last_name} {emp.first_name} (ID:{emp.id}) - {emp.role_title}")
            self.fname_var.set(emp.first_name)
            self.lname_var.set(emp.last_name)
            self._update_emp_context(emp)

    def _update_emp_context(self, emp):
        """Update the read-only context info below the employee selector."""
        if emp:
            dept_name = emp.dept_obj.name if emp.dept_obj else tr("no_selection")
            self.emp_dept_var.set(dept_name)
            self.emp_func_var.set(emp.role_title or "-")
            self.emp_status_var.set(f"✅ {tr('employee_selected')}")
            self.emp_status_label.configure(foreground="green")
        else:
            self.emp_dept_var.set("")
            self.emp_func_var.set("")
            self.emp_status_var.set(f"⚠️ {tr('no_employee_selected')}")
            self.emp_status_label.configure(foreground="orange")

    def _open_new_employee(self):
        """Open the Data Entry Form to create a new employee, then refresh the combobox."""
        from contragest.features.employee_manager.data_entry_form import DataEntryForm
        form = DataEntryForm(self, mode="add", on_save_callback=self._on_new_employee_saved)

    def _on_new_employee_saved(self):
        """Callback after a new employee is created - refresh and select the newest."""
        self._load_employees()
        if self.employees_cache:
            # Select the last added employee (highest ID)
            newest = max(self.employees_cache, key=lambda e: e.id)
            self._select_employee_by_id(newest.id)

    # ------------------------------------------------------------------ #
    #  Existing methods (updated)
    # ------------------------------------------------------------------ #

    def view_history(self):
        if not self.contract_id:
            return
            
        HistoryDialog(self, self.contract_id)

    def _update_duration(self, *args):
        """Calculate and display years, months, days between start and end dates."""
        try:
            start_str = self.start_date_entry.entry.get().strip()
            if not start_str:
                self.duration_var.set("-")
                return
            
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            
            if self.has_end_date.get():
                end_str = self.end_date_entry.entry.get().strip()
                if not end_str:
                    self.duration_var.set("-")
                    return
                end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            else:
                # If CDI (no end date), we might show duration as "Ongoing" or calculate since today?
                # User specifically asked for duration between dates. 
                # If it's a CDI, we'll show "-" or maybe calculate seniority?
                # But "Seniority" is usually distinct. 
                # Let's check for today if no end date?
                # Actually, typical HR UX for contract duration shows nothing for CDI 
                # unless explicitly calculating active seniority. 
                # Since the field is called "DURÉE", let's use Today if it's CDI 
                # to show how long they've been on this contract.
                end_date = date.today()

            if start_date and end_date:
                # Ensure start <= end for calculation logic
                if start_date > end_date:
                    self.duration_var.set("-")
                    return
                    
                # Standard inclusive contract math: Duration = (End - Start) + 1 day
                diff = relativedelta(end_date + timedelta(days=1), start_date)
                parts = []
                if diff.years > 0:
                    parts.append(f"{diff.years} {tr('years')}")
                if diff.months > 0:
                    parts.append(f"{diff.months} {tr('months')}")
                if diff.days > 0:
                    parts.append(f"{diff.days} {tr('days')}")
                
                if not parts:
                    if start_date == end_date:
                        self.duration_var.set(f"0 {tr('days')}")
                    else:
                        self.duration_var.set("-")
                else:
                    self.duration_var.set(", ".join(parts))
                
                # Sync period fields if not locked
                if not self._sync_lock:
                    self._sync_lock = True
                    self.period_years_var.set(diff.years)
                    self.period_months_var.set(diff.months)
                    self.period_days_var.set(diff.days)
                    self._sync_lock = False
        except Exception as e:
            # print(f"DEBUG: Duration calc error: {e}")
            self.duration_var.set("-")

    def _on_period_change(self, *args):
        """Update End Date based on Start Date + (Years, Months, Days)."""
        if self._sync_lock:
            return
        
        try:
            start_str = self.start_date_var.get().strip()
            if not start_str:
                return
            
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            
            y = self.period_years_var.get()
            m = self.period_months_var.get()
            d = self.period_days_var.get()
            
            # Using relativedelta for precise calendar math
            from dateutil.relativedelta import relativedelta
            # Standard inclusive contract math: End Date = Start + Period - 1 day
            # This ensures e.g. Feb 24 to Aug 23 is exactly 6 months.
            new_end = start_date + relativedelta(years=y, months=m, days=d) - timedelta(days=1)
            
            self._sync_lock = True
            self.end_date_var.set(new_end.strftime("%Y-%m-%d"))
            self.has_end_date.set(True) # Automatically enable end date if period is set
            self.end_date_entry.configure(state="normal")
            self._sync_lock = False
            
            # Duration will be updated automatically by end_date_var trace
        except Exception:
            pass
        finally:
            self._sync_lock = False

    def load_data(self):
        contract = self.session.query(Contract).filter(Contract.id == self.contract_id).first()
        if contract:
            # Select the employee in the combobox
            self._select_employee_by_id(contract.employee_id)
            self.type_var.set(contract.contract_type)
            
            self.start_date_var.set(str(contract.start_date))
            
            if contract.end_date:
                self.has_end_date.set(True)
                self.end_date_entry.configure(state="normal")
                self.end_date_var.set(str(contract.end_date))
            else:
                self.has_end_date.set(False)
                self.end_date_entry.configure(state="disabled")
            
            # Recalculate duration after loading
            self._update_duration()

    def save_contract(self):
        try:
            # Validate employee selection
            if not self.selected_employee_id:
                Messagebox.show_warning(tr("no_employee_selected"), tr("validation_error"))
                return

            fname = self.fname_var.get()
            lname = self.lname_var.get()
            ctype = self.type_var.get()
            
            start_str = self.start_date_entry.entry.get()
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            
            end = None
            if self.has_end_date.get():
                end_str = self.end_date_entry.entry.get()
                end = datetime.strptime(end_str, "%Y-%m-%d").date()

            from contragest.features.contracts.service import ContractService
            service = ContractService(self.session)
            
            if self.contract_id:
                # Update Existing - Security Check
                
                # 1. Mandatory Justification
                from ttkbootstrap.dialogs import Querybox
                reason = Querybox.get_string("Please provide a reason for this change:", "Justification Required", parent=self)
                if not reason:
                    return # User cancelled or empty
                
                # 2. Role-Based Auth
                if self.user and self.user.role != 'admin':
                    password = Querybox.get_string("Please enter your password to confirm:", "Authentication Required", parent=self)
                    if not password:
                        return
                        
                    from contragest.features.auth.service import verify_password
                    from contragest.features.auth.service import User, SessionLocal as AuthSession
                    auth_session = AuthSession()
                    try:
                        fresh_user = auth_session.query(User).get(self.user.id)
                        
                        if not fresh_user or not verify_password(fresh_user.password_hash, fresh_user.salt, password):
                             Messagebox.show_error("Incorrect password. Changes not saved.", "Authentication Failed")
                             return
                    finally:
                        auth_session.close()

                service.update_contract(
                    contract_id=self.contract_id,
                    first_name=fname,
                    last_name=lname,
                    contract_type=ctype,
                    start_date=start,
                    end_date=end,
                    user_id=self.user.id if self.user else None,
                    change_reason=reason
                )
            else:
                # New Contract - use selected existing employee
                service.create_contract(
                    employee_id=self.selected_employee_id,
                    contract_type=ctype,
                    start_date=start,
                    end_date=end,
                    user_id=self.user.id if self.user else None
                )

            Messagebox.show_info("Contract saved successfully!", "Success")
            if self.refresh_callback:
                self.refresh_callback()
            self.destroy()
            
        except ValueError as e:
            Messagebox.show_error(str(e), "Validation Error")
        except Exception as e:
            Messagebox.show_error(f"Error: {e}", "Error")
        finally:
            self.session.close()


class HistoryDialog(ttk.Toplevel):
    def __init__(self, parent, contract_id):
        super().__init__(parent)
        self.title(tr("view_history"))
        self.geometry("600x400")
        self.contract_id = contract_id
        
        # Load history data first
        rows = self.fetch_history_data()
        
        # Add Persistent Status Bar (Bottom) - Reserve before table expansion
        # In ContractForm, 'user' is passed to MainWindow
        # We try to find current_user on parent or root
        user = getattr(parent, 'current_user', None)
        if not user and hasattr(parent, 'parent'):
             user = getattr(parent.parent, 'current_user', None)
             
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status("Viewing History")

        self.create_widgets(rows)
        
    def create_widgets(self, rows):
        # Table
        cols = [
            tr("version"),
            tr("type"),
            tr("start_date"),
            tr("end_date"),
            tr("reason")
        ]
        
        from ttkbootstrap.tableview import Tableview
        self.table = Tableview(
            master=self,
            coldata=cols,
            rowdata=rows,
            paginated=False,
            searchable=False,
            bootstyle=INFO,
            autofit=True
        )
        self.table.pack(fill=BOTH, expand=YES, padx=10, pady=10)
        
    def fetch_history_data(self):
        session = SessionLocal()
        rows = []
        try:
            from contragest.features.contracts.service import ContractService
            service = ContractService(session)
            history = service.get_history(self.contract_id)
            
            for h in history:
                rows.append((
                    str(h.version_number),
                    str(h.contract_type),
                    str(h.start_date),
                    str(h.end_date) if h.end_date else "N/A",
                    str(h.change_reason or "")
                ))
            
        except Exception as e:
            print(f"ERROR HISTORY: {e}")
        finally:
            session.close()
        return rows


class RecoveryForm(ttk.Toplevel):
    def __init__(self, parent, refresh_callback=None):
        super().__init__(parent)
        self.title(tr("recover_deleted_contracts"))
        self.geometry("800x500")
        self.refresh_callback = refresh_callback
        self.session = SessionLocal()
        
        # Add Persistent Status Bar (Bottom) - Reserve before any expanded layout
        user = getattr(parent, 'current_user', None)
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status("Contract Archive Recovery")

        self.create_widgets()
        self.refresh_archive_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)
        
        ttk.Label(main_frame, text=tr("recover_deleted_contracts"), font=("Helvetica", 14, "bold")).pack(pady=10)
        
        self.table_container = ttk.Frame(main_frame)
        self.table_container.pack(fill=BOTH, expand=YES)
        
        self.cols = [
            tr("id"),
            tr("first_name"),
            tr("last_name"),
            tr("type"),
            tr("start_date"),
            tr("end_date"),
            tr("version")
        ]
        
        self.table = None # Init in refresh_archive_data
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="🔄 " + tr("refresh"), command=self.refresh_archive_data, bootstyle=INFO).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="♻️ " + tr("recover"), command=self.do_recovery, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ " + tr("cancel"), command=self.destroy, bootstyle=SECONDARY).pack(side=LEFT, padx=5)

    def refresh_archive_data(self):
        # 1. Clear previous widget residues completely
        for widget in self.table_container.winfo_children():
            widget.destroy()

        # 2. Fetch Data
        from contragest.core.database import ContractArchive
        archives = self.session.query(ContractArchive).order_by(ContractArchive.deleted_at.desc()).all()
        
        row_data = []
        for a in archives:
            row_data.append((
                str(a.id),
                a.first_name or "N/A",
                a.last_name or "N/A",
                a.contract_type or "N/A",
                str(a.start_date) if a.start_date else "N/A",
                str(a.end_date) if a.end_date else "N/A",
                str(a.version or 1)
            ))
            
        # 3. Recreate Table
        from ttkbootstrap.tableview import Tableview
        self.table = Tableview(
            master=self.table_container,
            coldata=self.cols,
            rowdata=row_data,
            paginated=False,
            searchable=True,
            bootstyle=PRIMARY,
            autofit=True
        )
        self.table.pack(fill=BOTH, expand=YES)

    def do_recovery(self):
        selected = self.table.view.selection()
        if not selected:
            Messagebox.show_info(tr("information"), tr("no_archived_contracts"))
            return
            
        count = len(selected)
        msg = tr("recover") + f" ({count})?"
        
        # Use explicit buttons to avoid localization issues in response comparison
        ans = Messagebox.show_question(
            msg, 
            tr("confirmation"),
            buttons=['No:secondary', 'Yes:success']
        )
        
        if ans != 'Yes':
            return
            
        from contragest.features.contracts.service import ContractService
        from contragest.features.auth.service import AuthService
        service = ContractService(self.session)
        auth_service = AuthService()
        success_count = 0
        
        try:
            for item_id in selected:
                item = self.table.view.item(item_id)
                archive_id = int(item['values'][0])
                user_id = getattr(self.master, 'current_user', None)
                service.recover_contract(archive_id, user_id=user_id.id if user_id else None)

                success_count += 1
                
            Messagebox.show_info(f"{success_count} " + tr("contract_recovered"), tr("success"))
            
            if self.refresh_callback:
                self.refresh_callback()
            self.refresh_archive_data()
        except Exception as e:
            self.session.rollback()
            Messagebox.show_error(f"Error recovering contracts: {e}", tr("error"))

    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()
