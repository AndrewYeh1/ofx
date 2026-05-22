import sys
import os
import multiprocessing
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    # Enable multiprocessing support for frozen PyInstaller executable
    multiprocessing.freeze_support()
    
    app = QApplication(sys.argv)
    
    # Load dark theme
    qss_path = os.path.join(os.path.dirname(__file__), "resources", "dark.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r") as f:
            app.setStyleSheet(f.read())
            
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
