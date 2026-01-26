"""
Multi-Sheet Excel Scanner
Scans all Excel files in data folder and reports which have multiple sheets
"""

import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Setup paths
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

print("="*70)
print("MULTI-SHEET EXCEL FILE SCANNER")
print("="*70)
print(f"Scanning: {DATA_DIR}")
print()

# Find all Excel files
excel_files = list(DATA_DIR.rglob("*.xlsx")) + list(DATA_DIR.rglob("*.xls"))

print(f"Found {len(excel_files)} Excel files")
print()

# Track results
multi_sheet_files = []
single_sheet_files = []
errors = []

# Scan each file
for i, filepath in enumerate(excel_files, 1):
    study_name = filepath.parent.name
    filename = filepath.name

    # Classify file type from name
    if "SAE" in filename or "eSAE" in filename:
        file_type = "SAE Dashboard"
    elif "EDRR" in filename:
        file_type = "EDRR"
    elif "Visit" in filename:
        file_type = "Visit Tracker"
    elif "EDC" in filename:
        file_type = "EDC Metrics"
    elif "MedDRA" in filename or "Medra" in filename:
        file_type = "MedDRA"
    elif "WHODD" in filename or "WHODrug" in filename or "WHOdra" in filename:
        file_type = "WHODD"
    elif "Missing" in filename and ("Lab" in filename or "LNR" in filename):
        file_type = "Missing Lab"
    elif "Missing" in filename and "Page" in filename:
        file_type = "Missing Pages"
    elif "Inactivated" in filename:
        file_type = "Inactivated"
    else:
        file_type = "Unknown"

    try:
        # Get sheet info
        xl_file = pd.ExcelFile(filepath)
        sheet_names = xl_file.sheet_names
        num_sheets = len(sheet_names)

        # Get row counts per sheet
        sheet_info = []
        total_rows = 0
        for sheet in sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet)
            rows = len(df)
            total_rows += rows
            sheet_info.append(f"{sheet}: {rows} rows")

        if num_sheets > 1:
            multi_sheet_files.append({
                'study': study_name,
                'file': filename,
                'type': file_type,
                'sheets': num_sheets,
                'sheet_names': sheet_names,
                'sheet_details': sheet_info,
                'total_rows': total_rows
            })
        else:
            single_sheet_files.append({
                'study': study_name,
                'file': filename,
                'type': file_type,
                'rows': total_rows
            })

    except Exception as e:
        errors.append(f"{study_name}/{filename}: {str(e)[:50]}")

# Print results
print("="*70)
print("MULTI-SHEET FILES (POTENTIAL DATA LOSS!)")
print("="*70)

if multi_sheet_files:
    for item in multi_sheet_files:
        print(f"\n📁 {item['study']}")
        print(f"   File: {item['file']}")
        print(f"   Type: {item['type']}")
        print(f"   Sheets: {item['sheets']}")
        print(f"   Total Rows: {item['total_rows']}")
        for detail in item['sheet_details']:
            print(f"      - {detail}")
else:
    print("\n✓ No multi-sheet files found!")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"Total files scanned: {len(excel_files)}")
print(f"Multi-sheet files: {len(multi_sheet_files)}")
print(f"Single-sheet files: {len(single_sheet_files)}")
print(f"Errors: {len(errors)}")

if multi_sheet_files:
    print("\n⚠️  WARNING: Your code only reads sheet_name=0 (first sheet)")
    print("   You are LOSING DATA from the other sheets!")

    # Group by file type
    from collections import defaultdict
    by_type = defaultdict(list)
    for item in multi_sheet_files:
        by_type[item['type']].append(item['study'])

    print("\nMulti-sheet files by type:")
    for ftype, studies in by_type.items():
        print(f"  {ftype}: {len(studies)} files")
        print(f"    Studies: {', '.join(sorted(set(studies)))}")

if errors:
    print("\nErrors encountered:")
    for err in errors[:5]:
        print(f"  • {err}")
    if len(errors) > 5:
        print(f"  ... and {len(errors)-5} more")

print("\n" + "="*70)
print("NEXT STEPS")
print("="*70)
print("1. Review which file types have multiple sheets")
print("2. Decide: combine sheets OR pick correct sheet")
print("3. Update read_excel_smart() to handle multiple sheets")
