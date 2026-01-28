"""
JAVELIN.AI - Aggregation Utilities
==================================

Functions for aggregating subject-level data to site, study, region,
and country levels. Used by Phase 03 (DQI calculation) and downstream
analysis phases.

Aggregation Hierarchy:
    Subject → Site → Study → Region → Country

Each level computes:
    - Count metrics (subjects, issues, risk categories)
    - Score metrics (mean, max, std DQI)
    - Risk distribution percentages

Functions:
    - aggregate_to_site: Subject → Site aggregation
    - aggregate_to_study: Site → Study aggregation
    - aggregate_to_region: Study → Region aggregation
    - aggregate_to_country: Site → Country aggregation
    - assign_aggregated_risk: Assign risk categories at aggregated levels
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

import warnings
warnings.filterwarnings('ignore')


def aggregate_to_site(
    df: pd.DataFrame,
    group_cols: List[str] = None,
    feature_cols: List[str] = None,
    dqi_score_col: str = 'dqi_score',
    risk_col: str = 'risk_category'
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Aggregate subject-level data to site level.

    Computes for each site:
    - subject_count: Number of subjects
    - avg_dqi_score, max_dqi_score, std_dqi_score: DQI statistics
    - high_risk_count, medium_risk_count: Risk category counts
    - high_risk_rate: Percentage of high-risk subjects
    - Sum of each feature column

    Args:
        df: Subject-level DataFrame
        group_cols: Columns to group by (default: ['study', 'site_id', 'country', 'region'])
        feature_cols: Feature columns to sum (default: from config)
        dqi_score_col: Name of DQI score column
        risk_col: Name of risk category column

    Returns:
        Tuple of (site DataFrame, thresholds used for risk assignment)
    """
    df = df.copy()

    # Default grouping columns
    if group_cols is None:
        group_cols = ['study', 'site_id', 'country', 'region']
        group_cols = [c for c in group_cols if c in df.columns]

    # Default feature columns
    if feature_cols is None:
        try:
            from config import DQI_WEIGHTS
            feature_cols = [f for f in DQI_WEIGHTS.keys() if f in df.columns and f != 'n_issue_types']
        except ImportError:
            feature_cols = []

    # Create binary risk columns
    df['is_high'] = (df[risk_col] == 'High').astype(int)
    df['is_medium'] = (df[risk_col] == 'Medium').astype(int)

    # Ensure has_issues exists
    if 'has_issues' not in df.columns:
        if 'n_issue_types' in df.columns:
            df['has_issues'] = (df['n_issue_types'] > 0).astype(int)
        else:
            df['has_issues'] = (df[dqi_score_col] > 0).astype(int)

    # Build aggregation dictionary
    agg_dict = {
        'subject_id': 'count',
        dqi_score_col: ['mean', 'max', 'std'],
        'n_issue_types': ['sum', 'mean'] if 'n_issue_types' in df.columns else ['count'],
        'is_high': 'sum',
        'is_medium': 'sum',
        'has_issues': 'sum',
    }

    # Add feature columns
    for col in feature_cols:
        if col in df.columns:
            agg_dict[col] = 'sum'

    # Perform aggregation
    site_df = df.groupby(group_cols).agg(agg_dict)

    # Flatten column names
    site_df.columns = [
        '_'.join(col).strip('_') if isinstance(col, tuple) else col
        for col in site_df.columns
    ]
    site_df = site_df.reset_index()

    # Rename columns
    rename_map = {
        'subject_id_count': 'subject_count',
        f'{dqi_score_col}_mean': 'avg_dqi_score',
        f'{dqi_score_col}_max': 'max_dqi_score',
        f'{dqi_score_col}_std': 'std_dqi_score',
        'n_issue_types_sum': 'total_issue_types',
        'n_issue_types_mean': 'avg_issue_types',
        'is_high_sum': 'high_risk_count',
        'is_medium_sum': 'medium_risk_count',
        'has_issues_sum': 'subjects_with_issues',
    }
    site_df = site_df.rename(columns=rename_map)

    # Fill NaN std with 0
    if 'std_dqi_score' in site_df.columns:
        site_df['std_dqi_score'] = site_df['std_dqi_score'].fillna(0)

    # Calculate high risk rate
    site_df['high_risk_rate'] = (
        site_df['high_risk_count'] / site_df['subject_count']
    ).fillna(0)

    # Assign site-level risk categories
    site_df, thresholds = assign_aggregated_risk(
        site_df,
        score_col='avg_dqi_score',
        output_col='site_risk_category',
        high_percentile=0.85,
        medium_percentile=0.50
    )

    return site_df, thresholds


