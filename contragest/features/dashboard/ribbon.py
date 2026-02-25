import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class RibbonMenu(ttk.Frame):
    def __init__(self, parent, callbacks, auth_service, user):
        super().__init__(parent)
        self.callbacks = callbacks
        self.auth_service = auth_service
        self.user = user
        
        # Style for Ribbon
        self.notebook = ttk.Notebook(self, style='Ribbon.TNotebook')
        self.notebook.pack(fill=X, expand=YES)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        # But we style it to look more integrated
        style = ttk.Style()
        style.configure('Ribbon.TNotebook', padding=0)
        style.configure('Ribbon.TNotebook.Tab', padding=[20, 5], font=('Helvetica', 10, 'bold'))
        
        self.setup_ui()

    def setup_ui(self):
        uid = self.user.id
        
        # 1. Home Tab (General)
        home_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(home_tab, text="🏠 Home")
        self.create_home_actions(home_tab)
        
        # 2. HR Tab (Human Resources)
        # Check view permission on HR components or just always allow dashboard
        hr_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(hr_tab, text="👔 HR")
        self.create_hr_actions(hr_tab)
        
        # 3. Tools Tab (Utilities)
        if self.auth_service.check_access(uid, 'User Management', 'view') or self.auth_service.check_access(uid, 'Audit Log', 'view'):
            tools_tab = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(tools_tab, text="🛠️ Tools")
            self.create_tools_actions(tools_tab)
            
        # 4. Reports Tab
        if self.auth_service.check_access(uid, 'Reports', 'view'):
            reports_tab = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(reports_tab, text="📊 Reports")
            self.create_reports_actions(reports_tab)

    def create_reports_actions(self, parent):
        group = ttk.LabelFrame(parent, text="Reports & Analytics")
        group.pack(side=LEFT, fill=Y, padx=5)
        
        self.add_ribbon_button(group, "📊 Reports", "INFO", lambda: self.callbacks.get('view_reports')('all'))

    def create_home_actions(self, parent):
        nav_group = ttk.LabelFrame(parent, text="Navigation")
        nav_group.pack(side=LEFT, fill=Y, padx=5)
        self.add_ribbon_button(nav_group, "🏠 Dashboard", "INFO", lambda: self.callbacks.get('view_reports')('dashboard'))

        settings_group = ttk.LabelFrame(parent, text="Settings")
        settings_group.pack(side=LEFT, fill=Y, padx=5)
        
        self.add_ribbon_button(settings_group, "🛠️ Application", "LIGHT", lambda: self.callbacks.get('settings')('application'))
        self.add_ribbon_button(settings_group, "🏢 Company", "LIGHT", lambda: self.callbacks.get('settings')('company'))

        session_group = ttk.LabelFrame(parent, text="Session")
        session_group.pack(side=LEFT, fill=Y, padx=5)

        # Action Buttons
        button_container = ttk.Frame(session_group)
        button_container.pack(side=LEFT, padx=5, pady=5)
        ttk.Button(button_container, text="🚪 Logout", bootstyle="outline-warning", command=self.callbacks.get('logout')).pack(side=LEFT, padx=2)
        ttk.Button(button_container, text="❌ Exit", bootstyle="danger", command=self.callbacks.get('exit')).pack(side=LEFT, padx=2)

    def create_hr_actions(self, parent):
        uid = self.user.id
        emp_group = ttk.LabelFrame(parent, text="Employees")
        emp_group.pack(side=LEFT, fill=Y, padx=5)
        if self.auth_service.check_access(uid, 'Employees', 'view'):
            self.add_ribbon_button(emp_group, "👥 Employees", "INFO", lambda: self.callbacks.get('view_reports')('employees'))

        contract_group = ttk.LabelFrame(parent, text="Contract")
        contract_group.pack(side=LEFT, fill=Y, padx=5)
        if self.auth_service.check_access(uid, 'Contracts', 'view'):
            self.add_ribbon_button(contract_group, "📑 Contracts", "INFO", lambda: self.callbacks.get('view_reports')('contracts'))

    def create_tools_actions(self, parent):
        uid = self.user.id
        group = ttk.LabelFrame(parent, text="Administrative")
        group.pack(side=LEFT, fill=Y, padx=5)
        
        if self.auth_service.check_access(uid, 'User Management', 'view'):
            self.add_ribbon_button(group, "👥 Users", "SECONDARY", self.callbacks.get('users'))
        
        if self.auth_service.check_access(uid, 'Audit Log', 'view'):
            self.add_ribbon_button(group, "🕵️ Mouchard", "SECONDARY", self.callbacks.get('mouchard'))

    def _on_tab_changed(self, event):
        try:
            tab_idx = self.notebook.index("current")
            tab_text = self.notebook.tab(tab_idx, "text")
            
            if "Home" in tab_text:
                self.callbacks.get('view_reports')('dashboard')
            elif "HR" in tab_text:
                self.callbacks.get('view_reports')('hr_tab')
            elif "Tools" in tab_text:
                self.callbacks.get('view_reports')('tools')
            elif "Reports" in tab_text:
                self.callbacks.get('view_reports')('reports_tab')
        except Exception as e:
            print(f"Error in ribbon tab change: {e}")

    def add_ribbon_button(self, parent, text, bootstyle, callback):
        btn = ttk.Button(
            parent, 
            text=text, 
            bootstyle=bootstyle, 
            command=callback,
            padding=10
        )
        btn.pack(side=LEFT, padx=5)
        return btn
