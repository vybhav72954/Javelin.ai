"""
JAVELIN.AI - Comprehensive Data Quality Diagnostics (FIXED)
=============================================================

This script diagnoses ALL issues in the data pipeline.
Run this BEFORE running the main pipeline to understand data quality.

FIXES in this version:
- Uses same multi-sheet reading logic as pipeline
- Distinguishes between "empty files" (OK) vs "actual errors"
- Clearer categorization of issues

Issues Checked:
---------------
1.  fillna(0) treats missing as zero - Track what WOULD be filled
2.  Empty string for missing categorical - Check for empty/null categoricals
4.  Left join drops subjects - Check for unmatched subjects
5.  No duplicate handling - Check for duplicates
6.  Site grouping with inconsistent metadata - Check consistency
7.  Subject ID format mismatch - Check ID format variations
8.  Silent file loading failures - Track which files fail to load
9.  No validation of loaded data - Check for invalid values
11. Percentile on small samples - Check sample sizes per feature
12. No outlier handling - Detect outliers in raw data
13. Multi-sheet data loss - Check if pipeline reads all sheets

Usage:
    python src/00_diagnostics.py
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

# Column mappings
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
    """
    Read Excel file - SAME LOGIC AS PIPELINE.
    Handles multi-sheet files for SAE Dashboard and Missing Pages.

    Returns:
        tuple: (DataFrame, error_message or None, is_legitimately_empty)
    """
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
            return df, None, df.empty

        elif file_type == 'sae_dashboard':
            # FIXED: Read BOTH sheets (same as pipeline)
            xl = pd.ExcelFile(filepath)
            sheet_names = xl.sheet_names

            all_dfs = []
            for sheet in sheet_names:
                if 'SAE' in sheet or 'Dashboard' in sheet:
                    df_sheet = pd.read_excel(filepath, sheet_name=sheet)
                    if not df_sheet.empty:
                        df_sheet['_source_sheet'] = sheet
                        all_dfs.append(df_sheet)

            if all_dfs:
                df = pd.concat(all_dfs, ignore_index=True, sort=False)
                return df, None, False
            else:
                return pd.DataFrame(), None, True  # Legitimately empty

        elif file_type == 'missing_pages':
            # FIXED: Read ALL sheets (same as pipeline)
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
                return df, None, False
            else:
                return pd.DataFrame(), None, True  # Legitimately empty
        else:
            df = pd.read_excel(filepath, sheet_name=0)
            return df, None, df.empty

    except Exception as e:
        return pd.DataFrame(), str(e), False


def standardize_subject_id(value):
    """Standardize subject ID for comparison."""
    if pd.isna(value):
        return None
    s = str(value).strip().upper()
    s = re.sub(r'^(SUBJECT|SUBJ|SUB|PATIENT|PAT|PT)[_\-\s]*', '', s, flags=re.IGNORECASE)
    s = s.lstrip('0') or '0'
    return s


# ============================================================================
# DIAGNOSTICS RUNNER
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
            'issue_8_file_errors': [],          # Actual errors
            'issue_8_empty_files': [],          # Legitimately empty (OK)
            'issue_9_invalid_values': {},
            'issue_11_small_samples': {},
            'issue_12_outliers': {},
        }
        self.file_mapping = None
        self.edc_subjects = {}
        self.edc_data = {}

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
        print("\n[1/7] Loading EDC baseline data...")

        edc_files = self.file_mapping[self.file_mapping['file_type'] == 'edc_metrics']

        for _, row in edc_files.iterrows():
            study = row['study']
            filepath = row['filepath']

            df, error, is_empty = read_excel_smart(filepath, 'edc_metrics')

            if error:
                self.findings['issue_8_file_errors'].append({
                    'study': study, 'file_type': 'edc_metrics',
                    'error': error, 'severity': 'CRITICAL'
                })
                continue

            if is_empty:
                self.findings['issue_8_empty_files'].append({
                    'study': study, 'file_type': 'edc_metrics',
                    'note': 'EDC file is empty - this is unusual'
                })
                continue

            subject_col = find_column(df.columns.tolist(), COLUMN_MAPPINGS['edc_metrics']['subject_id'])
            if not subject_col:
                self.findings['issue_8_file_errors'].append({
                    'study': study, 'file_type': 'edc_metrics',
                    'error': 'No subject_id column found', 'severity': 'CRITICAL'
                })
                continue

            subjects = df[subject_col].dropna().astype(str).str.strip()
            self.edc_subjects[study] = {
                'original': set(subjects.tolist()),
                'standardized': set(subjects.apply(standardize_subject_id).tolist())
            }
            self.edc_data[study] = df

            self._check_empty_categoricals(df, study, 'edc_metrics')
            self._check_duplicates(df, subject_col, study, 'edc_metrics')
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
            'studies_with_data': [],
            'studies_empty': [],
            'match_rate_by_study': {},
        }

        for _, row in files.iterrows():
            study = row['study']
            filepath = row['filepath']

            df, error, is_empty = read_excel_smart(filepath, file_type)

            if error:
                self.findings['issue_8_file_errors'].append({
                    'study': study, 'file_type': file_type,
                    'error': error, 'severity': 'HIGH'
                })
                continue

            if is_empty:
                # This is OK - some studies legitimately have no issues of this type
                self.findings['issue_8_empty_files'].append({
                    'study': study, 'file_type': file_type,
                    'note': 'No data (legitimate - study has no issues of this type)'
                })
                file_type_findings['studies_empty'].append(study)
                continue

            file_type_findings['studies_with_data'].append(study)

            subject_col = find_column(df.columns.tolist(),
                                       COLUMN_MAPPINGS.get(file_type, {}).get('subject_id', ['Subject', 'Subject ID']))

            if not subject_col:
                self.findings['issue_8_file_errors'].append({
                    'study': study, 'file_type': file_type,
                    'error': f'No subject_id column. Columns: {list(df.columns)[:5]}',
                    'severity': 'MEDIUM'
                })
                continue

            file_subjects = df[subject_col].dropna().astype(str).str.strip()
            file_subjects_std = set(file_subjects.apply(standardize_subject_id).tolist())
            file_type_findings['total_records'] += len(df)

            if study in self.edc_subjects:
                edc_std = self.edc_subjects[study]['standardized']
                file_subjects_orig = set(file_subjects.tolist())
                edc_orig = self.edc_subjects[study]['original']

                orig_matched = len(file_subjects_orig & edc_orig)
                std_matched = len(file_subjects_std & edc_std)
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
                }

                # Issue 7: Check if standardization helped
                if std_matched > orig_matched:
                    if 'id_format_issues' not in self.findings['issue_7_id_format_mismatch']:
                        self.findings['issue_7_id_format_mismatch']['id_format_issues'] = []
                    self.findings['issue_7_id_format_mismatch']['id_format_issues'].append({
                        'study': study, 'file_type': file_type,
                        'improvement': std_matched - orig_matched,
                        'note': 'ID standardization helped match more records'
                    })

            self._check_duplicates(df, subject_col, study, file_type)
            self._check_invalid_values(df, study, file_type)
            self._check_outliers(df, study, file_type)

        self.findings['issue_4_left_join_loss'][file_type] = file_type_findings

        total = file_type_findings['total_records']
        matched = file_type_findings['matched_records']
        n_with_data = len(file_type_findings['studies_with_data'])
        n_empty = len(file_type_findings['studies_empty'])

        if total > 0:
            print(f"      Records: {total:,} | Matched to EDC: {matched:,} ({matched/total*100:.1f}%)")
        print(f"      Studies with data: {n_with_data} | Studies empty (OK): {n_empty}")

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
                        'study': study, 'file_type': file_type, 'column': col_name,
                        'empty_strings': int(empty_count), 'nulls': int(null_count),
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
                'study': study, 'file_type': file_type,
                'duplicate_rows': int(dup_count),
                'unique_subjects': int(df[subject_col].nunique()),
                'total_rows': len(df),
                'note': 'Multiple records per subject is expected for some file types'
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
        """Issue 9: Check for invalid values."""
        issues = []

        for col in df.select_dtypes(include=[np.number]).columns:
            negative_count = (df[col] < 0).sum()
            if negative_count > 0:
                issues.append({'column': col, 'issue': 'negative_values', 'count': int(negative_count)})

        days_cols = [c for c in df.columns if 'day' in c.lower()]
        for col in days_cols:
            if df[col].dtype in [np.float64, np.int64, float, int]:
                impossible = (df[col] > 1825).sum()
                if impossible > 0:
                    issues.append({
                        'column': col, 'issue': 'impossibly_large_days',
                        'count': int(impossible), 'max_value': float(df[col].max())
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

            outlier_mask = np.abs(values - mean) > 3 * std
            outlier_count = outlier_mask.sum()

            if outlier_count > 0:
                outliers.append({
                    'column': col, 'outlier_count': int(outlier_count),
                    'mean': round(float(mean), 2), 'std': round(float(std), 2),
                    'max': round(float(values.max()), 2),
                    'threshold': round(float(mean + 3 * std), 2)
                })

        if outliers:
            key = f"{study}_{file_type}"
            self.findings['issue_12_outliers'][key] = outliers

    def check_fillna_impact(self):
        """Issue 1: Estimate impact of fillna(0)."""
        print("\n[6/7] Analyzing fillna(0) impact...")

        file_types = ['visit_tracker', 'missing_lab', 'sae_dashboard', 'missing_pages',
                      'meddra_coding', 'whodd_coding', 'inactivated', 'edrr']

        all_studies = set(self.edc_subjects.keys())

        for file_type in file_types:
            ft_data = self.findings['issue_4_left_join_loss'].get(file_type, {})
            studies_with_data = set(ft_data.get('studies_with_data', []))
            studies_empty = set(ft_data.get('studies_empty', []))

            self.findings['issue_1_fillna_impact'][file_type] = {
                'total_studies': len(all_studies),
                'studies_with_data': len(studies_with_data),
                'studies_empty': len(studies_empty),
                'studies_empty_list': sorted(list(studies_empty)),
                'note': 'Empty studies will have 0 values after fillna - this is correct behavior'
            }

        affected = sum(1 for d in self.findings['issue_1_fillna_impact'].values() if d['studies_empty'] > 0)
        print(f"   {affected}/{len(file_types)} file types have studies with no data (will be zeros - this is OK)")

    def check_small_samples(self):
        """Issue 11: Check for small sample sizes."""
        print("\n[7/7] Checking sample sizes...")

        for study, df in self.edc_data.items():
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

    def run_all_diagnostics(self):
        """Run all diagnostic checks."""
        print("=" * 70)
        print("JAVELIN.AI - DATA QUALITY DIAGNOSTICS (FIXED VERSION)")
        print("=" * 70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nNOTE: This version uses the same multi-sheet reading logic as the pipeline.")

        if not self.load_file_mapping():
            return False

        self.load_edc_baseline()

        print("\n[2/7] Checking file types against EDC baseline...")
        file_types = ['visit_tracker', 'missing_lab', 'sae_dashboard', 'missing_pages',
                      'meddra_coding', 'whodd_coding', 'inactivated', 'edrr']

        for file_type in file_types:
            self.check_file_type(file_type)

        self.check_fillna_impact()
        self.check_small_samples()

        return True

    def generate_report(self):
        """Generate human-readable report."""
        report = []
        report.append("=" * 70)
        report.append("JAVELIN.AI - DATA QUALITY DIAGNOSTICS REPORT (FIXED)")
        report.append("=" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Summary
        report.append("ISSUE SUMMARY")
        report.append("-" * 70)

        # Issue 8 split into errors vs empty
        n_errors = len(self.findings['issue_8_file_errors'])
        n_empty = len(self.findings['issue_8_empty_files'])

        summaries = [
            ("File errors (actual problems)", n_errors, "CRITICAL" if n_errors > 0 else "OK"),
            ("Empty files (legitimate)", n_empty, "INFO"),
            ("Empty categoricals", len(self.findings['issue_2_empty_categoricals']),
             "WARNING" if len(self.findings['issue_2_empty_categoricals']) > 20 else "OK"),
            ("Left join data loss",
             sum(d.get('unmatched_records', 0) for d in self.findings['issue_4_left_join_loss'].values()),
             "WARNING"),
            ("Duplicate records", len(self.findings['issue_5_duplicates']),
             "INFO" if len(self.findings['issue_5_duplicates']) > 0 else "OK"),
            ("Inconsistent metadata", len(self.findings['issue_6_inconsistent_metadata']),
             "WARNING" if len(self.findings['issue_6_inconsistent_metadata']) > 0 else "OK"),
            ("ID format issues", len(self.findings['issue_7_id_format_mismatch'].get('id_format_issues', [])),
             "INFO"),
            ("Invalid values", len(self.findings['issue_9_invalid_values']),
             "WARNING" if len(self.findings['issue_9_invalid_values']) > 0 else "OK"),
            ("Small sample sites",
             sum(1 for d in self.findings['issue_11_small_samples'].values() if d['pct_small_sites'] > 30),
             "INFO"),
            ("Outliers detected",
             sum(sum(o['outlier_count'] for o in outliers) for outliers in self.findings['issue_12_outliers'].values()),
             "INFO"),
        ]

        for name, count, status in summaries:
            symbol = "[!!!]" if status == "CRITICAL" else "[!!]" if status == "WARNING" else "[i]" if status == "INFO" else "[OK]"
            report.append(f"{symbol} {name}: {count:,}")

        # Detailed sections
        report.append("")
        report.append("=" * 70)
        report.append("DETAILED FINDINGS")
        report.append("=" * 70)

        # File Errors (actual problems)
        report.append("\n--- ACTUAL FILE ERRORS (need attention) ---")
        if self.findings['issue_8_file_errors']:
            for err in self.findings['issue_8_file_errors']:
                report.append(f"[{err.get('severity', 'HIGH')}] {err['study']}/{err['file_type']}: {err['error']}")
        else:
            report.append("✅ No actual file errors!")

        # Empty Files (OK)
        report.append("\n--- EMPTY FILES (legitimate - no issues of this type) ---")
        empty_by_type = defaultdict(list)
        for item in self.findings['issue_8_empty_files']:
            empty_by_type[item['file_type']].append(item['study'])
        for file_type, studies in empty_by_type.items():
            report.append(f"   {file_type}: {len(studies)} studies have no data (OK)")

        # ID Format Issues
        report.append("\n--- ID FORMAT ISSUES ---")
        id_issues = self.findings['issue_7_id_format_mismatch'].get('id_format_issues', [])
        if id_issues:
            for issue in id_issues[:5]:
                report.append(f"   {issue['study']}/{issue['file_type']}: +{issue['improvement']} records matched after standardization")
        else:
            report.append("✅ No ID format issues - all subjects match directly!")

        # Outliers
        report.append("\n--- OUTLIERS (handled by pipeline's cap_outliers) ---")
        total_outliers = sum(sum(o['outlier_count'] for o in outliers)
                            for outliers in self.findings['issue_12_outliers'].values())
        report.append(f"   Total outliers in raw data: {total_outliers:,}")
        report.append("   ✅ These are capped by the pipeline during processing")

        # Recommendations
        report.append("")
        report.append("=" * 70)
        report.append("STATUS & RECOMMENDATIONS")
        report.append("=" * 70)

        if n_errors == 0:
            report.append("\n✅ NO CRITICAL ISSUES - Pipeline is ready to run!")
            report.append("")
            report.append("The following are handled automatically by the pipeline:")
            report.append("  • Multi-sheet files (SAE, Missing Pages) - Combined automatically")
            report.append("  • Empty categorical values - Filled with 'Unknown'")
            report.append("  • Outliers - Capped using IQR * 3 method")
            report.append("  • Missing site_id - Looked up from EDC baseline")
            report.append("  • Small percentile samples - Uses max instead of p95")
        else:
            report.append(f"\n⚠️ {n_errors} FILE ERRORS need attention before running pipeline")

        return '\n'.join(report)

    def save_outputs(self):
        """Save all diagnostic outputs."""
        OUTPUT_DIR.mkdir(exist_ok=True)

        json_path = OUTPUT_DIR / "diagnostics_details.json"
        with open(json_path, 'w') as f:
            json.dump(self.findings, f, indent=2, default=str)
        print(f"\nSaved: {json_path}")

        report = self.generate_report()
        report_path = OUTPUT_DIR / "diagnostics_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Saved: {report_path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    runner = DiagnosticsRunner()

    if runner.run_all_diagnostics():
        runner.save_outputs()
        print("\n")
        print(runner.generate_report())

    print("\n" + "=" * 70)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