def aggregate_to_study(
    site_df: pd.DataFrame,
    score_col: str = 'avg_dqi_score'
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Aggregate site-level data to study level.

    Args:
        site_df: Site-level DataFrame
        score_col: Score column to aggregate

    Returns:
        Tuple of (study DataFrame, thresholds)
    """
    agg_dict = {
        'site_id': 'count',
        'subject_count': 'sum',
        score_col: ['mean', 'max', 'std'],
        'high_risk_count': 'sum',
        'medium_risk_count': 'sum',
        'subjects_with_issues': 'sum',
    }

    # Add feature columns if present
    feature_cols = [c for c in site_df.columns if c.endswith('_sum') or c in [
        'sae_pending_count', 'missing_visit_count', 'lab_issues_count',
        'missing_pages_count', 'uncoded_meddra_count', 'uncoded_whodd_count'
    ]]
    for col in feature_cols:
        if col in site_df.columns:
            agg_dict[col] = 'sum'

    study_df = site_df.groupby('study').agg(agg_dict)

    # Flatten columns
    study_df.columns = [
        '_'.join(col).strip('_') if isinstance(col, tuple) else col
        for col in study_df.columns
    ]
    study_df = study_df.reset_index()

    # Rename columns
    rename_map = {
        'site_id_count': 'site_count',
        'subject_count_sum': 'subject_count',
        f'{score_col}_mean': 'avg_dqi_score',
        f'{score_col}_max': 'max_dqi_score',
        f'{score_col}_std': 'std_dqi_score',
        'high_risk_count_sum': 'high_risk_count',
        'medium_risk_count_sum': 'medium_risk_count',
        'subjects_with_issues_sum': 'subjects_with_issues',
    }
    study_df = study_df.rename(columns=rename_map)

    if 'std_dqi_score' in study_df.columns:
        study_df['std_dqi_score'] = study_df['std_dqi_score'].fillna(0)

    # Assign study-level risk
    study_df, thresholds = assign_aggregated_risk(
        study_df,
        score_col='avg_dqi_score',
        output_col='study_risk_category',
        high_percentile=0.85,
        medium_percentile=0.50
    )

    return study_df, thresholds


def aggregate_to_region(
    site_df: pd.DataFrame,
    score_col: str = 'avg_dqi_score'
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Aggregate site-level data to region level.

    Args:
        site_df: Site-level DataFrame
        score_col: Score column to aggregate

    Returns:
        Tuple of (region DataFrame, thresholds)
    """
    if 'region' not in site_df.columns:
        return pd.DataFrame(), {}

    agg_dict = {
        'site_id': 'count',
        'subject_count': 'sum',
        score_col: ['mean', 'max', 'std'],
        'high_risk_count': 'sum',
        'medium_risk_count': 'sum',
    }

    region_df = site_df.groupby('region').agg(agg_dict)

    # Flatten columns
    region_df.columns = [
        '_'.join(col).strip('_') if isinstance(col, tuple) else col
        for col in region_df.columns
    ]
    region_df = region_df.reset_index()

    # Rename columns
    rename_map = {
        'site_id_count': 'site_count',
        'subject_count_sum': 'subject_count',
        f'{score_col}_mean': 'avg_dqi_score',
        f'{score_col}_max': 'max_dqi_score',
        f'{score_col}_std': 'std_dqi_score',
        'high_risk_count_sum': 'high_risk_count',
        'medium_risk_count_sum': 'medium_risk_count',
    }
    region_df = region_df.rename(columns=rename_map)

    if 'std_dqi_score' in region_df.columns:
        region_df['std_dqi_score'] = region_df['std_dqi_score'].fillna(0)

    # Assign region-level risk
    region_df, thresholds = assign_aggregated_risk(
        region_df,
        score_col='avg_dqi_score',
        output_col='region_risk_category',
        high_percentile=0.85,
        medium_percentile=0.50
    )

    return region_df, thresholds


def aggregate_to_country(
    site_df: pd.DataFrame,
    score_col: str = 'avg_dqi_score'
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Aggregate site-level data to country level.

    Args:
        site_df: Site-level DataFrame
        score_col: Score column to aggregate

    Returns:
        Tuple of (country DataFrame, thresholds)
    """
    if 'country' not in site_df.columns:
        return pd.DataFrame(), {}

    agg_dict = {
        'site_id': 'count',
        'subject_count': 'sum',
        score_col: ['mean', 'max', 'std'],
        'high_risk_count': 'sum',
        'medium_risk_count': 'sum',
    }

    country_df = site_df.groupby('country').agg(agg_dict)

    # Flatten columns
    country_df.columns = [
        '_'.join(col).strip('_') if isinstance(col, tuple) else col
        for col in country_df.columns
    ]
    country_df = country_df.reset_index()

    # Rename columns
    rename_map = {
        'site_id_count': 'site_count',
        'subject_count_sum': 'subject_count',
        f'{score_col}_mean': 'avg_dqi_score',
        f'{score_col}_max': 'max_dqi_score',
        f'{score_col}_std': 'std_dqi_score',
        'high_risk_count_sum': 'high_risk_count',
        'medium_risk_count_sum': 'medium_risk_count',
    }
    country_df = country_df.rename(columns=rename_map)

    if 'std_dqi_score' in country_df.columns:
        country_df['std_dqi_score'] = country_df['std_dqi_score'].fillna(0)

    # Assign country-level risk
    country_df, thresholds = assign_aggregated_risk(
        country_df,
        score_col='avg_dqi_score',
        output_col='country_risk_category',
        high_percentile=0.85,
        medium_percentile=0.50
    )

    return country_df, thresholds


def assign_aggregated_risk(
    df: pd.DataFrame,
    score_col: str = 'avg_dqi_score',
    output_col: str = 'risk_category',
    high_percentile: float = 0.85,
    medium_percentile: float = 0.50,
    min_high_threshold: float = 0.05,
    min_medium_threshold: float = 0.02
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Assign risk categories for aggregated data (site/study/region/country).

    Uses percentile-based thresholds on the score distribution.

    Args:
        df: Aggregated DataFrame
        score_col: Column containing scores
        output_col: Name for output risk category column
        high_percentile: Percentile for high-risk threshold
        medium_percentile: Percentile for medium-risk threshold
        min_high_threshold: Minimum score for high risk
        min_medium_threshold: Minimum score for medium risk

    Returns:
        Tuple of (DataFrame with risk column, thresholds used)
    """
    df = df.copy()

    # Get scores with issues
    scores_with_issues = df[df[score_col] > 0][score_col]

    if len(scores_with_issues) > 0:
        high_thresh = scores_with_issues.quantile(high_percentile)
        med_thresh = scores_with_issues.quantile(medium_percentile)
        high_thresh = max(high_thresh, min_high_threshold)
        med_thresh = max(med_thresh, min_medium_threshold)
    else:
        high_thresh = min_high_threshold * 2
        med_thresh = min_medium_threshold * 2

    # Assign categories
    df[output_col] = 'Low'
    df.loc[df[score_col] >= med_thresh, output_col] = 'Medium'
    df.loc[df[score_col] >= high_thresh, output_col] = 'High'

    thresholds = {
        'high': high_thresh,
        'medium': med_thresh
    }

    return df, thresholds


def calculate_risk_rates(
    df: pd.DataFrame,
    count_col: str = 'subject_count',
    high_col: str = 'high_risk_count',
    medium_col: str = 'medium_risk_count'
) -> pd.DataFrame:
    """
    Calculate risk rate percentages.

    Args:
        df: DataFrame with count columns
        count_col: Total count column
        high_col: High risk count column
        medium_col: Medium risk count column

    Returns:
        DataFrame with rate columns added
    """
    df = df.copy()

    if count_col in df.columns:
        if high_col in df.columns:
            df['high_risk_rate'] = (df[high_col] / df[count_col]).fillna(0)
        if medium_col in df.columns:
            df['medium_risk_rate'] = (df[medium_col] / df[count_col]).fillna(0)
        if high_col in df.columns and medium_col in df.columns:
            df['low_risk_rate'] = 1 - df.get('high_risk_rate', 0) - df.get('medium_risk_rate', 0)

    return df
