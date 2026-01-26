"""
Javelin.AI - Step 3: Calculate Data Quality Index (DQI)
========================================================================

FINAL VERSION - Validated and Clinically Sound

METHODOLOGY:
------------
1. DQI Score = Weighted sum of issue components
2. Each component uses Binary + Severity scoring:
   - Binary (50%): Does the subject have this issue? (0 or 1)
   - Severity (50%): How severe is the issue? (0 to 1 scale)
3. Risk categories based on score percentiles
4. Clinical override: SAE pending always triggers High risk

WHY THIS APPROACH:
------------------
- We analyzed whether DQ metrics predict SAE - They don't (negative correlation)
- Therefore, ML-based weights would be meaningless
- Domain knowledge weights based on clinical importance are more appropriate
- Binary + Severity ensures every issue type gets fair representation

VALIDATION CHECKS:
------------------
- Weights sum to 100%
- All SAE subjects captured in High risk
- Proper risk pyramid: Medium > High
- Score and category are aligned
- Capture rate > 80% of subjects with issues

Usage:
    python src/03_calculate_dqi.py

Outputs:
    - outputs/master_subject_with_dqi.csv  (subject-level DQI)
    - outputs/master_site_with_dqi.csv     (site-level aggregation)
    - outputs/dqi_weights.csv              (weights with rationale)
    - outputs/dqi_model_report.txt         (methodology report)
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
MASTER_SUBJECT_PATH = OUTPUT_DIR / "master_subject.csv"

# Feature weights based on clinical importance
# Rationale: Safety > Completeness > Timeliness > Administrative
FEATURE_WEIGHTS = {
    # TIER 1: SAFETY-CRITICAL (35% total)
    'sae_pending_count': {
        'weight': 0.20,
        'tier': 'Safety',
        'rationale': 'Pending SAE reviews require immediate regulatory attention'
    },
    'uncoded_meddra_count': {
        'weight': 0.15,
        'tier': 'Safety',
        'rationale': 'Uncoded adverse event terms prevent proper safety signal detection'
    },

    # TIER 2: DATA COMPLETENESS (32% total)
    'missing_visit_count': {
        'weight': 0.12,
        'tier': 'Completeness',
        'rationale': 'Missing visits mean missed safety assessments and protocol deviations'
    },
    'missing_pages_count': {
        'weight': 0.10,
        'tier': 'Completeness',
        'rationale': 'Missing CRF pages indicate incomplete subject records'
    },
    'lab_issues_count': {
        'weight': 0.10,
        'tier': 'Completeness',
        'rationale': 'Lab data issues can mask abnormal safety values'
    },

    # TIER 3: TIMELINESS (14% total)
    'max_days_outstanding': {
        'weight': 0.08,
        'tier': 'Timeliness',
        'rationale': 'Delayed data entry reduces real-time safety monitoring capability'
    },
    'max_days_page_missing': {
        'weight': 0.06,
        'tier': 'Timeliness',
        'rationale': 'Long-outstanding missing pages indicate systemic site issues'
    },

    # TIER 4: CODING & RECONCILIATION (11% total)
    'uncoded_whodd_count': {
        'weight': 0.06,
        'tier': 'Coding',
        'rationale': 'Uncoded drug terms affect concomitant medication tracking'
    },
    'edrr_open_issues': {
        'weight': 0.05,
        'tier': 'Reconciliation',
        'rationale': 'Open external data reconciliation issues need resolution'
    },

    # TIER 5: ADMINISTRATIVE (8% total)
    'n_issue_types': {
        'weight': 0.05,
        'tier': 'Composite',
        'rationale': 'Multiple concurrent issue types indicate systemic problems'
    },
    'inactivated_forms_count': {
        'weight': 0.03,
        'tier': 'Administrative',
        'rationale': 'Inactivated forms are corrections, lowest risk priority'
    },
}

# Verify weights sum to 1.0
_total_weight = sum(f['weight'] for f in FEATURE_WEIGHTS.values())
assert abs(_total_weight - 1.0) < 0.001, f"Weights must sum to 1.0, got {_total_weight}"


# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

def calculate_component_score(series, weight):
    """
    Calculate weighted score for a single feature.

    Formula: score = weight * (0.5 * binary + 0.5 * severity)

    Where:
        - binary = 1 if value > 0, else 0
        - severity = value / reference_max, capped at 1.0
        - reference_max = 95th percentile of non-zero values (or max if p95 is 0)

    This ensures:
        - Any issue gets at least 50% of the weight (binary component)
        - Severe issues get up to 100% of the weight (severity component)
        - Features with many zeros still contribute fairly

    Args:
        series: pandas Series of feature values
        weight: float, the weight for this feature (0-1)

    Returns:
        pandas Series of scores (0 to weight)
    """
    # Handle empty or all-zero series
    if series.max() == 0:
        return pd.Series(0.0, index=series.index)

    # Binary component: 1 if has issue, 0 if not
    binary = (series > 0).astype(float)

    # Calculate reference max for severity scaling
    # Issue 11 Fix: Require minimum 20 samples for stable p95, otherwise use max
    non_zero_values = series[series > 0]
    MIN_SAMPLES_FOR_PERCENTILE = 20

    if len(non_zero_values) >= MIN_SAMPLES_FOR_PERCENTILE:
        # Enough samples for stable percentile calculation
        p95 = non_zero_values.quantile(0.95)
        reference_max = p95 if p95 > 0 else non_zero_values.max()
    elif len(non_zero_values) > 0:
        # Small sample: use max instead of percentile
        reference_max = non_zero_values.max()
    else:
        reference_max = 1.0  # Fallback

    # Severity component: 0 to 1 based on magnitude
    severity = (series / reference_max).clip(0, 1)

    # Combined score: 50% binary + 50% severity, multiplied by weight
    score = weight * (0.5 * binary + 0.5 * severity)

    return score


def calculate_subject_dqi(df):
    """
    Calculate DQI score for each subject.

    Returns:
        df: DataFrame with dqi_score and component columns added
        components: dict with statistics for each component
    """
    df = df.copy()

    # First calculate n_issue_types (it's used as a feature)
    issue_columns = [col for col in FEATURE_WEIGHTS.keys()
                     if col in df.columns and col != 'n_issue_types']
    df['n_issue_types'] = (df[issue_columns] > 0).sum(axis=1)

    # Calculate DQI score as sum of components
    df['dqi_score'] = 0.0
    components = {}

    for feature, config in FEATURE_WEIGHTS.items():
        if feature not in df.columns:
            continue

        # Calculate component score
        component = calculate_component_score(df[feature], config['weight'])
        df[f'{feature}_component'] = component
        df['dqi_score'] += component

        # Store statistics
        components[feature] = {
            'weight': config['weight'],
            'tier': config['tier'],
            'subjects_with_issue': (df[feature] > 0).sum(),
            'mean_raw_value': df[feature].mean(),
            'max_raw_value': df[feature].max(),
            'mean_component': component.mean(),
            'max_component': component.max(),
        }

    # Ensure score is in valid range
    df['dqi_score'] = df['dqi_score'].clip(0, 1)

    return df, components


def assign_risk_categories(df):
    """
    Assign risk categories based on DQI score with guaranteed capture.

    Strategy:
        - High: SAE pending OR top 10% of non-SAE subjects with issues
        - Medium: Any issue that's not High
        - Low: No issues

    This guarantees:
        - 100% capture rate (all subjects with issues are flagged)
        - Proper pyramid shape (Medium > High)
        - All SAE subjects in High

    Returns:
        df: DataFrame with risk_category added
        thresholds: dict with threshold values
        overrides: dict with override counts
    """
    df = df.copy()

    # Identify subjects with any issues
    df['has_issues'] = (df['n_issue_types'] > 0).astype(int)

    # Step 1: Identify SAE subjects (always High)
    sae_mask = pd.Series(False, index=df.index)
    if 'sae_pending_count' in df.columns:
        sae_mask = df['sae_pending_count'] > 0

    # Step 2: For non-SAE subjects with issues, find top 10% by score
    non_sae_with_issues = df[(df['has_issues'] == 1) & (~sae_mask)]

    if len(non_sae_with_issues) > 0:
        # High threshold = 90th percentile of non-SAE subjects with issues
        high_threshold = non_sae_with_issues['dqi_score'].quantile(0.90)
        high_threshold = max(high_threshold, 0.10)  # Minimum threshold
    else:
        high_threshold = 0.20

    # Medium threshold is effectively 0 (any issue = Medium unless High)
    medium_threshold = 0.001  # Just above zero

    # Step 3: Assign categories
    # Start with Low (no issues)
    df['risk_category'] = 'Low'

    # Medium: has any issue
    df.loc[df['has_issues'] == 1, 'risk_category'] = 'Medium'

    # High: score >= threshold (non-SAE)
    df.loc[(~sae_mask) & (df['dqi_score'] >= high_threshold), 'risk_category'] = 'High'

    # High: SAE (clinical override - always High regardless of score)
    df.loc[sae_mask, 'risk_category'] = 'High'

    # Count overrides (SAE subjects who were below score threshold)
    overrides = {}
    if 'sae_pending_count' in df.columns:
        sae_below_threshold = sae_mask & (df['dqi_score'] < high_threshold)
        overrides['sae_to_high'] = sae_below_threshold.sum()

    thresholds = {
        'high': high_threshold,
        'medium': medium_threshold,
    }

    return df, thresholds, overrides


def aggregate_site_dqi(df):
    """
    Aggregate subject-level DQI to site level.

    Site metrics:
        - avg_dqi_score: Mean DQI across subjects
        - max_dqi_score: Maximum DQI (worst subject)
        - high_risk_count: Number of High risk subjects
        - medium_risk_count: Number of Medium risk subjects
        - total_issues: Sum of all issue counts

    Site risk category:
        - Based on avg_dqi_score percentiles only (not percentage-based)
        - This ensures proper pyramid shape (Medium > High)
    """
    # Prepare aggregation columns
    df = df.copy()
    df['is_high'] = (df['risk_category'] == 'High').astype(int)
    df['is_medium'] = (df['risk_category'] == 'Medium').astype(int)

    # Define aggregations
    agg_dict = {
        'subject_id': 'count',
        'dqi_score': ['mean', 'max', 'std'],
        'n_issue_types': ['sum', 'mean'],
        'is_high': 'sum',
        'is_medium': 'sum',
        'has_issues': 'sum',
    }

    # Add sum of each issue type
    for feature in FEATURE_WEIGHTS.keys():
        if feature in df.columns and feature != 'n_issue_types':
            agg_dict[feature] = 'sum'

    # Perform aggregation
    site_df = df.groupby(['study', 'site_id', 'country', 'region']).agg(agg_dict)

    # Flatten column names
    site_df.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col
                       for col in site_df.columns]
    site_df = site_df.reset_index()

    # Rename for clarity
    rename_map = {
        'subject_id_count': 'subject_count',
        'dqi_score_mean': 'avg_dqi_score',
        'dqi_score_max': 'max_dqi_score',
        'dqi_score_std': 'std_dqi_score',
        'n_issue_types_sum': 'total_issue_types',
        'n_issue_types_mean': 'avg_issue_types',
        'is_high_sum': 'high_risk_count',
        'is_medium_sum': 'medium_risk_count',
        'has_issues_sum': 'subjects_with_issues',
    }
    site_df = site_df.rename(columns=rename_map)

    # Fill NaN std with 0
    site_df['std_dqi_score'] = site_df['std_dqi_score'].fillna(0)

    # Calculate site risk category based on avg_dqi_score only
    # Use percentiles of sites WITH issues (avg_dqi > 0)
    sites_with_issues = site_df[site_df['avg_dqi_score'] > 0]['avg_dqi_score']

    if len(sites_with_issues) > 0:
        site_high_thresh = sites_with_issues.quantile(0.85)
        site_med_thresh = sites_with_issues.quantile(0.50)
        site_high_thresh = max(site_high_thresh, 0.05)
        site_med_thresh = max(site_med_thresh, 0.02)
    else:
        site_high_thresh = 0.10
        site_med_thresh = 0.05

    # Assign site risk category
    site_df['site_risk_category'] = 'Low'
    site_df.loc[site_df['avg_dqi_score'] >= site_med_thresh, 'site_risk_category'] = 'Medium'
    site_df.loc[site_df['avg_dqi_score'] >= site_high_thresh, 'site_risk_category'] = 'High'

    site_thresholds = {
        'high': site_high_thresh,
        'medium': site_med_thresh,
    }

    return site_df, site_thresholds


def aggregate_to_study_level(site_df):
    """
    Aggregate site-level DQI to study level.

    This addresses the gap where analysis was too site-focused
    and ignored study-level insights.

    Args:
        site_df: Site-level DataFrame with DQI scores

    Returns:
        study_df: Study-level DataFrame with aggregated DQI
        study_thresholds: Thresholds used for study risk categorization
    """
    # Aggregation dictionary
    agg_dict = {
        'site_id': 'count',  # Number of sites
        'subject_count': 'sum',
        'avg_dqi_score': ['mean', 'max', 'std'],
        'high_risk_count': 'sum',
        'medium_risk_count': 'sum',
        'subjects_with_issues': 'sum',
    }

    # Add sum of issue columns if they exist
    issue_cols = ['sae_pending_count_sum', 'missing_visit_count_sum', 'missing_pages_count_sum',
                  'lab_issues_count_sum', 'uncoded_meddra_count_sum', 'uncoded_whodd_count_sum',
                  'inactivated_forms_count_sum', 'edrr_open_issues_sum']

    for col in issue_cols:
        if col in site_df.columns:
            agg_dict[col] = 'sum'

    # Perform aggregation
    study_df = site_df.groupby('study').agg(agg_dict)

    # Flatten column names
    study_df.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col
                        for col in study_df.columns]
    study_df = study_df.reset_index()

    # Rename for clarity
    rename_map = {
        'site_id_count': 'site_count',
        'subject_count_sum': 'subject_count',
        'avg_dqi_score_mean': 'avg_dqi_score',
        'avg_dqi_score_max': 'max_site_dqi_score',
        'avg_dqi_score_std': 'std_dqi_score',
        'high_risk_count_sum': 'high_risk_subjects',
        'medium_risk_count_sum': 'medium_risk_subjects',
        'subjects_with_issues_sum': 'subjects_with_issues',
    }
    study_df = study_df.rename(columns=rename_map)

    # Fill NaN std with 0
    if 'std_dqi_score' in study_df.columns:
        study_df['std_dqi_score'] = study_df['std_dqi_score'].fillna(0)

    # Calculate derived metrics
    study_df['high_risk_rate'] = study_df['high_risk_subjects'] / study_df['subject_count']
    study_df['issue_rate'] = study_df['subjects_with_issues'] / study_df['subject_count']

    # Count high-risk sites per study
    high_risk_sites = site_df[site_df['site_risk_category'] == 'High'].groupby('study').size()
    study_df['high_risk_sites'] = study_df['study'].map(high_risk_sites).fillna(0).astype(int)
    study_df['high_risk_site_rate'] = study_df['high_risk_sites'] / study_df['site_count']

    # Determine study risk category based on multiple factors
    studies_with_issues = study_df[study_df['avg_dqi_score'] > 0]['avg_dqi_score']
    if len(studies_with_issues) > 0:
        study_high_thresh = studies_with_issues.quantile(0.85)
        study_med_thresh = studies_with_issues.quantile(0.50)
    else:
        study_high_thresh = 0.10
        study_med_thresh = 0.05

    # Assign study risk category
    study_df['study_risk_category'] = 'Low'

    # Medium criteria
    medium_mask = (
        (study_df['avg_dqi_score'] >= study_med_thresh) |
        (study_df['high_risk_rate'] > 0.05)
    )
    study_df.loc[medium_mask, 'study_risk_category'] = 'Medium'

    # High criteria (overrides medium)
    high_mask = (
        (study_df['avg_dqi_score'] >= study_high_thresh) |
        (study_df['high_risk_rate'] > 0.15) |
        (study_df['high_risk_site_rate'] > 0.20)
    )
    study_df.loc[high_mask, 'study_risk_category'] = 'High'

    study_thresholds = {
        'high': study_high_thresh,
        'medium': study_med_thresh,
    }

    return study_df, study_thresholds


def aggregate_to_region_level(site_df):
    """
    Aggregate site-level DQI to region level.

    This addresses the gap where analysis ignored regional patterns
    that could indicate systemic issues.

    Args:
        site_df: Site-level DataFrame with DQI scores

    Returns:
        region_df: Region-level DataFrame with aggregated DQI
        country_df: Country-level DataFrame with aggregated DQI
    """
    # -------------------------------------------------------------------------
    # REGION-LEVEL AGGREGATION
    # -------------------------------------------------------------------------
    region_agg = {
        'site_id': 'count',
        'subject_count': 'sum',
        'avg_dqi_score': ['mean', 'max', 'std'],
        'high_risk_count': 'sum',
        'medium_risk_count': 'sum',
        'subjects_with_issues': 'sum',
        'study': 'nunique',
        'country': 'nunique',
    }

    region_df = site_df.groupby('region').agg(region_agg)
    region_df.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col
                         for col in region_df.columns]
    region_df = region_df.reset_index()

    # Rename columns
    region_df = region_df.rename(columns={
        'site_id_count': 'site_count',
        'subject_count_sum': 'subject_count',
        'avg_dqi_score_mean': 'avg_dqi_score',
        'avg_dqi_score_max': 'max_dqi_score',
        'avg_dqi_score_std': 'std_dqi_score',
        'high_risk_count_sum': 'high_risk_subjects',
        'medium_risk_count_sum': 'medium_risk_subjects',
        'subjects_with_issues_sum': 'subjects_with_issues',
        'study_nunique': 'study_count',
        'country_nunique': 'country_count',
    })

    # Fill NaN
    region_df['std_dqi_score'] = region_df['std_dqi_score'].fillna(0)

    # Derived metrics
    region_df['high_risk_rate'] = region_df['high_risk_subjects'] / region_df['subject_count']
    region_df['issue_rate'] = region_df['subjects_with_issues'] / region_df['subject_count']

    # Count high-risk sites per region
    high_risk_sites = site_df[site_df['site_risk_category'] == 'High'].groupby('region').size()
    region_df['high_risk_sites'] = region_df['region'].map(high_risk_sites).fillna(0).astype(int)
    region_df['high_risk_site_rate'] = region_df['high_risk_sites'] / region_df['site_count']

    # Assign region risk category
    region_df['region_risk_category'] = 'Low'
    region_df.loc[region_df['avg_dqi_score'] >= region_df['avg_dqi_score'].median(), 'region_risk_category'] = 'Medium'
    region_df.loc[region_df['avg_dqi_score'] >= region_df['avg_dqi_score'].quantile(0.75), 'region_risk_category'] = 'High'

    # -------------------------------------------------------------------------
    # COUNTRY-LEVEL AGGREGATION
    # -------------------------------------------------------------------------
    country_agg = {
        'site_id': 'count',
        'subject_count': 'sum',
        'avg_dqi_score': ['mean', 'max', 'std'],
        'high_risk_count': 'sum',
        'medium_risk_count': 'sum',
        'subjects_with_issues': 'sum',
        'study': 'nunique',
        'region': 'first',
    }

    country_df = site_df.groupby('country').agg(country_agg)
    country_df.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col
                          for col in country_df.columns]
    country_df = country_df.reset_index()

    # Rename columns
    country_df = country_df.rename(columns={
        'site_id_count': 'site_count',
        'subject_count_sum': 'subject_count',
        'avg_dqi_score_mean': 'avg_dqi_score',
        'avg_dqi_score_max': 'max_dqi_score',
        'avg_dqi_score_std': 'std_dqi_score',
        'high_risk_count_sum': 'high_risk_subjects',
        'medium_risk_count_sum': 'medium_risk_subjects',
        'subjects_with_issues_sum': 'subjects_with_issues',
        'study_nunique': 'study_count',
        'region_first': 'region',
    })

    # Fill NaN
    country_df['std_dqi_score'] = country_df['std_dqi_score'].fillna(0)

    # Derived metrics
    country_df['high_risk_rate'] = country_df['high_risk_subjects'] / country_df['subject_count']
    country_df['issue_rate'] = country_df['subjects_with_issues'] / country_df['subject_count']

    # Count high-risk sites per country
    high_risk_sites = site_df[site_df['site_risk_category'] == 'High'].groupby('country').size()
    country_df['high_risk_sites'] = country_df['country'].map(high_risk_sites).fillna(0).astype(int)
    country_df['high_risk_site_rate'] = country_df['high_risk_sites'] / country_df['site_count']

    # Assign country risk category
    country_df['country_risk_category'] = 'Low'
    country_df.loc[country_df['avg_dqi_score'] >= country_df['avg_dqi_score'].median(), 'country_risk_category'] = 'Medium'
    country_df.loc[country_df['avg_dqi_score'] >= country_df['avg_dqi_score'].quantile(0.80), 'country_risk_category'] = 'High'

    return region_df, country_df


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_results(df, site_df, thresholds):
    """
    Run validation checks on the DQI results.

    Returns:
        dict with validation results
    """
    validations = {}

    # 1. SAE subjects in High
    if 'sae_pending_count' in df.columns:
        sae_subjects = df[df['sae_pending_count'] > 0]
        sae_in_high = (sae_subjects['risk_category'] == 'High').sum()
        validations['sae_capture'] = {
            'total_sae': len(sae_subjects),
            'in_high': sae_in_high,
            'rate': sae_in_high / len(sae_subjects) if len(sae_subjects) > 0 else 1.0,
            'pass': sae_in_high == len(sae_subjects)
        }

    # 2. Capture rate (should be ~100% with new logic)
    subjects_with_issues = df['has_issues'].sum()
    flagged = (df['risk_category'] != 'Low').sum()
    validations['capture_rate'] = {
        'subjects_with_issues': subjects_with_issues,
        'flagged': flagged,
        'rate': flagged / subjects_with_issues if subjects_with_issues > 0 else 0,
        'pass': (flagged / subjects_with_issues >= 0.99) if subjects_with_issues > 0 else True
    }

    # 3. Pyramid shape (Medium >= High)
    high_count = (df['risk_category'] == 'High').sum()
    medium_count = (df['risk_category'] == 'Medium').sum()
    validations['pyramid_shape'] = {
        'high': high_count,
        'medium': medium_count,
        'pass': medium_count >= high_count
    }

    # 4. Site pyramid shape
    site_high = (site_df['site_risk_category'] == 'High').sum()
    site_medium = (site_df['site_risk_category'] == 'Medium').sum()
    validations['site_pyramid'] = {
        'high': site_high,
        'medium': site_medium,
        'pass': site_medium >= site_high
    }

    # 5. Score-category alignment
    # Check that higher scores generally mean higher risk
    high_scores = df[df['risk_category'] == 'High']['dqi_score']
    medium_scores = df[df['risk_category'] == 'Medium']['dqi_score']
    low_scores = df[df['risk_category'] == 'Low']['dqi_score']

    validations['score_alignment'] = {
        'high_mean': high_scores.mean() if len(high_scores) > 0 else 0,
        'medium_mean': medium_scores.mean() if len(medium_scores) > 0 else 0,
        'low_mean': low_scores.mean() if len(low_scores) > 0 else 0,
        'pass': (high_scores.mean() if len(high_scores) > 0 else 0) >
                (medium_scores.mean() if len(medium_scores) > 0 else 0) >
                (low_scores.mean() if len(low_scores) > 0 else 0)
    }

    return validations


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def calculate_dqi():
    """Main function to calculate and save DQI scores."""

    print("=" * 70)
    print("JAVELIN.AI - DATA QUALITY INDEX (DQI) CALCULATION")
    print("=" * 70)
    print("\nFinal Version - Validated and Clinically Sound")

    # -------------------------------------------------------------------------
    # Load Data
    # -------------------------------------------------------------------------
    if not MASTER_SUBJECT_PATH.exists():
        print(f"\nERROR: {MASTER_SUBJECT_PATH} not found!")
        print("Please run 02_build_master_table.py first.")
        return False

    print(f"\nLoading {MASTER_SUBJECT_PATH}...")
    df = pd.read_csv(MASTER_SUBJECT_PATH)
    print(f"  Loaded {len(df):,} subjects")
    print(f"  Studies: {df['study'].nunique()}")
    print(f"  Sites: {df.groupby(['study', 'site_id']).ngroups:,}")

    # -------------------------------------------------------------------------
    # Step 1: Display Methodology
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 1: METHODOLOGY")
    print("=" * 70)

    print("\nScoring Formula:")
    print("  DQI = Sum of (weight x (0.5 x binary + 0.5 x severity))")
    print("  - Binary: 1 if issue exists, 0 otherwise")
    print("  - Severity: value / reference_max (capped at 1.0)")

    print("\nFeature Weights by Clinical Tier:")
    print("-" * 70)

    current_tier = None
    total_weight = 0
    for feature, config in sorted(FEATURE_WEIGHTS.items(),
                                   key=lambda x: (-x[1]['weight'])):
        if config['tier'] != current_tier:
            current_tier = config['tier']
            tier_weight = sum(f['weight'] for f in FEATURE_WEIGHTS.values()
                            if f['tier'] == current_tier)
            print(f"\n[{current_tier.upper()}] - {tier_weight:.0%} total")

        print(f"  {feature:<30} {config['weight']:>5.0%}  {config['rationale']}")
        total_weight += config['weight']

    print(f"\n{'TOTAL':<30} {total_weight:>5.0%}")

    # -------------------------------------------------------------------------
    # Step 2: Calculate Subject-Level DQI
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 2: CALCULATE SUBJECT-LEVEL DQI")
    print("=" * 70)

    df, components = calculate_subject_dqi(df)

    print("\nComponent Statistics:")
    print(f"{'Feature':<30} {'Weight':>7} {'Subjects':>10} {'Max Score':>10}")
    print("-" * 60)

    for feature, stats in sorted(components.items(),
                                  key=lambda x: -x[1]['weight']):
        print(f"{feature:<30} {stats['weight']:>6.0%} "
              f"{stats['subjects_with_issue']:>10,} "
              f"{stats['max_component']:>10.3f}")

    print(f"\nDQI Score Distribution:")
    print(f"  Min:    {df['dqi_score'].min():.4f}")
    print(f"  25th:   {df['dqi_score'].quantile(0.25):.4f}")
    print(f"  Median: {df['dqi_score'].median():.4f}")
    print(f"  75th:   {df['dqi_score'].quantile(0.75):.4f}")
    print(f"  Max:    {df['dqi_score'].max():.4f}")
    print(f"  Mean:   {df['dqi_score'].mean():.4f}")

    # -------------------------------------------------------------------------
    # Step 3: Assign Risk Categories
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 3: ASSIGN RISK CATEGORIES")
    print("=" * 70)

    df, thresholds, overrides = assign_risk_categories(df)

    print("\nThresholds:")
    print(f"  High:   SAE pending OR score >= {thresholds['high']:.4f} (90th percentile of non-SAE)")
    print(f"  Medium: Any issue (score > 0)")
    print(f"  Low:    No issues")

    print("\nClinical Overrides:")
    for override, count in overrides.items():
        print(f"  {override}: {count:,} subjects upgraded")

    risk_counts = df['risk_category'].value_counts()
    print("\nRisk Distribution:")
    for cat in ['High', 'Medium', 'Low']:
        count = risk_counts.get(cat, 0)
        pct = count / len(df) * 100
        print(f"  {cat:<8} {count:>8,} subjects ({pct:>5.1f}%)")

    # -------------------------------------------------------------------------
    # Step 4: Aggregate to Site Level
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 4: AGGREGATE TO SITE LEVEL")
    print("=" * 70)

    site_df, site_thresholds = aggregate_site_dqi(df)

    print(f"\nAggregated {len(df):,} subjects to {len(site_df):,} sites")

    print("\nSite Thresholds:")
    print(f"  High:   avg_dqi >= {site_thresholds['high']:.4f} (85th percentile)")
    print(f"  Medium: avg_dqi >= {site_thresholds['medium']:.4f} (50th percentile)")

    site_risk_counts = site_df['site_risk_category'].value_counts()
    print("\nSite Risk Distribution:")
    for cat in ['High', 'Medium', 'Low']:
        count = site_risk_counts.get(cat, 0)
        pct = count / len(site_df) * 100
        print(f"  {cat:<8} {count:>6} sites ({pct:>5.1f}%)")

    print("\nTop 10 Highest Risk Sites:")
    top_sites = site_df.nlargest(10, 'avg_dqi_score')[
        ['study', 'site_id', 'subject_count', 'avg_dqi_score',
         'high_risk_count', 'site_risk_category']
    ]
    print(top_sites.to_string(index=False))

    # -------------------------------------------------------------------------
    # Step 4b: Aggregate to Study Level (NEW - addresses Issue 2)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 4b: AGGREGATE TO STUDY LEVEL")
    print("=" * 70)

    study_df, study_thresholds = aggregate_to_study_level(site_df)

    print(f"\nAggregated {len(site_df):,} sites to {len(study_df):,} studies")

    print("\nStudy Thresholds:")
    print(f"  High:   avg_dqi >= {study_thresholds['high']:.4f} OR high_risk_rate > 15% OR high_risk_site_rate > 20%")
    print(f"  Medium: avg_dqi >= {study_thresholds['medium']:.4f} OR high_risk_rate > 5%")

    study_risk_counts = study_df['study_risk_category'].value_counts()
    print("\nStudy Risk Distribution:")
    for cat in ['High', 'Medium', 'Low']:
        count = study_risk_counts.get(cat, 0)
        pct = count / len(study_df) * 100
        print(f"  {cat:<8} {count:>4} studies ({pct:>5.1f}%)")

    print("\nTop 5 Highest Risk Studies:")
    top_studies = study_df.nlargest(5, 'avg_dqi_score')[
        ['study', 'site_count', 'subject_count', 'avg_dqi_score',
         'high_risk_subjects', 'study_risk_category']
    ]
    print(top_studies.to_string(index=False))

    # -------------------------------------------------------------------------
    # Step 4c: Aggregate to Region Level (NEW - addresses Issue 2)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 4c: AGGREGATE TO REGION/COUNTRY LEVEL")
    print("=" * 70)

    region_df, country_df = aggregate_to_region_level(site_df)

    print(f"\nAggregated to {len(region_df)} regions and {len(country_df)} countries")

    print("\nRegion Summary:")
    for _, row in region_df.iterrows():
        print(f"  {row['region']}: {int(row['site_count'])} sites, {int(row['subject_count']):,} subjects, "
              f"DQI={row['avg_dqi_score']:.4f}, High-risk={row['high_risk_rate']*100:.1f}%")

    print("\nTop 10 Highest Risk Countries:")
    top_countries = country_df.nlargest(10, 'avg_dqi_score')[
        ['country', 'region', 'site_count', 'subject_count', 'avg_dqi_score',
         'high_risk_rate', 'country_risk_category']
    ]
    top_countries['high_risk_rate'] = top_countries['high_risk_rate'] * 100
    top_countries = top_countries.rename(columns={'high_risk_rate': 'high_risk_%'})
    print(top_countries.to_string(index=False))

    # -------------------------------------------------------------------------
    # Step 5: Validation
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 5: VALIDATION")
    print("=" * 70)

    validations = validate_results(df, site_df, thresholds)

    all_pass = True
    for check_name, result in validations.items():
        status = "PASS" if result['pass'] else "FAIL"
        all_pass = all_pass and result['pass']
        print(f"\n{check_name}:")
        for key, value in result.items():
            if key != 'pass':
                if isinstance(value, float):
                    print(f"  {key}: {value:.2%}" if value <= 1 else f"  {key}: {value:.4f}")
                else:
                    print(f"  {key}: {value:,}" if isinstance(value, int) else f"  {key}: {value}")
        print(f"  Status: {status}")

    print(f"\nOverall Validation: {'ALL PASSED' if all_pass else 'SOME FAILED'}")

    # -------------------------------------------------------------------------
    # Step 6: Save Outputs
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 6: SAVE OUTPUTS")
    print("=" * 70)

    # Clean up helper columns before saving
    df_out = df.drop(columns=['is_high', 'is_medium'], errors='ignore')

    # Save subject data
    subject_path = OUTPUT_DIR / "master_subject_with_dqi.csv"
    df_out.to_csv(subject_path, index=False)
    print(f"\nSaved: {subject_path}")
    print(f"  {len(df_out):,} subjects with DQI scores")

    # Save site data
    site_path = OUTPUT_DIR / "master_site_with_dqi.csv"
    site_df.to_csv(site_path, index=False)
    print(f"\nSaved: {site_path}")
    print(f"  {len(site_df):,} sites with aggregated DQI")

    # Save study data (NEW - addresses Issue 2)
    study_path = OUTPUT_DIR / "master_study_with_dqi.csv"
    study_df.to_csv(study_path, index=False)
    print(f"\nSaved: {study_path}")
    print(f"  {len(study_df)} studies with aggregated DQI")

    # Save region data (NEW - addresses Issue 2)
    region_path = OUTPUT_DIR / "master_region_with_dqi.csv"
    region_df.to_csv(region_path, index=False)
    print(f"\nSaved: {region_path}")
    print(f"  {len(region_df)} regions with aggregated DQI")

    # Save country data (NEW - addresses Issue 2)
    country_path = OUTPUT_DIR / "master_country_with_dqi.csv"
    country_df.to_csv(country_path, index=False)
    print(f"\nSaved: {country_path}")
    print(f"  {len(country_df)} countries with aggregated DQI")

    # Save weights
    weights_data = []
    for feature, config in FEATURE_WEIGHTS.items():
        weights_data.append({
            'feature': feature,
            'weight': config['weight'],
            'tier': config['tier'],
            'rationale': config['rationale']
        })
    weights_df = pd.DataFrame(weights_data).sort_values('weight', ascending=False)
    weights_path = OUTPUT_DIR / "dqi_weights.csv"
    weights_df.to_csv(weights_path, index=False)
    print(f"\nSaved: {weights_path}")

    # Save report
    report_path = OUTPUT_DIR / "dqi_model_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("JAVELIN.AI - DATA QUALITY INDEX (DQI) MODEL REPORT\n")
        f.write("=" * 60 + "\n\n")

        f.write("EXECUTIVE SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total Subjects: {len(df):,}\n")
        f.write(f"Total Sites: {len(site_df):,}\n")
        f.write(f"Studies: {df['study'].nunique()}\n")
        f.write(f"Regions: {len(region_df)}\n")
        f.write(f"Countries: {len(country_df)}\n")
        f.write(f"Subjects with Issues: {df['has_issues'].sum():,} ({df['has_issues'].mean():.1%})\n\n")

        f.write("RISK DISTRIBUTION\n")
        f.write("-" * 40 + "\n")
        f.write("Subject Level:\n")
        for cat in ['High', 'Medium', 'Low']:
            count = risk_counts.get(cat, 0)
            f.write(f"  {cat}: {count:,} ({count/len(df)*100:.1f}%)\n")

        f.write("\nSite Level:\n")
        for cat in ['High', 'Medium', 'Low']:
            count = site_risk_counts.get(cat, 0)
            f.write(f"  {cat}: {count} ({count/len(site_df)*100:.1f}%)\n")

        f.write("\nStudy Level:\n")
        for cat in ['High', 'Medium', 'Low']:
            count = study_risk_counts.get(cat, 0)
            f.write(f"  {cat}: {count} ({count/len(study_df)*100:.1f}%)\n")

        f.write(f"\nCapture Rate: {validations['capture_rate']['rate']:.1%}\n")
        f.write(f"SAE Capture: {validations['sae_capture']['rate']:.0%}\n\n")

        f.write("REGIONAL SUMMARY\n")
        f.write("-" * 40 + "\n")
        for _, row in region_df.iterrows():
            f.write(f"{row['region']}:\n")
            f.write(f"  Sites: {int(row['site_count'])} | Subjects: {int(row['subject_count']):,}\n")
            f.write(f"  DQI: {row['avg_dqi_score']:.4f} | High-risk rate: {row['high_risk_rate']*100:.1f}%\n\n")

        f.write("METHODOLOGY\n")
        f.write("-" * 40 + "\n")
        f.write("1. Scoring: Binary (50%) + Severity (50%) x Weight\n")
        f.write("2. High: SAE pending OR top 10% of non-SAE scores\n")
        f.write("3. Medium: Any issue that is not High\n")
        f.write("4. Low: No issues\n")
        f.write("5. Site Risk: Based on average DQI score percentiles\n\n")

        f.write("FEATURE WEIGHTS\n")
        f.write("-" * 40 + "\n")
        for feature, config in sorted(FEATURE_WEIGHTS.items(), key=lambda x: -x[1]['weight']):
            f.write(f"{feature}: {config['weight']:.0%}\n")
            f.write(f"  Tier: {config['tier']}\n")
            f.write(f"  Rationale: {config['rationale']}\n\n")

        f.write("VALIDATION RESULTS\n")
        f.write("-" * 40 + "\n")
        for check_name, result in validations.items():
            status = "PASS" if result['pass'] else "FAIL"
            f.write(f"{check_name}: {status}\n")
        f.write(f"\nOverall: {'ALL PASSED' if all_pass else 'SOME FAILED'}\n")

    print(f"\nSaved: {report_path}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"""
