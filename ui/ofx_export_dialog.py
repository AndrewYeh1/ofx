from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox

class OfxExportDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export to OFX")
        self.setMinimumWidth(300)
        
        self.columns = [str(c) for c in columns]
        
        self.layout = QVBoxLayout(self)
        
        # Date mapping
        self.layout.addWidget(QLabel("Date Column:"))
        self.date_combo = QComboBox()
        self.date_combo.addItems(self.columns)
        self.layout.addWidget(self.date_combo)
        
        # Amount mapping
        self.layout.addWidget(QLabel("Amount Column:"))
        self.amount_combo = QComboBox()
        self.amount_combo.addItems(self.columns)
        if len(self.columns) > 1:
            self.amount_combo.setCurrentIndex(1)
        self.layout.addWidget(self.amount_combo)
        
        # Payee mapping
        self.layout.addWidget(QLabel("Payee/Description Column:"))
        self.payee_combo = QComboBox()
        self.payee_combo.addItems(self.columns)
        if len(self.columns) > 2:
            self.payee_combo.setCurrentIndex(2)
        self.layout.addWidget(self.payee_combo)
        
        # Buttons
        self.btn_layout = QHBoxLayout()
        self.btn_export = QPushButton("Export")
        self.btn_cancel = QPushButton("Cancel")
        
        self.btn_export.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.btn_cancel)
        self.btn_layout.addWidget(self.btn_export)
        
        self.layout.addLayout(self.btn_layout)

    def get_mapping(self):
        return {
            "date": self.date_combo.currentIndex(),
            "amount": self.amount_combo.currentIndex(),
            "payee": self.payee_combo.currentIndex()
        }
