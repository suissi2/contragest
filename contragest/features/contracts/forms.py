import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import datetime, timedelta
import os
import shutil
from PIL import Image, ImageTk
from tkinter import filedialog
from contragest.core.database import SessionLocal, AppConfig, Employee, Contract, ContractHistory
from contragest.core.i18n import tr, get_lang_manager

class SettingsForm(ttk.Toplevel):
    def __init__(self, parent, refresh_callback=None, initial_tab='application'):
        super().__init__(parent)
        self.title(tr("settings"))
        # Increase height to accommodate all fields and buttons
        self.geometry("480x750")
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

        # --- GLOBAL ACTION BUTTONS ---
        
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="📡 " + tr("test_connection"), command=self.test_email, bootstyle=INFO).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="💾 " + tr("save_settings"), command=self.save_settings, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        
        # Test Trigger Button
        ttk.Button(self, text="🧪 Set Test Alert (2 min)", command=self.prepare_test_alert, bootstyle="outline-warning").pack(pady=(0, 10))

    def test_email(self):
        # Create a temp config object to test with current form values
        from contragest.logic.alerts import EmailService
        
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
        
        service = EmailService(temp_config)
        success, message = service.test_connection()
        
        if success:
            Messagebox.show_info(message, "Connection Test")
        else:
            Messagebox.show_error(message, "Connection Test Failed")

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
    def __init__(self, parent, contract_id=None, user=None, refresh_callback=None):
        super().__init__(parent)
        self.title(tr("contract_info"))
        self.geometry("500x500")
        self.refresh_callback = refresh_callback
        self.contract_id = contract_id
        self.user = user
        self.session = SessionLocal()
        
        self.create_widgets()
        if contract_id:
            self.load_data()

    def create_widgets(self):
        # Container for better padding
        main_container = ttk.Frame(self, padding=20)
        main_container.pack(fill=BOTH, expand=YES)

        anchor_start = get_anchor_start()
        anchor_end = get_anchor_end()

        # Employee Info Section
        emp_group = ttk.Labelframe(main_container, text=tr("employee_info"), padding=15)
        emp_group.pack(fill=X, pady=(0, 15))
        
        # First Name
        row1 = ttk.Frame(emp_group)
        row1.pack(fill=X, pady=5)
        pack_start(ttk.Label(row1, text=tr("first_name") + ":", width=12))
        self.fname_var = ttk.StringVar()
        pack_start(ttk.Entry(row1, textvariable=self.fname_var), expand=True, fill=X, padx=5)
        
        # Last Name
        row2 = ttk.Frame(emp_group)
        row2.pack(fill=X, pady=5)
        pack_start(ttk.Label(row2, text=tr("last_name") + ":", width=12))
        self.lname_var = ttk.StringVar()
        pack_end(ttk.Entry(row2, textvariable=self.lname_var), expand=True, fill=X, padx=5)

        # Contract Info Section
        contract_group = ttk.Labelframe(main_container, text=tr("contract_info"), padding=15)
        contract_group.pack(fill=X)
        
        # Type
        row3 = ttk.Frame(contract_group)
        row3.pack(fill=X, pady=5)
        pack_start(ttk.Label(row3, text=tr("type") + ":", width=12))
        self.type_var = ttk.StringVar()
        types = ["CDI", "CDD", "Stage", "Freelance"]
        combo = ttk.Combobox(row3, textvariable=self.type_var, values=types, state="readonly")
        pack_end(combo, expand=True, fill=X, padx=5)
        combo.current(0)
        
        # Start Date
        row4 = ttk.Frame(contract_group)
        row4.pack(fill=X, pady=5)
        pack_start(ttk.Label(row4, text=tr("start_date") + ":", width=12))
        self.start_date_var = ttk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.start_date_entry = ttk.DateEntry(row4, dateformat="%Y-%m-%d")
        pack_end(self.start_date_entry, expand=True, fill=X, padx=5)
        
        # End Date
        row5 = ttk.Frame(contract_group)
        row5.pack(fill=X, pady=5)
        pack_start(ttk.Label(row5, text=tr("end_date") + ":", width=12))
        
        self.has_end_date = ttk.BooleanVar(value=False)
        self.end_date_entry = ttk.DateEntry(row5, dateformat="%Y-%m-%d")
        
        def toggle_end_date():
            if self.has_end_date.get():
                self.end_date_entry.configure(state="normal")
            else:
                self.end_date_entry.configure(state="disabled")
                
        check = ttk.Checkbutton(row5, variable=self.has_end_date, command=toggle_end_date, bootstyle="round-toggle")
        pack_end(check, padx=5)
        pack_end(self.end_date_entry, expand=True, fill=X, padx=5)
        
        toggle_end_date() # Initial state

        # Buttons
        button_frame = ttk.Frame(main_container)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="💾 " + tr("save"), command=self.save_contract, bootstyle=SUCCESS, width=15).pack(side=LEFT, padx=10, ipady=5)
        
        if self.contract_id:
             ttk.Button(button_frame, text="📜 " + tr("view_history"), command=self.view_history, bootstyle=SECONDARY, width=15).pack(side=LEFT, padx=10, ipady=5)

    def view_history(self):
        if not self.contract_id:
            return
            
        HistoryDialog(self, self.contract_id)

    def load_data(self):
        contract = self.session.query(Contract).filter(Contract.id == self.contract_id).first()
        if contract:
            self.fname_var.set(contract.employee.first_name)
            self.lname_var.set(contract.employee.last_name)
            self.type_var.set(contract.contract_type)
            
            # Use entry.set_date or similar if available, or just entry.entry.delete/insert
            self.start_date_entry.entry.delete(0, END)
            self.start_date_entry.entry.insert(0, str(contract.start_date))
            
            if contract.end_date:
                self.has_end_date.set(True)
                self.end_date_entry.configure(state="normal")
                self.end_date_entry.entry.delete(0, END)
                self.end_date_entry.entry.insert(0, str(contract.end_date))
            else:
                self.has_end_date.set(False)
                self.end_date_entry.configure(state="disabled")

    def save_contract(self):
        try:
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
            from contragest.features.auth.service import AuthService
            auth_service = AuthService()
            service = ContractService(self.session, auth_service=auth_service)
            
            if self.contract_id:
                # Update Existing - Security Check
                
                # 1. Mandatory Justification
                from ttkbootstrap.dialogs import Querybox
                reason = Querybox.get_string("Please provide a reason for this change:", "Justification Required", parent=self)
                if not reason:
                    return # User cancelled or empty
                
                # 2. Role-Based Auth
                if self.user and self.user.role != 'admin':
                    password = Querybox.get_string("Please enter your password to confirm:", "Authentication Required", show='*', parent=self)
                    if not password:
                        return
                        
                    if not auth_service.verify_user_password(self.user.id, password):
                         Messagebox.show_error("Incorrect password. Changes not saved.", "Authentication Failed")
                         return

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
                # New Contract
                # Create Employee first
                employee = Employee(first_name=fname, last_name=lname)
                self.session.add(employee)
                self.session.flush() # Get ID
                
                service.create_contract(
                    employee_id=employee.id,
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
        auth_service = AuthService()
        service = ContractService(self.session, auth_service=auth_service)
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
