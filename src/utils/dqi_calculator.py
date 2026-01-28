"""
JAVELIN.AI - DQI Calculation Utilities
======================================

Core functions for calculating Data Quality Intelligence (DQI) scores
and assigning risk categories. Used by both Phase 03 (DQI calculation)
and the sensitivity analysis validation script.

DQI Scoring Methodology:
    - Binary Component (50%): Whether an issue exists (0 or 1)
    - Severity Component (50%): Scaled value relative to reference maximum
    - Total Score: Sum of weighted components, range [0, 1]

Risk Categories:
    - High: SAE pending (clinical override) OR top 10% of non-SAE scores
    - Medium: Any issue present, not High
    - Low: No issues detected

Functions:
    - calculate_reference_max: Compute reference maximum for severity scaling
    - calculate_component_score: Calculate weighted score for a feature
    - calculate_dqi_with_weights: Calculate full DQI score with custom weights
    - assign_risk_categories: Assign High/Medium/Low risk categories
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, Any

import warnings
warnings.filterwarnings('ignore')


# Default minimum samples for percentile calculation
DEFAULT_MIN_SAMPLES = 20

# Default percentile for reference maximum
DEFAULT_REFERENCE_PERCENTILE = 0.95


def calculate_reference_max(
    series: pd.Series,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    percentile: float = DEFAULT_REFERENCE_PERCENTILE
) -> float:
    """
    Calculate the reference maximum for severity scaling.

    Uses the 95th percentile of non-zero values if enough samples exist,
    otherwise falls back to the maximum value. This prevents extreme
    outliers from dominating the severity calculation.

    Args:
        series: Input series with numeric values
        min_samples: Minimum non-zero samples required for percentile
        percentile: Percentile to use for reference (default: 0.95)

    Returns:
        Reference maximum value (minimum 1.0)

    Examples:
        >>> s = pd.Series([0, 1, 2, 3, 4, 5, 100])
        >>> calculate_reference_max(s, min_samples=5)  # Uses 95th percentile
        >>> calculate_reference_max(s, min_samples=100)  # Uses max (100)
    """
    non_zero = series[series > 0]

    if len(non_zero) >= min_samples:
        ref_max = non_zero.quantile(percentile)
        if ref_max <= 0:
            ref_max = non_zero.max()
    elif len(non_zero) > 0:
        ref_max = non_zero.max()
    else:
        ref_max = 1.0

    # Ensure minimum of 1.0 to avoid division issues
    return max(ref_max, 1.0)


def calculate_component_score(
    series: pd.Series,
    weight: float,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    binary_weight: float = 0.5,
    severity_weight: float = 0.5
) -> pd.Series:
    """
    Calculate weighted score for a single feature using Binary + Severity.

    The score combines:
    - Binary component: 1 if issue present, 0 otherwise
    - Severity component: value / reference_max, clipped to [0, 1]

    Args:
        series: Input series with feature values
        weight: Weight for this feature (from DQI_WEIGHTS)
        min_samples: Minimum samples for percentile calculation
        binary_weight: Weight for binary component (default: 0.5)
        severity_weight: Weight for severity component (default: 0.5)

    Returns:
        Series of component scores

    Examples:
        >>> s = pd.Series([0, 1, 2, 5, 10])
        >>> scores = calculate_component_score(s, weight=0.10)
        >>> scores.iloc[0]  # No issue = 0
        0.0
        >>> scores.iloc[-1]  # Highest value
    """
    # Handle edge case of all zeros
    if series.max() == 0:
        return pd.Series(0.0, index=series.index)

    # Binary component: 1 if has issue, 0 otherwise
    binary = (series > 0).astype(float)

    # Calculate reference maximum for severity scaling
    reference_max = calculate_reference_max(series, min_samples)

    # Severity component: scaled by reference max
    severity = (series / reference_max).clip(0, 1)

    # Combined score with weights
    score = weight * (binary_weight * binary + severity_weight * severity)

    return score


def calculate_dqi_with_weights(
    df: pd.DataFrame,
    weights: Dict[str, float],
    min_samples: int = DEFAULT_MIN_SAMPLES
) -> pd.Series:
    """
    Calculate DQI scores for all subjects using given weights.

    This function can be used with custom weights (e.g., for sensitivity
    analysis) or with the standard weights from config.

    Args:
        df: DataFrame with subject data (must contain feature columns)
        weights: Dict mapping feature names to weights (must sum to 1.0)
        min_samples: Minimum samples for percentile calculation

    Returns:
        Series of DQI scores (range [0, 1])

    Examples:
        >>> weights = {'sae_pending_count': 0.20, 'missing_visit_count': 0.15, ...}
        >>> scores = calculate_dqi_with_weights(df, weights)
    """
    df = df.copy()
    df['dqi_score_calc'] = 0.0

    for feature, weight in weights.items():
        if feature not in df.columns:
            continue

        component = calculate_component_score(
            df[feature],
            weight=weight,
            min_samples=min_samples
        )
        df['dqi_score_calc'] += component

    return df['dqi_score_calc'].clip(0, 1)


def assign_risk_categories(
    df: pd.DataFrame,
    dqi_score_col: str = 'dqi_score',
    high_percentile: float = 0.90,
    min_high_threshold: float = 0.10,
    sae_col: str = 'sae_pending_count',
    has_issues_col: str = 'has_issues'
) -> Tuple[pd.DataFrame, Dict[str, float], Dict[str, int]]:
    """
    Assign risk categories based on DQI scores with clinical override.

    Risk Assignment Logic:
    1. All subjects with pending SAEs → High (clinical override)
    2. Non-SAE subjects above high_percentile threshold → High
    3. Subjects with any issue but not High → Medium
    4. Subjects with no issues → Low

    Args:
        df: DataFrame with DQI scores
        dqi_score_col: Name of DQI score column
        high_percentile: Percentile threshold for High risk (default: 0.90)
        min_high_threshold: Minimum score for High (default: 0.10)
        sae_col: Column name for SAE count
        has_issues_col: Column name for has_issues flag

    Returns:
        Tuple of:
        - DataFrame with 'risk_category' column added
        - Dict of thresholds used {'high': float, 'medium': float}
        - Dict of overrides applied {'sae_to_high': int}

    Examples:
        >>> df, thresholds, overrides = assign_risk_categories(df)
        >>> df['risk_category'].value_counts()
        Medium    5000
        Low       3000
        High       500
    """
    df = df.copy()

    # Ensure has_issues column exists
    if has_issues_col not in df.columns:
        # Try to compute from n_issue_types if available
        if 'n_issue_types' in df.columns:
            df[has_issues_col] = (df['n_issue_types'] > 0).astype(int)
        else:
            # Fallback: any non-zero score means has issues
            df[has_issues_col] = (df[dqi_score_col] > 0).astype(int)

    # Identify SAE subjects (clinical override)
    sae_mask = pd.Series(False, index=df.index)
    if sae_col in df.columns:
        sae_mask = df[sae_col] > 0

    # Calculate threshold from non-SAE subjects with issues
    non_sae_with_issues = df[(df[has_issues_col] == 1) & (~sae_mask)]

    if len(non_sae_with_issues) > 0:
        high_threshold = non_sae_with_issues[dqi_score_col].quantile(high_percentile)
        high_threshold = max(high_threshold, min_high_threshold)
    else:
        high_threshold = min_high_threshold * 2  # Default fallback

    medium_threshold = 0.001  # Any issue

    # Assign categories
    df['risk_category'] = 'Low'
    df.loc[df[has_issues_col] == 1, 'risk_category'] = 'Medium'
    df.loc[(~sae_mask) & (df[dqi_score_col] >= high_threshold), 'risk_category'] = 'High'
    df.loc[sae_mask, 'risk_category'] = 'High'  # Clinical override

    # Track overrides
    overrides = {}
    if sae_col in df.columns:
        sae_below_threshold = sae_mask & (df[dqi_score_col] < high_threshold)
        overrides['sae_to_high'] = sae_below_threshold.sum()

    thresholds = {
        'high': high_threshold,
        'medium': medium_threshold
    }

    return df, thresholds, overrides


def calculate_subject_dqi(
    df: pd.DataFrame,
    feature_weights: Optional[Dict[str, Dict[str, Any]]] = None
) -> Tuple[pd.DataFrame, Dict[str, Dict]]:
    """
    Calculate full DQI scores for subjects with component breakdown.

    This is the main entry point for Phase 03 DQI calculation.
    Computes n_issue_types, individual component scores, and total DQI.

    Args:
        df: DataFrame with subject-level data
        feature_weights: Dict of {feature: {'weight': float, 'tier': str, ...}}
                        If None, imports from config.

    Returns:
        Tuple of:
        - DataFrame with dqi_score and component columns added
        - Dict of component statistics for reporting

    Examples:
        >>> df, components = calculate_subject_dqi(df)
        >>> df['dqi_score'].describe()
    """
    # Import weights from config if not provided
    if feature_weights is None:
        try:
            from config import DQI_WEIGHTS
            feature_weights = DQI_WEIGHTS
        except ImportError:
            raise ValueError("feature_weights must be provided if config is not available")

    df = df.copy()

    # Calculate n_issue_types
    issue_columns = [
        col for col in feature_weights.keys()
        if col in df.columns and col != 'n_issue_types'
    ]
    df['n_issue_types'] = (df[issue_columns] > 0).sum(axis=1)

    # Initialize DQI score
    df['dqi_score'] = 0.0
    components = {}

    # Calculate each component
    for feature, config in feature_weights.items():
        if feature not in df.columns:
            continue

        weight = config['weight'] if isinstance(config, dict) else config
        tier = config.get('tier', 'Unknown') if isinstance(config, dict) else 'Unknown'

        component = calculate_component_score(df[feature], weight)
        df[f'{feature}_component'] = component
        df['dqi_score'] += component

        # Track component statistics
        components[feature] = {
            'weight': weight,
            'tier': tier,
            'subjects_with_issue': (df[feature] > 0).sum(),
            'mean_raw_value': df[feature].mean(),
            'max_raw_value': df[feature].max(),
            'mean_component': component.mean(),
            'max_component': component.max(),
        }

    # Clip final score to [0, 1]
    df['dqi_score'] = df['dqi_score'].clip(0, 1)

    return df, components


def get_risk_distribution(df: pd.DataFrame, risk_col: str = 'risk_category') -> Dict[str, int]:
    """
    Get the distribution of risk categories.

    Args:
        df: DataFrame with risk categories
        risk_col: Name of risk category column

    Returns:
        Dict with counts for each category
    """
    if risk_col not in df.columns:
        return {'High': 0, 'Medium': 0, 'Low': 0}

    dist = df[risk_col].value_counts()
    return {
        'High': dist.get('High', 0),
        'Medium': dist.get('Medium', 0),
        'Low': dist.get('Low', 0),
    }


def validate_dqi_weights(weights: Dict[str, float], tolerance: float = 0.001) -> bool:
    """
    Validate that DQI weights sum to 1.0.

    Args:
        weights: Dict of feature weights
        tolerance: Acceptable deviation from 1.0

    Returns:
        True if valid, raises AssertionError otherwise
    """
    if isinstance(list(weights.values())[0], dict):
        # Handle nested structure with 'weight' key
        total = sum(v['weight'] for v in weights.values())
    else:
        total = sum(weights.values())

    assert abs(total - 1.0) < tolerance, f"Weights must sum to 1.0, got {total}"
    return True
