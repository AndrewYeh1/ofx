from PyQt6.QtWidgets import QTableView, QWidget, QHBoxLayout, QComboBox
from PyQt6.QtCore import Qt, pyqtSignal

class DropdownHeaderTableView(QTableView):
    mapping_changed = pyqtSignal(dict) # Emits the dict of col_index -> selected_text

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Remove the outer frame for a cleaner look
        from PyQt6.QtWidgets import QFrame
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        # Configure the native horizontal header
        header = self.horizontalHeader()
        header.setMinimumHeight(40)  # Make room for the tile
        
        # Connect section resizing and scroll events to sync the dropdowns
        header.sectionResized.connect(self.update_dropdown_positions)
        self.horizontalScrollBar().valueChanged.connect(self.update_dropdown_positions)
        
        self.header_dropdowns = []
        self.column_mappings = {}

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_dropdown_positions()

    def setModel(self, model):
        super().setModel(model)
        if model:
            self.setup_header_dropdowns(model.columnCount())
        else:
            self.clear_header_dropdowns()

    def clear_header_dropdowns(self):
        for combo in self.header_dropdowns:
            combo.deleteLater()
        self.header_dropdowns.clear()
        self.column_mappings.clear()

    def setup_header_dropdowns(self, num_columns):
        self.clear_header_dropdowns()

        fields = ["Unmapped", "Date", "Payee", "Amount"]

        header = self.horizontalHeader()
        for col in range(num_columns):
            # Parent the combobox directly to the native header
            combo = QComboBox(header)
            combo.setObjectName("headerDropdown")
            combo.addItems(fields)
            
            # Smart default mappings: Column 0 -> Date, Column 1 -> Payee, Column 2 -> Amount
            if col == 0 and num_columns >= 3:
                combo.setCurrentIndex(1)  # Date
            elif col == 1 and num_columns >= 3:
                combo.setCurrentIndex(2)  # Payee
            elif col == 2 and num_columns >= 3:
                combo.setCurrentIndex(3)  # Amount
            else:
                combo.setCurrentIndex(0)  # Unmapped

            # Monitor change events
            combo.currentIndexChanged.connect(lambda idx, c=col: self.on_mapping_changed(c, idx))
            
            self.header_dropdowns.append(combo)
            combo.show()
            
            self.column_mappings[col] = combo.currentText()

        self.update_dropdown_positions()

    def update_dropdown_positions(self, *args):
        if not self.header_dropdowns:
            return
            
        header = self.horizontalHeader()
        offset = header.offset()
        header_height = header.height()
        
        for col, combo in enumerate(self.header_dropdowns):
            x = header.sectionPosition(col) - offset
            width = header.sectionSize(col)
            
            # Pad so the dropdown looks like a floating tile within the header cell
            pad_x = 4
            pad_y = 6
            
            if width > 2 * pad_x:
                combo.setGeometry(x + pad_x, pad_y, width - (2 * pad_x), header_height - (2 * pad_y))
                combo.show()
            else:
                combo.hide()

    def on_mapping_changed(self, col_index, selected_index):
        if col_index < len(self.header_dropdowns):
            combo = self.header_dropdowns[col_index]
            self.column_mappings[col_index] = combo.currentText()
            self.mapping_changed.emit(self.column_mappings)

    def get_mappings(self):
        """Returns a dict mapping col_index -> field name (e.g. {0: 'Date', 1: 'Payee', 2: 'Amount'})"""
        return self.column_mappings
