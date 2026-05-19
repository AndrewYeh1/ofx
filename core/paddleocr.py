import os
# Workarounds for PaddleOCR 3.5 on Windows
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import cv2
import numpy as np
from multiprocessing import Process, Queue
from multiprocessing.shared_memory import SharedMemory

from paddleocr import LayoutDetection

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage


def _worker_loop(task_queue: Queue, result_queue: Queue):
    """Persistent worker process — initializes engine once, processes jobs forever."""
    engine = LayoutDetection(enable_mkldnn=False)
    
    while True:
        job = task_queue.get()
        if job is None:  # Poison pill = shutdown
            break
        
        shm_name, shape, dtype_str = job
        shm = SharedMemory(name=shm_name)
        arr = np.ndarray(shape, dtype=np.dtype(dtype_str), buffer=shm.buf)
        img = arr.copy()  # Copy out of shared memory
        shm.close()
        shm.unlink()
        
        results_list = list(engine.predict(img))
        
        page_result = results_list[0]
        filtered = []
        for box in page_result['boxes']:
            if box['label'] == 'table':
                filtered.append({
                    'label': box['label'],
                    'score': float(box['score']),
                    'coordinate': [float(v) for v in box['coordinate']],
                })
        result_queue.put(filtered)


class TableDetectionWorker(QObject):
    result_ready = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self._pixmap = None
        self._task_queue = Queue()
        self._result_queue = Queue()
        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._check_result)
        
        # Start persistent worker process
        self._process = Process(
            target=_worker_loop,
            args=(self._task_queue, self._result_queue),
            daemon=True,
        )
        self._process.start()

    def import_pixmap(self, pixmap: QPixmap):
        """Just store the pixmap reference — keep this fast."""
        self._pixmap = pixmap

    def start(self):
        """Convert pixmap and send to worker process via shared memory."""
        # Convert QPixmap → numpy (must happen on main thread)
        image = self._pixmap.toImage()
        image = image.convertToFormat(QImage.Format.Format_RGB888)
        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine()
        ptr = image.bits()
        ptr.setsize(height * bytes_per_line)
        # Handle stride: bytesPerLine may differ from width*3
        raw = np.frombuffer(ptr, np.uint8).reshape((height, bytes_per_line))
        arr = raw[:, :width * 3].reshape((height, width, 3))
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        arr = np.ascontiguousarray(arr)
        
        # Send via shared memory (zero-copy, no pickling the big array)
        shm = SharedMemory(create=True, size=arr.nbytes)
        shared_arr = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
        shared_arr[:] = arr
        
        self._task_queue.put((shm.name, arr.shape, arr.dtype.str))
        shm.close()  # Close local handle; worker will unlink after reading
        
        self._timer.start()

    def _check_result(self):
        """Polled from main thread — emits signal when worker process is done."""
        if not self._result_queue.empty():
            self._timer.stop()
            self.result_ready.emit(self._result_queue.get())
    
    def shutdown(self):
        """Send poison pill to stop the worker process."""
        self._task_queue.put(None)
        self._process.join(timeout=5)
