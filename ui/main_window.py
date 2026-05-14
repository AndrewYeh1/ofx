import pytesseract
import pandas as pd
from PIL import Image
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QFileDialog, 
                             QGraphicsScene, QMessageBox, QTableView, QSplitter, QGraphicsView,
                             QSpinBox, QLabel)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt

from .canvas import InteractiveCanvas, GridOverlay
from .models import PandasModel
from .ofx_export_dialog import OfxExportDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interactive OCR Table Extractor")
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

        self.toolbar.addSpacing(20)

        self.toolbar.addWidget(QLabel("Rows:"))
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 100)
        self.spin_rows.setValue(5)
        self.spin_rows.valueChanged.connect(self.update_grid)
        self.toolbar.addWidget(self.spin_rows)

        self.toolbar.addWidget(QLabel("Cols:"))
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 50)
        self.spin_cols.setValue(4)
        self.spin_cols.valueChanged.connect(self.update_grid)
        self.toolbar.addWidget(self.spin_cols)

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

        # Canvas
        self.scene = QGraphicsScene()
        self.canvas = InteractiveCanvas(self.scene)
        self.splitter.addWidget(self.canvas)

        # Data Table
        self.table_view = QTableView()
        self.splitter.addWidget(self.table_view)
        self.splitter.setSizes([700, 300])

        # State
        self.current_image_path = None
        self.current_image_pil = None
        self.df = None
        
        # Check Tesseract
        import os
        if os.name == 'nt':
            tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            alt_tesseract_path = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
            if os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            elif os.path.exists(alt_tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = alt_tesseract_path

        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError:
            QMessageBox.warning(self, "Tesseract Not Found", 
                                "Tesseract-OCR is not installed or not in your PATH.\n"
                                "Please install it from https://github.com/UB-Mannheim/tesseract/wiki "
                                "for OCR features to work on Windows.")

    def fit_to_view(self):
        self.canvas.fit_to_view()

    def update_grid(self):
        if self.canvas.grid_overlay:
            self.canvas.grid_overlay.set_grid(self.spin_rows.value(), self.spin_cols.value())

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
        else:
            pixmap = QPixmap(file_name)
            self.current_image_pil = Image.open(file_name).convert("RGB")
            
        self.canvas.set_image(pixmap)
        self.update_grid() # Apply current spinbox values
        
        # Fit to screen automatically
        self.canvas.fit_to_view()

    def extract_data(self):
        if not self.current_image_pil or not self.canvas.grid_overlay:
            QMessageBox.warning(self, "Error", "Load a document first.")
            return

        grid = self.canvas.grid_overlay
        rows = grid.rows
        cols = grid.cols
        
        # Get absolute coordinates of the grid relative to the image
        scene_pos = grid.scenePos()
        rect = grid.rect
        
        # Image bounds
        img_w, img_h = self.current_image_pil.size
        
        # Clamp to image boundaries
        x_start = max(0, int(scene_pos.x()))
        y_start = max(0, int(scene_pos.y()))
        x_end = min(img_w, int(scene_pos.x() + rect.width()))
        y_end = min(img_h, int(scene_pos.y() + rect.height()))
        
        # Real width and height
        grid_w = x_end - x_start
        grid_h = y_end - y_start

        if grid_w <= 0 or grid_h <= 0:
            QMessageBox.warning(self, "Error", "Grid is entirely outside the image.")
            return

        col_boundaries = [0.0] + grid.col_fractions + [1.0]
        row_boundaries = [0.0] + grid.row_fractions + [1.0]

        data = []
        for r in range(rows):
            row_data = []
            for c in range(cols):
                cx1 = x_start + col_boundaries[c] * grid_w
                cy1 = y_start + row_boundaries[r] * grid_h
                cx2 = x_start + col_boundaries[c+1] * grid_w
                cy2 = y_start + row_boundaries[r+1] * grid_h
                
                # Check for zero sized cell to prevent crash
                if (cx2 - cx1) < 2 or (cy2 - cy1) < 2:
                    row_data.append("")
                    continue
                    
                cell_img = self.current_image_pil.crop((cx1, cy1, cx2, cy2))
                text = pytesseract.image_to_string(cell_img, config='--psm 6').strip()
                # Normalize newlines and extra spaces into a single space
                text = " ".join(text.split())
                row_data.append(text)
            data.append(row_data)

        if data:
            self.df = pd.DataFrame(data)
            model = PandasModel(self.df)
            self.table_view.setModel(model)
        else:
            QMessageBox.warning(self, "Error", "No data extracted.")
        
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

