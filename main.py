import sys
import os
import subprocess

# Redirect stdout/stderr to devnull when running as a windowed PyInstaller app (console=False)
# This prevents libraries that try to print/log (like paddlex downloader) from crashing the app
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# Patch subprocess.Popen to prevent third-party libraries from flashing cmd windows on Windows
if os.name == 'nt':
    _original_popen = subprocess.Popen
    class HiddenPopen(_original_popen):
        def __init__(self, *args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = 0x08000000 # CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)
    subprocess.Popen = HiddenPopen

import multiprocessing
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    # Enable multiprocessing support for frozen PyInstaller executable
    multiprocessing.freeze_support()
    
    app = QApplication(sys.argv)
    
    # Load dark theme
    base_dir = os.path.dirname(os.path.abspath(__file__))
    res_dir = os.path.join(base_dir, "resources")
    qss_path = os.path.join(res_dir, "dark.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r") as f:
            qss_content = f.read()
            # Replace relative URLs with absolute paths (forward slashes for Qt)
            res_dir_qss = res_dir.replace("\\", "/")
            qss_content = qss_content.replace("url(resources/", f"url({res_dir_qss}/")
            qss_content = qss_content.replace("url(icons/", f"url({res_dir_qss}/")
            app.setStyleSheet(qss_content)
            
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
