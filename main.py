import sys
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from contragest.core.gui_utils import center_window
from contragest.features.auth.login_window import AuthApp
from contragest.core.database import init_db
from contragest.features.auth.service import init_db as init_auth_db

class AppController:
    def __init__(self):
        self.root = ttk.Window(
            title="Contragest",
            themename="superhero",
            resizable=(True, True)
        )
        self.current_frame = None
        self.current_user = None

    def center_window(self, width, height):
        center_window(self.root, width, height)

    def show_login(self):
        if self.current_frame:
            self.current_frame.destroy()
        
        from contragest.features.auth.login_window import AuthApp
        self.root.title("Secure Auth System")
        self.root.state('normal')
        self.root.resizable(False, False)
        self.center_window(500, 650)
        self.root.config(menu="") # Remove dashboard menu if returning from logout
        
        self.current_frame = AuthApp(self.root, success_callback=self.on_login_success)
        self.current_frame.pack(fill=BOTH, expand=YES)

    def on_login_success(self, user):
        self.current_user = user
        self.show_dashboard()

    def show_dashboard(self):
        if self.current_frame:
            self.current_frame.destroy()
        
        from contragest.features.dashboard.main_window import MainWindow
        self.root.resizable(True, True)
        self.current_frame = MainWindow(self.root, self.current_user, logout_callback=self.show_login)
        self.current_frame.pack(fill=BOTH, expand=YES)
        
        # Apply window-level dashboard settings
        self.current_frame.setup_window()

    def run(self):
        self.show_login()
        self.root.mainloop()

def main():
    print("Initializing Contragest...")
    init_auth_db()
    init_db()
    
    # Sync roles (Migration)
    from contragest.features.auth.service import AuthService
    AuthService().sync_legacy_roles()
    
    print("Databases initialized.")

    controller = AppController()
    controller.run()

if __name__ == "__main__":
    main()
