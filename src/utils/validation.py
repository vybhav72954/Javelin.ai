"""
JAVELIN.AI - Data Validation Utilities
======================================

Functions for validating, cleaning, and preparing data for analysis.
Includes outlier handling, missing value management, and data quality checks.

Functions:
    - validate_loaded_data: Check and fix common data issues
    - cap_outliers: Cap extreme values using IQR or Z-score
    - safe_max: Safely compute maximum with NaN handling
    - safe_mean: Safely compute mean with NaN handling
    - fill_missing_categoricals: Fill missing categorical values
    - validate_required_columns: Check for required columns
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Union

import warnings
warnings.filterwarnings('ignore')


def validate_loaded_data(
    df: pd.DataFrame,
    file_type: str,
    filepath: Union[str, Path],
    max_days: int = 1825,
    fix_issues: bool = True
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Validate and optionally fix common data quality issues.

    Checks for:
    - Empty dataframes
    - Negative values in numeric columns
    - Impossible date values (> 5 years outstanding)

    Args:
        df: Input DataFrame to validate
        file_type: Type of file for context-aware validation
        filepath: Path for error reporting
        max_days: Maximum allowed days for date-related columns (default: 5 years)
        fix_issues: If True, fix issues in place; if False, only report

    Returns:
        Tuple of (validated DataFrame, list of issues found)

    Examples:
        >>> df, issues = validate_loaded_data(df, 'visit_tracker', 'path/to/file.xlsx')
        >>> if issues:
        ...     print(f"Found {len(issues)} issues")
    """
    issues = []

    # Check for empty dataframe
    if df.empty:
        return df, ['Empty dataframe']

    # Get numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    # Check for negative values
    for col in numeric_cols:
        neg_count = (df[col] < 0).sum()
        if neg_count > 0:
            issues.append(f"{col}: {neg_count} negative values")
            if fix_issues:
                df.loc[df[col] < 0, col] = 0

    # Check for impossible day values (> 5 years)
    day_cols = [c for c in df.columns if 'day' in c.lower()]
    for col in day_cols:
        if col in numeric_cols:
            impossible = (df[col] > max_days).sum()
            if impossible > 0:
                issues.append(f"{col}: {impossible} values > {max_days} days (capped)")
                if fix_issues:
                    df.loc[df[col] > max_days, col] = max_days

    # Add issue suffix for logging
    if issues:
        for i, issue in enumerate(issues):
            issues[i] = f"[{file_type}] {issue}"

    return df, issues


def cap_outliers(
    series: pd.Series,
    multiplier: float = 3.0,
    method: str = 'iqr'
) -> pd.Series:
    """
    Cap extreme values in a series using IQR or Z-score method.

    Args:
        series: Input series with numeric values
        multiplier: Multiplier for IQR or standard deviations
        method: 'iqr' for Interquartile Range, 'zscore' for Z-score

    Returns:
        Series with capped values

    Methods:
        IQR: upper = Q3 + multiplier * IQR, lower = Q1 - multiplier * IQR
        Z-score: upper/lower = mean ± multiplier * std

    Examples:
        >>> s = pd.Series([1, 2, 3, 4, 100])
        >>> capped = cap_outliers(s, multiplier=3.0, method='iqr')
        >>> capped.max()  # Will be less than 100
    """
    if series.empty or series.isna().all():
        return series

    series = series.copy()

    if method == 'iqr':
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1

        if IQR == 0:
            return series

        upper_bound = Q3 + multiplier * IQR
        lower_bound = max(0, Q1 - multiplier * IQR)

    elif method == 'zscore':
        mean = series.mean()
        std = series.std()

        if std == 0 or pd.isna(std):
            return series

        upper_bound = mean + multiplier * std
        lower_bound = max(0, mean - multiplier * std)

    else:
        raise ValueError(f"Unknown method: {method}. Use 'iqr' or 'zscore'.")

    return series.clip(lower=lower_bound, upper=upper_bound)


def safe_max(series: pd.Series, default: float = 0) -> float:
    """
    Safely compute the maximum of a series, handling NaN and empty series.

    Args:
        series: Input series
        default: Value to return if series is empty or all NaN

    Returns:
        Maximum value or default

    Examples:
        >>> safe_max(pd.Series([1, 2, np.nan, 4]))
        4.0
        >>> safe_max(pd.Series([]))
        0
        >>> safe_max(pd.Series([np.nan, np.nan]))
        0
    """
    if series.empty or series.isna().all():
        return default

    result = series.max()
    return default if pd.isna(result) else result


