from PyQt6.QtCore import pyqtSignal, QThread

import camelot
import pandas as pd
import tabulate

class DataDetectionWorker(QThread):
    result_ready = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.df = None
        self.path = None
        self.bbox = None
        self.page_num = 0
    
    def import_path(self, path: str):
        self.path = path
    
    def set_page_num(self, page_num: int):
        self.page_num = page_num
    
    def set_bbox(self, bbox: list, page_height_px: int, render_dpi: int = 300):
        """Convert pixel coords (top-left origin) to Camelot PDF points (bottom-left origin).
        
        Args:
            bbox: list of [x1, y1, x2, y2] in pixel coordinates
            page_height_px: height of the rendered image in pixels
            render_dpi: DPI used to render the PDF image (must match what was used in get_pixmap)
        """
        scale = 72.0 / render_dpi  # PDF points per pixel
        page_h_pts = page_height_px * scale  # Page height in PDF points
        
        self.bbox = []
        for box in bbox:
            x1, y1, x2, y2 = box['coordinate']
            # Scale to PDF points
            px1 = x1 * scale
            px2 = x2 * scale
            # Flip Y: Camelot Y=0 is bottom of page
            py1 = page_h_pts - (y2 * scale)  # top-left y2 becomes bottom-left y1
            py2 = page_h_pts - (y1 * scale)  # top-left y1 becomes bottom-left y2
            self.bbox.append(f"{px1},{py1},{px2},{py2}")

    def run(self):
        tables = camelot.read_pdf(
            self.path,
            pages=str(self.page_num),
            flavor="stream",
            table_areas=self.bbox
        )

        if tables.n > 0:
            self.df = pd.concat([t.df for t in tables], ignore_index=True)
            self.result_ready.emit(True)
        else:
            self.result_ready.emit(False)
