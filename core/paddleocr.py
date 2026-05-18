import os
# Workarounds for PaddleOCR 3.5 on Windows
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import cv2
import numpy as np

from paddleocr import LayoutDetection

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

class TableDetectionWorker(QThread):
    result_ready = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.layout_engine = LayoutDetection(enable_mkldnn=False)
        self.pixmap = None
    
    def import_pixmap(self, pixmap: QPixmap):
        self.pixmap = pixmap

    def run(self):
        image = self.pixmap.toImage()
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(height * width * 4)
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)

        results_list = list(self.layout_engine.predict(arr))

        page_result = results_list[0]
        boxes = page_result['boxes']
        filtered_results = []
        for i, box in enumerate(boxes):
            if box['label'] == 'table':
                filtered_results.append(box)

        self.result_ready.emit(filtered_results)
