import pandas as pd
from PIL import Image
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QFileDialog, 
                             QGraphicsScene, QMessageBox, QTableView, QSplitter, QGraphicsView,
                             QSpinBox, QLabel, QAbstractSpinBox, QCheckBox)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt

from .canvas import InteractiveCanvas
from .models import PandasModel
from .table_view import DropdownHeaderTableView
from utils.data import PageData
from utils.ofx import validate_mappings, determine_mapping_type, prepare_page_data, export_to_ofx
from core.camelot import DataDetectionWorker
from core.paddleocr import TableDetectionWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Extractor")
        self.resize(1000, 600)

        # Main Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Toolbar
        self.toolbar = QHBoxLayout()
        self.btn_load = QPushButton("Load Document")
        self.btn_load.clicked.connect(self.load_document)
        self.toolbar.addWidget(self.btn_load)

        self.btn_fit = QPushButton("Fit to Screen")
        self.btn_fit.clicked.connect(self.fit_to_view)
        self.toolbar.addWidget(self.btn_fit)

        self.btn_add_bbox = QPushButton("Add Bounding Box")
        self.btn_add_bbox.clicked.connect(self.add_bounding_box)
        self.btn_add_bbox.setEnabled(False)
        self.toolbar.addWidget(self.btn_add_bbox)

        self.btn_remove_bbox = QPushButton("Remove Bounding Box")
        self.btn_remove_bbox.clicked.connect(self.remove_bounding_box)
        self.btn_remove_bbox.setEnabled(False)
        self.toolbar.addWidget(self.btn_remove_bbox)

        self.toolbar.addStretch()

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self.export_csv)
        self.toolbar.addWidget(self.btn_export)

        self.btn_export_ofx = QPushButton("Export OFX")
        self.btn_export_ofx.clicked.connect(self.export_ofx)
        self.toolbar.addWidget(self.btn_export_ofx)
        
        self.cb_export_all = QCheckBox("Export All Pages")
        self.toolbar.addWidget(self.cb_export_all)

        self.layout.addLayout(self.toolbar)

        # Splitter for Canvas and Data Table
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)

        # Canvas Container
        self.canvas_container = QWidget()
        self.canvas_container_layout = QVBoxLayout(self.canvas_container)
        self.splitter.addWidget(self.canvas_container)

        # Canvas
        self.scene = QGraphicsScene()
        self.canvas = InteractiveCanvas(self.scene)
        self.canvas.box_updated.connect(self.on_box_updated)
        self.canvas_container_layout.addWidget(self.canvas)
        self.canvas_container_layout.setContentsMargins(0, 0, 10, 0)

        # Page Controls
        self.scroll_right_button = QPushButton(">")
        self.scroll_right_button.clicked.connect(self.scroll_right)
        self.page_num = QSpinBox()
        self.page_num.setRange(0, 0)
        self.page_num.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.page_num.valueChanged.connect(self.scroll_to_page)
        self.scroll_left_button = QPushButton("<")
        self.scroll_left_button.clicked.connect(self.scroll_left)
        self.left_right_layout = QHBoxLayout()
        self.left_right_layout.addStretch()
        self.left_right_layout.addWidget(self.scroll_left_button)
        self.left_right_layout.addWidget(self.page_num)
        self.left_right_layout.addWidget(self.scroll_right_button)
        self.left_right_layout.addStretch()
        self.canvas_container_layout.addLayout(self.left_right_layout)

        # Data Table Container
        self.table_container = QWidget()
        self.table_layout = QVBoxLayout(self.table_container)
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table_view = DropdownHeaderTableView()
        self.table_layout.addWidget(self.table_view)
        
        # Bottom Right Toolbar
        self.table_toolbar = QHBoxLayout()
        self.table_toolbar.addStretch()  # Push everything to the right
        self.table_toolbar.addWidget(QLabel("Default Year:"))
        import datetime
        self.year_spinbox = QSpinBox()
        self.year_spinbox.setRange(1900, 2100)
        self.year_spinbox.setValue(datetime.datetime.now().year)
        self.table_toolbar.addWidget(self.year_spinbox)
        
        self.btn_fill_dates = QPushButton("Fill Missing Dates")
        self.btn_fill_dates.clicked.connect(self.fill_missing_dates)
        self.table_toolbar.addWidget(self.btn_fill_dates)
        
        self.table_layout.addLayout(self.table_toolbar)

        self.splitter.addWidget(self.table_container)
        self.splitter.setSizes([700, 300])

        # State
        self.current_image_path = None
        self.df = None

        # Data Processing
        self.table_detection_worker = TableDetectionWorker()
        self.table_detection_worker.result_ready.connect(self.worker_completed)
        self.data_detection_worker = DataDetectionWorker()
        self.pages = []
        self.processing_page = 0
    
    def worker_completed(self, result):
        if self.processing_page == self.page_num.value() - 1:
            self.canvas.draw_largest_bounding_box(result)
            self.update_bbox_buttons()
        
        # Save only the largest bounding box so returning to the page doesn't draw all of them
        largest_box = self.canvas._find_largest_box([box['coordinate'] for box in result])
        if largest_box:
            self.pages[self.processing_page].bounding_boxes = [{'coordinate': largest_box}]
        else:
            self.pages[self.processing_page].bounding_boxes = []
            
        self.pages[self.processing_page].processing_status = "Completed"

        self.extract_data(self.processing_page)

        if self.processing_page == self.page_num.value() - 1:
            self.display_data(self.processing_page)
    
        if self.processing_page < self.page_num.maximum() - 1:
            self.processing_page += 1
            self.table_detection_worker.import_pixmap(self.pages[self.processing_page].pixmap)
            self.table_detection_worker.start()

    def scroll_right(self):
        self.page_num.setValue(self.page_num.value() + 1)
    
    def scroll_left(self):
        self.page_num.setValue(self.page_num.value() - 1)
    
    def scroll_to_page(self):
        target_page = self.page_num.value() - 1
        
        # Save state for the current page before switching
        if hasattr(self, 'current_page_index') and 0 <= self.current_page_index < len(self.pages):
            self.pages[self.current_page_index].column_mappings = self.table_view.get_mappings().copy()
            self.pages[self.current_page_index].disabled_rows = self.table_view.get_disabled_rows().copy()
            
        self.current_page_index = target_page

        self.canvas.clear_bounding_boxes()
        self.canvas.set_image(self.pages[target_page].pixmap)
        self.canvas.draw_bounding_boxes(self.pages[target_page].bounding_boxes)
        self.update_bbox_buttons()
        
        if self.pages[target_page].processing_status == "Completed":
            self.display_data(target_page)
        else:
            self.table_view.setModel(PandasModel(pd.DataFrame()))

    def update_bbox_buttons(self):
        if not self.pages or self.page_num.value() == 0:
            self.btn_add_bbox.setEnabled(False)
            self.btn_remove_bbox.setEnabled(False)
            return
            
        has_boxes = len(self.canvas.bounding_boxes) > 0
        self.btn_add_bbox.setEnabled(not has_boxes)
        self.btn_remove_bbox.setEnabled(has_boxes)

    def add_bounding_box(self):
        if not self.pages or self.page_num.value() == 0:
            return
        pixmap = self.pages[self.current_page_index].pixmap
        w, h = pixmap.width(), pixmap.height()
        default_box = [{'coordinate': [w * 0.1, h * 0.1, w * 0.9, h * 0.9]}]
        self.canvas.draw_bounding_boxes(default_box)
        self.pages[self.current_page_index].bounding_boxes = default_box
        self.update_bbox_buttons()
        self.on_box_updated()
        
    def remove_bounding_box(self):
        if not self.pages or self.page_num.value() == 0:
            return
        self.canvas.clear_bounding_boxes()
        self.pages[self.current_page_index].bounding_boxes = []
        self.update_bbox_buttons()
        self.on_box_updated()

    def on_box_updated(self):
        if not self.pages or self.page_num.value() == 0:
            return
            
        boxes = self.canvas.get_bounding_boxes()
        self.pages[self.current_page_index].bounding_boxes = [{'coordinate': box} for box in boxes]
        
        self.extract_data(self.current_page_index)
        self.display_data(self.current_page_index)

    def fit_to_view(self):
        self.canvas.fit_to_view()

    def load_document(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Document", "", "Images/PDFs (*.png *.jpg *.jpeg *.bmp *.pdf)")
        if not file_name:
            return
            
        self.current_image_path = file_name
        
        # Abort any ongoing background table detection from the previous document
        if hasattr(self, 'table_detection_worker'):
            self.table_detection_worker.cancel()
            
        self.pages.clear()
        self.processing_page = 0
        if hasattr(self, 'current_page_index'):
            del self.current_page_index
            
        self.table_view.setModel(PandasModel(pd.DataFrame()))
        
        # Block signals temporarily to prevent automatic/conditional triggering of scroll_to_page
        self.page_num.blockSignals(True)
        
        if file_name.lower().endswith(".pdf"):
            # open file
            doc = fitz.open(file_name)
            # add all pages to self.pages
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=300)
                img_data = pix.tobytes("ppm")
                qimg = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(qimg)
                self.pages.append(PageData(page_num, [], pixmap, None, "Pending"))
            # set page range
            self.page_num.setRange(1, doc.page_count)
            self.page_num.setValue(1)
        else:
            # open file
            pixmap = QPixmap(file_name)
            # add page to self.pages
            self.pages.append(PageData(0, [], pixmap, None, "Pending"))
            # set page range
            self.page_num.setRange(1, 1)
            self.page_num.setValue(1)
        
        # Re-enable signals
        self.page_num.blockSignals(False)
        
        # Explicitly call scroll_to_page once to load the first page and display it
        self.scroll_to_page()
        self.canvas.fit_to_view()

        self.detect_tables()
    
    def detect_tables(self):
        self.table_detection_worker.import_pixmap(self.canvas.pixmap)
        self.table_detection_worker.start()
    
    def extract_data(self, page_num: int):
        self.data_detection_worker.import_path(self.current_image_path)
        self.data_detection_worker.set_page_num(page_num + 1)
        self.data_detection_worker.set_bbox(
            self.pages[page_num].bounding_boxes,
            page_height_px=self.pages[page_num].pixmap.height()
        )
        self.data_detection_worker.start()
        self.data_detection_worker.wait()
        self.pages[page_num].df = self.data_detection_worker.df
        
        # Clear out previous manual row disables to force the automatic filter to run
        self.pages[page_num].disabled_rows = None
    
    def display_data(self, page_num: int):
        page_data = self.pages[page_num]
        if page_data.df is None:
            self.table_view.setModel(PandasModel(pd.DataFrame()))
            return
            
        self.table_view.setModel(PandasModel(page_data.df))
        
        # Restore saved state if it exists
        if page_data.column_mappings is not None:
            self.table_view.set_mappings(page_data.column_mappings)
            
        if page_data.disabled_rows is not None:
            self.table_view.set_disabled_rows(page_data.disabled_rows)

    def export_csv(self):
        if self.df is None:
            QMessageBox.warning(self, "Error", "No data to export.")
            return
            
        file_name, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if file_name:
            self.df.to_csv(file_name, index=False, header=False)
            QMessageBox.information(self, "Success", f"Saved to {file_name}")

    def export_ofx(self):
        if not self.pages:
            QMessageBox.warning(self, "Error", "No documents loaded.")
            return

        export_all = self.cb_export_all.isChecked()
        pages_to_export = []
        
        if export_all:
            pages_to_export = [p for p in self.pages if p.df is not None]
            if not pages_to_export:
                QMessageBox.warning(self, "Error", "No extracted data available to export.")
                return
        else:
            current_page = self.pages[self.current_page_index]
            if current_page.df is None:
                QMessageBox.warning(self, "Error", "Current page has no extracted data.")
                return
            pages_to_export = [current_page]

        # Sync the current active table view state to its PageData object
        if hasattr(self, 'current_page_index') and self.current_page_index < len(self.pages):
            self.pages[self.current_page_index].column_mappings = self.table_view.get_mappings().copy()
            self.pages[self.current_page_index].disabled_rows = self.table_view.get_disabled_rows().copy()

        # Validation
        mapping_type = None
        for page in pages_to_export:
            err = validate_mappings(page.column_mappings)
            if err:
                page_display_num = page.page_num + 1 if hasattr(page, 'page_num') else 'Unknown'
                QMessageBox.warning(self, "Mapping Error", f"Page {page_display_num}: {err}")
                return
                
            p_type = determine_mapping_type(page.column_mappings)
            if mapping_type is None:
                mapping_type = p_type
            elif mapping_type != p_type:
                QMessageBox.warning(self, "Consistency Error", 
                    "When exporting all pages, mappings must be consistently formatted (either all use 'Amount', or all use 'Deposit'/'Withdrawal').")
                return

        # Choose File
        file_name, _ = QFileDialog.getSaveFileName(self, "Save OFX", "", "OFX Files (*.ofx)")
        if not file_name:
            return

        try:
            user_year = self.year_spinbox.value()
            # Process Data
            dataframes = []
            all_errors = []
            for page in pages_to_export:
                page_display_num = page.page_num + 1 if hasattr(page, 'page_num') else 'Unknown'
                df_clean, errors = prepare_page_data(page.df, page.column_mappings, page.disabled_rows or set(), page_display_num, user_year)
                dataframes.append(df_clean)
                all_errors.extend(errors)
                
            final_df = pd.concat(dataframes, ignore_index=True)
            if final_df.empty:
                QMessageBox.warning(self, "Error", "No valid data to export after filtering.")
                return

            export_to_ofx(final_df, file_name)
            
            if all_errors:
                err_msg = f"Saved to {file_name}\n\nWarning: Some data was ignored due to invalid formatting:\n"
                for i, err in enumerate(all_errors):
                    if i >= 10:
                        err_msg += f"...and {len(all_errors) - 10} more errors."
                        break
                    err_msg += f"- Page {err['page']}, Column index {err['col']}, Row {err['row'] + 1}\n"
                QMessageBox.warning(self, "Export Completed with Warnings", err_msg)
            else:
                QMessageBox.information(self, "Success", f"Saved to {file_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save OFX: {str(e)}")

    def fill_missing_dates(self):
        if not self.pages or self.page_num.value() == 0:
            return
            
        if not hasattr(self, 'current_page_index') or self.current_page_index >= len(self.pages):
            return
            
        page = self.pages[self.current_page_index]
        if page.df is None or page.df.empty:
            return
            
        # Get column mappings to find the 'Date' column
        mappings = self.table_view.get_mappings()
        inv_map = {v: k for k, v in mappings.items() if v != "Unmapped"}
        
        if "Date" not in inv_map:
            QMessageBox.warning(self, "Warning", "Please map a column to 'Date' first.")
            return
            
        date_col = inv_map["Date"]
        
        import numpy as np
        # Convert empty strings or whitespace-only to NaN temporarily to use ffill
        page.df[date_col] = page.df[date_col].replace(r'^\s*$', np.nan, regex=True)
        page.df[date_col] = page.df[date_col].ffill()
        
        # Update the UI
        self.display_data(self.current_page_index)

