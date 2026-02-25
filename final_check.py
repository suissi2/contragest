
try:
    from contragest.features.dashboard.main_window import MainWindow
    print("MainWindow import successful.")
except Exception as e:
    print(f"MainWindow import failed: {e}")
    import traceback
    traceback.print_exc()
