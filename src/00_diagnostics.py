"""
JAVELIN.AI - Comprehensive Data Quality Diagnostics
=====================================================

This script diagnoses ALL 12 identified issues in the data pipeline.
Run this BEFORE running the main pipeline to understand data quality.

Issues Checked:
---------------
1.  fillna(0) treats missing as zero - Track what WOULD be filled
2.  Empty string for missing categorical - Check for empty/null categoricals
3.  No documentation - N/A (documentation issue, not data)
4.  Left join drops subjects in other files - Check for unmatched subjects
5.  No duplicate handling - Check for duplicates
6.  Site grouping with inconsistent metadata - Check site/country/region consistency
7.  Subject ID format mismatch across files - Check ID format variations
8.  Silent file loading failures - Track which files fail to load
9.  No validation of loaded data - Check for invalid values
10. Aggregation edge cases (max of NaN = 0) - Check for all-NaN groups
11. Percentile on small samples - Check sample sizes per feature
12. No outlier handling - Detect outliers in raw data

Usage:
    python src/00_diagnostics.py

Output:
    - outputs/diagnostics_report.txt   : Human-readable report
    - outputs/diagnostics_details.json : Detailed findings
    - outputs/diagnostics_summary.csv  : Issue summary table
"""

import os
import re
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FILE_MAPPING_PATH = OUTPUT_DIR / "file_mapping.csv"

# Column mappings (same as 02_build_master_table.py)
COLUMN_MAPPINGS = {
    'edc_metrics': {
        'subject_id': ['Subject ID', 'Subject', 'SubjectID', 'SUBJECT ID'],
        'site_id': ['Site ID', 'Site', 'SiteID', 'SITE ID', 'Site Number'],
        'country': ['Country', 'COUNTRY'],
        'region': ['Region', 'REGION'],
    },
    'visit_tracker': {
        'subject_id': ['Subject', 'Subject ID', 'SubjectID'],
        'site_id': ['Site', 'Site ID', 'Site Number'],
        'days_outstanding': ['# Days Outstanding', 'Days Outstanding', 'Days_Outstanding'],
    },
    'missing_lab': {
        'subject_id': ['Subject', 'Subject ID'],
        'site_id': ['Site number', 'Site', 'Site ID'],
    },
    'sae_dashboard': {
        'subject_id': ['Patient ID', 'Subject', 'Subject ID', 'PatientID'],
        'site_id': ['Site', 'Site ID'],
    },
    'missing_pages': {
        'subject_id': ['Subject Name', 'SubjectName', 'Subject', 'Subject ID'],
        'site_id': ['Site Number', 'SiteNumber', 'SiteGroupName', 'Site', 'Site ID'],
        'days_missing': ['No. #Days Page Missing', '# of Days Missing', 'Days Missing'],
    },
    'meddra_coding': {
        'subject_id': ['Subject', 'Subject ID'],
    },
    'whodd_coding': {
        'subject_id': ['Subject', 'Subject ID'],
    },
    'inactivated': {
        'subject_id': ['Subject', 'Subject ID'],
        'site_id': ['Study Site Number', 'Site', 'Site ID', 'Site Number'],
    },
    'edrr': {
        'subject_id': ['Subject', 'Subject ID'],
        'open_issues': ['Total Open issue Count per subject', 'Open Issues', 'Open Issue Count'],
    },
}

