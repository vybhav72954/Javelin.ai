"""
JAVELIN.AI - Data Loading Utilities
====================================

Functions for reading Excel files, finding columns with fuzzy matching,
and standardizing column names across different data sources.

These functions are used by multiple phases to ensure consistent
data loading behavior.

Functions:
    - find_column: Fuzzy match column names
    - standardize_columns: Rename columns to standard names
    - read_excel_smart: Intelligent Excel reading with header detection
    - detect_header_row: Find the actual header row in messy Excel files
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

import warnings
warnings.filterwarnings('ignore')


def find_column(
    df_columns: List[str],
    possible_names: List[str],
    exact_match_first: bool = True
) -> Optional[str]:
    """
    Find a column name from a list of possible names using fuzzy matching.

    Searches for exact matches first, then partial matches (substring).
    Case-insensitive matching is used for partial matches.

    Args:
        df_columns: List of actual column names in the DataFrame
        possible_names: List of possible names to search for (priority order)
        exact_match_first: If True, check exact matches before partial

    Returns:
        The actual column name if found, None otherwise

    Examples:
        >>> cols = ['Subject ID', 'Site Number', 'Country']
        >>> find_column(cols, ['Subject', 'Subject ID', 'PatientID'])
        'Subject ID'

        >>> find_column(cols, ['site_id', 'Site', 'Site Number'])
        'Site Number'
    """
    if not df_columns or not possible_names:
        return None

    # Convert to list if needed
    df_columns = list(df_columns)
    df_columns_lower = [str(c).lower().strip() for c in df_columns]

    # First pass: exact matches
    if exact_match_first:
        for name in possible_names:
            if name in df_columns:
                return name

    # Second pass: case-insensitive partial matches
    for name in possible_names:
        name_lower = name.lower().strip()
        for i, col_lower in enumerate(df_columns_lower):
            # Check if either contains the other
            if name_lower in col_lower or col_lower in name_lower:
                return df_columns[i]

    return None


def standardize_columns(
    df: pd.DataFrame,
    file_type: str,
    column_mappings: Optional[Dict[str, Dict[str, List[str]]]] = None
) -> pd.DataFrame:
    """
    Rename DataFrame columns to standard names based on file type.

    Uses a mapping dictionary to find and rename columns to consistent
    names across different data sources.

    Args:
        df: Input DataFrame
        file_type: Type of file (e.g., 'edc_metrics', 'visit_tracker')
        column_mappings: Optional custom mappings. If None, uses config.

    Returns:
        DataFrame with standardized column names

    Examples:
        >>> df = pd.DataFrame({'Subject ID': [1, 2], 'Site Number': [101, 102]})
        >>> df = standardize_columns(df, 'edc_metrics')
        >>> list(df.columns)
        ['subject_id', 'site_id']
    """
    # Import mappings from config if not provided
    if column_mappings is None:
        try:
            from config import COLUMN_MAPPINGS
            column_mappings = COLUMN_MAPPINGS
        except ImportError:
            # Fallback mappings if config not available
            column_mappings = _get_default_column_mappings()

    mapping = column_mappings.get(file_type, {})
    if not mapping:
        return df

    rename_dict = {}
    for standard_name, possible_names in mapping.items():
        actual_col = find_column(df.columns.tolist(), possible_names)
        if actual_col and actual_col != standard_name:
            rename_dict[actual_col] = standard_name

    if rename_dict:
        df = df.rename(columns=rename_dict)

    return df


def detect_header_row(
    df: pd.DataFrame,
    header_indicators: Optional[List[str]] = None,
    max_rows_to_check: int = 10
) -> int:
    """
    Detect the actual header row in a DataFrame with potential junk rows.

    Some Excel files have title rows, blank rows, or metadata before
    the actual data header. This function finds the real header.

    Args:
        df: DataFrame read with header=None
        header_indicators: Strings that indicate a header row
        max_rows_to_check: Maximum number of rows to scan

    Returns:
        Row index of the detected header (0-indexed)

    Examples:
        >>> # File with title in row 0, header in row 2
        >>> detect_header_row(df, ['Subject ID', 'Site'])
        2
    """
    if header_indicators is None:
        header_indicators = [
            'Subject ID', 'Subject', 'Site ID', 'Site',
            'Patient ID', 'Country', 'Visit', 'Project Name'
        ]

    for i in range(min(max_rows_to_check, len(df))):
        row_str = ' '.join(df.iloc[i].astype(str).tolist())
        for indicator in header_indicators:
            if indicator in row_str:
                return i

    return 0  # Default to first row


def read_excel_smart(
    filepath: Union[str, Path],
    file_type: str,
    validate: bool = True,
    column_mappings: Optional[Dict] = None
) -> pd.DataFrame:
    """
    Intelligently read an Excel file based on its type.

    Handles various file formats and quirks:
    - EDC Metrics: Detects header row, filters out junk rows
    - SAE Dashboard: Combines multiple sheets
    - Missing Pages: Combines multiple sheets
    - Other: Standard single-sheet read

    Args:
        filepath: Path to the Excel file
        file_type: Type of file for special handling
        validate: If True, run validation on loaded data
        column_mappings: Optional custom column mappings

    Returns:
        DataFrame with data from the file

    Raises:
        Returns empty DataFrame on error (with warning printed)
    """
    filepath = Path(filepath)

    try:
        if file_type == 'edc_metrics':
            df = _read_edc_metrics(filepath)

        elif file_type == 'sae_dashboard':
            df = _read_multi_sheet_file(filepath, sheet_filter=['SAE', 'Dashboard'])

        elif file_type == 'missing_pages':
            df = _read_multi_sheet_file(filepath, sheet_filter=None)

        else:
            df = pd.read_excel(filepath, sheet_name=0)

        # Apply validation if requested
        if validate and not df.empty:
            from .validation import validate_loaded_data
            df, _ = validate_loaded_data(df, file_type, filepath)

        # Standardize columns
        if not df.empty:
            df = standardize_columns(df, file_type, column_mappings)

        return df

    except Exception as e:
        print(f"    [WARN] Error reading {filepath}: {e}")
        return pd.DataFrame()


def _read_edc_metrics(filepath: Path) -> pd.DataFrame:
    """Read EDC Metrics file with header detection."""
    # First read without header to detect actual header row
    df_raw = pd.read_excel(filepath, sheet_name=0, header=None)

    header_row = detect_header_row(df_raw, ['Subject ID', 'Project Name'])

    # Re-read with correct header
    df = pd.read_excel(filepath, sheet_name=0, header=header_row)

    # Filter out non-data rows
    if 'Subject ID' in df.columns:
        df = df[df['Subject ID'].notna()]
        df = df[~df['Subject ID'].astype(str).str.contains(
            'Subject ID|Responsible|Total|Summary', na=False, case=False
        )]

    return df


def _read_multi_sheet_file(
    filepath: Path,
    sheet_filter: Optional[List[str]] = None
) -> pd.DataFrame:
    """Read and combine multiple sheets from an Excel file."""
    xl = pd.ExcelFile(filepath)
    all_dfs = []

    for sheet in xl.sheet_names:
        # Apply sheet filter if provided
        if sheet_filter:
            if not any(f in sheet for f in sheet_filter):
                continue

        try:
            df_sheet = pd.read_excel(filepath, sheet_name=sheet)
            if not df_sheet.empty:
                df_sheet['_source_sheet'] = sheet
                all_dfs.append(df_sheet)
        except Exception:
            continue

    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True, sort=False)
        total_rows = sum(len(d) for d in all_dfs)
        print(f"      Combined {len(all_dfs)} sheets: {total_rows} total rows")
        return df

    return pd.DataFrame()


def _get_default_column_mappings() -> Dict[str, Dict[str, List[str]]]:
    """Return default column mappings if config is not available."""
    return {
        'edc_metrics': {
            'subject_id': ['Subject ID', 'Subject', 'SubjectID', 'SUBJECT ID'],
            'site_id': ['Site ID', 'Site', 'SiteID', 'SITE ID', 'Site Number'],
            'country': ['Country', 'COUNTRY'],
            'region': ['Region', 'REGION'],
            'subject_status': ['Subject Status', 'Status'],
            'latest_visit': ['Latest Visit', 'Latest Visit (SV)'],
        },
        'visit_tracker': {
            'subject_id': ['Subject', 'Subject ID', 'SubjectID'],
            'site_id': ['Site', 'Site ID', 'Site Number'],
            'country': ['Country'],
            'visit': ['Visit', 'Visit Name'],
            'days_outstanding': ['# Days Outstanding', 'Days Outstanding'],
        },
        'missing_lab': {
            'subject_id': ['Subject', 'Subject ID'],
            'site_id': ['Site number', 'Site', 'Site ID'],
            'country': ['Country'],
            'issue': ['Issue', 'Issue Type'],
        },
        'sae_dashboard': {
            'subject_id': ['Patient ID', 'Subject', 'Subject ID'],
            'site_id': ['Site', 'Site ID'],
            'country': ['Country'],
            'review_status': ['Review Status', 'ReviewStatus'],
            'action_status': ['Action Status', 'ActionStatus'],
        },
        'missing_pages': {
            'subject_id': ['Subject Name', 'SubjectName', 'Subject', 'Subject ID'],
            'site_id': ['Site Number', 'SiteNumber', 'Site', 'Site ID'],
            'days_missing': ['No. #Days Page Missing', '# of Days Missing', 'Days Missing'],
        },
        'meddra_coding': {
            'subject_id': ['Subject', 'Subject ID'],
            'coding_status': ['Coding Status', 'CodingStatus'],
        },
        'whodd_coding': {
            'subject_id': ['Subject', 'Subject ID'],
            'coding_status': ['Coding Status', 'CodingStatus'],
        },
        'inactivated': {
            'subject_id': ['Subject', 'Subject ID'],
            'site_id': ['Study Site Number', 'Site', 'Site ID', 'Site Number'],
            'country': ['Country'],
        },
        'edrr': {
            'subject_id': ['Subject', 'Subject ID'],
            'open_issues': ['Total Open issue Count per subject', 'Open Issues'],
        },
    }
