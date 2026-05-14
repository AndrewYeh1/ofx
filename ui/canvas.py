from PyQt6.QtWidgets import QGraphicsView, QGraphicsObject, QGraphicsSceneMouseEvent
from PyQt6.QtGui import QPen, QColor, QPainter, QCursor
from PyQt6.QtCore import QPointF, QRectF, Qt

class GridOverlay(QGraphicsObject):
    def __init__(self, x, y, width, height):
        super().__init__()
        self.rect = QRectF(0, 0, width, height)
        self.setPos(x, y)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.rows = 5
        self.cols = 4
        self.col_fractions = [i / self.cols for i in range(1, self.cols)]
        self.row_fractions = [i / self.rows for i in range(1, self.rows)]

        self.border_width = 4
        self._is_resizing = False
        self._resize_edge = None
        self._click_pos = None
        self._click_rect = None
        self._original_frac = 0.0
        self.setAcceptHoverEvents(True)

    def boundingRect(self):
        margin = self.border_width / 2.0
        return self.rect.adjusted(-margin, -margin, margin, margin)

    def paint(self, painter: QPainter, option, widget=None):
        pen_outer = QPen(QColor(0, 255, 0, 180)) # Green overlay
        pen_outer.setWidth(self.border_width)
        pen_inner = QPen(QColor(0, 255, 0, 100)) # Semi-transparent green
        pen_inner.setWidth(2)
        pen_inner.setStyle(Qt.PenStyle.DashLine)

        painter.setPen(pen_outer)
        painter.drawRect(self.rect)

        painter.setPen(pen_inner)
        w = self.rect.width()
        h = self.rect.height()

        # Draw columns
        for frac in self.col_fractions:
            x = frac * w
            painter.drawLine(QPointF(x, 0), QPointF(x, h))

        # Draw rows
        for frac in self.row_fractions:
            y = frac * h
            painter.drawLine(QPointF(0, y), QPointF(w, y))

    def set_grid(self, rows, cols):
        self.prepareGeometryChange()
        self.rows = max(1, rows)
        self.cols = max(1, cols)
        self.col_fractions = [i / self.cols for i in range(1, self.cols)]
        self.row_fractions = [i / self.rows for i in range(1, self.rows)]
        self.update()

    def get_edge(self, pos):
        margin = 15
        rect = self.rect
        x, y = pos.x(), pos.y()
        w = rect.width()
        h = rect.height()
        
        # Check inner columns first
        for i, frac in enumerate(self.col_fractions):
            line_x = rect.left() + frac * w
            if abs(x - line_x) < margin:
                return f'inner_col_{i}'

        # Check inner rows
        for i, frac in enumerate(self.row_fractions):
            line_y = rect.top() + frac * h
            if abs(y - line_y) < margin:
                return f'inner_row_{i}'

        left = abs(x - rect.left()) < margin
        right = abs(x - rect.right()) < margin
        top = abs(y - rect.top()) < margin
        bottom = abs(y - rect.bottom()) < margin
        
        if top and left: return 'topleft'
        if top and right: return 'topright'
        if bottom and left: return 'bottomleft'
        if bottom and right: return 'bottomright'
        if left: return 'left'
        if right: return 'right'
        if top: return 'top'
        if bottom: return 'bottom'
        return None

    def hoverMoveEvent(self, event):
        edge = self.get_edge(event.pos())
        if edge:
            if edge in ['left', 'right'] or edge.startswith('inner_col'):
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            elif edge in ['top', 'bottom'] or edge.startswith('inner_row'):
                self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
            elif edge in ['topleft', 'bottomright']:
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
            elif edge in ['topright', 'bottomleft']:
                self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        edge = self.get_edge(event.pos())
        if edge:
            self._is_resizing = True
            self._resize_edge = edge
            # Store local pos for inner lines, scene pos for outer boundary
            self._click_pos = event.pos() if edge.startswith('inner') else event.scenePos()
            self._click_rect = QRectF(self.pos().x(), self.pos().y(), self.rect.width(), self.rect.height())
            
            if edge.startswith('inner_col'):
                idx = int(edge.split('_')[-1])
                self._original_frac = self.col_fractions[idx]
            elif edge.startswith('inner_row'):
                idx = int(edge.split('_')[-1])
                self._original_frac = self.row_fractions[idx]
            event.accept()
        else:
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._is_resizing:
            self.prepareGeometryChange()
            
            if self._resize_edge.startswith('inner'):
                w = self.rect.width()
                h = self.rect.height()
                diff = event.pos() - self._click_pos
                
                if self._resize_edge.startswith('inner_col'):
                    idx = int(self._resize_edge.split('_')[-1])
                    new_x = self._original_frac * w + diff.x()
                    min_x = self.col_fractions[idx-1] * w + 10 if idx > 0 else 10
                    max_x = self.col_fractions[idx+1] * w - 10 if idx < len(self.col_fractions) - 1 else w - 10
                    new_x = max(min_x, min(new_x, max_x))
                    self.col_fractions[idx] = new_x / w
                
                elif self._resize_edge.startswith('inner_row'):
                    idx = int(self._resize_edge.split('_')[-1])
                    new_y = self._original_frac * h + diff.y()
                    min_y = self.row_fractions[idx-1] * h + 10 if idx > 0 else 10
                    max_y = self.row_fractions[idx+1] * h - 10 if idx < len(self.row_fractions) - 1 else h - 10
                    new_y = max(min_y, min(new_y, max_y))
                    self.row_fractions[idx] = new_y / h
                
                self.update()
            else:
                diff = event.scenePos() - self._click_pos
                new_rect = QRectF(self._click_rect)

                if 'left' in self._resize_edge:
                    new_rect.setLeft(new_rect.left() + diff.x())
                if 'right' in self._resize_edge:
                    new_rect.setRight(new_rect.right() + diff.x())
                if 'top' in self._resize_edge:
                    new_rect.setTop(new_rect.top() + diff.y())
                if 'bottom' in self._resize_edge:
                    new_rect.setBottom(new_rect.bottom() + diff.y())

                # Prevent inverting or going too small
                if new_rect.width() < 20:
                    if 'left' in self._resize_edge: new_rect.setLeft(new_rect.right() - 20)
                    else: new_rect.setRight(new_rect.left() + 20)
                if new_rect.height() < 20:
                    if 'top' in self._resize_edge: new_rect.setTop(new_rect.bottom() - 20)
                    else: new_rect.setBottom(new_rect.top() + 20)

                self.setPos(new_rect.x(), new_rect.y())
                self.rect.setWidth(new_rect.width())
                self.rect.setHeight(new_rect.height())
                self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if self._is_resizing:
            self._is_resizing = False
            self._resize_edge = None
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            super().mouseReleaseEvent(event)


class InteractiveCanvas(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.image_item = None
        self.grid_overlay = None

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def set_image(self, pixmap):
        self.scene().clear()
        self.image_item = self.scene().addPixmap(pixmap)
        self.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        
        # Add default grid overlay
        margin = 50
        w = max(100, pixmap.width() - margin * 2)
        h = max(100, pixmap.height() - margin * 2)
        self.grid_overlay = GridOverlay(margin, margin, w, h)
        self.scene().addItem(self.grid_overlay)

    def fit_to_view(self):
        if self.image_item:
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Zoom logic
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor

            if event.angleDelta().y() > 0:
                zoom_factor = zoom_in_factor
            else:
                zoom_factor = zoom_out_factor

            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)