# Numeric columns that would be filled with 0
NUMERIC_ISSUE_COLUMNS = {
    'visit_tracker': ['days_outstanding'],
    'missing_lab': [],  # count-based
    'sae_dashboard': [],  # count-based
    'missing_pages': ['days_missing'],
    'meddra_coding': [],  # count-based
    'whodd_coding': [],  # count-based
    'inactivated': [],  # count-based
    'edrr': ['open_issues'],
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def find_column(df_columns, possible_names):
    """Find the actual column name from a list of possibilities."""
    df_columns_lower = [str(c).lower().strip() for c in df_columns]
    for name in possible_names:
        if name in df_columns:
            return name
        name_lower = name.lower().strip()
        for i, col_lower in enumerate(df_columns_lower):
            if name_lower in col_lower or col_lower in name_lower:
                return df_columns[i]
    return None


def read_excel_smart(filepath, file_type):
    """Read Excel file, handling multi-row headers."""
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
        else:
            df = pd.read_excel(filepath, sheet_name=0)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def standardize_subject_id(value):
    """Standardize subject ID for comparison."""
    if pd.isna(value):
        return None
    s = str(value).strip().upper()
    # Remove common prefixes
    s = re.sub(r'^(SUBJECT|SUBJ|SUB|PATIENT|PAT|PT)[_\-\s]*', '', s, flags=re.IGNORECASE)
    # Remove leading zeros
    s = s.lstrip('0') or '0'
    return s


# ============================================================================
# DIAGNOSTIC FUNCTIONS
# ============================================================================

class DiagnosticsRunner:
    def __init__(self):
        self.findings = {
            'issue_1_fillna_impact': {},
            'issue_2_empty_categoricals': {},
            'issue_4_left_join_loss': {},
            'issue_5_duplicates': {},
            'issue_6_inconsistent_metadata': {},
            'issue_7_id_format_mismatch': {},
            'issue_8_file_load_failures': [],
            'issue_9_invalid_values': {},
            'issue_10_nan_aggregation': {},
            'issue_11_small_samples': {},
            'issue_12_outliers': {},
            'issue_13_multi_sheet_data_loss': {},  # NEW: Track multi-sheet files
        }
        self.file_mapping = None
        self.edc_subjects = {}  # study -> set of subject_ids
        self.edc_data = {}  # study -> DataFrame

    def load_file_mapping(self):
        """Load file mapping from discovery phase."""
        if not FILE_MAPPING_PATH.exists():
            print(f"ERROR: {FILE_MAPPING_PATH} not found!")
            print("Please run 01_data_discovery.py first.")
            return False

        self.file_mapping = pd.read_csv(FILE_MAPPING_PATH)
        print(f"Loaded file mapping: {len(self.file_mapping)} files from {self.file_mapping['study'].nunique()} studies")
        return True

    def load_edc_baseline(self):
        """Load EDC metrics as baseline for subject list."""
        print("\n[1/8] Loading EDC baseline data...")

        edc_files = self.file_mapping[self.file_mapping['file_type'] == 'edc_metrics']

        for _, row in edc_files.iterrows():
            study = row['study']
            filepath = row['filepath']

            df, error = read_excel_smart(filepath, 'edc_metrics')

            if error:
                self.findings['issue_8_file_load_failures'].append({
                    'study': study,
                    'file_type': 'edc_metrics',
                    'filepath': filepath,
                    'error': error
                })
                continue

            if df.empty:
                self.findings['issue_8_file_load_failures'].append({
                    'study': study,
                    'file_type': 'edc_metrics',
                    'filepath': filepath,
                    'error': 'Empty dataframe'
                })
                continue

            # Find subject_id column
            subject_col = find_column(df.columns.tolist(), COLUMN_MAPPINGS['edc_metrics']['subject_id'])
            if not subject_col:
                self.findings['issue_8_file_load_failures'].append({
                    'study': study,
                    'file_type': 'edc_metrics',
                    'filepath': filepath,
                    'error': 'No subject_id column found'
                })
                continue

            # Store subject IDs (both original and standardized)
            subjects = df[subject_col].dropna().astype(str).str.strip()
            self.edc_subjects[study] = {
                'original': set(subjects.tolist()),
                'standardized': set(subjects.apply(standardize_subject_id).tolist())
            }
            self.edc_data[study] = df

            # Issue 2: Check for empty categoricals
            self._check_empty_categoricals(df, study, 'edc_metrics')

            # Issue 5: Check for duplicates
            self._check_duplicates(df, subject_col, study, 'edc_metrics')

            # Issue 6: Check metadata consistency
            self._check_metadata_consistency(df, study)

        total_subjects = sum(len(v['original']) for v in self.edc_subjects.values())
        print(f"   Loaded {len(self.edc_subjects)} studies with {total_subjects:,} total subjects")

    def check_file_type(self, file_type):
        """Check a specific file type against EDC baseline."""
        print(f"\n   Checking {file_type}...")

        files = self.file_mapping[self.file_mapping['file_type'] == file_type]

        file_type_findings = {
            'total_records': 0,
            'matched_records': 0,
            'unmatched_records': 0,
            'studies_with_no_matches': [],
            'studies_with_all_zeros': [],
            'match_rate_by_study': {},
        }

        for _, row in files.iterrows():
            study = row['study']
            filepath = row['filepath']

            df, error = read_excel_smart(filepath, file_type)

            if error:
                self.findings['issue_8_file_load_failures'].append({
                    'study': study,
                    'file_type': file_type,
                    'filepath': filepath,
                    'error': error
                })
                continue

            if df.empty:
                self.findings['issue_8_file_load_failures'].append({
                    'study': study,
                    'file_type': file_type,
                    'filepath': filepath,
                    'error': 'Empty dataframe after load'
                })
                file_type_findings['studies_with_all_zeros'].append(study)
                continue

            # Find subject_id column
            subject_col = find_column(df.columns.tolist(),
                                       COLUMN_MAPPINGS.get(file_type, {}).get('subject_id', ['Subject', 'Subject ID']))

            if not subject_col:
                self.findings['issue_8_file_load_failures'].append({
                    'study': study,
                    'file_type': file_type,
                    'filepath': filepath,
                    'error': f'No subject_id column found. Columns: {list(df.columns)[:5]}'
                })
                continue

            # Get subjects from this file
            file_subjects = df[subject_col].dropna().astype(str).str.strip()
            file_subjects_std = set(file_subjects.apply(standardize_subject_id).tolist())

            file_type_findings['total_records'] += len(df)

            # Issue 4 & 7: Check match rate with EDC
            if study in self.edc_subjects:
                edc_std = self.edc_subjects[study]['standardized']

                # Try original match first
                file_subjects_orig = set(file_subjects.tolist())
                edc_orig = self.edc_subjects[study]['original']

                orig_matched = len(file_subjects_orig & edc_orig)
                std_matched = len(file_subjects_std & edc_std)

                # Use better match rate
                matched = max(orig_matched, std_matched)
                unmatched = len(file_subjects_orig) - matched

                file_type_findings['matched_records'] += matched
                file_type_findings['unmatched_records'] += unmatched

                match_rate = matched / len(file_subjects_orig) if len(file_subjects_orig) > 0 else 0
                file_type_findings['match_rate_by_study'][study] = {
                    'total_in_file': len(file_subjects_orig),
                    'matched': matched,
                    'unmatched': unmatched,
                    'match_rate': round(match_rate, 3),
                    'orig_match_rate': round(orig_matched / len(file_subjects_orig), 3) if len(file_subjects_orig) > 0 else 0,
                    'std_match_rate': round(std_matched / len(file_subjects_orig), 3) if len(file_subjects_orig) > 0 else 0,
                }

                if matched == 0 and len(file_subjects_orig) > 0:
                    file_type_findings['studies_with_no_matches'].append(study)

                # Issue 7: Check if standardization helped
                if std_matched > orig_matched:
                    if 'id_format_issues' not in self.findings['issue_7_id_format_mismatch']:
                        self.findings['issue_7_id_format_mismatch']['id_format_issues'] = []
                    self.findings['issue_7_id_format_mismatch']['id_format_issues'].append({
                        'study': study,
                        'file_type': file_type,
                        'orig_match_rate': round(orig_matched / len(file_subjects_orig), 3) if len(file_subjects_orig) > 0 else 0,
                        'std_match_rate': round(std_matched / len(file_subjects_orig), 3) if len(file_subjects_orig) > 0 else 0,
                        'improvement': std_matched - orig_matched
                    })

            # Issue 5: Check duplicates
            self._check_duplicates(df, subject_col, study, file_type)

            # Issue 9: Check for invalid values
            self._check_invalid_values(df, study, file_type)

            # Issue 12: Check for outliers
            self._check_outliers(df, study, file_type)

        # Store findings for this file type
        self.findings['issue_4_left_join_loss'][file_type] = file_type_findings

        # Calculate overall stats
        total = file_type_findings['total_records']
        matched = file_type_findings['matched_records']
        if total > 0:
            print(f"      Total records: {total:,}, Matched to EDC: {matched:,} ({matched/total*100:.1f}%)")
            if file_type_findings['studies_with_no_matches']:
                print(f"      WARNING: {len(file_type_findings['studies_with_no_matches'])} studies with 0% match rate")

    def _check_empty_categoricals(self, df, study, file_type):
        """Issue 2: Check for empty strings or nulls in categorical columns."""
        categorical_cols = ['site_id', 'country', 'region', 'subject_status']

        for col_name in categorical_cols:
            col = find_column(df.columns.tolist(),
                             COLUMN_MAPPINGS.get(file_type, {}).get(col_name, [col_name]))
            if col and col in df.columns:
                empty_count = (df[col].astype(str).str.strip() == '').sum()
                null_count = df[col].isna().sum()

                if empty_count > 0 or null_count > 0:
                    key = f"{study}_{file_type}_{col_name}"
                    self.findings['issue_2_empty_categoricals'][key] = {
                        'study': study,
                        'file_type': file_type,
                        'column': col_name,
                        'empty_strings': int(empty_count),
                        'nulls': int(null_count),
                        'total_rows': len(df)
                    }

    def _check_duplicates(self, df, subject_col, study, file_type):
        """Issue 5: Check for duplicate subject IDs."""
        if subject_col not in df.columns:
            return

        dup_count = df.duplicated(subset=[subject_col], keep=False).sum()
        if dup_count > 0:
            key = f"{study}_{file_type}"
            self.findings['issue_5_duplicates'][key] = {
                'study': study,
                'file_type': file_type,
                'duplicate_rows': int(dup_count),
                'unique_subjects': int(df[subject_col].nunique()),
                'total_rows': len(df)
            }

    def _check_metadata_consistency(self, df, study):
        """Issue 6: Check if same site has different country/region values."""
        site_col = find_column(df.columns.tolist(), COLUMN_MAPPINGS['edc_metrics']['site_id'])
        country_col = find_column(df.columns.tolist(), COLUMN_MAPPINGS['edc_metrics']['country'])
        region_col = find_column(df.columns.tolist(), COLUMN_MAPPINGS['edc_metrics']['region'])

        if not site_col:
            return

        issues = []

        for col, col_name in [(country_col, 'country'), (region_col, 'region')]:
            if col and col in df.columns:
                # Group by site, check if multiple values
                site_values = df.groupby(site_col)[col].nunique()
                inconsistent = site_values[site_values > 1]

                if len(inconsistent) > 0:
                    issues.append({
                        'attribute': col_name,
                        'sites_affected': len(inconsistent),
                        'example_sites': inconsistent.head(3).index.tolist()
                    })

        if issues:
            self.findings['issue_6_inconsistent_metadata'][study] = issues

    def _check_invalid_values(self, df, study, file_type):
        """Issue 9: Check for invalid values (negative numbers, impossible values)."""
        issues = []

        # Check numeric columns for negative values
        for col in df.select_dtypes(include=[np.number]).columns:
            negative_count = (df[col] < 0).sum()
            if negative_count > 0:
                issues.append({
                    'column': col,
                    'issue': 'negative_values',
                    'count': int(negative_count)
                })

        # Check days columns for impossibly large values (> 5 years)
        days_cols = [c for c in df.columns if 'day' in c.lower()]
        for col in days_cols:
            if df[col].dtype in [np.float64, np.int64, float, int]:
                impossible = (df[col] > 1825).sum()  # > 5 years
                if impossible > 0:
                    issues.append({
                        'column': col,
                        'issue': 'impossibly_large_days',
                        'count': int(impossible),
                        'max_value': float(df[col].max())
                    })

        if issues:
            key = f"{study}_{file_type}"
            self.findings['issue_9_invalid_values'][key] = issues

    def _check_outliers(self, df, study, file_type):
        """Issue 12: Check for statistical outliers."""
        outliers = []

        for col in df.select_dtypes(include=[np.number]).columns:
            values = df[col].dropna()
            if len(values) < 10:
                continue

            mean = values.mean()
            std = values.std()

            if std == 0:
                continue

            # Count values > 3 std from mean
            outlier_mask = np.abs(values - mean) > 3 * std
            outlier_count = outlier_mask.sum()

            if outlier_count > 0:
                outliers.append({
                    'column': col,
                    'outlier_count': int(outlier_count),
                    'mean': round(float(mean), 2),
                    'std': round(float(std), 2),
                    'max': round(float(values.max()), 2),
                    'threshold': round(float(mean + 3 * std), 2)
                })

        if outliers:
            key = f"{study}_{file_type}"
            self.findings['issue_12_outliers'][key] = outliers

    def check_fillna_impact(self):
        """Issue 1: Estimate impact of fillna(0)."""
        print("\n[7/8] Analyzing fillna(0) impact...")

        # For each file type, count how many studies would have ALL zeros after merge
        file_types = ['visit_tracker', 'missing_lab', 'sae_dashboard', 'missing_pages',
                      'meddra_coding', 'whodd_coding', 'inactivated', 'edrr']

        all_studies = set(self.edc_subjects.keys())

        for file_type in file_types:
            ft_data = self.findings['issue_4_left_join_loss'].get(file_type, {})
            match_by_study = ft_data.get('match_rate_by_study', {})

            # Studies with 0 matches = would be all zeros after fillna
            zero_match_studies = [s for s, d in match_by_study.items() if d['matched'] == 0]

            # Studies not in match data = file failed to load = would be all zeros
            missing_studies = all_studies - set(match_by_study.keys())

            all_zero_studies = set(zero_match_studies) | missing_studies

            self.findings['issue_1_fillna_impact'][file_type] = {
                'total_studies': len(all_studies),
                'studies_with_data': len(all_studies) - len(all_zero_studies),
                'studies_all_zeros': len(all_zero_studies),
                'all_zero_study_list': sorted(list(all_zero_studies)),
                'pct_studies_affected': round(len(all_zero_studies) / len(all_studies) * 100, 1) if all_studies else 0
            }

        # Summary
        affected_file_types = sum(1 for ft, d in self.findings['issue_1_fillna_impact'].items()
                                   if d['studies_all_zeros'] > 0)
        print(f"   {affected_file_types}/{len(file_types)} file types have studies that would be all-zeros")

    def check_small_samples(self):
        """Issue 11: Check for small sample sizes that would affect percentile calculations."""
        print("\n[8/8] Checking sample sizes...")

        for study, df in self.edc_data.items():
            # Count subjects per site
            site_col = find_column(df.columns.tolist(), COLUMN_MAPPINGS['edc_metrics']['site_id'])
            if site_col:
                site_counts = df.groupby(site_col).size()
                small_sites = (site_counts < 5).sum()
                single_subject_sites = (site_counts == 1).sum()

                if small_sites > 0:
                    self.findings['issue_11_small_samples'][study] = {
                        'total_sites': len(site_counts),
                        'sites_with_lt_5_subjects': int(small_sites),
                        'sites_with_1_subject': int(single_subject_sites),
                        'pct_small_sites': round(small_sites / len(site_counts) * 100, 1)
                    }

    def check_multi_sheet_files(self):
        """Issue 13: Check for multi-sheet Excel files where we might be losing data."""
        print("\n[BONUS] Checking for multi-sheet data loss...")

        # File types known to have multiple sheets with important data
        multi_sheet_types = {
            'sae_dashboard': ['SAE Dashboard_DM', 'SAE Dashboard_Safety'],
            'missing_pages': ['All Pages Missing', 'Visit Level Pages Missing'],
        }

        for file_type, expected_sheets in multi_sheet_types.items():
            files = self.file_mapping[self.file_mapping['file_type'] == file_type]

            for _, row in files.iterrows():
                study = row['study']
                filepath = row['filepath']

                try:
                    xl = pd.ExcelFile(filepath)
                    sheet_names = xl.sheet_names

                    if len(sheet_names) > 1:
                        # Count rows in each sheet
                        sheet_rows = {}
                        total_rows = 0
                        for sheet in sheet_names:
                            df_sheet = pd.read_excel(filepath, sheet_name=sheet)
                            sheet_rows[sheet] = len(df_sheet)
                            total_rows += len(df_sheet)

                        # First sheet rows (what we were reading)
                        first_sheet_rows = sheet_rows.get(sheet_names[0], 0)

                        # Data loss = total - first sheet
                        data_loss = total_rows - first_sheet_rows

                        if data_loss > 0:
                            key = f"{study}_{file_type}"
                            self.findings['issue_13_multi_sheet_data_loss'][key] = {
                                'study': study,
                                'file_type': file_type,
                                'total_sheets': len(sheet_names),
                                'sheet_names': sheet_names,
                                'rows_per_sheet': sheet_rows,
                                'first_sheet_rows': first_sheet_rows,
                                'total_rows': total_rows,
                                'rows_lost': data_loss,
                                'pct_data_lost': round(data_loss / total_rows * 100, 1) if total_rows > 0 else 0
                            }
                except Exception as e:
                    pass  # Skip files that can't be read

    def run_all_diagnostics(self):
        """Run all diagnostic checks."""
        print("=" * 70)
        print("JAVELIN.AI - COMPREHENSIVE DATA DIAGNOSTICS")
        print("=" * 70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if not self.load_file_mapping():
            return False

        # Load EDC as baseline
        self.load_edc_baseline()

        # Check each file type against EDC
        print("\n[2/8] Checking file types against EDC baseline...")
        file_types = ['visit_tracker', 'missing_lab', 'sae_dashboard', 'missing_pages',
                      'meddra_coding', 'whodd_coding', 'inactivated', 'edrr']

        for i, file_type in enumerate(file_types, 3):
            self.check_file_type(file_type)

        # Additional checks
        self.check_fillna_impact()
        self.check_small_samples()
        self.check_multi_sheet_files()  # NEW: Check for multi-sheet data loss

        return True

    def generate_report(self):
        """Generate human-readable report."""
        report = []
        report.append("=" * 70)
        report.append("JAVELIN.AI - DATA QUALITY DIAGNOSTICS REPORT")
        report.append("=" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Summary table
        report.append("ISSUE SUMMARY")
        report.append("-" * 70)

        issue_summary = [
            ("1. fillna(0) impact", self._summarize_fillna()),
            ("2. Empty categoricals", self._summarize_empty_cats()),
            ("4. Left join data loss", self._summarize_join_loss()),
            ("5. Duplicates", self._summarize_duplicates()),
            ("6. Inconsistent metadata", self._summarize_metadata()),
            ("7. ID format mismatch", self._summarize_id_mismatch()),
            ("8. File load failures", self._summarize_load_failures()),
            ("9. Invalid values", self._summarize_invalid()),
            ("11. Small samples", self._summarize_small_samples()),
            ("12. Outliers", self._summarize_outliers()),
            ("13. Multi-sheet data loss", self._summarize_multi_sheet()),
        ]

        for issue_name, summary in issue_summary:
            status = summary.get('status', 'UNKNOWN')
            count = summary.get('count', 0)
            symbol = "[!!!]" if status == 'CRITICAL' else "[!!]" if status == 'WARNING' else "[OK]"
            report.append(f"{symbol} {issue_name}: {summary.get('message', 'No data')}")

        report.append("")

        # Detailed sections
        report.append("=" * 70)
        report.append("DETAILED FINDINGS")
        report.append("=" * 70)

        # Issue 1: fillna impact
        report.append("\n--- ISSUE 1: fillna(0) Impact ---")
        for file_type, data in self.findings['issue_1_fillna_impact'].items():
            if data['studies_all_zeros'] > 0:
                report.append(f"{file_type}: {data['studies_all_zeros']}/{data['total_studies']} studies would have ALL zeros")
                report.append(f"   Affected studies: {data['all_zero_study_list']}")

        # Issue 4: Left join loss
        report.append("\n--- ISSUE 4: Left Join Data Loss ---")
        for file_type, data in self.findings['issue_4_left_join_loss'].items():
            if data.get('unmatched_records', 0) > 0:
                total = data['total_records']
                unmatched = data['unmatched_records']
                report.append(f"{file_type}: {unmatched:,}/{total:,} records ({unmatched/total*100:.1f}%) would be LOST in left join")

            # Show studies with poor match rates
            for study, match_data in data.get('match_rate_by_study', {}).items():
                if match_data['match_rate'] < 0.8 and match_data['total_in_file'] > 10:
                    report.append(f"   {study}: only {match_data['match_rate']*100:.0f}% match rate "
                                  f"({match_data['matched']}/{match_data['total_in_file']})")

        # Issue 7: ID format mismatch
        report.append("\n--- ISSUE 7: Subject ID Format Mismatch ---")
        id_issues = self.findings['issue_7_id_format_mismatch'].get('id_format_issues', [])
        if id_issues:
            for issue in id_issues[:10]:  # Top 10
                report.append(f"{issue['study']}/{issue['file_type']}: "
                              f"orig match {issue['orig_match_rate']*100:.0f}% -> "
                              f"standardized {issue['std_match_rate']*100:.0f}% "
                              f"(+{issue['improvement']} subjects)")
        else:
            report.append("No ID format issues detected")

        # Issue 8: File load failures
        report.append("\n--- ISSUE 8: File Load Failures ---")
        failures = self.findings['issue_8_file_load_failures']
        if failures:
            for f in failures:
                report.append(f"{f['study']}/{f['file_type']}: {f['error']}")
        else:
            report.append("No file load failures")

        # Issue 12: Outliers
        report.append("\n--- ISSUE 12: Outliers Detected ---")
        outlier_count = 0
        for key, outliers in self.findings['issue_12_outliers'].items():
            for o in outliers:
                if o['outlier_count'] > 10:  # Only significant outliers
                    report.append(f"{key} - {o['column']}: {o['outlier_count']} outliers "
                                  f"(max={o['max']}, threshold={o['threshold']})")
                    outlier_count += 1
        if outlier_count == 0:
            report.append("No significant outliers detected")

        # Issue 13: Multi-sheet data loss
        report.append("\n--- ISSUE 13: Multi-Sheet Data Loss (CRITICAL!) ---")
        multi_sheet_findings = self.findings['issue_13_multi_sheet_data_loss']
        if multi_sheet_findings:
            total_lost = sum(f['rows_lost'] for f in multi_sheet_findings.values())
            report.append(f"TOTAL ROWS LOST: {total_lost:,}")
            report.append("")
            for key, data in multi_sheet_findings.items():
                if data['rows_lost'] > 0:
                    report.append(f"{data['study']} - {data['file_type']}:")
                    report.append(f"   Sheets: {data['sheet_names']}")
                    report.append(f"   First sheet only: {data['first_sheet_rows']} rows")
                    report.append(f"   Total in all sheets: {data['total_rows']} rows")
                    report.append(f"   DATA LOST: {data['rows_lost']} rows ({data['pct_data_lost']}%)")
        else:
            report.append("No multi-sheet data loss detected")

        report.append("")
        report.append("=" * 70)
        report.append("RECOMMENDATIONS")
        report.append("=" * 70)

        # Generate recommendations based on findings
        recommendations = self._generate_recommendations()
        for i, rec in enumerate(recommendations, 1):
            report.append(f"{i}. [{rec['priority']}] {rec['issue']}")
            report.append(f"   Action: {rec['action']}")
            report.append("")

        return '\n'.join(report)

    def _summarize_fillna(self):
        affected = sum(1 for d in self.findings['issue_1_fillna_impact'].values() if d['studies_all_zeros'] > 0)
        total = len(self.findings['issue_1_fillna_impact'])
        if affected > total * 0.3:
            return {'status': 'CRITICAL', 'count': affected, 'message': f'{affected}/{total} file types have studies with all-zero data'}
        elif affected > 0:
            return {'status': 'WARNING', 'count': affected, 'message': f'{affected}/{total} file types have studies with all-zero data'}
        return {'status': 'OK', 'count': 0, 'message': 'No all-zero studies detected'}

    def _summarize_empty_cats(self):
        count = len(self.findings['issue_2_empty_categoricals'])
        if count > 20:
            return {'status': 'WARNING', 'count': count, 'message': f'{count} columns with empty/null values'}
        return {'status': 'OK', 'count': count, 'message': f'{count} columns with empty/null values'}

    def _summarize_join_loss(self):
        total_lost = sum(d.get('unmatched_records', 0) for d in self.findings['issue_4_left_join_loss'].values())
        total_records = sum(d.get('total_records', 0) for d in self.findings['issue_4_left_join_loss'].values())
        if total_records > 0:
            pct = total_lost / total_records * 100
            if pct > 10:
                return {'status': 'CRITICAL', 'count': total_lost, 'message': f'{total_lost:,} records ({pct:.1f}%) would be lost in joins'}
            elif pct > 1:
                return {'status': 'WARNING', 'count': total_lost, 'message': f'{total_lost:,} records ({pct:.1f}%) would be lost in joins'}
        return {'status': 'OK', 'count': total_lost, 'message': f'{total_lost:,} records would be lost'}

    def _summarize_duplicates(self):
        count = len(self.findings['issue_5_duplicates'])
        if count > 0:
            return {'status': 'WARNING', 'count': count, 'message': f'{count} files have duplicate subject IDs'}
        return {'status': 'OK', 'count': 0, 'message': 'No duplicates found'}

    def _summarize_metadata(self):
        count = len(self.findings['issue_6_inconsistent_metadata'])
        if count > 0:
            return {'status': 'WARNING', 'count': count, 'message': f'{count} studies have inconsistent site metadata'}
        return {'status': 'OK', 'count': 0, 'message': 'Metadata is consistent'}

    def _summarize_id_mismatch(self):
        issues = self.findings['issue_7_id_format_mismatch'].get('id_format_issues', [])
        if len(issues) > 5:
            return {'status': 'WARNING', 'count': len(issues), 'message': f'{len(issues)} files have ID format inconsistencies'}
        return {'status': 'OK', 'count': len(issues), 'message': f'{len(issues)} minor ID format issues'}

    def _summarize_load_failures(self):
        count = len(self.findings['issue_8_file_load_failures'])
        if count > 0:
            return {'status': 'CRITICAL', 'count': count, 'message': f'{count} files failed to load'}
        return {'status': 'OK', 'count': 0, 'message': 'All files loaded successfully'}

    def _summarize_invalid(self):
        count = len(self.findings['issue_9_invalid_values'])
        if count > 0:
            return {'status': 'WARNING', 'count': count, 'message': f'{count} files have invalid values'}
        return {'status': 'OK', 'count': 0, 'message': 'No invalid values detected'}

    def _summarize_small_samples(self):
        affected = sum(1 for d in self.findings['issue_11_small_samples'].values()
                       if d['pct_small_sites'] > 30)
        if affected > 0:
            return {'status': 'WARNING', 'count': affected, 'message': f'{affected} studies have >30% small sites'}
        return {'status': 'OK', 'count': 0, 'message': 'Sample sizes adequate'}

    def _summarize_outliers(self):
        total_outliers = sum(sum(o['outlier_count'] for o in outliers)
                             for outliers in self.findings['issue_12_outliers'].values())
        if total_outliers > 1000:
            return {'status': 'WARNING', 'count': total_outliers, 'message': f'{total_outliers:,} outlier values detected'}
        return {'status': 'OK', 'count': total_outliers, 'message': f'{total_outliers:,} outlier values detected'}

    def _summarize_multi_sheet(self):
        findings = self.findings['issue_13_multi_sheet_data_loss']
        if not findings:
            return {'status': 'OK', 'count': 0, 'message': 'No multi-sheet data loss detected'}

        total_rows_lost = sum(f['rows_lost'] for f in findings.values())
        files_affected = len(findings)

        if total_rows_lost > 1000:
            return {'status': 'CRITICAL', 'count': total_rows_lost,
                    'message': f'{total_rows_lost:,} rows lost across {files_affected} multi-sheet files'}
        elif total_rows_lost > 0:
            return {'status': 'WARNING', 'count': total_rows_lost,
                    'message': f'{total_rows_lost:,} rows lost across {files_affected} multi-sheet files'}
        return {'status': 'OK', 'count': 0, 'message': 'No multi-sheet data loss'}

    def _generate_recommendations(self):
        recommendations = []

        # Based on findings, generate prioritized recommendations

        # Issue 13: Multi-sheet data loss (MOST CRITICAL)
        multi_sheet_loss = sum(f['rows_lost'] for f in self.findings['issue_13_multi_sheet_data_loss'].values())
        if multi_sheet_loss > 0:
            recommendations.append({
                'priority': 'CRITICAL',
                'issue': f'Multi-sheet Excel files: {multi_sheet_loss:,} rows of data being ignored',
                'action': 'Update read_excel_smart() to read ALL sheets from SAE Dashboard and Missing Pages files. Use the FIXED version of 02_build_master_table.py.'
            })

        if len(self.findings['issue_8_file_load_failures']) > 0:
            recommendations.append({
                'priority': 'CRITICAL',
                'issue': 'File load failures',
                'action': 'Fix file loading errors before proceeding. Check file formats and paths.'
            })

        fillna_affected = sum(1 for d in self.findings['issue_1_fillna_impact'].values() if d['studies_all_zeros'] > 0)
        if fillna_affected > 0:
            recommendations.append({
                'priority': 'HIGH',
                'issue': f'fillna(0) would create {fillna_affected} all-zero file types',
                'action': 'Add data completeness tracking before fillna(0). Track which studies have real data vs missing data.'
            })

        join_loss = sum(d.get('unmatched_records', 0) for d in self.findings['issue_4_left_join_loss'].values())
        if join_loss > 0:
            recommendations.append({
                'priority': 'HIGH',
                'issue': f'{join_loss:,} records would be lost in left joins',
                'action': 'Investigate unmatched records. Consider ID standardization or outer joins with tracking.'
            })

        id_issues = len(self.findings['issue_7_id_format_mismatch'].get('id_format_issues', []))
        if id_issues > 0:
            recommendations.append({
                'priority': 'MEDIUM',
                'issue': f'{id_issues} files have ID format mismatches',
                'action': 'Implement subject ID standardization before joins.'
            })

        if len(self.findings['issue_5_duplicates']) > 0:
            recommendations.append({
                'priority': 'MEDIUM',
                'issue': 'Duplicate subject IDs found',
                'action': 'Add duplicate detection and handling (keep first, sum, or flag).'
            })

        if len(self.findings['issue_12_outliers']) > 0:
            recommendations.append({
                'priority': 'LOW',
                'issue': 'Outliers detected in numeric columns',
                'action': 'Consider outlier capping or flagging before DQI calculation.'
            })

        return recommendations

    def save_outputs(self):
        """Save all diagnostic outputs."""
        OUTPUT_DIR.mkdir(exist_ok=True)

        # Save detailed JSON
        json_path = OUTPUT_DIR / "diagnostics_details.json"
        with open(json_path, 'w') as f:
            json.dump(self.findings, f, indent=2, default=str)
        print(f"\nSaved: {json_path}")

        # Save report
        report = self.generate_report()
        report_path = OUTPUT_DIR / "diagnostics_report.txt"
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"Saved: {report_path}")

        # Save summary CSV
        summary_rows = []
        for issue_num, (name, findings) in enumerate([
            ('fillna_impact', self.findings['issue_1_fillna_impact']),
            ('empty_categoricals', self.findings['issue_2_empty_categoricals']),
            ('left_join_loss', self.findings['issue_4_left_join_loss']),
            ('duplicates', self.findings['issue_5_duplicates']),
            ('inconsistent_metadata', self.findings['issue_6_inconsistent_metadata']),
            ('id_format_mismatch', self.findings['issue_7_id_format_mismatch']),
            ('file_load_failures', self.findings['issue_8_file_load_failures']),
            ('invalid_values', self.findings['issue_9_invalid_values']),
            ('small_samples', self.findings['issue_11_small_samples']),
            ('outliers', self.findings['issue_12_outliers']),
        ], 1):
            if isinstance(findings, dict):
                count = len(findings)
            elif isinstance(findings, list):
                count = len(findings)
            else:
                count = 0
            summary_rows.append({
                'issue_number': issue_num,
                'issue_name': name,
                'items_found': count
            })

        summary_df = pd.DataFrame(summary_rows)
        summary_path = OUTPUT_DIR / "diagnostics_summary.csv"
        summary_df.to_csv(summary_path, index=False)
        print(f"Saved: {summary_path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    runner = DiagnosticsRunner()

    if runner.run_all_diagnostics():
        runner.save_outputs()

        # Print report to console
        print("\n")
        print(runner.generate_report())

    print("\n" + "=" * 70)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 70)
    print("""
Review the outputs:
  1. outputs/diagnostics_report.txt   - Human-readable summary
  2. outputs/diagnostics_details.json - Full details for each issue
  3. outputs/diagnostics_summary.csv  - Quick overview

Based on findings, consider:
  - Fixing file load failures first
  - Adding data completeness tracking
  - Implementing ID standardization
  - Adding outlier handling
""")


if __name__ == "__main__":
    main()
