import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import camelot
import pandas as pd
import tabulate

def main():
    # pdf_path = "test_data\XO_559-5238933_Dec_31-Jan_31_2025.pdf"
    # pdf_path = "test_data\RBC Cudals Jan 2025.pdf"
    pdf_path = "test_data\TD_BUSINESS_TRAVEL_VISA_8839_Apr_06-2026.pdf"
    print("A debug image (cv_debug.png) has been saved to your directory so you can see what the CV system saw!\n")
    
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