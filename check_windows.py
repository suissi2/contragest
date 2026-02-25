
import win32gui

def enum_windows_callback(hwnd, list):
    if win32gui.IsWindowVisible(hwnd):
        window_text = win32gui.GetWindowText(hwnd)
        if window_text:
            list.append(window_text)

windows = []
win32gui.EnumWindows(enum_windows_callback, windows)
print("Visible Windows:")
for win in windows:
    if "Contragest" in win or "Auth" in win or "System" in win:
        print(f"- {win}")