def safe_mean(series: pd.Series, default: float = 0) -> float:
    """
    Safely compute the mean of a series, handling NaN and empty series.

    Args:
        series: Input series
        default: Value to return if series is empty or all NaN

    Returns:
        Mean value or default

    Examples:
        >>> safe_mean(pd.Series([1, 2, 3, np.nan]))
        2.0
        >>> safe_mean(pd.Series([]))
        0
    """
    if series.empty or series.isna().all():
        return default

    result = series.mean()
    return default if pd.isna(result) else result


def fill_missing_categoricals(
    df: pd.DataFrame,
    categorical_cols: Optional[List[str]] = None,
    fill_value: str = 'Unknown'
) -> pd.DataFrame:
    """
    Fill missing values in categorical columns with a placeholder.

    Handles various representations of missing data:
    - Empty strings
    - NaN values
    - String 'nan'
    - Whitespace-only strings

    Args:
        df: Input DataFrame
        categorical_cols: List of columns to fill. If None, uses default list.
        fill_value: Value to use for missing data

    Returns:
        DataFrame with filled categorical columns

    Examples:
        >>> df = pd.DataFrame({'country': ['USA', '', np.nan, '  ']})
        >>> df = fill_missing_categoricals(df, ['country'])
        >>> df['country'].tolist()
        ['USA', 'Unknown', 'Unknown', 'Unknown']
    """
    df = df.copy()

    # Default categorical columns
    if categorical_cols is None:
        categorical_cols = ['country', 'region', 'subject_status']

    for col in categorical_cols:
        if col not in df.columns:
            continue

        # Replace empty strings
        df[col] = df[col].replace('', fill_value)

        # Fill NaN
        df[col] = df[col].fillna(fill_value)

        # Convert to string and strip whitespace
        df[col] = df[col].astype(str).str.strip()

        # Replace string 'nan'
        df[col] = df[col].replace('nan', fill_value)
        df[col] = df[col].replace('None', fill_value)

        # Replace whitespace-only strings
        df.loc[df[col].str.len() == 0, col] = fill_value

    return df


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: List[str],
    raise_error: bool = False
) -> Tuple[bool, List[str]]:
    """
    Check if a DataFrame has all required columns.

    Args:
        df: Input DataFrame
        required_columns: List of column names that must be present
        raise_error: If True, raise ValueError for missing columns

    Returns:
        Tuple of (all_present: bool, missing_columns: list)

    Raises:
        ValueError: If raise_error=True and columns are missing

    Examples:
        >>> df = pd.DataFrame({'a': [1], 'b': [2]})
        >>> validate_required_columns(df, ['a', 'b', 'c'])
        (False, ['c'])
    """
    missing = [col for col in required_columns if col not in df.columns]

    if missing and raise_error:
        raise ValueError(f"Missing required columns: {missing}")

    return len(missing) == 0, missing


def check_duplicate_subjects(
    df: pd.DataFrame,
    subject_col: str = 'subject_id',
    study_col: str = 'study'
) -> pd.DataFrame:
    """
    Identify duplicate subject entries within studies.

    Args:
        df: Input DataFrame
        subject_col: Name of subject ID column
        study_col: Name of study column

    Returns:
        DataFrame of duplicate entries
    """
    if subject_col not in df.columns:
        return pd.DataFrame()

    group_cols = [study_col, subject_col] if study_col in df.columns else [subject_col]

    duplicates = df[df.duplicated(subset=group_cols, keep=False)]
    return duplicates.sort_values(group_cols)


def validate_numeric_ranges(
    df: pd.DataFrame,
    column_ranges: dict
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Validate that numeric columns fall within expected ranges.

    Args:
        df: Input DataFrame
        column_ranges: Dict of {column: (min_val, max_val)}

    Returns:
        Tuple of (validated DataFrame, list of issues)

    Examples:
        >>> ranges = {'score': (0, 1), 'count': (0, 1000)}
        >>> df, issues = validate_numeric_ranges(df, ranges)
    """
    df = df.copy()
    issues = []

    for col, (min_val, max_val) in column_ranges.items():
        if col not in df.columns:
            continue

        below_min = (df[col] < min_val).sum()
        above_max = (df[col] > max_val).sum()

        if below_min > 0:
            issues.append(f"{col}: {below_min} values below {min_val}")
            df.loc[df[col] < min_val, col] = min_val

        if above_max > 0:
            issues.append(f"{col}: {above_max} values above {max_val}")
            df.loc[df[col] > max_val, col] = max_val

    return df, issues
