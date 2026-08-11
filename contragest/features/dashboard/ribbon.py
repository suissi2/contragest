import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from contragest.core.i18n import tr
from contragest.core.gui_utils import DesignTokens, apply_premium_style

class RibbonMenu(ttk.Frame):
    def __init__(self, parent, callbacks, auth_service, user):
        super().__init__(parent)
        self.callbacks = callbacks
        self.auth_service = auth_service
        self.user = user
        self.buttons = []
        
        # Style for Ribbon
        self.notebook = ttk.Notebook(self, style='Ribbon.TNotebook')
        self.notebook.pack(fill=X, expand=YES)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        style = ttk.Style()
        apply_premium_style(style)
        # Premium Styling for Ribbon Tabs
        style.configure('Ribbon.TNotebook', padding=0, background=DesignTokens.BG_APP)
        style.configure('Ribbon.TNotebook.Tab', 
                        padding=[20, 8], 
                        font=(DesignTokens.FONT_PRIMARY, 10, 'bold'),
                        background=DesignTokens.BG_APP,
                        foreground=DesignTokens.TEXT_MUTED)
        style.map('Ribbon.TNotebook.Tab',
                  background=[('selected', DesignTokens.SURFACE)],
                  foreground=[('selected', DesignTokens.PRIMARY)])
        
        self.setup_ui()

    def setup_ui(self):
        uid = self.user.id
        
        # Define Tabs
        self.tabs = {}
        
        # 1. Home Tab
        home_tab = ttk.Frame(self.notebook, padding=(20, 15))
        self.notebook.add(home_tab, text="  HOME  ")
        self.create_home_actions(home_tab)
        
        # 2. HR Tab
        hr_tab = ttk.Frame(self.notebook, padding=(20, 15))
        self.notebook.add(hr_tab, text="  HUMAN RESOURCES  ")
        self.create_hr_actions(hr_tab)
        
        # 3. Tools Tab
        if self.auth_service.check_access(uid, 'User Management', 'view') or self.auth_service.check_access(uid, 'Audit Log', 'view'):
            tools_tab = ttk.Frame(self.notebook, padding=(20, 15))
            self.notebook.add(tools_tab, text="  UTILITIES  ")
            self.create_tools_actions(tools_tab)
            
        # 4. Reports Tab
        if self.auth_service.check_access(uid, 'Reports', 'view'):
            reports_tab = ttk.Frame(self.notebook, padding=(20, 15))
            self.notebook.add(reports_tab, text="  ANALYTICS  ")
            self.create_reports_actions(reports_tab)

    def create_home_actions(self, parent):
        # Using custom frame for grouping to allow more styling control than LabelFrame
        nav_group = self.create_ribbon_group(parent, "NAVIGATION")
        self.add_ribbon_button(nav_group, "🏠 DASHBOARD", "info", lambda: self.callbacks.get('view_reports')('dashboard'))

        settings_group = self.create_ribbon_group(parent, "SETTINGS")
        self.add_ribbon_button(settings_group, "🛠️ APP CONFIG", "secondary", lambda: self.callbacks.get('settings')('application'))
        self.add_ribbon_button(settings_group, "🏢 COMPANY", "secondary", lambda: self.callbacks.get('settings')('company'))

        session_group = self.create_ribbon_group(parent, "SESSION")
        self.add_ribbon_button(session_group, "🚪 LOGOUT", "warning-outline", self.callbacks.get('logout'))
        self.add_ribbon_button(session_group, "❌ EXIT", "danger", self.callbacks.get('exit'))

    def create_hr_actions(self, parent):
        uid = self.user.id
        emp_group = self.create_ribbon_group(parent, "EMPLOYEES")
        if self.auth_service.check_access(uid, 'Employees', 'view'):
            self.add_ribbon_button(emp_group, "🌳 HIERARCHY", "info", self.callbacks.get('employee_manager'))

        contract_group = self.create_ribbon_group(parent, "CONTRACTS")
        if self.auth_service.check_access(uid, 'Contracts', 'view'):
            self.add_ribbon_button(contract_group, "📑 MANAGEMENT", "info", lambda: self.callbacks.get('view_reports')('contracts'))

        pointage_group = self.create_ribbon_group(parent, "ATTENDANCE")
        self.add_ribbon_button(pointage_group, "⏱️ POINTAGE", "info", self.callbacks.get('pointage'))
        self.add_ribbon_button(pointage_group, "📱 CHRONOS DASH", "success", self.callbacks.get('chronos'))

    def create_tools_actions(self, parent):
        uid = self.user.id
        admin_group = self.create_ribbon_group(parent, "ADMINISTRATION")
        
        if self.auth_service.check_access(uid, 'User Management', 'view'):
            self.add_ribbon_button(admin_group, "👥 USERS", "secondary", self.callbacks.get('users'))
        
        if self.auth_service.check_access(uid, 'Audit Log', 'view'):
            self.add_ribbon_button(admin_group, "🕵️ AUDIT LOG", "secondary", self.callbacks.get('mouchard'))

    def create_reports_actions(self, parent):
        analytics_group = self.create_ribbon_group(parent, "ANALYTICS")
        self.add_ribbon_button(analytics_group, "📊 ALL REPORTS", "info", lambda: self.callbacks.get('view_reports')('all'))

    def create_ribbon_group(self, parent, label):
        """Creates a styled group for ribbon items."""
        group_frame = ttk.Frame(parent)
        group_frame.pack(side=LEFT, fill=Y, padx=10)
        
        content_frame = ttk.Frame(group_frame)
        content_frame.pack(side=TOP, fill=BOTH, expand=YES)
        
        lbl = ttk.Label(group_frame, text=label, font=(DesignTokens.FONT_PRIMARY, 7, 'bold'), foreground=DesignTokens.TEXT)
        lbl.pack(side=BOTTOM, pady=(6, 0))
        
        # Separator for vertical visual cue
        sep = ttk.Separator(parent, orient=VERTICAL)
        sep.pack(side=LEFT, fill=Y, padx=2, pady=10)
        
        return content_frame

    def add_ribbon_button(self, parent, text, bootstyle, callback):
        """Adds a button with hover animation effects."""
        btn = ttk.Button(
            parent, 
            text=text, 
            bootstyle=bootstyle, 
            command=callback,
            padding=(25, 12)
        )
        btn.pack(side=LEFT, padx=10, pady=10)
        
        # Hover Animations
        def on_enter(e):
            if 'outline' in bootstyle:
                btn.configure(bootstyle=bootstyle.replace('-outline', ''))
            else:
                # Slight highlight for solid buttons
                btn.configure(bootstyle=f"light-{bootstyle}" if "light" not in bootstyle else bootstyle)
                
        def on_leave(e):
            btn.configure(bootstyle=bootstyle)
            
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        self.buttons.append(btn)
        return btn

    def _on_tab_changed(self, event):
        try:
            tab_idx = self.notebook.index("current")
            tab_text = self.notebook.tab(tab_idx, "text")
            
            if "HOME" in tab_text:
                self.callbacks.get('view_reports')('dashboard')
            elif "HUMAN RESOURCES" in tab_text:
                self.callbacks.get('view_reports')('hr_tab')
            elif "UTILITIES" in tab_text:
                self.callbacks.get('view_reports')('tools')
            elif "ANALYTICS" in tab_text:
                self.callbacks.get('view_reports')('reports_tab')
        except Exception as e:
            print(f"Error in ribbon tab change: {e}")
