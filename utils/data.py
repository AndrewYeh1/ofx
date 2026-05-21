from typing import List
import pandas as pd
from PyQt6.QtGui import QPixmap

class PageData:
    def __init__(self, page_num: int, bounding_boxes: List[List[int]], pixmap: QPixmap, df: pd.DataFrame, processing_status: str):
        self.page_num = page_num
        self.bounding_boxes = bounding_boxes # [[x1, y1, x2, y2], ...]
        self.pixmap = pixmap
        self.df = df
        self.processing_status = processing_status
        self.column_mappings = None
        self.disabled_rows = None
