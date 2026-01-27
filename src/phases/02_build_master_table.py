"""
Javelin.AI - Phase 02: Build Master Table
==========================================
This script builds unified master tables from all study data.

Prerequisites:
    - Run 01_data_discovery.py first
    - Check outputs/file_mapping.csv exists

Usage:
    python src/phases/02_build_master_table.py

Output:
    - outputs/master_subject.csv  : One row per subject with all metrics
    - outputs/master_site.csv     : Aggregated site-level metrics
    - outputs/master_study.csv    : Aggregated study-level metrics
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# PATH SETUP
# ============================================================================

_SCRIPT_DIR = Path(__file__).parent.resolve()
_SRC_DIR = _SCRIPT_DIR.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# ============================================================================
# CONFIGURATION
# ============================================================================

try:
    from config import (
        PROJECT_ROOT, DATA_DIR, OUTPUT_DIR, COLUMN_MAPPINGS, THRESHOLDS,
        NUMERIC_ISSUE_COLUMNS, OUTLIER_CAP_COLUMNS, CATEGORICAL_COLUMNS
    )
    _USING_CONFIG = True
except ImportError:
    _USING_CONFIG = False
    PROJECT_ROOT = _SRC_DIR.parent
    DATA_DIR = PROJECT_ROOT / "data"
    OUTPUT_DIR = PROJECT_ROOT / "outputs"
    COLUMN_MAPPINGS = {
        'edc_metrics': {
            'subject_id': ['Subject ID', 'Subject', 'SubjectID', 'SUBJECT ID'],
            'site_id': ['Site ID', 'Site', 'SiteID', 'SITE ID', 'Site Number'],
            'country': ['Country', 'COUNTRY'],
            'region': ['Region', 'REGION'],
            'subject_status': ['Subject Status', 'Status', 'Subject Status (Source: PRIMARY Form)'],
            'latest_visit': ['Latest Visit', 'Latest Visit (SV)', 'Latest Visit (SV) (Source: Rave EDC: BO4)'],
        },
        'visit_tracker': {
            'subject_id': ['Subject', 'Subject ID', 'SubjectID'],
            'site_id': ['Site', 'Site ID', 'Site Number'],
            'country': ['Country'],
            'visit': ['Visit', 'Visit Name'],
            'days_outstanding': ['# Days Outstanding', 'Days Outstanding', 'Days_Outstanding'],
        },
        'missing_lab': {
            'subject_id': ['Subject', 'Subject ID'],
            'site_id': ['Site number', 'Site', 'Site ID'],
            'country': ['Country'],
            'issue': ['Issue', 'Issue Type'],
        },
        'sae_dashboard': {
            'subject_id': ['Patient ID', 'Subject', 'Subject ID', 'PatientID'],
            'site_id': ['Site', 'Site ID'],
            'country': ['Country'],
            'review_status': ['Review Status', 'ReviewStatus'],
            'action_status': ['Action Status', 'ActionStatus'],
        },
        'missing_pages': {
            'subject_id': ['Subject Name', 'SubjectName', 'Subject', 'Subject ID'],
            'site_id': ['Site Number', 'SiteNumber', 'SiteGroupName(CountryName)', 'Site', 'Site ID'],
            'days_missing': ['No. #Days Page Missing', '# of Days Missing', 'Days Missing', '#Days Page Missing'],
        },
        'meddra_coding': {'subject_id': ['Subject', 'Subject ID'], 'coding_status': ['Coding Status', 'CodingStatus']},
        'whodd_coding': {'subject_id': ['Subject', 'Subject ID'], 'coding_status': ['Coding Status', 'CodingStatus']},
        'inactivated': {'subject_id': ['Subject', 'Subject ID'], 'site_id': ['Study Site Number', 'Site', 'Site ID', 'Site Number'], 'country': ['Country']},
        'edrr': {'subject_id': ['Subject', 'Subject ID'], 'open_issues': ['Total Open issue Count per subject', 'Open Issues', 'Open Issue Count']},
    }
    class THRESHOLDS:
        OUTLIER_IQR_MULTIPLIER = 3.0
        MAX_DAYS_CAP = 1825
    NUMERIC_ISSUE_COLUMNS = ['missing_visit_count', 'max_days_outstanding', 'lab_issues_count', 'sae_total_count', 'sae_pending_count', 'missing_pages_count', 'max_days_page_missing', 'uncoded_meddra_count', 'uncoded_whodd_count', 'inactivated_forms_count', 'edrr_open_issues']
    OUTLIER_CAP_COLUMNS = ['max_days_outstanding', 'max_days_page_missing', 'lab_issues_count', 'inactivated_forms_count']
    CATEGORICAL_COLUMNS = ['country', 'region', 'subject_status']

FILE_MAPPING_PATH = OUTPUT_DIR / "file_mapping.csv"

# ============================================================================
# DATA QUALITY FUNCTIONS
# ============================================================================

def validate_loaded_data(df, file_type, filepath):
    issues = []
    if df.empty:
        return df, ['Empty dataframe']
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        neg_count = (df[col] < 0).sum()
        if neg_count > 0:
            issues.append(f"{col}: {neg_count} negative values (set to 0)")
            df.loc[df[col] < 0, col] = 0
    max_days = THRESHOLDS.MAX_DAYS_CAP
    day_cols = [c for c in df.columns if 'day' in c.lower()]
    for col in day_cols:
        if col in numeric_cols:
            impossible = (df[col] > max_days).sum()
            if impossible > 0:
                issues.append(f"{col}: {impossible} values > 5 years (capped at {max_days})")
                df.loc[df[col] > max_days, col] = max_days
    return df, issues

def cap_outliers(series, multiplier=None, method='iqr'):
    if multiplier is None:
        multiplier = THRESHOLDS.OUTLIER_IQR_MULTIPLIER
    if series.empty or series.isna().all():
        return series
    if method == 'iqr':
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        if IQR == 0:
            return series
        upper_bound = Q3 + multiplier * IQR
        lower_bound = max(0, Q1 - multiplier * IQR)
    else:
        mean = series.mean()
        std = series.std()
        if std == 0:
            return series
        upper_bound = mean + multiplier * std
        lower_bound = max(0, mean - multiplier * std)
    return series.clip(lower=lower_bound, upper=upper_bound)

def safe_max(series):
    if series.empty or series.isna().all():
        return 0
    result = series.max()
    return 0 if pd.isna(result) else result

def fill_missing_categoricals(df, categorical_cols=None):
    if categorical_cols is None:
        categorical_cols = CATEGORICAL_COLUMNS
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].replace('', 'Unknown')
            df[col] = df[col].fillna('Unknown')
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace('nan', 'Unknown')
    return df

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def find_column(df_columns, possible_names):
    df_columns_lower = [str(c).lower().strip() for c in df_columns]
    for name in possible_names:
        if name in df_columns:
            return name
        name_lower = name.lower().strip()
        for i, col_lower in enumerate(df_columns_lower):
            if name_lower in col_lower or col_lower in name_lower:
                return df_columns[i]
    return None

def standardize_columns(df, file_type):
    mapping = COLUMN_MAPPINGS.get(file_type, {})
    rename_dict = {}
    for standard_name, possible_names in mapping.items():
        actual_col = find_column(df.columns.tolist(), possible_names)
        if actual_col and actual_col != standard_name:
            rename_dict[actual_col] = standard_name
    if rename_dict:
        df = df.rename(columns=rename_dict)
    return df

def read_excel_smart(filepath, file_type):
    try:
        if file_type == 'edc_metrics':
            df = pd.read_excel(filepath, sheet_name=0, header=None)
            header_row = 0
            for i in range(min(5, len(df))):
                row_str = ' '.join(df.iloc[i].astype(str).tolist())
                if 'Subject ID' in row_str or 'Project Name' in row_str:
                    header_row = i
                    break
            df = pd.read_excel(filepath, sheet_name=0, header=header_row)
            if 'Subject ID' in df.columns:
                df = df[df['Subject ID'].notna()]
                df = df[~df['Subject ID'].astype(str).str.contains('Subject ID|Responsible', na=False)]
        elif file_type == 'sae_dashboard':
            xl = pd.ExcelFile(filepath)
            all_dfs = []
            for sheet in xl.sheet_names:
                if 'SAE' in sheet or 'Dashboard' in sheet:
                    df_sheet = pd.read_excel(filepath, sheet_name=sheet)
                    if not df_sheet.empty:
                        df_sheet['_source_sheet'] = sheet
                        all_dfs.append(df_sheet)
            if all_dfs:
                df = pd.concat(all_dfs, ignore_index=True, sort=False)
                print(f"      Combined {len(all_dfs)} SAE sheets: {sum(len(d) for d in all_dfs)} total rows")
            else:
                df = pd.DataFrame()
        elif file_type == 'missing_pages':
            xl = pd.ExcelFile(filepath)
            all_dfs = []
            for sheet in xl.sheet_names:
                df_sheet = pd.read_excel(filepath, sheet_name=sheet)
                if not df_sheet.empty:
                    df_sheet['_source_sheet'] = sheet
                    all_dfs.append(df_sheet)
            if all_dfs:
                df = pd.concat(all_dfs, ignore_index=True, sort=False)
                print(f"      Combined {len(all_dfs)} Missing Pages sheets: {sum(len(d) for d in all_dfs)} total rows")
            else:
                df = pd.DataFrame()
        else:
            df = pd.read_excel(filepath, sheet_name=0)
        if not df.empty:
            df, _ = validate_loaded_data(df, file_type, filepath)
        return df
    except Exception as e:
        print(f"    [WARN] Error reading {filepath}: {e}")
        return pd.DataFrame()

def load_edc_lookup(file_mapping_df):
    print("\n[INFO] Building Subject -> Site lookup table from EDC Metrics...")
    edc_files = file_mapping_df[file_mapping_df['file_type'] == 'edc_metrics']
    lookup_records = []
    for _, row in tqdm(edc_files.iterrows(), total=len(edc_files), desc="   Loading EDC files"):
        study = row['study']
        filepath = row['filepath']
        df = read_excel_smart(filepath, 'edc_metrics')
        if df.empty:
            continue
        df = standardize_columns(df, 'edc_metrics')
        if 'subject_id' in df.columns and 'site_id' in df.columns:
            for _, r in df.iterrows():
                if pd.notna(r.get('subject_id')):
                    lookup_records.append({
                        'study': study,
                        'subject_id': str(r['subject_id']).strip(),
                        'site_id': str(r.get('site_id', '')).strip() if pd.notna(r.get('site_id')) else '',
                        'country': str(r.get('country', '')).strip() if pd.notna(r.get('country')) else '',
                        'region': str(r.get('region', '')).strip() if pd.notna(r.get('region')) else '',
                    })
    lookup_df = pd.DataFrame(lookup_records)
    print(f"   [OK] Lookup table: {len(lookup_df)} subject-site mappings")
    return lookup_df

# ============================================================================
# AGGREGATION FUNCTIONS
# ============================================================================

def aggregate_edc_metrics(file_mapping_df, lookup_df):
    print("\n[INFO] Processing EDC Metrics (base table)...")
    edc_files = file_mapping_df[file_mapping_df['file_type'] == 'edc_metrics']
    all_records = []
    for _, row in tqdm(edc_files.iterrows(), total=len(edc_files), desc="   Processing"):
        study = row['study']
        filepath = row['filepath']
        df = read_excel_smart(filepath, 'edc_metrics')
        if df.empty:
            continue
        df = standardize_columns(df, 'edc_metrics')
        for _, r in df.iterrows():
            if pd.notna(r.get('subject_id')):
                all_records.append({
                    'study': study,
                    'subject_id': str(r.get('subject_id', '')).strip(),
                    'site_id': str(r.get('site_id', '')).strip() if pd.notna(r.get('site_id')) else '',
                    'country': str(r.get('country', '')).strip() if pd.notna(r.get('country')) else '',
                    'region': str(r.get('region', '')).strip() if pd.notna(r.get('region')) else '',
                    'subject_status': str(r.get('subject_status', '')).strip() if pd.notna(r.get('subject_status')) else '',
                    'latest_visit': str(r.get('latest_visit', '')).strip() if pd.notna(r.get('latest_visit')) else '',
                })
    result_df = pd.DataFrame(all_records)
    print(f"   [OK] EDC Metrics: {len(result_df)} subjects")
    return result_df

def aggregate_visit_tracker(file_mapping_df, lookup_df):
    print("\n[INFO] Processing Visit Tracker...")
    files = file_mapping_df[file_mapping_df['file_type'] == 'visit_tracker']
    all_records = []
    for _, row in tqdm(files.iterrows(), total=len(files), desc="   Processing"):
        study = row['study']
        filepath = row['filepath']
        df = read_excel_smart(filepath, 'visit_tracker')
        if df.empty:
            continue
        df = standardize_columns(df, 'visit_tracker')
        if 'subject_id' not in df.columns:
            subject_col = find_column(df.columns.tolist(), ['Subject', 'Subject ID', 'SubjectID'])
            if subject_col:
                df = df.rename(columns={subject_col: 'subject_id'})
            else:
                continue
        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue
            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                lookup_match = lookup_df[(lookup_df['study'] == study) & (lookup_df['subject_id'] == str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]
            days_col = find_column(group.columns.tolist(), ['days_outstanding', '# Days Outstanding', 'Days Outstanding'])
            max_days = 0
            if days_col and days_col in group.columns:
                max_days = pd.to_numeric(group[days_col], errors='coerce').max()
                if pd.isna(max_days):
                    max_days = 0
            all_records.append({'study': study, 'subject_id': str(subject_id).strip(), 'site_id': site_id, 'missing_visit_count': len(group), 'max_days_outstanding': max_days})
    result_df = pd.DataFrame(all_records)
    print(f"   [OK] Visit Tracker: {len(result_df)} subject records")
    return result_df

def aggregate_missing_lab(file_mapping_df, lookup_df):
    print("\n[INFO] Processing Missing Lab...")
    files = file_mapping_df[file_mapping_df['file_type'] == 'missing_lab']
    all_records = []
    for _, row in tqdm(files.iterrows(), total=len(files), desc="   Processing"):
        study = row['study']
        filepath = row['filepath']
        df = read_excel_smart(filepath, 'missing_lab')
        if df.empty:
            continue
        df = standardize_columns(df, 'missing_lab')
        if 'subject_id' not in df.columns:
            subject_col = find_column(df.columns.tolist(), ['Subject', 'Subject ID'])
            if subject_col:
                df = df.rename(columns={subject_col: 'subject_id'})
            else:
                continue
        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue
            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                lookup_match = lookup_df[(lookup_df['study'] == study) & (lookup_df['subject_id'] == str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]
            all_records.append({'study': study, 'subject_id': str(subject_id).strip(), 'site_id': site_id, 'lab_issues_count': len(group)})
    result_df = pd.DataFrame(all_records)
    print(f"   [OK] Missing Lab: {len(result_df)} subject records")
    return result_df

def aggregate_sae_dashboard(file_mapping_df, lookup_df):
    print("\n[INFO] Processing SAE Dashboard...")
    files = file_mapping_df[file_mapping_df['file_type'] == 'sae_dashboard']
    all_records = []
    for _, row in tqdm(files.iterrows(), total=len(files), desc="   Processing"):
        study = row['study']
        filepath = row['filepath']
        df = read_excel_smart(filepath, 'sae_dashboard')
        if df.empty:
            continue
        df = standardize_columns(df, 'sae_dashboard')
        if 'subject_id' not in df.columns:
            subject_col = find_column(df.columns.tolist(), ['Patient ID', 'Subject', 'Subject ID'])
            if subject_col:
                df = df.rename(columns={subject_col: 'subject_id'})
            else:
                continue
        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue
            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                lookup_match = lookup_df[(lookup_df['study'] == study) & (lookup_df['subject_id'] == str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]
            pending_count = 0
            if 'review_status' in group.columns:
                pending_count = len(group[group['review_status'] != 'Review Completed'])
            else:
                pending_count = len(group)
            all_records.append({'study': study, 'subject_id': str(subject_id).strip(), 'site_id': site_id, 'sae_total_count': len(group), 'sae_pending_count': pending_count})
    result_df = pd.DataFrame(all_records)
    print(f"   [OK] SAE Dashboard: {len(result_df)} subject records")
    return result_df

def aggregate_missing_pages(file_mapping_df, lookup_df):
    print("\n[INFO] Processing Missing Pages...")
    files = file_mapping_df[file_mapping_df['file_type'] == 'missing_pages']
    all_records = []
    for _, row in tqdm(files.iterrows(), total=len(files), desc="   Processing"):
        study = row['study']
        filepath = row['filepath']
        df = read_excel_smart(filepath, 'missing_pages')
        if df.empty:
            continue
        df = standardize_columns(df, 'missing_pages')
        if 'subject_id' not in df.columns:
            subject_col = find_column(df.columns.tolist(), ['Subject Name', 'SubjectName', 'Subject'])
            if subject_col:
                df = df.rename(columns={subject_col: 'subject_id'})
            else:
                continue
        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue
            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                lookup_match = lookup_df[(lookup_df['study'] == study) & (lookup_df['subject_id'] == str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]
            max_days = 0
            days_col = find_column(group.columns.tolist(), ['days_missing', 'No. #Days Page Missing', '# of Days Missing'])
            if days_col and days_col in group.columns:
                max_days = pd.to_numeric(group[days_col], errors='coerce').max()
                if pd.isna(max_days):
                    max_days = 0
            all_records.append({'study': study, 'subject_id': str(subject_id).strip(), 'site_id': site_id, 'missing_pages_count': len(group), 'max_days_page_missing': max_days})
    result_df = pd.DataFrame(all_records)
    print(f"   [OK] Missing Pages: {len(result_df)} subject records")
    return result_df

def aggregate_coding(file_mapping_df, lookup_df, coding_type='meddra'):
    file_type = f'{coding_type}_coding'
    print(f"\n[INFO] Processing {coding_type.upper()} Coding...")
    files = file_mapping_df[file_mapping_df['file_type'] == file_type]
    all_records = []
    for _, row in tqdm(files.iterrows(), total=len(files), desc="   Processing"):
        study = row['study']
        filepath = row['filepath']
        df = read_excel_smart(filepath, file_type)
        if df.empty:
            continue
        df = standardize_columns(df, file_type)
        if 'subject_id' not in df.columns:
            subject_col = find_column(df.columns.tolist(), ['Subject', 'Subject ID'])
            if subject_col:
                df = df.rename(columns={subject_col: 'subject_id'})
            else:
                continue
        uncoded_df = df.copy()
        if 'coding_status' in df.columns:
            uncoded_df = df[df['coding_status'].str.contains('UnCoded|Uncoded|Not Coded', case=False, na=False)]
        for subject_id, group in uncoded_df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue
            site_id = ''
            lookup_match = lookup_df[(lookup_df['study'] == study) & (lookup_df['subject_id'] == str(subject_id).strip())]
            if not lookup_match.empty:
                site_id = lookup_match['site_id'].iloc[0]
            all_records.append({'study': study, 'subject_id': str(subject_id).strip(), 'site_id': site_id, f'uncoded_{coding_type}_count': len(group)})
    result_df = pd.DataFrame(all_records)
    print(f"   [OK] {coding_type.upper()} Coding: {len(result_df)} subject records with uncoded terms")
    return result_df

def aggregate_inactivated(file_mapping_df, lookup_df):
    print("\n[INFO] Processing Inactivated Forms...")
    files = file_mapping_df[file_mapping_df['file_type'] == 'inactivated']
    all_records = []
    for _, row in tqdm(files.iterrows(), total=len(files), desc="   Processing"):
        study = row['study']
        filepath = row['filepath']
        df = read_excel_smart(filepath, 'inactivated')
        if df.empty:
            continue
        df = standardize_columns(df, 'inactivated')
        if 'subject_id' not in df.columns:
            subject_col = find_column(df.columns.tolist(), ['Subject', 'Subject ID'])
            if subject_col:
                df = df.rename(columns={subject_col: 'subject_id'})
            else:
                continue
        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue
            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                lookup_match = lookup_df[(lookup_df['study'] == study) & (lookup_df['subject_id'] == str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]
            all_records.append({'study': study, 'subject_id': str(subject_id).strip(), 'site_id': site_id, 'inactivated_forms_count': len(group)})
    result_df = pd.DataFrame(all_records)
    print(f"   [OK] Inactivated: {len(result_df)} subject records")
    return result_df

def aggregate_edrr(file_mapping_df, lookup_df):
    print("\n[INFO] Processing EDRR...")
    files = file_mapping_df[file_mapping_df['file_type'] == 'edrr']
    all_records = []
    for _, row in tqdm(files.iterrows(), total=len(files), desc="   Processing"):
        study = row['study']
        filepath = row['filepath']
        df = read_excel_smart(filepath, 'edrr')
        if df.empty:
            continue
        df = standardize_columns(df, 'edrr')
        if 'subject_id' not in df.columns:
            subject_col = find_column(df.columns.tolist(), ['Subject', 'Subject ID'])
            if subject_col:
                df = df.rename(columns={subject_col: 'subject_id'})
            else:
                continue
        for _, r in df.iterrows():
            subject_id = r.get('subject_id')
            if pd.isna(subject_id):
                continue
            site_id = ''
            lookup_match = lookup_df[(lookup_df['study'] == study) & (lookup_df['subject_id'] == str(subject_id).strip())]
            if not lookup_match.empty:
                site_id = lookup_match['site_id'].iloc[0]
            open_issues = 0
            issues_col = find_column(df.columns.tolist(), ['open_issues', 'Total Open issue Count per subject', 'Open Issues'])
            if issues_col and issues_col in r.index:
                open_issues = pd.to_numeric(r[issues_col], errors='coerce')
                if pd.isna(open_issues):
                    open_issues = 0
            all_records.append({'study': study, 'subject_id': str(subject_id).strip(), 'site_id': site_id, 'edrr_open_issues': int(open_issues)})
    result_df = pd.DataFrame(all_records)
    print(f"   [OK] EDRR: {len(result_df)} subject records")
    return result_df

# ============================================================================
# MAIN BUILD FUNCTION
# ============================================================================

def build_master_tables(output_dir=None):
    _output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    _file_mapping_path = _output_dir / "file_mapping.csv"

    print("=" * 70)
    print("JAVELIN.AI - BUILD MASTER TABLES")
    print("=" * 70)
    if _USING_CONFIG:
        print("(Using centralized config)")

    if not _file_mapping_path.exists():
        print(f"\n[ERROR] {_file_mapping_path} not found!")
        print("   Run 01_data_discovery.py first.")
        return False

    file_mapping_df = pd.read_csv(_file_mapping_path)
    print(f"\n[INFO] Loaded file mapping: {len(file_mapping_df)} files from {file_mapping_df['study'].nunique()} studies")

    lookup_df = load_edc_lookup(file_mapping_df)
    edc_df = aggregate_edc_metrics(file_mapping_df, lookup_df)
    visit_df = aggregate_visit_tracker(file_mapping_df, lookup_df)
    lab_df = aggregate_missing_lab(file_mapping_df, lookup_df)
    sae_df = aggregate_sae_dashboard(file_mapping_df, lookup_df)
    pages_df = aggregate_missing_pages(file_mapping_df, lookup_df)
    meddra_df = aggregate_coding(file_mapping_df, lookup_df, 'meddra')
    whodd_df = aggregate_coding(file_mapping_df, lookup_df, 'whodd')
    inactivated_df = aggregate_inactivated(file_mapping_df, lookup_df)
    edrr_df = aggregate_edrr(file_mapping_df, lookup_df)

    print("\n" + "=" * 70)
    print("MERGING INTO MASTER SUBJECT TABLE")
    print("=" * 70)

    master_subject = edc_df.copy()
    merge_keys = ['study', 'subject_id']

    if not visit_df.empty:
        visit_df_agg = visit_df.groupby(merge_keys).agg({'missing_visit_count': 'sum', 'max_days_outstanding': 'max'}).reset_index()
        master_subject = master_subject.merge(visit_df_agg, on=merge_keys, how='left')

    if not lab_df.empty:
        lab_df_agg = lab_df.groupby(merge_keys).agg({'lab_issues_count': 'sum'}).reset_index()
        master_subject = master_subject.merge(lab_df_agg, on=merge_keys, how='left')

    if not sae_df.empty:
        sae_df_agg = sae_df.groupby(merge_keys).agg({'sae_total_count': 'sum', 'sae_pending_count': 'sum'}).reset_index()
        master_subject = master_subject.merge(sae_df_agg, on=merge_keys, how='left')

    if not pages_df.empty:
        pages_df_agg = pages_df.groupby(merge_keys).agg({'missing_pages_count': 'sum', 'max_days_page_missing': 'max'}).reset_index()
        master_subject = master_subject.merge(pages_df_agg, on=merge_keys, how='left')

    if not meddra_df.empty:
        meddra_df_agg = meddra_df.groupby(merge_keys).agg({'uncoded_meddra_count': 'sum'}).reset_index()
        master_subject = master_subject.merge(meddra_df_agg, on=merge_keys, how='left')

    if not whodd_df.empty:
        whodd_df_agg = whodd_df.groupby(merge_keys).agg({'uncoded_whodd_count': 'sum'}).reset_index()
        master_subject = master_subject.merge(whodd_df_agg, on=merge_keys, how='left')

    if not inactivated_df.empty:
        inactivated_df_agg = inactivated_df.groupby(merge_keys).agg({'inactivated_forms_count': 'sum'}).reset_index()
        master_subject = master_subject.merge(inactivated_df_agg, on=merge_keys, how='left')

    if not edrr_df.empty:
        edrr_df_agg = edrr_df.groupby(merge_keys).agg({'edrr_open_issues': 'sum'}).reset_index()
        master_subject = master_subject.merge(edrr_df_agg, on=merge_keys, how='left')

    # Data quality fixes
    print("\n[INFO] Applying outlier capping (IQR * 3)...")
    for col in OUTLIER_CAP_COLUMNS:
        if col in master_subject.columns:
            before_max = master_subject[col].max()
            master_subject[col] = cap_outliers(master_subject[col])
            after_max = master_subject[col].max()
            if before_max != after_max:
                print(f"   {col}: max {before_max:.0f} -> {after_max:.0f}")

    for col in NUMERIC_ISSUE_COLUMNS:
        if col in master_subject.columns:
            master_subject[col] = master_subject[col].fillna(0).astype(int)

    print("\n[INFO] Filling missing categorical values...")
    master_subject = fill_missing_categoricals(master_subject)
    for col in CATEGORICAL_COLUMNS:
        if col in master_subject.columns:
            unknown_count = (master_subject[col] == 'Unknown').sum()
            if unknown_count > 0:
                print(f"   {col}: {unknown_count} values set to 'Unknown'")

    master_subject['total_uncoded_count'] = master_subject.get('uncoded_meddra_count', 0) + master_subject.get('uncoded_whodd_count', 0)

    print(f"\n[OK] Master Subject Table: {len(master_subject)} rows")
    print(f"   Columns: {list(master_subject.columns)}")

    # Site-level aggregation
    print("\n" + "=" * 70)
    print("CREATING SITE-LEVEL AGGREGATION")
    print("=" * 70)

    site_agg_cols = {'subject_id': 'count', 'missing_visit_count': 'sum', 'lab_issues_count': 'sum', 'sae_total_count': 'sum', 'sae_pending_count': 'sum', 'missing_pages_count': 'sum', 'uncoded_meddra_count': 'sum', 'uncoded_whodd_count': 'sum', 'inactivated_forms_count': 'sum', 'edrr_open_issues': 'sum'}
    site_agg_cols = {k: v for k, v in site_agg_cols.items() if k in master_subject.columns}
    master_site = master_subject.groupby(['study', 'site_id', 'country', 'region']).agg(site_agg_cols).reset_index()
    master_site = master_site.rename(columns={'subject_id': 'subject_count'})
    print(f"[OK] Master Site Table: {len(master_site)} rows")

    # Study-level aggregation
    print("\n" + "=" * 70)
    print("CREATING STUDY-LEVEL AGGREGATION")
    print("=" * 70)

    study_agg_cols = {'subject_id': 'count', 'site_id': 'nunique', 'missing_visit_count': 'sum', 'lab_issues_count': 'sum', 'sae_total_count': 'sum', 'sae_pending_count': 'sum', 'missing_pages_count': 'sum', 'total_uncoded_count': 'sum', 'inactivated_forms_count': 'sum', 'edrr_open_issues': 'sum'}
    study_agg_cols = {k: v for k, v in study_agg_cols.items() if k in master_subject.columns}
    master_study = master_subject.groupby('study').agg(study_agg_cols).reset_index()
    master_study = master_study.rename(columns={'subject_id': 'subject_count', 'site_id': 'site_count'})
    print(f"[OK] Master Study Table: {len(master_study)} rows")

    # Save outputs
    print("\n" + "=" * 70)
    print("SAVING OUTPUTS")
    print("=" * 70)

    _output_dir.mkdir(exist_ok=True)
    master_subject.to_csv(_output_dir / "master_subject.csv", index=False)
    print(f"[OK] Saved: {_output_dir}/master_subject.csv ({len(master_subject)} subjects)")
    master_site.to_csv(_output_dir / "master_site.csv", index=False)
    print(f"[OK] Saved: {_output_dir}/master_site.csv ({len(master_site)} sites)")
    master_study.to_csv(_output_dir / "master_study.csv", index=False)
    print(f"[OK] Saved: {_output_dir}/master_study.csv ({len(master_study)} studies)")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)
    print(f"\nTotal Studies: {master_subject['study'].nunique()}")
    print(f"Total Sites: {master_subject['site_id'].nunique()}")
    print(f"Total Subjects: {len(master_subject)}")
    print(f"\nIssue Counts:")
    print(f"  * Subjects with missing visits: {(master_subject['missing_visit_count'] > 0).sum()}")
    print(f"  * Subjects with lab issues: {(master_subject['lab_issues_count'] > 0).sum()}")
    print(f"  * Subjects with pending SAE: {(master_subject['sae_pending_count'] > 0).sum()}")
    print(f"  * Subjects with missing pages: {(master_subject['missing_pages_count'] > 0).sum()}")
    print(f"  * Subjects with uncoded terms: {(master_subject['total_uncoded_count'] > 0).sum()}")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Review outputs/master_subject.csv
2. Run: python src/phases/03_calculate_dqi.py (to add DQI scores)
""")
    return True

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    build_master_tables()
