import os
import sys

# Crucial settings for PyInstaller & PaddleOCR / PaddleX
if hasattr(sys, '_MEIPASS'):
    # Avoid duplicate OpenMP library loading crashes
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    
    # If we bundled pre-downloaded models inside the app (fully offline mode), use them
    bundled_models_dir = os.path.join(sys._MEIPASS, "models")
    if os.path.isdir(os.path.join(bundled_models_dir, ".paddlex")):
        os.environ["PADDLEX_HOME"] = bundled_models_dir

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
        self._start_process()

    def _start_process(self):
        self._process = Process(
            target=_worker_loop,
            args=(self._task_queue, self._result_queue),
            daemon=True,
        )
        self._process.start()
        
    def cancel(self):
        """Safely terminate the current processing and restart the worker."""
        self._timer.stop()
        if self._process.is_alive():
            self._process.terminate()
            self._process.join()
            
        # Do NOT try to drain the queues here; terminating a process while it holds the queue lock 
        # causes empty() and get() to deadlock the entire UI thread. 
        # Instead, we safely close and discard the old queues.
        try:
            self._task_queue.close()
            self._task_queue.cancel_join_thread()
            self._result_queue.close()
            self._result_queue.cancel_join_thread()
        except:
            pass
            
        # Recreate fresh queues to guarantee no deadlocks
        self._task_queue = Queue()
        self._result_queue = Queue()
            
        # Cleanup any lingering shared memory handle in the main process
        if hasattr(self, '_current_shm') and self._current_shm is not None:
            try:
                self._current_shm.close()
                self._current_shm.unlink()
            except:
                pass
            self._current_shm = None
            
        self._start_process()

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
        
        # Send via shared memory
        shm = SharedMemory(create=True, size=arr.nbytes)
        shared_arr = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
        shared_arr[:] = arr
        
        # Keep reference alive so Windows doesn't destroy the handle before worker opens it
        self._current_shm = shm
        
        self._task_queue.put((shm.name, arr.shape, arr.dtype.str))
        
        self._timer.start()

    def _check_result(self):
        """Polled from main thread — emits signal when worker process is done."""
        if not self._result_queue.empty():
            self._timer.stop()
            
            # Safe to close local handle now that worker has definitely processed it
            if hasattr(self, '_current_shm') and self._current_shm is not None:
                try: self._current_shm.close()
                except: pass
                self._current_shm = None
                
            self.result_ready.emit(self._result_queue.get())
    
    def shutdown(self):
        """Send poison pill to stop the worker process."""
        self._task_queue.put(None)
        self._process.join(timeout=5)
