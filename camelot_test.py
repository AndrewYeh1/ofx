import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import camelot
import pandas as pd
import tabulate
from core.cv_detector import CVTableDetector

def main():
    # pdf_path = "test_data\XO_559-5238933_Dec_31-Jan_31_2025.pdf"
    # pdf_path = "test_data\RBC Cudals Jan 2025.pdf"
    pdf_path = "test_data\TD_BUSINESS_TRAVEL_VISA_8839_Apr_06-2026.pdf"
    
    print("1. Running OpenCV to find the largest text blob...")
    detector = CVTableDetector()
    
    # We'll just test page 1 (index 0) for now
    bbox = detector.detect_largest_table(pdf_path, page_num=0)
    
    if not bbox:
        print("Failed to detect any table bounding box.")
        return
        
    print(f"Detected bounding box for Camelot: {bbox}")
    print("A debug image (cv_debug.png) has been saved to your directory so you can see what the CV system saw!\n")
    
    print("2. Running Camelot with the extracted bounding box...")
    tables = camelot.read_pdf(
        pdf_path, 
        pages="1", 
        flavor="stream",
        table_areas=[bbox]
    )
    
    if tables.n > 0:
        df = pd.concat([t.df for t in tables], ignore_index=True)
        print("\n=== EXTRACTED TABLE ===")
        print(tabulate.tabulate(df, headers="keys", tablefmt="psql", showindex=False))
    else:
        print("Camelot found no tables inside that bounding box.")

if __name__ == "__main__":
    main()