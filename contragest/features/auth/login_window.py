import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from contragest.features.auth.service import AuthService
from contragest.lib.auth_core.ui.login import AuthLoginWindow
from contragest.core.gui_utils import center_window

class AuthApp(ttk.Frame):
    def __init__(self, master, success_callback):
        super().__init__(master, padding=20)
        self.pack(fill=BOTH, expand=YES)
        
        self.auth_service = AuthService() # This is now our Adapter
        self.success_callback = success_callback
        
        # Embed the reusable login window
        self.login_ui = AuthLoginWindow(
            master=self, 
            auth_service=self.auth_service, 
            on_success=self.on_login_success,
            title="Contragest Login"
        )
        self.login_ui.pack(fill=BOTH, expand=YES)
        
        # Apply custom styling or additional widgets if needed
        # (The reusable window is basic, we might want to wrap it in a nice frame or add Logo)
        
    def on_login_success(self, user):
        # The core returns the user object.
        # We pass it to the main app callback
        self.success_callback(user)

if __name__ == "__main__":
    root = ttk.Window(themename="superhero")
    app = AuthApp(root, lambda u: print(f"Logged in: {u.username}"))
    root.mainloop()