DATASET:
  Subjects: {len(df):,}
  Sites: {len(site_df):,}
  Studies: {df['study'].nunique()}

METHODOLOGY:
  Scoring: Binary + Severity (50/50) x Weight
  High: SAE pending OR top 10% of non-SAE scores
  Medium: Any issue not High
  Low: No issues
  Site: 85th/50th percentile of avg scores

SUBJECT RISK DISTRIBUTION:
  High:   {risk_counts.get('High', 0):,} ({risk_counts.get('High', 0)/len(df)*100:.1f}%)
  Medium: {risk_counts.get('Medium', 0):,} ({risk_counts.get('Medium', 0)/len(df)*100:.1f}%)
  Low:    {risk_counts.get('Low', 0):,} ({risk_counts.get('Low', 0)/len(df)*100:.1f}%)

SITE RISK DISTRIBUTION:
  High:   {site_risk_counts.get('High', 0)} ({site_risk_counts.get('High', 0)/len(site_df)*100:.1f}%)
  Medium: {site_risk_counts.get('Medium', 0)} ({site_risk_counts.get('Medium', 0)/len(site_df)*100:.1f}%)
  Low:    {site_risk_counts.get('Low', 0)} ({site_risk_counts.get('Low', 0)/len(site_df)*100:.1f}%)

VALIDATION:
  All Checks: {'PASSED' if all_pass else 'FAILED'}
  SAE Capture: {validations['sae_capture']['rate']:.0%}
  Overall Capture: {validations['capture_rate']['rate']:.1%}
  Pyramid Shape: {'Valid' if validations['pyramid_shape']['pass'] else 'Invalid'}
""")

    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Review: outputs/master_subject_with_dqi.csv
2. Review: outputs/master_site_with_dqi.csv  
3. Review: outputs/dqi_weights.csv
4. Review: outputs/dqi_model_report.txt
5. Run: python src/04_build_knowledge_graph.py
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    success = calculate_dqi()
    if not success:
        exit(1)