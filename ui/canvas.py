from PyQt6.QtWidgets import QGraphicsView, QGraphicsObject, QGraphicsSceneMouseEvent
from PyQt6.QtGui import QPen, QColor, QPainter, QCursor, QPixmap
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal

from core.paddleocr import TableDetectionWorker

class BoundingBox(QGraphicsObject):
    box_updated = pyqtSignal()

    def __init__(self, x, y, width, height):
        super().__init__()
        self.rect = QRectF(0, 0, width, height)
        self.setPos(x, y)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges)

        self.border_width = 10
        self._is_resizing = False
        self._resize_edge = None
        self._click_pos = None
        self._click_rect = None
        self.setAcceptHoverEvents(True)

    def boundingRect(self):
        margin = self.border_width / 2.0
        return self.rect.adjusted(-margin, -margin, margin, margin)

    def paint(self, painter: QPainter, option, widget=None):
        pen_outer = QPen(QColor(255, 0, 0, 180)) # Red overlay
        pen_outer.setWidth(self.border_width)

        painter.setPen(pen_outer)
        painter.drawRect(self.rect)

    def get_edge(self, pos):
        margin = 15
        rect = self.rect
        x, y = pos.x(), pos.y()
        w = rect.width()
        h = rect.height()

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
            if edge in ['left', 'right']:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            elif edge in ['top', 'bottom']:
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
            self._click_pos = event.scenePos()
            self._click_rect = QRectF(self.pos().x(), self.pos().y(), self.rect.width(), self.rect.height())
            event.accept()
        else:
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._is_resizing:
            self.prepareGeometryChange()

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
            self.box_updated.emit()
        else:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            super().mouseReleaseEvent(event)
            self.box_updated.emit() # Box was likely moved


class InteractiveCanvas(QGraphicsView):
    box_updated = pyqtSignal()

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.image_item = None
        self.grid_overlay = None
        self.pixmap = None
        self.bounding_boxes = []
        self.table_detection_worker = TableDetectionWorker()

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)

    def set_image(self, pixmap: QPixmap):
        self.scene().clear()
        self.bounding_boxes = []
        self.pixmap = pixmap
        self.image_item = self.scene().addPixmap(pixmap)
        self.setSceneRect(0, 0, pixmap.width(), pixmap.height())

    def fit_to_view(self):
        if self.image_item:
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    
    def draw_bounding_boxes(self, boxes: list):
        for box in boxes:
            x1, y1, x2, y2 = box['coordinate']
            bb = BoundingBox(x1, y1, x2 - x1, y2 - y1)
            bb.box_updated.connect(self.box_updated.emit)
            self.bounding_boxes.append(bb)
            self.scene().addItem(bb)

    def _find_largest_box(self, rects: list):
        if not rects:
            return None
        max_area = 0
        max_rect = None
        for rect in rects:
            area = (rect[2] - rect[0]) * (rect[3] - rect[1])
            if area > max_area:
                max_area = area
                max_rect = rect
        return max_rect

    def draw_largest_bounding_box(self, boxes: list):
        rects = [box['coordinate'] for box in boxes]
        largest = self._find_largest_box(rects)
        
        if largest:
            x1, y1, x2, y2 = largest
            bb = BoundingBox(x1, y1, x2 - x1, y2 - y1)
            bb.box_updated.connect(self.box_updated.emit)
            self.bounding_boxes.append(bb)
            self.scene().addItem(bb)

    def get_bounding_boxes(self):
        """Return a list of [x1, y1, x2, y2] in scene coordinates for each bounding box."""
        result = []
        for bb in self.bounding_boxes:
            pos = bb.scenePos()
            x1 = pos.x()
            y1 = pos.y()
            x2 = x1 + bb.rect.width()
            y2 = y1 + bb.rect.height()
            result.append([x1, y1, x2, y2])
        return result
    
    def get_largest_bounding_box(self):
        result = self.get_bounding_boxes()
        largest = self._find_largest_box(result)
        return [largest] if largest else []
    
    def clear_bounding_boxes(self):
        for bb in self.bounding_boxes:
            self.scene().removeItem(bb)
        self.bounding_boxes = []

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
