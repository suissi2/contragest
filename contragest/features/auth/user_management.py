import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from contragest.features.auth.service import AuthService
from contragest.lib.auth_core.ui.management import UserManagementPanel
from contragest.core.gui_utils import center_window
from contragest.core.i18n import tr

class UserManagementWindow(ttk.Toplevel):
    def __init__(self, parent, current_user):
        super().__init__(parent)
        self.title(tr("user_management_title"))
        self.geometry("900x600")
        self.current_user = current_user
        self.auth_service = AuthService() # Adapter
        
        self.setup_ui()
        self.center_window()

    def center_window(self):
        center_window(self)

    def setup_ui(self):
        # Header
        header = ttk.Frame(self, bootstyle=SECONDARY, padding=10)
        header.pack(fill=X)
        ttk.Label(header, text=tr("user_management_title"), font=("Helvetica", 14, "bold"), bootstyle="inverse-secondary").pack(side=LEFT)
        
        # Embed reusable panel
        self.panel = UserManagementPanel(self, self.auth_service, self.current_user)
        self.panel.pack(fill=BOTH, expand=YES, padx=10, pady=10)

if __name__ == "__main__":
    # Internal test
    from contragest.core.database import SessionLocal
    from contragest.features.auth.service import User
    
    db = SessionLocal()
    admin = db.query(User).filter_by(role='admin').first()
    db.close()
    
    root = ttk.Window(themename="superhero")
    if admin:
        UserManagementWindow(root, admin)
        root.mainloop()
    else:
        print("No admin user found for testing.")
