import ttkbootstrap as ttk
from contragest.features.dashboard.main_window import MainWindow
from contragest.core.database import SessionLocal
from contragest.features.auth.service import User
import sys

def verify():
    # Setup dummy environment
    db = SessionLocal()
    admin = db.query(User).filter_by(role='admin').first()
    db.close()
    
    if not admin:
        print("Error: No admin user found in database.")
        sys.exit(1)
        
    root = ttk.Window(themename="superhero")
    app = MainWindow(root, admin)
    
    # Check for components
    success = True
    if not hasattr(app, "main_notebook"):
        print("FAILED: main_notebook not found in MainWindow")
        success = False
    else:
        print("SUCCESS: main_notebook found")
        
    if not hasattr(app, "reports_frame"):
        print("FAILED: reports_frame not found in MainWindow")
        success = False
    else:
        print("SUCCESS: reports_frame found")

    if not hasattr(app, "hr_frame"):
        print("FAILED: hr_frame not found in MainWindow")
        success = False
    else:
        print("SUCCESS: hr_frame found")
        
    # Standalone verification is better done manually, 
    # but we've verified the placeholder integration.
            
    if success:
        print("Integration verification PASSED")
    else:
        print("Integration verification FAILED")
    
    # Optional: root.mainloop() if manual check is needed
    # root.destroy() 

if __name__ == "__main__":
    verify()
