import os
# Critical workarounds for PaddleOCR 3.5 on Windows
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import fitz
import cv2
import numpy as np

from paddleocr import LayoutDetection

# Color map for region types (BGR)
REGION_COLORS = {
    'table':            (0, 0, 255),       # Red
    'table_title':      (0, 0, 200),       # Dark Red
    'paragraph_title':  (255, 100, 0),     # Blue
    'header':           (255, 0, 0),       # Pure Blue
    'footer':           (0, 255, 255),     # Yellow
    'text':             (0, 200, 0),       # Green
    'figure':           (200, 0, 200),     # Purple
    'figure_title':     (200, 100, 200),   # Light Purple
    'number':           (0, 200, 200),     # Cyan
    'reference':        (128, 128, 128),   # Gray
}
DEFAULT_COLOR = (100, 100, 100)

def test_paddle_layout(pdf_path, page_num=0):
    print(f"Loading {pdf_path} (Page {page_num + 1})...")
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    pix = page.get_pixmap(dpi=150)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    elif pix.n == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    print("Initializing Layout Detection Engine...")
    layout_engine = LayoutDetection(enable_mkldnn=False)
    
    print("Running AI Layout Analysis...")
    results_list = list(layout_engine.predict(img))
    
    if not results_list:
        print("No results returned!")
        return
        
    page_result = results_list[0]
    boxes = page_result['boxes']
    
    print(f"\nFound {len(boxes)} structural regions:")
    print("-" * 60)
    
    for i, box in enumerate(boxes):
        label = box['label']
        score = box['score']
        coords = box['coordinate']
        x1, y1, x2, y2 = [int(v) for v in coords]
        
        color = REGION_COLORS.get(label, DEFAULT_COLOR)
        thickness = 3 if label == 'table' else 2
        
        # Draw bounding box
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
        
        # Draw label background
        label_text = f"{label} ({score:.0%})"
        text_size, _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(img, (x1, y1 - text_size[1] - 8), (x1 + text_size[0] + 6, y1), color, -1)
        cv2.putText(img, label_text, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        print(f"  [{i+1}] {label:20s} | confidence: {score:.1%} | bbox: ({x1}, {y1}) -> ({x2}, {y2})")

    output_path = "paddle_layout_debug.png"
    cv2.imwrite(output_path, img)
    print(f"\n>>> Saved Layout Visualization to: {output_path}")

if __name__ == "__main__":
    pdf_file = r"test_data\XO_559-5238933_Dec_31-Jan_31_2025.pdf"
    
    if os.path.exists(pdf_file):
        test_paddle_layout(pdf_file)
    else:
        print(f"Error: Could not find test file at {pdf_file}")
