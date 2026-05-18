import pandas as pd
from PIL import Image
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QFileDialog, 
                             QGraphicsScene, QMessageBox, QTableView, QSplitter, QGraphicsView,
                             QSpinBox, QLabel, QAbstractSpinBox)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt

from .canvas import InteractiveCanvas
from .models import PandasModel
from .ofx_export_dialog import OfxExportDialog

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

        self.toolbar.addStretch()

        self.btn_extract = QPushButton("Extract Data")
        self.btn_extract.setObjectName("greenBtn")
        self.btn_extract.clicked.connect(self.extract_data)
        self.toolbar.addWidget(self.btn_extract)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self.export_csv)
        self.toolbar.addWidget(self.btn_export)

        self.btn_export_ofx = QPushButton("Export OFX")
        self.btn_export_ofx.clicked.connect(self.export_ofx)
        self.toolbar.addWidget(self.btn_export_ofx)

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

        # Data Table
        self.table_view = QTableView()
        self.splitter.addWidget(self.table_view)
        self.splitter.setSizes([700, 300])

        # State
        self.current_image_path = None
        self.current_image_pil = None
        self.df = None

        # Data Processing
        self.table_detection_worker = TableDetectionWorker()
        self.data_detection_worker = DataDetectionWorker()

    def scroll_right(self):
        self.page_num.setValue(self.page_num.value() + 1)
    
    def scroll_left(self):
        self.page_num.setValue(self.page_num.value() - 1)
    
    def scroll_to_page(self):
        # implement page change
        pass

    def fit_to_view(self):
        self.canvas.fit_to_view()

    def load_document(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Document", "", "Images/PDFs (*.png *.jpg *.jpeg *.bmp *.pdf)")
        if not file_name:
            return
            
        self.current_image_path = file_name
        
        if file_name.lower().endswith(".pdf"):
            doc = fitz.open(file_name)
            page = doc.load_page(0) # Load first page
            pix = page.get_pixmap(dpi=300) # High DPI for OCR
            img_data = pix.tobytes("ppm")
            qimg = QImage.fromData(img_data)
            pixmap = QPixmap.fromImage(qimg)
            self.current_image_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.page_num.setRange(1, doc.page_count)
            self.page_num.setValue(1)
        else:
            pixmap = QPixmap(file_name)
            self.current_image_pil = Image.open(file_name).convert("RGB")
            self.page_num.setRange(1, 1)
            self.page_num.setValue(1)
        
        self.canvas.set_image(pixmap)
        self.canvas.fit_to_view()
        self.detect_tables()
    
    def detect_tables(self):
        self.table_detection_worker.import_pixmap(self.canvas.pixmap)
        self.table_detection_worker.start()
        self.table_detection_worker.result_ready.connect(self.canvas.draw_bounding_boxes)
    
    def extract_data(self):
        self.data_detection_worker.import_path(self.current_image_path)
        self.data_detection_worker.set_bbox(
            self.canvas.get_bounding_boxes(),
            page_height_px=self.canvas.pixmap.height()
        )
        self.data_detection_worker.start()
        self.data_detection_worker.result_ready.connect(self.display_data)
    
    def display_data(self):
        self.df = self.data_detection_worker.df
        self.table_view.setModel(PandasModel(self.df))

    def export_csv(self):
        if self.df is None:
            QMessageBox.warning(self, "Error", "No data to export.")
            return
            
        file_name, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if file_name:
            self.df.to_csv(file_name, index=False, header=False)
            QMessageBox.information(self, "Success", f"Saved to {file_name}")

    def export_ofx(self):
        if self.df is None:
            QMessageBox.warning(self, "Error", "No data to export.")
            return

        dialog = OfxExportDialog(self.df.columns, self)
        if dialog.exec():
            mapping = dialog.get_mapping()
            
            file_name, _ = QFileDialog.getSaveFileName(self, "Save OFX", "", "OFX Files (*.ofx)")
            if not file_name:
                return

            try:
                # Basic OFX generation
                ofx_header = (
                    "OFXHEADER:100\n"
                    "DATA:OFXSGML\n"
                    "VERSION:102\n"
                    "SECURITY:NONE\n"
                    "ENCODING:USASCII\n"
                    "CHARSET:1252\n"
                    "COMPRESSION:NONE\n"
                    "OLDFILEUID:NONE\n"
                    "NEWFILEUID:NONE\n\n"
                )

                ofx_body = (
                    "<OFX>\n"
                    "  <BANKMSGSRSV1>\n"
                    "    <STMTTRNRS>\n"
                    "      <TRNUID>1</TRNUID>\n"
                    "      <STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>\n"
                    "      <STMTRS>\n"
                    "        <CURDEF>USD</CURDEF>\n"
                    "        <BANKACCTFROM>\n"
                    "          <BANKID>123456789</BANKID>\n"
                    "          <ACCTID>123456789</ACCTID>\n"
                    "          <ACCTTYPE>CHECKING</ACCTTYPE>\n"
                    "        </BANKACCTFROM>\n"
                    "        <BANKTRANLIST>\n"
                )

                transactions = []
                for idx, row in self.df.iterrows():
                    date_val = str(row[mapping['date']]).strip()
                    amount_val = str(row[mapping['amount']]).strip()
                    payee_val = str(row[mapping['payee']]).strip()

                    trn_type = "CREDIT" if not amount_val.startswith("-") else "DEBIT"

                    txn = (
                        "          <STMTTRN>\n"
                        f"            <TRNTYPE>{trn_type}</TRNTYPE>\n"
                        f"            <DTPOSTED>{date_val}</DTPOSTED>\n"
                        f"            <TRNAMT>{amount_val}</TRNAMT>\n"
                        f"            <FITID>{idx}</FITID>\n"
                        f"            <NAME>{payee_val}</NAME>\n"
                        "          </STMTTRN>\n"
                    )
                    transactions.append(txn)

                ofx_footer = (
                    "        </BANKTRANLIST>\n"
                    "      </STMTRS>\n"
                    "    </STMTTRNRS>\n"
                    "  </BANKMSGSRSV1>\n"
                    "</OFX>\n"
                )

                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(ofx_header)
                    f.write(ofx_body)
                    for txn in transactions:
                        f.write(txn)
                    f.write(ofx_footer)

                QMessageBox.information(self, "Success", f"Saved to {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save OFX: {str(e)}")

