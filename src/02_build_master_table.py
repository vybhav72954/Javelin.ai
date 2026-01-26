"""
Javelin.AI - Step 2: Build Master Table
========================================
This script builds unified master tables from all study data.

Prerequisites:
    - Run 01_data_discovery.py first
    - Check outputs/file_mapping.csv exists

Usage:
    python src/02_build_master_table.py

Output:
    - outputs/master_subject.csv  : One row per subject with all metrics
    - outputs/master_site.csv     : Aggregated site-level metrics
    - outputs/master_study.csv    : Aggregated study-level metrics
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# DATA QUALITY FUNCTIONS (Issues 2, 9, 10, 12)
# ============================================================================

def validate_loaded_data(df, file_type, filepath):
    """
    Issue 9: Validate loaded data for common problems.
    Returns cleaned dataframe and list of issues found.
    """
    issues = []

    if df.empty:
        return df, ['Empty dataframe']

    # Check for negative values in numeric columns (shouldn't exist)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        neg_count = (df[col] < 0).sum()
        if neg_count > 0:
            issues.append(f"{col}: {neg_count} negative values (set to 0)")
            df.loc[df[col] < 0, col] = 0

    # Check for impossibly large day values (> 5 years = 1825 days)
    day_cols = [c for c in df.columns if 'day' in c.lower()]
    for col in day_cols:
        if col in numeric_cols:
            impossible = (df[col] > 1825).sum()
            if impossible > 0:
                issues.append(f"{col}: {impossible} values > 5 years (capped at 1825)")
                df.loc[df[col] > 1825, col] = 1825

    return df, issues


def cap_outliers(series, multiplier=3.0, method='iqr'):
    """
    Issue 12: Cap outliers using IQR method.
    Values beyond Q3 + multiplier*IQR are capped.

    Args:
        series: pandas Series of numeric values
        multiplier: IQR multiplier (default 3.0 = very conservative)
        method: 'iqr' or 'std'

    Returns:
        Series with outliers capped
    """
    if series.empty or series.isna().all():
        return series

    if method == 'iqr':
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1

        if IQR == 0:  # All values are the same
            return series

        upper_bound = Q3 + multiplier * IQR
        lower_bound = max(0, Q1 - multiplier * IQR)  # Don't go below 0 for counts
    else:  # std method
        mean = series.mean()
        std = series.std()
        if std == 0:
            return series
        upper_bound = mean + multiplier * std
        lower_bound = max(0, mean - multiplier * std)

    return series.clip(lower=lower_bound, upper=upper_bound)


def safe_max(series):
    """
    Issue 10: Safe max aggregation that handles all-NaN cases.
    Returns 0 instead of NaN when all values are NaN.
    """
    if series.empty or series.isna().all():
        return 0
    result = series.max()
    return 0 if pd.isna(result) else result


def fill_missing_categoricals(df):
    """
    Issue 2: Fill empty strings and NaN in categorical columns with 'Unknown'.
    """
    categorical_cols = ['country', 'region', 'subject_status']

    for col in categorical_cols:
        if col in df.columns:
            # Replace empty strings
            df[col] = df[col].replace('', 'Unknown')
            # Replace NaN
            df[col] = df[col].fillna('Unknown')
            # Strip whitespace
            df[col] = df[col].astype(str).str.strip()
            # Replace 'nan' string
            df[col] = df[col].replace('nan', 'Unknown')

    return df

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FILE_MAPPING_PATH = OUTPUT_DIR / "file_mapping.csv"

# Column name variations for each file type
# Used for standardizing column names across studies
COLUMN_MAPPINGS = {
    'edc_metrics':{
        'subject_id':['Subject ID', 'Subject', 'SubjectID', 'SUBJECT ID'],
        'site_id':['Site ID', 'Site', 'SiteID', 'SITE ID', 'Site Number'],
        'country':['Country', 'COUNTRY'],
        'region':['Region', 'REGION'],
        'subject_status':['Subject Status', 'Status', 'Subject Status (Source: PRIMARY Form)'],
        'latest_visit':['Latest Visit', 'Latest Visit (SV)', 'Latest Visit (SV) (Source: Rave EDC: BO4)'],
    },
    'visit_tracker':{
        'subject_id':['Subject', 'Subject ID', 'SubjectID'],
        'site_id':['Site', 'Site ID', 'Site Number'],
        'country':['Country'],
        'visit':['Visit', 'Visit Name'],
        'days_outstanding':['# Days Outstanding', 'Days Outstanding', 'Days_Outstanding'],
    },
    'missing_lab':{
        'subject_id':['Subject', 'Subject ID'],
        'site_id':['Site number', 'Site', 'Site ID'],
        'country':['Country'],
        'issue':['Issue', 'Issue Type'],
    },
    'sae_dashboard':{
        'subject_id':['Patient ID', 'Subject', 'Subject ID', 'PatientID'],
        'site_id':['Site', 'Site ID'],
        'country':['Country'],
        'review_status':['Review Status', 'ReviewStatus'],
        'action_status':['Action Status', 'ActionStatus'],
    },
    'missing_pages':{
        'subject_id':['Subject Name', 'SubjectName', 'Subject', 'Subject ID'],
        'site_id':['Site Number', 'SiteNumber', 'SiteGroupName(CountryName)', 'Site', 'Site ID'],
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
        'country':['Country'],
    },
    'edrr':{
        'subject_id':['Subject', 'Subject ID'],
        'open_issues':['Total Open issue Count per subject', 'Open Issues', 'Open Issue Count'],
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def find_column(df_columns, possible_names):
    """Find the actual column name from a list of possibilities."""
    df_columns_lower = [str(c).lower().strip() for c in df_columns]
    for name in possible_names:
        # Exact match first
        if name in df_columns:
            return name
        # Case-insensitive match
        name_lower = name.lower().strip()
        for i, col_lower in enumerate(df_columns_lower):
            if name_lower in col_lower or col_lower in name_lower:
                return df_columns[i]
    return None


def standardize_columns(df, file_type):
    """Rename columns to standard names based on file type."""
    mapping = COLUMN_MAPPINGS.get(file_type, {})
    rename_dict = {}

    for standard_name, possible_names in mapping.items():
        actual_col = find_column(df.columns.tolist(), possible_names)
        if actual_col and actual_col!=standard_name:
            rename_dict[actual_col] = standard_name

    if rename_dict:
        df = df.rename(columns=rename_dict)

    return df


def read_excel_smart(filepath, file_type):
    """
    Read Excel file, handling:
    - Multi-row headers for EDC metrics
    - Multi-sheet files for SAE Dashboard (combines both sheets)
    - Multi-sheet files for Missing Pages (combines both sheets)

    Returns:
        DataFrame with combined data from relevant sheets
    """
    try:
        if file_type == 'edc_metrics':
            # EDC Metrics has multi-row header - data starts at row 4
            # Only need "Subject Level Metrics" sheet (first sheet)
            df = pd.read_excel(filepath, sheet_name=0, header=None)

            # Find the row with actual data (look for "Subject" in columns)
            header_row = 0
            for i in range(min(5, len(df))):
                row_str = ' '.join(df.iloc[i].astype(str).tolist())
                if 'Subject ID' in row_str or 'Project Name' in row_str:
                    header_row = i
                    break

            # Re-read with correct header
            df = pd.read_excel(filepath, sheet_name=0, header=header_row)

            # Skip any remaining metadata rows (where Subject ID is NaN or contains header text)
            if 'Subject ID' in df.columns:
                df = df[df['Subject ID'].notna()]
                df = df[~df['Subject ID'].astype(str).str.contains('Subject ID|Responsible', na=False)]

        elif file_type == 'sae_dashboard':
            # SAE Dashboard has 2 sheets: SAE Dashboard_DM and SAE Dashboard_Safety
            # We need to read BOTH and combine them
            xl = pd.ExcelFile(filepath)
            sheet_names = xl.sheet_names

            all_dfs = []
            for sheet in sheet_names:
                # Only read sheets that look like SAE data
                if 'SAE' in sheet or 'Dashboard' in sheet:
                    df_sheet = pd.read_excel(filepath, sheet_name=sheet)
                    if not df_sheet.empty:
                        # Add source sheet column for tracking
                        df_sheet['_source_sheet'] = sheet
                        all_dfs.append(df_sheet)

            if all_dfs:
                # Combine all sheets
                df = pd.concat(all_dfs, ignore_index=True, sort=False)
                print(f"      Combined {len(all_dfs)} SAE sheets: {sum(len(d) for d in all_dfs)} total rows")
            else:
                df = pd.DataFrame()

        elif file_type == 'missing_pages':
            # Missing Pages has 2 sheets: All Pages Missing and Visit Level Pages Missing
            # Combine both for complete picture
            xl = pd.ExcelFile(filepath)
            sheet_names = xl.sheet_names

            all_dfs = []
            for sheet in sheet_names:
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
            # Standard read for other file types
            df = pd.read_excel(filepath, sheet_name=0)

        # Issue 9: Validate loaded data
        if not df.empty:
            df, issues = validate_loaded_data(df, file_type, filepath)
            # Only print if there were issues
            # (commented out to reduce noise, uncomment for debugging)
            # if issues:
            #     print(f"      Validation issues in {filepath}: {issues}")

        return df
    except Exception as e:
        print(f"    ⚠️ Error reading {filepath}: {e}")
        return pd.DataFrame()


def load_edc_lookup(file_mapping_df):
    """
    Load all EDC Metrics files and create a Subject → Site lookup table.
    This is used for Option 2: joining site_id when missing from other files.
    """
    print("\n📋 Building Subject → Site lookup table from EDC Metrics...")

    edc_files = file_mapping_df[file_mapping_df['file_type']=='edc_metrics']

    lookup_records = []

    for _, row in tqdm(edc_files.iterrows(), total=len(edc_files), desc="   Loading EDC files"):
        study = row['study']
        filepath = row['filepath']

        df = read_excel_smart(filepath, 'edc_metrics')
        if df.empty:
            continue

        df = standardize_columns(df, 'edc_metrics')

        # Extract subject-site mapping
        if 'subject_id' in df.columns and 'site_id' in df.columns:
            for _, r in df.iterrows():
                if pd.notna(r.get('subject_id')):
                    lookup_records.append({
                        'study':study,
                        'subject_id':str(r['subject_id']).strip(),
                        'site_id':str(r.get('site_id', '')).strip() if pd.notna(r.get('site_id')) else '',
                        'country':str(r.get('country', '')).strip() if pd.notna(r.get('country')) else '',
                        'region':str(r.get('region', '')).strip() if pd.notna(r.get('region')) else '',
                    })

    lookup_df = pd.DataFrame(lookup_records)
    print(f"   ✅ Lookup table: {len(lookup_df)} subject-site mappings")

    return lookup_df


# ============================================================================
# AGGREGATION FUNCTIONS FOR EACH FILE TYPE
# ============================================================================

def aggregate_edc_metrics(file_mapping_df, lookup_df):
    """Load and process EDC Metrics - this is our base table."""
    print("\n📊 Processing EDC Metrics (base table)...")

    edc_files = file_mapping_df[file_mapping_df['file_type']=='edc_metrics']
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
                    'study':study,
                    'subject_id':str(r.get('subject_id', '')).strip(),
                    'site_id':str(r.get('site_id', '')).strip() if pd.notna(r.get('site_id')) else '',
                    'country':str(r.get('country', '')).strip() if pd.notna(r.get('country')) else '',
                    'region':str(r.get('region', '')).strip() if pd.notna(r.get('region')) else '',
                    'subject_status':str(r.get('subject_status', '')).strip() if pd.notna(
                        r.get('subject_status')) else '',
                    'latest_visit':str(r.get('latest_visit', '')).strip() if pd.notna(r.get('latest_visit')) else '',
                })

    result_df = pd.DataFrame(all_records)
    print(f"   ✅ EDC Metrics: {len(result_df)} subjects")
    return result_df


def aggregate_visit_tracker(file_mapping_df, lookup_df):
    """Aggregate Visit Tracker - count missing visits per subject."""
    print("\n📊 Processing Visit Tracker...")

    files = file_mapping_df[file_mapping_df['file_type']=='visit_tracker']
    all_records = []

    for _, row in tqdm(files.iterrows(), total=len(files), desc="   Processing"):
        study = row['study']
        filepath = row['filepath']

        df = read_excel_smart(filepath, 'visit_tracker')
        if df.empty:
            continue

        df = standardize_columns(df, 'visit_tracker')

        # Check if we have the required columns
        if 'subject_id' not in df.columns:
            # Try to find subject column with different name
            subject_col = find_column(df.columns.tolist(), ['Subject', 'Subject ID', 'SubjectID'])
            if subject_col:
                df = df.rename(columns={subject_col:'subject_id'})
            else:
                print(f"    ⚠️ Skipping {filepath} - no subject column found")
                continue

        # Aggregate per subject
        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue

            # Get site_id from file or lookup
            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                # Option 2: Lookup from EDC
                lookup_match = lookup_df[(lookup_df['study']==study) &
                                         (lookup_df['subject_id']==str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]

            # Calculate metrics
            days_outstanding_col = find_column(group.columns.tolist(),
                                               ['days_outstanding', '# Days Outstanding', 'Days Outstanding'])
            max_days = 0
            if days_outstanding_col and days_outstanding_col in group.columns:
                max_days = pd.to_numeric(group[days_outstanding_col], errors='coerce').max()
                if pd.isna(max_days):
                    max_days = 0

            all_records.append({
                'study':study,
                'subject_id':str(subject_id).strip(),
                'site_id':site_id,
                'missing_visit_count':len(group),
                'max_days_outstanding':max_days,
            })

    result_df = pd.DataFrame(all_records)
    print(f"   ✅ Visit Tracker: {len(result_df)} subject records")
    return result_df


def aggregate_missing_lab(file_mapping_df, lookup_df):
    """Aggregate Missing Lab - count lab issues per subject."""
    print("\n📊 Processing Missing Lab...")

    files = file_mapping_df[file_mapping_df['file_type']=='missing_lab']
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
                df = df.rename(columns={subject_col:'subject_id'})
            else:
                continue

        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue

            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                lookup_match = lookup_df[(lookup_df['study']==study) &
                                         (lookup_df['subject_id']==str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]

            all_records.append({
                'study':study,
                'subject_id':str(subject_id).strip(),
                'site_id':site_id,
                'lab_issues_count':len(group),
            })

    result_df = pd.DataFrame(all_records)
    print(f"   ✅ Missing Lab: {len(result_df)} subject records")
    return result_df


def aggregate_sae_dashboard(file_mapping_df, lookup_df):
    """Aggregate SAE Dashboard - count pending SAE reviews per subject."""
    print("\n📊 Processing SAE Dashboard...")

    files = file_mapping_df[file_mapping_df['file_type']=='sae_dashboard']
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
                df = df.rename(columns={subject_col:'subject_id'})
            else:
                continue

        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue

            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                lookup_match = lookup_df[(lookup_df['study']==study) &
                                         (lookup_df['subject_id']==str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]

            # Count pending (not completed) reviews
            pending_count = 0
            if 'review_status' in group.columns:
                pending_count = len(group[group['review_status']!='Review Completed'])
            else:
                pending_count = len(group)  # Assume all are pending if no status

            all_records.append({
                'study':study,
                'subject_id':str(subject_id).strip(),
                'site_id':site_id,
                'sae_total_count':len(group),
                'sae_pending_count':pending_count,
            })

    result_df = pd.DataFrame(all_records)
    print(f"   ✅ SAE Dashboard: {len(result_df)} subject records")
    return result_df


def aggregate_missing_pages(file_mapping_df, lookup_df):
    """Aggregate Missing Pages - count missing pages per subject."""
    print("\n📊 Processing Missing Pages...")

    files = file_mapping_df[file_mapping_df['file_type']=='missing_pages']
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
                df = df.rename(columns={subject_col:'subject_id'})
            else:
                continue

        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue

            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                lookup_match = lookup_df[(lookup_df['study']==study) &
                                         (lookup_df['subject_id']==str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]

            # Get max days missing
            max_days = 0
            days_col = find_column(group.columns.tolist(),
                                   ['days_missing', 'No. #Days Page Missing', '# of Days Missing'])
            if days_col and days_col in group.columns:
                max_days = pd.to_numeric(group[days_col], errors='coerce').max()
                if pd.isna(max_days):
                    max_days = 0

            all_records.append({
                'study':study,
                'subject_id':str(subject_id).strip(),
                'site_id':site_id,
                'missing_pages_count':len(group),
                'max_days_page_missing':max_days,
            })

    result_df = pd.DataFrame(all_records)
    print(f"   ✅ Missing Pages: {len(result_df)} subject records")
    return result_df


def aggregate_coding(file_mapping_df, lookup_df, coding_type='meddra'):
    """Aggregate Coding Reports - count uncoded terms per subject."""
    file_type = f'{coding_type}_coding'
    print(f"\n📊 Processing {coding_type.upper()} Coding...")

    files = file_mapping_df[file_mapping_df['file_type']==file_type]
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
                df = df.rename(columns={subject_col:'subject_id'})
            else:
                continue

        # Filter for uncoded terms
        uncoded_df = df.copy()
        if 'coding_status' in df.columns:
            uncoded_df = df[df['coding_status'].str.contains('UnCoded|Uncoded|Not Coded', case=False, na=False)]

        for subject_id, group in uncoded_df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue

            # Lookup site from EDC
            site_id = ''
            lookup_match = lookup_df[(lookup_df['study']==study) &
                                     (lookup_df['subject_id']==str(subject_id).strip())]
            if not lookup_match.empty:
                site_id = lookup_match['site_id'].iloc[0]

            all_records.append({
                'study':study,
                'subject_id':str(subject_id).strip(),
                'site_id':site_id,
                f'uncoded_{coding_type}_count':len(group),
            })

    result_df = pd.DataFrame(all_records)
    print(f"   ✅ {coding_type.upper()} Coding: {len(result_df)} subject records with uncoded terms")
    return result_df


def aggregate_inactivated(file_mapping_df, lookup_df):
    """Aggregate Inactivated Forms - count per subject."""
    print("\n📊 Processing Inactivated Forms...")

    files = file_mapping_df[file_mapping_df['file_type']=='inactivated']
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
                df = df.rename(columns={subject_col:'subject_id'})
            else:
                continue

        for subject_id, group in df.groupby('subject_id'):
            if pd.isna(subject_id):
                continue

            # Get site_id from file or lookup (Option 2)
            site_id = ''
            if 'site_id' in group.columns and group['site_id'].notna().any():
                site_id = str(group['site_id'].iloc[0]).strip()
            else:
                # Option 2: Lookup from EDC
                lookup_match = lookup_df[(lookup_df['study']==study) &
                                         (lookup_df['subject_id']==str(subject_id).strip())]
                if not lookup_match.empty:
                    site_id = lookup_match['site_id'].iloc[0]

            all_records.append({
                'study':study,
                'subject_id':str(subject_id).strip(),
                'site_id':site_id,
                'inactivated_forms_count':len(group),
            })

    result_df = pd.DataFrame(all_records)
    print(f"   ✅ Inactivated: {len(result_df)} subject records")
    return result_df


def aggregate_edrr(file_mapping_df, lookup_df):
    """Aggregate EDRR - open issues per subject."""
    print("\n📊 Processing EDRR...")

    files = file_mapping_df[file_mapping_df['file_type']=='edrr']
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
                df = df.rename(columns={subject_col:'subject_id'})
            else:
                continue

        for _, r in df.iterrows():
            subject_id = r.get('subject_id')
            if pd.isna(subject_id):
                continue

            # Lookup site from EDC
            site_id = ''
            lookup_match = lookup_df[(lookup_df['study']==study) &
                                     (lookup_df['subject_id']==str(subject_id).strip())]
            if not lookup_match.empty:
                site_id = lookup_match['site_id'].iloc[0]

            # Get open issues count
            open_issues = 0
            issues_col = find_column(df.columns.tolist(),
                                     ['open_issues', 'Total Open issue Count per subject', 'Open Issues'])
            if issues_col and issues_col in r.index:
                open_issues = pd.to_numeric(r[issues_col], errors='coerce')
                if pd.isna(open_issues):
                    open_issues = 0

            all_records.append({
                'study':study,
                'subject_id':str(subject_id).strip(),
                'site_id':site_id,
                'edrr_open_issues':int(open_issues),
            })

    result_df = pd.DataFrame(all_records)
    print(f"   ✅ EDRR: {len(result_df)} subject records")
    return result_df


# ============================================================================
# MAIN BUILD FUNCTION
# ============================================================================

def build_master_tables():
    """Main function to build all master tables."""

    print("=" * 70)
    print("JAVELIN.AI - BUILD MASTER TABLES")
    print("=" * 70)

    # Check prerequisites
    if not FILE_MAPPING_PATH.exists():
        print(f"\n❌ ERROR: {FILE_MAPPING_PATH} not found!")
        print("   Run 01_data_discovery.py first.")
        return

    # Load file mapping
    file_mapping_df = pd.read_csv(FILE_MAPPING_PATH)
    print(f"\n📁 Loaded file mapping: {len(file_mapping_df)} files from {file_mapping_df['study'].nunique()} studies")

    # Step 1: Build Subject-Site lookup from EDC Metrics
    lookup_df = load_edc_lookup(file_mapping_df)

    # Step 2: Process each file type
    edc_df = aggregate_edc_metrics(file_mapping_df, lookup_df)
    visit_df = aggregate_visit_tracker(file_mapping_df, lookup_df)
    lab_df = aggregate_missing_lab(file_mapping_df, lookup_df)
    sae_df = aggregate_sae_dashboard(file_mapping_df, lookup_df)
    pages_df = aggregate_missing_pages(file_mapping_df, lookup_df)
    meddra_df = aggregate_coding(file_mapping_df, lookup_df, 'meddra')
    whodd_df = aggregate_coding(file_mapping_df, lookup_df, 'whodd')
    inactivated_df = aggregate_inactivated(file_mapping_df, lookup_df)
    edrr_df = aggregate_edrr(file_mapping_df, lookup_df)

    # Step 3: Merge all into master_subject
    print("\n" + "=" * 70)
    print("MERGING INTO MASTER SUBJECT TABLE")
    print("=" * 70)

    # Start with EDC as base
    master_subject = edc_df.copy()

    # Merge each aggregated dataframe
    merge_keys = ['study', 'subject_id']

    # Visit Tracker
    if not visit_df.empty:
        visit_df_agg = visit_df.groupby(merge_keys).agg({
            'missing_visit_count':'sum',
            'max_days_outstanding':'max'
        }).reset_index()
        master_subject = master_subject.merge(visit_df_agg, on=merge_keys, how='left')

    # Missing Lab
    if not lab_df.empty:
        lab_df_agg = lab_df.groupby(merge_keys).agg({
            'lab_issues_count':'sum'
        }).reset_index()
        master_subject = master_subject.merge(lab_df_agg, on=merge_keys, how='left')

    # SAE Dashboard
    if not sae_df.empty:
        sae_df_agg = sae_df.groupby(merge_keys).agg({
            'sae_total_count':'sum',
            'sae_pending_count':'sum'
        }).reset_index()
        master_subject = master_subject.merge(sae_df_agg, on=merge_keys, how='left')

    # Missing Pages
    if not pages_df.empty:
        pages_df_agg = pages_df.groupby(merge_keys).agg({
            'missing_pages_count':'sum',
            'max_days_page_missing':'max'
        }).reset_index()
        master_subject = master_subject.merge(pages_df_agg, on=merge_keys, how='left')

    # MedDRA Coding
    if not meddra_df.empty:
        meddra_df_agg = meddra_df.groupby(merge_keys).agg({
            'uncoded_meddra_count':'sum'
        }).reset_index()
        master_subject = master_subject.merge(meddra_df_agg, on=merge_keys, how='left')

    # WHODD Coding
    if not whodd_df.empty:
        whodd_df_agg = whodd_df.groupby(merge_keys).agg({
            'uncoded_whodd_count':'sum'
        }).reset_index()
        master_subject = master_subject.merge(whodd_df_agg, on=merge_keys, how='left')

    # Inactivated
    if not inactivated_df.empty:
        inactivated_df_agg = inactivated_df.groupby(merge_keys).agg({
            'inactivated_forms_count':'sum'
        }).reset_index()
        master_subject = master_subject.merge(inactivated_df_agg, on=merge_keys, how='left')

    # EDRR
    if not edrr_df.empty:
        edrr_df_agg = edrr_df.groupby(merge_keys).agg({
            'edrr_open_issues':'sum'
        }).reset_index()
        master_subject = master_subject.merge(edrr_df_agg, on=merge_keys, how='left')

    # ========================================================================
    # DATA QUALITY FIXES (Issues 2, 10, 12)
    # ========================================================================

    # Issue 12: Cap outliers BEFORE filling NaN (conservative IQR * 3)
    # Only cap columns with known outlier issues (from diagnostics)
    outlier_cols = ['max_days_outstanding', 'max_days_page_missing',
                    'lab_issues_count', 'inactivated_forms_count']

    print("\n📊 Applying outlier capping (IQR * 3)...")
    for col in outlier_cols:
        if col in master_subject.columns:
            before_max = master_subject[col].max()
            master_subject[col] = cap_outliers(master_subject[col], multiplier=3.0, method='iqr')
            after_max = master_subject[col].max()
            if before_max != after_max:
                print(f"   {col}: max {before_max:.0f} → {after_max:.0f}")

    # Fill NaN with 0 for numeric columns
    numeric_cols = ['missing_visit_count', 'max_days_outstanding', 'lab_issues_count',
                    'sae_total_count', 'sae_pending_count', 'missing_pages_count',
                    'max_days_page_missing', 'uncoded_meddra_count', 'uncoded_whodd_count',
                    'inactivated_forms_count', 'edrr_open_issues']

    for col in numeric_cols:
        if col in master_subject.columns:
            master_subject[col] = master_subject[col].fillna(0).astype(int)

    # Issue 2: Fill missing categorical values with 'Unknown'
    print("\n📊 Filling missing categorical values...")
    master_subject = fill_missing_categoricals(master_subject)
    for col in ['country', 'region', 'subject_status']:
        if col in master_subject.columns:
            unknown_count = (master_subject[col] == 'Unknown').sum()
            if unknown_count > 0:
                print(f"   {col}: {unknown_count} values set to 'Unknown'")

    # Add total uncoded count
    master_subject['total_uncoded_count'] = (
            master_subject.get('uncoded_meddra_count', 0) +
            master_subject.get('uncoded_whodd_count', 0)
    )

    print(f"\n✅ Master Subject Table: {len(master_subject)} rows")
    print(f"   Columns: {list(master_subject.columns)}")

    # Step 4: Create Site-level aggregation
    print("\n" + "=" * 70)
    print("CREATING SITE-LEVEL AGGREGATION")
    print("=" * 70)

    site_agg_cols = {
        'subject_id':'count',
        'missing_visit_count':'sum',
        'lab_issues_count':'sum',
        'sae_total_count':'sum',
        'sae_pending_count':'sum',
        'missing_pages_count':'sum',
        'uncoded_meddra_count':'sum',
        'uncoded_whodd_count':'sum',
        'inactivated_forms_count':'sum',
        'edrr_open_issues':'sum',
    }

    # Filter to only existing columns
    site_agg_cols = {k:v for k, v in site_agg_cols.items() if k in master_subject.columns}

    master_site = master_subject.groupby(['study', 'site_id', 'country', 'region']).agg(site_agg_cols).reset_index()
    master_site = master_site.rename(columns={'subject_id':'subject_count'})

    print(f"✅ Master Site Table: {len(master_site)} rows")

    # Step 5: Create Study-level aggregation
    print("\n" + "=" * 70)
    print("CREATING STUDY-LEVEL AGGREGATION")
    print("=" * 70)

    study_agg_cols = {
        'subject_id':'count',
        'site_id':'nunique',
        'missing_visit_count':'sum',
        'lab_issues_count':'sum',
        'sae_total_count':'sum',
        'sae_pending_count':'sum',
        'missing_pages_count':'sum',
        'total_uncoded_count':'sum',
        'inactivated_forms_count':'sum',
        'edrr_open_issues':'sum',
    }

    study_agg_cols = {k:v for k, v in study_agg_cols.items() if k in master_subject.columns}

    master_study = master_subject.groupby('study').agg(study_agg_cols).reset_index()
    master_study = master_study.rename(columns={'subject_id':'subject_count', 'site_id':'site_count'})

    print(f"✅ Master Study Table: {len(master_study)} rows")

    # Step 6: Save outputs
    print("\n" + "=" * 70)
    print("SAVING OUTPUTS")
    print("=" * 70)

    OUTPUT_DIR.mkdir(exist_ok=True)

    master_subject.to_csv(OUTPUT_DIR / "master_subject.csv", index=False)
    print(f"✅ Saved: outputs/master_subject.csv ({len(master_subject)} subjects)")

    master_site.to_csv(OUTPUT_DIR / "master_site.csv", index=False)
    print(f"✅ Saved: outputs/master_site.csv ({len(master_site)} sites)")

    master_study.to_csv(OUTPUT_DIR / "master_study.csv", index=False)
    print(f"✅ Saved: outputs/master_study.csv ({len(master_study)} studies)")

    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)

    print(f"\nTotal Studies: {master_subject['study'].nunique()}")
    print(f"Total Sites: {master_subject['site_id'].nunique()}")
    print(f"Total Subjects: {len(master_subject)}")

    print(f"\nIssue Counts:")
    print(f"  • Subjects with missing visits: {(master_subject['missing_visit_count'] > 0).sum()}")
    print(f"  • Subjects with lab issues: {(master_subject['lab_issues_count'] > 0).sum()}")
    print(f"  • Subjects with pending SAE: {(master_subject['sae_pending_count'] > 0).sum()}")
    print(f"  • Subjects with missing pages: {(master_subject['missing_pages_count'] > 0).sum()}")
    print(f"  • Subjects with uncoded terms: {(master_subject['total_uncoded_count'] > 0).sum()}")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Review outputs/master_subject.csv
2. Run: python src/03_calculate_dqi.py (to add DQI scores)
""")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__=="__main__":
    build_master_tables()
