"""
Javelin.AI - Phase 01: Data Discovery
======================================
This script scans your data folder, classifies all files, and discovers column mappings.

Run this FIRST before anything else.

Usage:
    python src/phases/01_data_discovery.py

Output:
    - outputs/file_mapping.csv      : Which file is which type
    - outputs/column_report.csv     : Column variations found per file type
    - outputs/discovery_issues.txt  : Any files/columns that need manual review
"""

import os
import re
import sys
import pandas as pd
from pathlib import Path
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# PATH SETUP - Add src directory to path for config import
# ============================================================================
_SCRIPT_DIR = Path(__file__).parent.resolve()
_SRC_DIR = _SCRIPT_DIR.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# ============================================================================
# CONFIGURATION - Import from config.py or use local fallbacks
# ============================================================================

try:
    from config import (
        PROJECT_ROOT, DATA_DIR, OUTPUT_DIR,
        FILE_PATTERNS, EXPECTED_COLUMNS
    )

    _USING_CONFIG = True
except ImportError:
    _USING_CONFIG = False
    # Fallback: Define locally (maintains backward compatibility)
    PROJECT_ROOT = _SRC_DIR.parent
    DATA_DIR = PROJECT_ROOT / "data"
    OUTPUT_DIR = PROJECT_ROOT / "outputs"

    # File type patterns - order matters (first match wins)
    FILE_PATTERNS = {
        'edc_metrics':[
            r'CPID.*EDC.*Metrics',
            r'EDC.*Metrics',
            r'CPID_EDC',
        ],
        'visit_tracker':[
            r'Visit.*Projection.*Tracker',
            r'Visit.*Tracker',
            r'Missing.*visit',
        ],
        'missing_lab':[
            r'Missing.*Lab.*Name',
            r'Missing.*LNR',
            r'Lab.*Range',
            r'Missing_Lab',
        ],
        'sae_dashboard':[
            r'eSAE.*Dashboard',
            r'SAE.*Dashboard',
            r'SAE_Dashboard',
            r'eSAE_',
        ],
        'missing_pages':[
            r'Missing.*Pages.*Report',
            r'Global.*Missing.*Pages',
            r'Missing.*Page.*Report',
            r'Missing_page',
        ],
        'meddra_coding':[
            r'GlobalCodingReport.*MedDRA',
            r'MedDRA',
            r'Medra',
        ],
        'whodd_coding':[
            r'GlobalCodingReport.*WHODD',
            r'GlobalCodingReport.*WHODrug',
            r'WHODD',
            r'WHODrug',
            r'WHOdra',
        ],
        'inactivated':[
            r'Inactivated.*Folders',
            r'Inactivated.*Forms',
            r'Inactivated.*Report',
            r'Inactivated',
            r'inactivated',
        ],
        'edrr':[
            r'Compiled.*EDRR',
            r'EDRR',
            r'Compiled_EDRR',
        ],
    }

    # Expected columns per file type (canonical names)
    EXPECTED_COLUMNS = {
        'edc_metrics':{
            'subject_id':['Subject ID', 'Subject', 'SubjectID', 'SUBJECT ID'],
            'site_id':['Site ID', 'Site', 'SiteID', 'SITE ID', 'Site Number'],
            'country':['Country', 'COUNTRY'],
            'region':['Region', 'REGION'],
            'subject_status':['Subject Status', 'Status', 'Subject Status (Source: PRIMARY Form)'],
        },
        'visit_tracker':{
            'subject_id':['Subject', 'Subject ID', 'SubjectID'],
            'site_id':['Site', 'Site ID', 'Site Number'],
            'visit':['Visit', 'Visit Name'],
            'days_outstanding':['# Days Outstanding', 'Days Outstanding', 'Days_Outstanding'],
        },
        'missing_lab':{
            'subject_id':['Subject', 'Subject ID'],
            'site_id':['Site number', 'Site', 'Site ID'],
            'issue':['Issue', 'Issue Type'],
        },
        'sae_dashboard':{
            'subject_id':['Patient ID', 'Subject', 'Subject ID', 'PatientID'],
            'site_id':['Site', 'Site ID'],
            'review_status':['Review Status', 'ReviewStatus'],
            'action_status':['Action Status', 'ActionStatus'],
        },
        'missing_pages':{
            'subject_id':['Subject Name', 'SubjectName', 'Subject', 'Subject ID'],
            'site_id':['Site Number', 'SiteNumber', 'SiteGroupName', 'Site', 'Site ID'],
            'days_missing':['No. #Days Page Missing', '# of Days Missing', 'Days Missing', '#Days Page Missing'],
        },
        'meddra_coding':{
            'subject_id':['Subject', 'Subject ID'],
            'coding_status':['Coding Status', 'CodingStatus'],
        },
        'whodd_coding':{
            'subject_id':['Subject', 'Subject ID'],
            'coding_status':['Coding Status', 'CodingStatus'],
        },
        'inactivated':{
            'subject_id':['Subject', 'Subject ID'],
            'site_id':['Study Site Number', 'Site', 'Site ID', 'Site Number'],
        },
        'edrr':{
            'subject_id':['Subject', 'Subject ID'],
            'open_issues':['Total Open issue Count per subject', 'Open Issues', 'Open Issue Count'],
        },
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_study_name(folder_name):
    """Extract study number from folder name."""
    match = re.search(r'Study[_\s]*(\d+)', folder_name, re.IGNORECASE)
    if match:
        return f"Study_{match.group(1)}"
    return folder_name


def classify_file(filename):
    """Classify a file into one of the 9 types based on patterns."""
    for file_type, patterns in FILE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return file_type
    return 'unknown'


def get_excel_columns(filepath):
    """Read Excel file and return column names from the first sheet."""
    try:
        df = pd.read_excel(filepath, sheet_name=0, nrows=5)

        first_col = str(df.columns[0])

        if 'Unnamed' in first_col or first_col in ['Project Name', 'Study', 'Country']:
            df_raw = pd.read_excel(filepath, sheet_name=0, header=None, nrows=10)

            for i in range(min(5, len(df_raw))):
                row_str = ' '.join(df_raw.iloc[i].astype(str).tolist())
                if 'Subject' in row_str or 'Patient' in row_str:
                    df = pd.read_excel(filepath, sheet_name=0, header=i, nrows=5)
                    break

        return list(df.columns), None
    except Exception as e:
        return [], str(e)


def find_column_mapping(actual_columns, expected_columns_dict):
    """Map actual columns to expected canonical names."""
    mapping = {}
    missing = []

    for canonical_name, variations in expected_columns_dict.items():
        found = False
        for actual_col in actual_columns:
            actual_col_clean = str(actual_col).strip()
            for variation in variations:
                if variation.lower() in actual_col_clean.lower():
                    mapping[canonical_name] = actual_col_clean
                    found = True
                    break
            if found:
                break
        if not found:
            missing.append(canonical_name)

    return mapping, missing


# ============================================================================
# MAIN DISCOVERY FUNCTION
# ============================================================================

def run_discovery(data_dir=None, output_dir=None):
    """
    Main function to discover and classify all files.

    Args:
        data_dir: Optional override for data directory
        output_dir: Optional override for output directory

    Returns:
        bool: True if successful, False otherwise
    """
    # Use provided directories or defaults
    _data_dir = Path(data_dir) if data_dir else DATA_DIR
    _output_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    print("=" * 70)
    print("JAVELIN.AI - DATA DISCOVERY")
    print("=" * 70)
    print(f"\nProject Root: {PROJECT_ROOT}")
    print(f"Looking for data in: {_data_dir}")
    if _USING_CONFIG:
        print("(Using centralized config)")

    _output_dir.mkdir(exist_ok=True)

    file_mapping = []
    column_report = []
    issues = []

    if not _data_dir.exists():
        print(f"\n[ERROR] Data directory '{_data_dir}' not found!")
        print(f"   Please create it and add your study folders.")
        print(f"\n   Expected structure:")
        print(f"   {_data_dir}/")
        print(f"   +-- Study 1_CPID_Input Files - Anonymization/")
        print(f"   +-- Study 2_CPID_Input Files - Anonymization/")
        print(f"   +-- ...")
        return False

    study_folders = [f for f in _data_dir.iterdir() if f.is_dir()]

    if not study_folders:
        print(f"\n[ERROR] No study folders found in '{_data_dir}'!")
        return False

    print(f"\n[INFO] Found {len(study_folders)} study folders")

    for study_folder in sorted(study_folders):
        study_name = extract_study_name(study_folder.name)
        print(f"\n{'-' * 50}")
        print(f"Processing: {study_name}")

        excel_files = list(study_folder.glob("*.xlsx")) + list(study_folder.glob("*.xls"))

        if not excel_files:
            issues.append(f"WARNING: No Excel files found in {study_folder.name}")
            continue

        print(f"   Found {len(excel_files)} Excel files")

        classified_count = defaultdict(int)

        for excel_file in excel_files:
            file_type = classify_file(excel_file.name)
            classified_count[file_type] += 1

            columns, error = get_excel_columns(excel_file)

            if error:
                issues.append(f"ERROR reading {excel_file.name}: {error}")
                columns = []

            column_mapping = {}
            missing_columns = []
            if file_type!='unknown' and columns:
                column_mapping, missing_columns = find_column_mapping(
                    columns,
                    EXPECTED_COLUMNS.get(file_type, {})
                )

            file_mapping.append({
                'study':study_name,
                'folder':study_folder.name,
                'filename':excel_file.name,
                'file_type':file_type,
                'filepath':str(excel_file),
                'num_columns':len(columns),
            })

            column_report.append({
                'study':study_name,
                'filename':excel_file.name,
                'file_type':file_type,
                'columns_found':'|'.join(columns[:20]),
                'subject_id_col':column_mapping.get('subject_id', 'NOT FOUND'),
                'site_id_col':column_mapping.get('site_id', 'NOT FOUND'),
                'missing_expected':'|'.join(missing_columns) if missing_columns else 'None',
            })

            if file_type=='unknown':
                issues.append(f"UNKNOWN FILE TYPE: {study_name}/{excel_file.name}")

            if missing_columns and file_type!='unknown':
                issues.append(f"MISSING COLUMNS in {study_name}/{excel_file.name} ({file_type}): {missing_columns}")

        for expected_type in FILE_PATTERNS.keys():
            if classified_count[expected_type]==0:
                issues.append(f"MISSING FILE TYPE: {study_name} has no {expected_type} file")

        print(f"   Classification: ", end="")
        for ftype, count in sorted(classified_count.items()):
            symbol = "[OK]" if ftype!='unknown' else "[?]"
            print(f"{ftype}:{count}{symbol} ", end="")
        print()

    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)

    df_files = pd.DataFrame(file_mapping)
    df_files.to_csv(_output_dir / "file_mapping.csv", index=False)
    print(f"\n[OK] Saved: {_output_dir / 'file_mapping.csv'} ({len(df_files)} files)")

    df_columns = pd.DataFrame(column_report)
    df_columns.to_csv(_output_dir / "column_report.csv", index=False)
    print(f"[OK] Saved: {_output_dir / 'column_report.csv'}")

    with open(_output_dir / "discovery_issues.txt", 'w') as f:
        f.write("JAVELIN.AI - DATA DISCOVERY ISSUES\n")
        f.write("=" * 50 + "\n\n")
        if issues:
            for issue in issues:
                f.write(f"* {issue}\n")
        else:
            f.write("No issues found! All files classified successfully.\n")
    print(f"[OK] Saved: {_output_dir / 'discovery_issues.txt'} ({len(issues)} issues)")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print("\nFile Type Distribution:")
    type_counts = df_files['file_type'].value_counts()
    for ftype, count in type_counts.items():
        symbol = "[OK]" if ftype!='unknown' else "[WARN]"
        print(f"  {symbol} {ftype}: {count} files")

    print(f"\nStudies: {df_files['study'].nunique()}")
    print(f"Total Files: {len(df_files)}")
    print(f"Issues Found: {len(issues)}")

    if issues:
        print("\n[WARN] ISSUES REQUIRING ATTENTION:")
        for issue in issues[:10]:
            print(f"   * {issue}")
        if len(issues) > 10:
            print(f"   ... and {len(issues) - 10} more (see discovery_issues.txt)")
    else:
        print("\n[OK] All files classified successfully!")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Review outputs/discovery_issues.txt for any problems
2. Check outputs/file_mapping.csv to verify classifications
3. Check outputs/column_report.csv to verify column mappings
4. Fix any issues manually if needed
5. Run: python src/phases/02_build_master_table.py
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__=="__main__":
    success = run_discovery()
    if not success:
        exit(1)
