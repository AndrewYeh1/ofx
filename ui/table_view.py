from PyQt6.QtWidgets import QTableView, QWidget, QHBoxLayout, QComboBox, QCheckBox
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
        
        # Connect section resizing and scroll events to sync the dropdowns
        header.sectionResized.connect(self.update_dropdown_positions)
        self.horizontalScrollBar().valueChanged.connect(self.update_dropdown_positions)
        
        # Configure the native vertical header for checkboxes
        v_header = self.verticalHeader()
        v_header.sectionResized.connect(self.update_checkbox_positions)
        self.verticalScrollBar().valueChanged.connect(self.update_checkbox_positions)
        
        self.header_dropdowns = []
        self.column_mappings = {}
        
        self.row_checkboxes = []
        self.disabled_rows = set()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_dropdown_positions()
        self.update_checkbox_positions()

    def setModel(self, model):
        super().setModel(model)
        if model and model.columnCount() > 0:
            self.horizontalHeader().setMinimumHeight(40)
            self.verticalHeader().setMinimumWidth(36)
            self.setup_row_checkboxes(model.rowCount())
            self.auto_disable_header_footer_rows(model)
            self.setup_header_dropdowns(model.columnCount(), model)
        else:
            self.horizontalHeader().setMinimumHeight(0)
            self.verticalHeader().setMinimumWidth(0)
            self.clear_header_dropdowns()
            self.clear_row_checkboxes()

    def auto_disable_header_footer_rows(self, model):
        import re
        # Common keywords that indicate a bank statement header or footer row
        keywords = {r'\bdate\b', r'\bdescription\b', r'\bopening\b', r'\bclosing\b', r'\bbalance\b', r'\btotal\b', r'\bpage\b'}
        
        pattern = re.compile('|'.join(keywords))
        
        for row in range(model.rowCount()):
            row_text = []
            for col in range(model.columnCount()):
                val = model.data(model.index(row, col))
                if val:
                    row_text.append(str(val).lower())
            
            combined_text = " ".join(row_text)
            if pattern.search(combined_text):
                self.set_row_disabled(row, True)

    def clear_header_dropdowns(self):
        for combo in self.header_dropdowns:
            combo.deleteLater()
        self.header_dropdowns.clear()
        self.column_mappings.clear()

    def clear_row_checkboxes(self):
        for chk in self.row_checkboxes:
            chk.deleteLater()
        self.row_checkboxes.clear()
        self.disabled_rows.clear()

    def setup_header_dropdowns(self, num_columns, model=None):
        self.clear_header_dropdowns()

        fields = ["Unmapped", "Date", "Description", "Amount", "Deposit", "Withdrawal"]

        # Gather text from disabled rows (likely headers) to intelligently guess columns
        col_headers = {}
        if model:
            for col in range(num_columns):
                words = []
                for row in self.disabled_rows:
                    val = model.data(model.index(row, col))
                    if val:
                        words.append(str(val).lower())
                col_headers[col] = " ".join(words)

        def guess_mapping(header_text):
            if not header_text:
                return 0
            if any(w in header_text for w in ['date', 'time', 'posted']):
                return 1  # Date
            if any(w in header_text for w in ['description', 'payee', 'transaction', 'detail', 'type']):
                return 2  # Description
            if any(w in header_text for w in ['amount', 'balance', 'total']):
                return 3  # Amount
            if any(w in header_text for w in ['withdraw', 'debit', 'deduct', 'out']):
                return 5  # Withdrawal
            if any(w in header_text for w in ['deposit', 'credit', 'addition', 'in']):
                return 4  # Deposit
            return 0  # Unmapped

        header = self.horizontalHeader()
        for col in range(num_columns):
            # Parent the combobox directly to the native header
            combo = QComboBox(header)
            combo.setObjectName("headerDropdown")
            combo.addItems(fields)
            
            # Smart default mappings
            guessed_idx = guess_mapping(col_headers.get(col, ""))
            combo.setCurrentIndex(guessed_idx)
            
            def update_combo_style(cb=combo):
                if cb.currentIndex() == 0:
                    cb.setStyleSheet("QComboBox { background-color: #5a3030; color: white; border: 1px solid #7a4040; }")
                else:
                    cb.setStyleSheet("")
            
            update_combo_style()

            # Monitor change events
            def on_change(idx, c=col, cb=combo):
                update_combo_style(cb)
                self.on_mapping_changed(c, idx)
                
            combo.currentIndexChanged.connect(on_change)
            
            self.header_dropdowns.append(combo)
            combo.show()
            
            self.column_mappings[col] = combo.currentText()

        self.update_dropdown_positions()

    def setup_row_checkboxes(self, num_rows):
        self.clear_row_checkboxes()
        
        v_header = self.verticalHeader()
        for row in range(num_rows):
            chk = QCheckBox(v_header)
            chk.setChecked(True)  # All rows enabled by default
            chk.stateChanged.connect(lambda state, r=row: self.on_row_checkbox_changed(r, state))
            self.row_checkboxes.append(chk)
            chk.show()
            
        self.update_checkbox_positions()

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

    def on_row_checkbox_changed(self, row_index, state):
        # state is 0 for Qt.CheckState.Unchecked
        if state == 0:
            self.disabled_rows.add(row_index)
        else:
            self.disabled_rows.discard(row_index)

    def update_checkbox_positions(self, *args):
        if not self.row_checkboxes:
            return
            
        v_header = self.verticalHeader()
        offset = v_header.offset()
        header_width = v_header.width()
        
        for row, chk in enumerate(self.row_checkboxes):
            y = v_header.sectionPosition(row) - offset
            height = v_header.sectionSize(row)
            
            # Simple centering calculation
            chk_width = 16
            chk_height = 16
            x_pos = (header_width - chk_width) // 2
            y_pos = y + (height - chk_height) // 2
            
            if height > 10:
                chk.setGeometry(x_pos, y_pos, chk_width, chk_height)
                chk.show()
            else:
                chk.hide()

    def get_mappings(self):
        """Returns a dict mapping col_index -> field name (e.g. {0: 'Date', 1: 'Description', 2: 'Amount'})"""
        return self.column_mappings

    def set_mappings(self, mappings: dict):
        """Restore column mappings."""
        for col_index, text in mappings.items():
            if col_index < len(self.header_dropdowns):
                combo = self.header_dropdowns[col_index]
                idx = combo.findText(text)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    def get_disabled_rows(self):
        """Returns a set of row indices that the user has unchecked."""
        return self.disabled_rows

    def set_disabled_rows(self, disabled_rows: set):
        """Restore disabled rows state."""
        for row in range(len(self.row_checkboxes)):
            is_disabled = row in disabled_rows
            self.set_row_disabled(row, is_disabled)

    def set_row_disabled(self, row_index, disabled: bool):
        """Programmatically check or uncheck a row."""
        if 0 <= row_index < len(self.row_checkboxes):
            chk = self.row_checkboxes[row_index]
            chk.setChecked(not disabled)
