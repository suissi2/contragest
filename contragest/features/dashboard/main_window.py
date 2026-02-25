import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tableview import Tableview
from ttkbootstrap.dialogs import Messagebox
from contragest.core.i18n import tr, get_lang_manager
from contragest.logic.scheduler import BackgroundScheduler
from contragest.features.contracts.forms import ContractForm, SettingsForm
from contragest.features.dashboard.ribbon import RibbonMenu
from datetime import datetime, date
from contragest.core.database import get_db, Contract
from contragest.logic.alerts import AlertManager
from contragest.features.auth.service import AuthService

from contragest.core.layout import pack_start, pack_end, is_rtl
from contragest.core.system_info import get_pc_info, get_location_and_weather
from PIL import Image, ImageTk
import os

class MainWindow(ttk.Frame):
    def __init__(self, parent, user, logout_callback=None):
        super().__init__(parent)
        self.current_user = user
        self.parent = parent # This is the root window
        self.logout_callback = logout_callback
        self.auth_service = AuthService()
        self.load_initial_language()
        
        self.scheduler = BackgroundScheduler(
            ui_callback_info=self.on_env_data_received,
            ui_callback_alert=self.on_scheduled_alert_triggered
        )
        
        # UI Setup (Ribbon + Content)
        callbacks = {
            'add': self.open_new_contract,
            'edit': self.open_edit_contract,
            'delete': self.delete_contract,
            'refresh': self.refresh_data,
            'recovery': self.open_recovery_manager,
            'users': self.open_user_management,
            'settings': self.open_settings,
            'mouchard': self.open_mouchard,
            'logout': self.handle_logout,
            'exit': self.confirm_exit,
            'view_reports': self.show_reports,
            'send_alerts': self.manual_send_alerts
        }
        self.ribbon = RibbonMenu(self, callbacks, auth_service=self.auth_service, user=user)
        self.ribbon.pack(fill=X, side=TOP)

        # Main Content Area (Notebook for switching views)
        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.pack(fill=BOTH, expand=YES)
        
        # Dashboard Tab (Home/Hero)
        self.dashboard_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.dashboard_frame, text="🏠 Home")
        self.create_home_view()

        # Contracts Tab (Actual Management)
        self.contracts_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.contracts_frame, text="📑 Contracts")
        self.create_contracts_view()

        # HR Tab (Human Resources Workspace)
        self.hr_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.hr_frame, text="👔 HR")
        
        hr_content = ttk.Frame(self.hr_frame)
        hr_content.place(relx=0.5, rely=0.4, anchor=CENTER)
        ttk.Label(hr_content, text="👔 HR Management Hub", font=("Helvetica", 18, "bold")).pack(pady=(0, 10))
        ttk.Label(hr_content, text="Select a tool from the HR Ribbon Menu above to begin.", font=("Helvetica", 12)).pack()

        # Reports window reference (opened on demand as Toplevel)
        self.reports_window = None
        
        # Tools Tab (Administrative Workspace)
        if user.role == 'admin':
            self.tools_frame = ttk.Frame(self.main_notebook)
            self.main_notebook.add(self.tools_frame, text="🛠️ Tools")
            
            # Clean styling to replace dashboard when active
            tools_content = ttk.Frame(self.tools_frame)
            tools_content.place(relx=0.5, rely=0.4, anchor=CENTER)
            ttk.Label(tools_content, text="🛠️ Administrative Tools Area", font=("Helvetica", 18, "bold")).pack(pady=(0, 10))
            ttk.Label(tools_content, text="Select a tool from the Ribbon Menu above to begin.", font=("Helvetica", 12)).pack()
            
        # Reports Tab (Analytics Workspace)
        if user.role == 'admin':
            self.reports_frame = ttk.Frame(self.main_notebook)
            self.main_notebook.add(self.reports_frame, text="📊 Reports")
            
            reports_content = ttk.Frame(self.reports_frame)
            reports_content.place(relx=0.5, rely=0.4, anchor=CENTER)
            ttk.Label(reports_content, text="📊 Reports & Analytics Hub", font=("Helvetica", 18, "bold")).pack(pady=(0, 10))
            ttk.Label(reports_content, text="Select a report type from the Ribbon Menu above to view detailed data.", font=("Helvetica", 12)).pack()
            
        
        # Hide notebook tabs for a Ribbon-sync feel
        style = ttk.Style()
        style.configure('Main.TNotebook', tabposition='n', padding=0)
        style.layout('Main.TNotebook.Tab', []) 
        self.main_notebook.configure(style='Main.TNotebook')
        self.create_status_bar()
        self.status_label.config(text=f"Logged in as: {user.username} ({user.role})")
        
        # Start Clock
        self.update_clock()
        
        # Initialize visual effects
        self.flash_state = False
        self.animate_flash()
        
        # Load data and start services immediately
        self.refresh_data()
        self.scheduler.start()
        
        # Run startup check
        self.after(1000, self.run_startup_check)
        
        AuthService().log_action(user.id, "SESSION_START", "Authenticated access to dashboard")

    def setup_window(self):
        """Applies window-level settings to the root."""
        self.parent.title(tr("app_title"))
        self.parent.state('zoomed') # Maximized for desktop dashboard
        
        # Configure application menu (restored)
        self.create_menu()
        self.parent.config(menu=self.menu_bar)

    def load_initial_language(self):
        from contragest.core.database import SessionLocal, AppConfig
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            lang = config.language if config and config.language else "en"
            get_lang_manager().load_language(lang)
        except:
             pass
        finally:
            session.close()

    def create_menu(self):
        self.menu_bar = ttk.Menu(self.parent)
        menu_bar = self.menu_bar
        
        # File Menu
        file_menu = ttk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="🚪 " + tr("logout") if hasattr(self, "tr") else "🚪 Logout", command=self.handle_logout)
        file_menu.add_separator()
        file_menu.add_command(label="❌ " + tr("exit"), command=self.confirm_exit)
        menu_bar.add_cascade(label=tr("file"), menu=file_menu)
        
        # Contracts Menu
        contract_menu = ttk.Menu(menu_bar, tearoff=0)
        contract_menu.add_command(label="➕ " + tr("new_contract"), command=self.open_new_contract)
        menu_bar.add_cascade(label=tr("contracts"), menu=contract_menu)
        
        # Settings Menu
        settings_menu = ttk.Menu(menu_bar, tearoff=0)
        settings_menu.add_command(label="⚙️ " + tr("configuration"), command=lambda: self.open_settings('application'))
        
        # Utility Submenu
        print(f"DEBUG: Building menu for user: {self.current_user.username}, Role: {self.current_user.role}")
        if self.current_user.role == 'admin':
            print("DEBUG: Admin role detected. Adding Utility menu.")
            utility_menu = ttk.Menu(settings_menu, tearoff=0)
            utility_menu.add_command(label="🔄 " + tr("recover_deleted_contracts"), command=self.open_recovery_manager)
            utility_menu.add_command(label="👥 User Management", command=self.open_user_management)
            settings_menu.add_cascade(label=tr("utility"), menu=utility_menu)
        else:
            print(f"DEBUG: Non-admin role '{self.current_user.role}' detected. Skipping Utility menu.")
        
        menu_bar.add_cascade(label=tr("settings"), menu=settings_menu)
        # Menu will be applied in setup_window

    def create_home_view(self):
        # Top Bar (Stats) - Globally visible in Home
        self.stats_frame = ttk.Frame(self.dashboard_frame, bootstyle=SECONDARY)
        self.stats_frame.pack(fill=X, padx=10, pady=10)
        
        self.lbl_stats = ttk.Label(self.stats_frame, text="", font=("Helvetica", 11), bootstyle="inverse-secondary")
        self.lbl_stats.pack(pady=10)
        
        self.logo_label = ttk.Label(self.stats_frame, bootstyle="inverse-secondary")
        self.logo_label.pack(side=LEFT, padx=20)
        self.load_company_logo()
        
        # Hero Area
        self.hero_frame = ttk.Frame(self.dashboard_frame)
        self.hero_frame.pack(fill=BOTH, expand=YES)
        
        hero_content = ttk.Frame(self.hero_frame)
        hero_content.place(relx=0.5, rely=0.4, anchor=CENTER)
        
        self.hero_logo = ttk.Label(hero_content)
        self.hero_logo.pack()
        self.load_company_logo(label=self.hero_logo, size=(300, 300))
        
        ttk.Label(hero_content, text="Contragest", font=("Helvetica", 24, "bold")).pack(pady=20)
        ttk.Label(hero_content, text="Professional Contract Management System", font=("Helvetica", 14)).pack()

    def create_contracts_view(self):
        # Toolbar (Cleaned)
        toolbar = ttk.Frame(self.contracts_frame)
        toolbar.pack(fill=X, padx=10, pady=5)
        
        self.btn_add_contract = ttk.Button(toolbar, text="➕ " + tr("new_contract"), command=self.open_new_contract, bootstyle=SUCCESS)
        self.btn_add_contract.pack(side=LEFT, padx=5)
        
        self.btn_send_alerts = ttk.Button(toolbar, text="📧 " + tr("send_alerts"), command=self.manual_send_alerts, bootstyle=SECONDARY)
        pack_end(self.btn_send_alerts, padx=5)

        # Treeview Container (Restored)
        self.tree_frame = ttk.Frame(self.contracts_frame)
        self.tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        self.cols = [
            tr("edit"), tr("delete"), tr("id"), tr("first_name"), tr("last_name"), 
            tr("type"), tr("start_date"), tr("end_date"), tr("seniority"),
            tr("days_left"), tr("status")
        ]
        self.table = None 
        
        # Reverse columns for RTL? Treeviews in RTL usually keep column order but align text right.
        # But logically, column 1 should be on right. Tkinter Treeview doesn't natively flip columns easily.
        # We will keep LTR column order for simplicity unless strictly required, 
        # but we can set anchor='e' for cells if RTL.
        
        self.table = None # Created in refresh_data

    def refresh_data(self):
        print("DEBUG: Refreshing data...")
        from contragest.core.database import SessionLocal, AppConfig  # Import here to ensure clean session
        db = SessionLocal()
        try:
            config = db.query(AppConfig).first()
            contracts = db.query(Contract).all()
            print(f"DEBUG: Found {len(contracts)} contracts.")
            
            row_data = []
            active_count = 0
            expiring_count = 0
            expired_count = 0
            today = date.today()
            
            for c in contracts:
                print(f"DEBUG: Processing contract {c.id} for {c.employee.first_name}")
                status_display = tr("active")
                
                # Action Icons
                edit_icon = "✏️"
                delete_icon = "🗑️"
                
                if c.end_date:
                    days_left = (c.end_date - today).days
                    if days_left < 0:
                        status_key = "expired"
                        status_display = tr("expired")
                        expired_count += 1
                    elif days_left <= (config.alert_threshold_days if config else 30):
                        status_key = "expiring_soon"
                        status_display = tr("expiring_soon")
                        expiring_count += 1
                    else:
                        active_count += 1
                else:
                    days_left = None
                    active_count += 1 # CDI
                
                days_left_display = str(days_left) if days_left is not None else "∞"
                
                # Calculate Seniority
                seniority_display = self.calculate_seniority(c.start_date)
                
                row_data.append((
                    edit_icon,
                    delete_icon,
                    str(c.id),
                    c.employee.first_name,
                    c.employee.last_name,
                    c.contract_type,
                    str(c.start_date),
                    str(c.end_date) if c.end_date else "N/A",
                    seniority_display,
                    days_left_display,
                    status_display
                ))
            
            print(f"DEBUG: Loading table with {len(row_data)} rows.")
            
            # Recreate table to avoid update bugs
            if self.table:
                self.table.destroy()
            
            # Ensure we're clean
            for widget in self.tree_frame.winfo_children():
                widget.destroy()

            self.table = Tableview(
                master=self.tree_frame,
                coldata=self.cols,
                rowdata=row_data,
                paginated=False,
                searchable=True,
                bootstyle=PRIMARY,
                autofit=True,
                autoalign=False,
            )
            self.table.pack(fill=BOTH, expand=True)
            self.table.autofit_columns() 
            
            self.table.view.bind("<Double-1>", lambda e: self.open_edit_contract())
            self.table.view.bind("<ButtonRelease-1>", self.on_table_click)
            
            # Apply tags for row coloring
            for item_id in self.table.view.get_children():
                values = self.table.view.item(item_id, 'values')
                if not values: continue
                # Status is last column
                status_text = values[-1]
                
                # Check translated status texts
                if status_text == tr("expired"):
                    self.table.view.item(item_id, tags=('danger',))
                elif status_text == tr("expiring_soon"):
                    self.table.view.item(item_id, tags=('warning',))
                else:
                    self.table.view.item(item_id, tags=('success',))
            
            stats_text = f"{tr('active')}: {active_count} | {tr('expiring_soon')}: {expiring_count} | {tr('expired')}: {expired_count}"
            self.lbl_stats.config(text=stats_text)
            
            # Refresh Reports View if it exists and is active
            if hasattr(self, '_reports_view_ref') and self._reports_view_ref.winfo_exists():
                if hasattr(self._reports_view_ref, 'refresh_all'):
                    self._reports_view_ref.refresh_all()
                else:
                    self._reports_view_ref.setup_ui()
            
            # Update Send Alerts Button State
            if config and all([config.smtp_server, config.smtp_user, config.smtp_password, config.notification_email]):
                self.btn_send_alerts.configure(state="normal")
            else:
                self.btn_send_alerts.configure(state="disabled")

            # Refresh company logos
            self.load_company_logo()
            if hasattr(self, 'hero_logo'):
                self.load_company_logo(label=self.hero_logo, size=(300, 300))

            print("DEBUG: Refresh complete.")
            
        except Exception as e:
            print(f"ERROR in refresh_data: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()

    def create_status_bar(self):
        """Creates a sophisticated bottom toolbar."""
        self.status_bar = ttk.Frame(self, bootstyle=DARK)
        self.status_bar.pack(side=BOTTOM, fill=X)
        
        # PC Info Section
        pc_name, local_ip = get_pc_info()
        self.lbl_pc = ttk.Label(self.status_bar, text=f"💻 {pc_name} ({local_ip})", font=("Helvetica", 9), bootstyle="inverse-dark")
        self.lbl_pc.pack(side=LEFT, padx=10, pady=2)
        
        # Session Status Section
        self.status_label = ttk.Label(self.status_bar, text="", font=("Helvetica", 9), bootstyle="inverse-dark")
        self.status_label.pack(side=LEFT, padx=10, pady=2)
        
        ttk.Separator(self.status_bar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5, pady=2)
        
        # Location & Weather Section
        self.lbl_env = ttk.Label(self.status_bar, text="🌍 " + tr("loading") + "...", font=("Helvetica", 9), bootstyle="inverse-dark")
        self.lbl_env.pack(side=LEFT, padx=10, pady=2)
        
        ttk.Separator(self.status_bar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5, pady=2)
        
        # Clock Section (Flush Right)
        self.lbl_clock = ttk.Label(self.status_bar, text="", font=("Helvetica", 9, "bold"), bootstyle="inverse-dark")
        self.lbl_clock.pack(side=RIGHT, padx=10, pady=2)

        ttk.Sizegrip(self.status_bar).pack(side=RIGHT)

    def update_clock(self):
        """Updates the clock in the status bar every second."""
        if not self.winfo_exists():
            return
            
        now = datetime.now()
        self.lbl_clock.config(text=now.strftime("📅 %d/%m/%Y   🕒 %H:%M:%S"))
        self.after(1000, self.update_clock)

    def on_env_data_received(self, location, temp):
        """Callback from background thread to update environmental UI."""
        if self.winfo_exists() and hasattr(self, 'lbl_env') and self.lbl_env.winfo_exists():
            self.after(0, lambda: self.lbl_env.config(text=f"🌍 {location}   🌡️ {temp}"))

    def confirm_exit(self):
        """Prompt user with a styled dialog before exiting."""
        ans = Messagebox.show_question(
            "Are you sure you want to exit the application?", 
            "Confirm Exit", 
            buttons=['No:secondary', 'Yes:danger']
        )
        if ans == 'Yes':
            self.quit()

    def handle_logout(self):
        """Prompt user with a styled dialog before logging out."""
        ans = Messagebox.show_question(
            "Are you sure you want to log out of your session?", 
            "Confirm Logout", 
            buttons=['No:secondary', 'Yes:warning']
        )
        if ans != 'Yes':
            return
            
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.stop()
        self.current_user = None
        if self.logout_callback:
            self.logout_callback()

    def __del__(self):
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.stop()

    def animate_flash(self):
        """Creates a smooth flashing effect for critical status rows."""
        if not self.winfo_exists():
            return
            
        self.flash_state = not self.flash_state
        
        if self.table and self.table.view:
            # Alternate colors for danger and warning tags
            if self.flash_state:
                # Vivid colors
                self.table.view.tag_configure('danger', background='#ff4444', foreground='white')
                self.table.view.tag_configure('warning', background='#ffbb33', foreground='black')
            else:
                # Standard colors from Superhero theme (roughly)
                self.table.view.tag_configure('danger', background='#d9534f', foreground='white')
                self.table.view.tag_configure('warning', background='#f0ad4e', foreground='white')
        
        # Schedule next flash
        self.after(800, self.animate_flash)

    def on_table_click(self, event):
        """Detects if Edit or Delete icons were clicked."""
        region = self.table.view.identify_region(event.x, event.y)
        if region != "cell":
            return
            
        row_id = self.table.view.identify_row(event.y)
        column = self.table.view.identify_column(event.x)
        
        if not row_id:
            return
            
        # Ensure the row is selected and focused for the subsequent actions
        self.table.view.selection_set(row_id)
        self.table.view.focus(row_id)
        
        if column == "#1": # Edit icon
            self.open_edit_contract()
        elif column == "#2": # Delete icon
            self.delete_contract()

    def calculate_deletion_password(self):
        """
        Formula: ((day + month + (year % 100)) * 2) - 10
        For 11/02/2026: (11 + 2 + 26) * 2 - 10 = 39 * 2 - 10 = 78 - 10 = 68
        Note: The user example said 11/02/2026 -> (11+2+26)*2-10.
        """
        now = datetime.now()
        day = now.day
        month = now.month
        year_short = now.year % 100
        password = ((day + month + year_short) * 2) - 10
        return str(password)

    def on_scheduled_alert_triggered(self, count, success):
        """Callback from background thread when a scheduled alert runs."""
        if success:
            print(f"DEBUG UI: Background alert successfully sent for {count} contracts.")
        else:
            # Maybe show a toast or small notification instead of a blocking Messagebox 
            # for "scheduled" background alerts? 
            # But the user might want a clear warning if it fails.
            self.after(0, lambda: Messagebox.show_error(tr("email_failed").format(count=count), tr("error")))

    def run_startup_check(self):
        from contragest.core.database import SessionLocal, AppConfig
        from contragest.core.logging import setup_logger
        logger = setup_logger("main_window")
        
        db = SessionLocal()
        try:
            config = db.query(AppConfig).first()
            if not config or not config.automatic_alerts_enabled:
                logger.info("Automatic alerts disabled in config. Skipping startup check.")
                return
            
            now = datetime.now()
            today_date = now.date()
            
            # Check if an alert was already sent today
            if config.last_alert_date == today_date:
                logger.info("Alert already sent or checked for today. Skipping startup check.")
                return

            # Refinement: Only run startup check if current time is >= alert time
            try:
                alert_time = datetime.strptime(config.alert_time, "%H:%M").time()
                scheduled_datetime = datetime.combine(today_date, alert_time)
                
                if now < scheduled_datetime:
                    logger.info(f"Startup check before scheduled time ({config.alert_time}). Skipping to allow precise scheduler to run later.")
                    return
            except Exception as e:
                logger.error(f"Error in startup check time parsing: {e}")
                
        finally:
            db.close()

        alert_manager = AlertManager()
        # Startup check counts as an automated check
        logger.info("Running automated startup check...")
        count, sent_success = alert_manager.check_and_notify(is_automated=True)
        if count > 0:
            if sent_success:
                Messagebox.show_warning(f"Sent alerts for {count} expiring contracts!", "Expiration Alert")
            else:
                Messagebox.show_error(tr("email_failed").format(count=count), tr("error"))
    
    @AuthService.require_permission('Contracts', 'view')
    def manual_send_alerts(self):
        from contragest.core.logging import setup_logger
        logger = setup_logger("main_window")
        logger.info("Manual alert trigger initiated by user.")
        
        alert_manager = AlertManager()
        count, sent_success = alert_manager.check_and_notify()
        if count > 0:
            if sent_success:
                Messagebox.show_info(tr("alerts_sent").format(count=count), tr("success"))
            else:
                Messagebox.show_error(tr("email_failed").format(count=count), tr("error"))
        else:
            Messagebox.show_info(tr("no_expiring_contracts"), tr("information"))

    @AuthService.require_permission('Contracts', 'add')
    def open_new_contract(self):
        ContractForm(self, user=self.current_user, refresh_callback=self.refresh_data)

    @AuthService.require_permission('Settings', 'view')
    def open_settings(self, initial_tab='application'):
        if initial_tab == 'company':
            from contragest.features.company_manager.ui import CompanyManagerWindow
            CompanyManagerWindow(self)
        else:
            SettingsForm(self, refresh_callback=self.refresh_data, initial_tab=initial_tab)

    @AuthService.require_permission('Contracts', 'delete')
    def open_recovery_manager(self):
        # Security Password Check
        correct_pwd = self.calculate_deletion_password()
        from ttkbootstrap.dialogs import Querybox
        password_input = Querybox.get_string(
            prompt=tr("enter_password"),
            title=tr("password_title"),
            parent=self,
            initialvalue=""
        )
        
        if password_input != correct_pwd:
            if password_input is not None:
                Messagebox.show_error(tr("incorrect_password"), tr("error"))
            return
            
        from contragest.features.contracts.forms import RecoveryForm
        RecoveryForm(self, refresh_callback=self.refresh_data)

    @AuthService.require_permission('User Management', 'view')
    def open_user_management(self):
        from contragest.features.auth.user_management import UserManagementWindow
        UserManagementWindow(self, self.current_user)

    @AuthService.require_permission('Contracts', 'edit')
    def open_edit_contract(self):
        contract_id = None
        
        # 1. Try Dashboard table (if visible)
        if self.table:
            selected = self.table.view.selection()
            if selected:
                item = self.table.view.item(selected[0])
                contract_id = int(item['values'][2]) # ID is now 3rd column
        
        # 2. Try Reports view (if active)
        if contract_id is None and hasattr(self, '_reports_view_ref'):
            contract_id = self._reports_view_ref.get_selected_contract_id()
            
        if contract_id is None:
            Messagebox.show_info(tr("select_contract_to_edit"), tr("information"))
            return
        
        ContractForm(self, contract_id=contract_id, user=self.current_user, refresh_callback=self.refresh_data)

    @AuthService.require_permission('Contracts', 'delete')
    def delete_contract(self):
        contract_id = None
        
        # 1. Try Dashboard table
        if self.table:
            selected = self.table.view.selection()
            if selected:
                item = self.table.view.item(selected[0])
                contract_id = int(item['values'][2])
        
        # 2. Try Reports view
        if contract_id is None and hasattr(self, '_reports_view_ref'):
            contract_id = self._reports_view_ref.get_selected_contract_id()

        if contract_id is None:
            Messagebox.show_info(tr("select_contract_to_delete"), tr("information"))
            return
        
        correct_pwd = self.calculate_deletion_password()
        print(f"DEBUG UI: Expected password: {correct_pwd}")
        
        from ttkbootstrap.dialogs import Querybox
        password_input = Querybox.get_string(
            prompt=tr("enter_password"),
            title=tr("password_title"),
            parent=self,
            initialvalue=""
        )
        print(f"DEBUG UI: Password input: {password_input}")
        
        if password_input != correct_pwd:
            if password_input is not None:
                Messagebox.show_error(tr("incorrect_password"), tr("error"))
            return

        # Explicitly define buttons to avoid localization issues in response comparison
        ans = Messagebox.show_question(
            tr("confirm_delete_contract"), 
            tr("confirmation"), 
            buttons=['No:secondary', 'Yes:danger']
        )
        if ans != 'Yes':
            return
            
        from contragest.core.database import SessionLocal
        from contragest.features.contracts.service import ContractService
        
        db = SessionLocal()
        try:
            service = ContractService(db)
            service.delete_contract(contract_id, user_id=self.current_user.id)
            
            self.refresh_data()
            Messagebox.show_info(tr("contract_deleted"), tr("success"))
        except Exception as e:
            db.rollback()
            Messagebox.show_error(f"Error deleting contract: {e}", tr("error"))
        finally:
            db.close()

    def calculate_seniority(self, start_date: date) -> str:
        """
        Calculates the seniority since the start date in months and days.
        Uses relativedelta for accurate handling of month lengths and leap years.
        """
        if not start_date:
            return "-"
        
        try:
            today = date.today()
            # If start_date is in the future, seniority is 0
            if start_date > today:
                return f"0{tr('months')} 0{tr('days')}"
                
            # Calculate total months accurately without third-party libs
            years = today.year - start_date.year
            months = today.month - start_date.month
            total_months = years * 12 + months
            
            if today.day < start_date.day:
                total_months -= 1
                import calendar
                prev_month_year = today.year if today.month > 1 else today.year - 1
                prev_month = today.month - 1 if today.month > 1 else 12
                _, last_month_days = calendar.monthrange(prev_month_year, prev_month)
                days = last_month_days - start_date.day + today.day
            else:
                days = today.day - start_date.day
            
            return f"{total_months}{tr('months')} {days}{tr('days')}"
        except Exception as e:
            print(f"Error calculating seniority: {e}")
            return "N/A"

    def load_company_logo(self, label=None, size=(40, 40)):
        if label is None:
            label = self.logo_label
            
        from contragest.core.database import SessionLocal, AppConfig
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            if config and config.company_logo_path and os.path.exists(config.company_logo_path):
                img = Image.open(config.company_logo_path)
                img.thumbnail(size)
                photo = ImageTk.PhotoImage(img)
                # Keep reference to avoid garbage collection
                label.config(image=photo)
                label.image = photo 
                if label == self.logo_label:
                    self.photo = photo
        except Exception as e:
            print(f"Error loading logo in MainWindow: {e}")
        finally:
            session.close()

    def show_reports(self, sub_tab='all'):
        """Opens a standalone Reports window (Toplevel)."""
        if sub_tab == 'dashboard':
            self.main_notebook.select(self.dashboard_frame)
            return
        
        if sub_tab == 'contracts':
            self.main_notebook.select(self.contracts_frame)
            return

        if sub_tab == 'tools':
            if hasattr(self, 'tools_frame'):
                self.main_notebook.select(self.tools_frame)
            return

        if sub_tab == 'reports_tab':
            if hasattr(self, 'reports_frame'):
                self.main_notebook.select(self.reports_frame)
            return

        if sub_tab == 'hr_tab':
            if hasattr(self, 'hr_frame'):
                self.main_notebook.select(self.hr_frame)
            return

        if sub_tab == 'employees':
            # Open standalone reports window and select Employees tab
            self.show_reports('all')
            if hasattr(self, '_reports_view_ref'):
                self._reports_view_ref.notebook.select(2) # Employees tab
            return

        # Open or focus the Reports window
        if self.reports_window and self.reports_window.winfo_exists():
            self.reports_window.lift()
            self.reports_window.focus_force()
        else:
            self.reports_window = ttk.Toplevel(self)
            self.reports_window.title("📊 Reports")
            self.reports_window.geometry("1200x700")
            self.reports_window.resizable(True, True)
            
            from contragest.features.reports.reports_view import ReportsView
            reports_view = ReportsView(self.reports_window)
            reports_view.pack(fill='both', expand=True)
            
            # Store reference for sub-tab selection
            self._reports_view_ref = reports_view
        
        # Select the requested sub-tab
        tab_map = {
            'users': 0,
            'spy': 1,
            'employees': 2,
            'contracts': 3
        }
        
        if hasattr(self, '_reports_view_ref'):
            if sub_tab in tab_map:
                self._reports_view_ref.notebook.select(tab_map[sub_tab])
            elif sub_tab == 'all':
                self._reports_view_ref.notebook.select(0)

    @AuthService.require_permission('Audit Log', 'view')
    def open_mouchard(self):
        from contragest.features.auth.mouchard_window import MouchardWindow
        from contragest.features.auth.service import AuthService
        MouchardWindow(self, AuthService(), self.current_user)

