import fitz
import cv2
import numpy as np

class CVTableDetector:
    # --- TUNING PARAMETERS ---
    
    # Kernel Generation
    START_KERNEL_W = 1
    START_KERNEL_H = 4
    KERNEL_STEP_W = 1
    KERNEL_STEP_H = 1
    MAX_ITERATIONS = 40
    
    # Coverage Targets
    TARGET_COVERAGE_MIN = 0.50
    TARGET_COVERAGE_MAX = 0.90
    
    # Fallback Plateau
    PLATEAU_TOLERANCE = 0.05  # 5% coverage variance allowed in a plateau
    
    # Output Padding
    BBOX_PADDING = 5          # Pixels to expand the final bounding box by
    
    # Density Filtering
    DENSITY_THRESHOLD = 2     # Minimum local density out of 255 (2 = ~0.8% text coverage). Lower = more sensitive.

    def __init__(self):
        pass

    def detect_largest_table(self, pdf_path, page_num=0):
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        pix = page.get_pixmap(dpi=72)
        
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        
        if pix.n == 4:
            gray = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Calculate total text pixels on the page
        total_white_pixels = cv2.countNonZero(thresh)
        if total_white_pixels == 0:
            return None
            
        page_h = pix.h
        results = []
        
        # Generate kernel steps based on constants
        kernel_steps = [
            (self.START_KERNEL_W + i * self.KERNEL_STEP_W, 
             self.START_KERNEL_H + i * self.KERNEL_STEP_H) 
            for i in range(self.MAX_ITERATIONS)
        ]
        
        print("\n--- Starting Auto-Tuning CV Loop ---")
        
        for kw, kh in kernel_steps:
            # DENSITY FILTERING
            # 1. Blur the image to average the white pixels in every (kw, kh) window.
            # This creates a grayscale heatmap of local text density.
            blurred = cv2.blur(thresh, (kw, kh))
            
            # 2. Threshold the density map to only keep areas with sufficient text density.
            # This ignores isolated sparse text (like loose sidebars) while merging dense tables.
            _, density_mask = cv2.threshold(blurred, self.DENSITY_THRESHOLD, 255, cv2.THRESH_BINARY)
            
            contours, _ = cv2.findContours(density_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
                
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            
            # Calculate what percentage of the page's text falls inside this bounding box
            roi = thresh[y:y+h, x:x+w]
            white_pixels_in_bbox = cv2.countNonZero(roi)
            coverage = white_pixels_in_bbox / total_white_pixels
            
            # Convert to Camelot coordinates
            cam_y1 = page_h - (y + h)
            cam_y2 = page_h - y
            pad = self.BBOX_PADDING
            x1 = max(0, x - pad)
            y1 = max(0, cam_y1 - pad)
            x2 = x + w + pad
            y2 = cam_y2 + pad
            
            bbox_str = f"{x1},{y1},{x2},{y2}"
            
            results.append({
                'kernel': (kw, kh),
                'coverage': coverage,
                'bbox': bbox_str,
                'cv_rect': (x, y, w, h),
                'dilated': density_mask
            })
            
            print(f"Kernel {kw}x{kh} -> Text Coverage: {coverage:.1%}")
            
            # If we hit the Goldilocks zone, stop iterating!
            if self.TARGET_COVERAGE_MIN <= coverage <= self.TARGET_COVERAGE_MAX:
                print(f">>> Target reached! Stopping at {coverage:.1%} coverage.")
                best_result = results[-1]
                break
        else:
            # Fallback: We didn't hit the target. Find the "Plateau".
            print(">>> Target not reached. Finding longest stable plateau...")
            longest_plateau = []
            current_plateau = [results[0]]
            
            for i in range(1, len(results)):
                prev_cov = current_plateau[-1]['coverage']
                curr_cov = results[i]['coverage']
                
                # If coverage changes by less than the tolerance, we are in a plateau
                if abs(curr_cov - prev_cov) <= self.PLATEAU_TOLERANCE:
                    current_plateau.append(results[i])
                else:
                    if len(current_plateau) > len(longest_plateau):
                        longest_plateau = current_plateau
                    current_plateau = [results[i]]
                    
            if len(current_plateau) > len(longest_plateau):
                longest_plateau = current_plateau
                
            print(f">>> Found plateau of {len(longest_plateau)} steps at {longest_plateau[0]['coverage']:.1%} coverage.")
            # Use the first (tightest) kernel from the longest plateau
            best_result = longest_plateau[0]

        # DEBUG VISUALIZATION
        x, y, w, h = best_result['cv_rect']
        debug_img = cv2.cvtColor(best_result['dilated'], cv2.COLOR_GRAY2BGR)
        cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 0, 255), 2)
        cv2.imwrite("cv_debug.png", debug_img)
        
        return best_result['bbox']
