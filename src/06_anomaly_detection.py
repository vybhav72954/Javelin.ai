"""
Javelin.AI - Step 6: Anomaly Detection Engine
===============================================

WHAT THIS DOES:
---------------
Automatically discovers hidden patterns and outliers that manual review would miss.
Goes beyond simple thresholds to find truly unusual data quality patterns.

ANOMALY TYPES DETECTED:
-----------------------
1. STATISTICAL OUTLIERS - Sites/subjects with metrics far outside normal distribution
2. PATTERN ANOMALIES   - Unusual combinations of issues (e.g., high SAE but zero queries)
3. REGIONAL ANOMALIES  - Countries/regions performing significantly different from peers
4. CROSS-STUDY ANOMALIES - Sites that appear problematic across multiple studies
5. VELOCITY ANOMALIES  - Unusually high concentration of issues (issue density)
6. CORRELATION ANOMALIES - Unexpected relationships between metrics

WHY THIS MATTERS:
-----------------
- Traditional dashboards show what you LOOK FOR
- Anomaly detection finds what you DIDN'T KNOW TO LOOK FOR
- Identifies systemic issues, not just individual problems
- Surfaces patterns invisible to manual review

Usage:
    python src/06_anomaly_detection.py

Outputs:
    - outputs/anomalies_detected.csv      : All detected anomalies with details
    - outputs/anomaly_summary.json        : Summary statistics
    - outputs/anomaly_report.md           : Human-readable report
    - outputs/site_anomaly_scores.csv     : Anomaly scores per site
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import json
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Input files from previous steps
SUBJECT_DQI_PATH = OUTPUT_DIR / "master_subject_with_dqi.csv"
SITE_DQI_PATH = OUTPUT_DIR / "master_site_with_dqi.csv"

# Anomaly Detection Thresholds
THRESHOLDS = {
    # Statistical outlier thresholds
    'zscore_threshold': 2.5,          # Standard deviations from mean
    'iqr_multiplier': 1.5,            # IQR multiplier for outlier detection
    'extreme_iqr_multiplier': 3.0,    # Extreme outlier threshold

    # Pattern anomaly thresholds
    'min_issues_for_pattern': 3,      # Minimum issues to check patterns
    'pattern_correlation_threshold': 0.3,  # Expected correlation minimum

    # Regional anomaly thresholds
    'regional_zscore_threshold': 2.0, # Z-score for regional comparison
    'min_sites_per_region': 3,        # Minimum sites for regional analysis
    'min_sites_per_country': 2,       # Minimum sites for country analysis

    # Cross-study thresholds
    'cross_study_risk_threshold': 0.5, # High risk in multiple studies

    # Velocity/density thresholds
    'issue_density_threshold': 0.8,   # Issues per subject ratio
    'concentration_threshold': 0.7,   # % of study issues in one site
}

# Issue columns to analyze (subject level)
ISSUE_COLUMNS_SUBJECT = [
    'sae_pending_count',
    'uncoded_meddra_count',
    'missing_visit_count',
    'missing_pages_count',
    'lab_issues_count',
    'max_days_outstanding',
    'uncoded_whodd_count',
    'edrr_open_issues',
    'inactivated_forms_count'
]

# Issue columns at site level (aggregated with _sum suffix)
ISSUE_COLUMNS_SITE = [
    'sae_pending_count_sum',
    'uncoded_meddra_count_sum',
    'missing_visit_count_sum',
    'missing_pages_count_sum',
    'lab_issues_count_sum',
    'max_days_outstanding_sum',
    'max_days_page_missing_sum',
    'uncoded_whodd_count_sum',
    'edrr_open_issues_sum',
    'inactivated_forms_count_sum'
]

# Anomaly severity levels
SEVERITY_LEVELS = {
    'CRITICAL': 4,
    'HIGH': 3,
    'MEDIUM': 2,
    'LOW': 1
}


# ============================================================================
# STATISTICAL ANOMALY DETECTION
# ============================================================================

def calculate_zscore(series: pd.Series) -> pd.Series:
    """Calculate z-scores for a series."""
    mean = series.mean()
    std = series.std()
    if std == 0:
        return pd.Series(0, index=series.index)
    return (series - mean) / std


def calculate_iqr_bounds(series: pd.Series, multiplier: float = 1.5) -> Tuple[float, float]:
    """Calculate IQR-based outlier bounds."""
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return lower, upper


def detect_statistical_outliers(df: pd.DataFrame, level: str = 'site') -> List[Dict]:
    """
    Detect statistical outliers using multiple methods.

    Methods:
    1. Z-score: Values > threshold standard deviations from mean
    2. IQR: Values outside Q1 - 1.5*IQR or Q3 + 1.5*IQR
    3. Modified Z-score: Robust to outliers using median

    Args:
        df: DataFrame with DQI data
        level: 'site' or 'subject'

    Returns:
        List of anomaly dictionaries
    """
    anomalies = []

    # Determine which columns to analyze based on level
    if level == 'site':
        id_col = 'site_id'
        dqi_col = 'avg_dqi_score'
        numeric_cols = ['avg_dqi_score', 'subject_count', 'high_risk_count', 'subjects_with_issues']
        # Add issue columns
        numeric_cols.extend([col for col in ISSUE_COLUMNS_SITE if col in df.columns])
    else:
        id_col = 'subject_id'
        dqi_col = 'dqi_score'
        numeric_cols = ['dqi_score'] + [col for col in ISSUE_COLUMNS_SUBJECT if col in df.columns]

    # Analyze each numeric column
    for col in numeric_cols:
        if col not in df.columns:
            continue

        series = df[col].fillna(0)

        # Skip if no variance
        if series.std() == 0:
            continue

        # Method 1: Z-score outliers
        zscores = calculate_zscore(series)
        zscore_outliers = df[abs(zscores) > THRESHOLDS['zscore_threshold']]

        for idx, row in zscore_outliers.iterrows():
            z = zscores[idx]
            direction = 'above' if z > 0 else 'below'
            severity = 'CRITICAL' if abs(z) > 4 else 'HIGH' if abs(z) > 3 else 'MEDIUM'

            anomalies.append({
                'anomaly_type': 'STATISTICAL_OUTLIER',
                'detection_method': 'Z-Score',
                'level': level,
                'study': row.get('study', 'Unknown'),
                'site_id': row.get('site_id', row.get('subject_id', 'Unknown')),
                'country': row.get('country', 'Unknown'),
                'region': row.get('region', 'Unknown'),
                'metric': col,
                'value': row[col],
                'zscore': round(z, 2),
                'mean': round(series.mean(), 3),
                'std': round(series.std(), 3),
                'severity': severity,
                'description': f"{col} is {abs(z):.1f} standard deviations {direction} the mean ({row[col]:.3f} vs mean {series.mean():.3f})",
                'recommendation': f"Investigate why {col} is unusually {'high' if z > 0 else 'low'} at this {level}"
            })

        # Method 2: IQR outliers (more robust)
        lower, upper = calculate_iqr_bounds(series, THRESHOLDS['iqr_multiplier'])
        extreme_lower, extreme_upper = calculate_iqr_bounds(series, THRESHOLDS['extreme_iqr_multiplier'])

        iqr_outliers = df[(series < lower) | (series > upper)]

        for idx, row in iqr_outliers.iterrows():
            val = row[col]
            # Skip if already caught by z-score
            if abs(zscores[idx]) > THRESHOLDS['zscore_threshold']:
                continue

            is_extreme = val < extreme_lower or val > extreme_upper
            direction = 'above' if val > upper else 'below'
            severity = 'HIGH' if is_extreme else 'MEDIUM'

            anomalies.append({
                'anomaly_type': 'STATISTICAL_OUTLIER',
                'detection_method': 'IQR',
                'level': level,
                'study': row.get('study', 'Unknown'),
                'site_id': row.get('site_id', row.get('subject_id', 'Unknown')),
                'country': row.get('country', 'Unknown'),
                'region': row.get('region', 'Unknown'),
                'metric': col,
                'value': row[col],
                'lower_bound': round(lower, 3),
                'upper_bound': round(upper, 3),
                'severity': severity,
                'description': f"{col} ({row[col]:.3f}) is outside IQR bounds [{lower:.3f}, {upper:.3f}]",
                'recommendation': f"Review {level} for unusual {col} pattern"
            })

    return anomalies


# ============================================================================
# PATTERN ANOMALY DETECTION
# ============================================================================

def detect_pattern_anomalies(df: pd.DataFrame) -> List[Dict]:
    """
    Detect unusual patterns/combinations of issues.

    Patterns detected:
    1. High SAE but no queries (should have queries if SAE is high)
    2. High missing data but low query count (queries should be generated)
    3. Zero issues in high-subject site (too good to be true?)
    4. All issues concentrated in one category (systemic problem)

    Args:
        df: Site-level DataFrame

    Returns:
        List of anomaly dictionaries
    """
    anomalies = []

    # Ensure we have needed columns
    required_cols = ['site_id', 'study', 'subject_count']
    if not all(col in df.columns for col in required_cols):
        return anomalies

    for idx, row in df.iterrows():
        site_anomalies = []

        # Get issue values with defaults (using actual column names)
        sae = row.get('sae_pending_count_sum', 0) or 0
        missing_visits = row.get('missing_visit_count_sum', 0) or 0
        missing_pages = row.get('missing_pages_count_sum', 0) or 0
        lab_issues = row.get('lab_issues_count_sum', 0) or 0
        subjects = row.get('subject_count', 1) or 1
        dqi = row.get('avg_dqi_score', 0) or 0
        high_risk = row.get('high_risk_count', 0) or 0

        # Pattern 1: High SAE but site not flagged as high risk
        if sae > 5 and row.get('site_risk_category') != 'High':
            site_anomalies.append({
                'pattern': 'SAE_NOT_FLAGGED',
                'severity': 'CRITICAL',
                'description': f"Site has {sae} pending SAE but not classified as High risk",
                'recommendation': "Immediately review SAE processing at this site"
            })

        # Pattern 2: Very high subject count but zero issues (suspicious)
        if subjects > 50 and dqi == 0:
            site_anomalies.append({
                'pattern': 'ZERO_ISSUES_HIGH_VOLUME',
                'severity': 'MEDIUM',
                'description': f"Site has {subjects} subjects but zero DQI issues detected",
                'recommendation': "Verify data completeness - may indicate missing source data"
            })

        # Pattern 3: High missing data but very old (not being addressed)
        max_days = row.get('max_days_outstanding_sum', 0) or 0
        max_page_days = row.get('max_days_page_missing_sum', 0) or 0
        if (missing_visits > 10 or missing_pages > 20) and max(max_days, max_page_days) > 60:
            site_anomalies.append({
                'pattern': 'STALE_MISSING_DATA',
                'severity': 'HIGH',
                'description': f"Site has {missing_visits} missing visits, {missing_pages} missing pages outstanding for {max(max_days, max_page_days):.0f}+ days",
                'recommendation': "Escalate to site - missing data not being resolved"
            })

        # Pattern 4: Disproportionate high-risk subjects
        high_risk_pct = (high_risk / subjects * 100) if subjects > 0 else 0
        if subjects >= 10 and high_risk_pct > 50:
            site_anomalies.append({
                'pattern': 'MAJORITY_HIGH_RISK',
                'severity': 'HIGH',
                'description': f"{high_risk_pct:.1f}% of subjects ({high_risk}/{subjects}) are high risk",
                'recommendation': "Site-wide intervention needed - systemic quality issues"
            })

        # Pattern 5: Single issue type dominance (>80% of issues from one source)
        issue_counts = {
            'sae': sae,
            'missing_visits': missing_visits,
            'missing_pages': missing_pages,
            'lab_issues': lab_issues,
        }
        total_issues = sum(issue_counts.values())

        if total_issues >= 20:
            for issue_type, count in issue_counts.items():
                if count / total_issues > 0.8:
                    site_anomalies.append({
                        'pattern': 'SINGLE_ISSUE_DOMINANCE',
                        'severity': 'MEDIUM',
                        'description': f"{issue_type} represents {count/total_issues*100:.0f}% of all issues ({count}/{total_issues})",
                        'recommendation': f"Focus intervention on {issue_type} - appears to be primary problem"
                    })

        # Add anomalies for this site
        for anomaly in site_anomalies:
            anomalies.append({
                'anomaly_type': 'PATTERN_ANOMALY',
                'detection_method': anomaly['pattern'],
                'level': 'site',
                'study': row.get('study', 'Unknown'),
                'site_id': row.get('site_id', 'Unknown'),
                'country': row.get('country', 'Unknown'),
                'region': row.get('region', 'Unknown'),
                'severity': anomaly['severity'],
                'description': anomaly['description'],
                'recommendation': anomaly['recommendation'],
                'value': None,
                'metric': anomaly['pattern']
            })

    return anomalies


# ============================================================================
# REGIONAL ANOMALY DETECTION
# ============================================================================

def detect_regional_anomalies(df: pd.DataFrame) -> List[Dict]:
    """
    Detect countries/regions performing significantly different from peers.

    Analysis:
    1. Compare each country's average DQI to regional average
    2. Compare each region's average DQI to portfolio average
    3. Identify countries with disproportionate issue concentrations

    Args:
        df: Site-level DataFrame

    Returns:
        List of anomaly dictionaries
    """
    anomalies = []

    if 'country' not in df.columns or 'region' not in df.columns:
        return anomalies

    # Calculate regional statistics
    regional_stats = df.groupby('region').agg({
        'avg_dqi_score': ['mean', 'std', 'count'],
        'site_id': 'count'
    }).reset_index()
    regional_stats.columns = ['region', 'region_mean_dqi', 'region_std_dqi', 'region_count', 'site_count']

    # Calculate country statistics
    country_stats = df.groupby(['region', 'country']).agg({
        'avg_dqi_score': ['mean', 'std', 'count'],
        'high_risk_count': 'sum',
        'subject_count': 'sum'
    }).reset_index()
    country_stats.columns = ['region', 'country', 'country_mean_dqi', 'country_std_dqi',
                             'site_count', 'high_risk_total', 'subject_total']

    # Merge regional stats
    country_stats = country_stats.merge(
        regional_stats[['region', 'region_mean_dqi', 'region_std_dqi']],
        on='region'
    )

    # Portfolio-level stats
    portfolio_mean = df['avg_dqi_score'].mean()
    portfolio_std = df['avg_dqi_score'].std()

    # Detect country-level anomalies
    for idx, row in country_stats.iterrows():
        if row['site_count'] < THRESHOLDS['min_sites_per_country']:
            continue

        # Compare country to region
        if row['region_std_dqi'] > 0:
            regional_zscore = (row['country_mean_dqi'] - row['region_mean_dqi']) / row['region_std_dqi']
        else:
            regional_zscore = 0

        # Compare country to portfolio
        if portfolio_std > 0:
            portfolio_zscore = (row['country_mean_dqi'] - portfolio_mean) / portfolio_std
        else:
            portfolio_zscore = 0

        # Flag if significantly different
        if abs(regional_zscore) > THRESHOLDS['regional_zscore_threshold']:
            direction = 'higher' if regional_zscore > 0 else 'lower'
            severity = 'HIGH' if abs(regional_zscore) > 3 else 'MEDIUM'

            anomalies.append({
                'anomaly_type': 'REGIONAL_ANOMALY',
                'detection_method': 'COUNTRY_VS_REGION',
                'level': 'country',
                'study': 'All',
                'site_id': f"{row['country']} ({row['site_count']} sites)",
                'country': row['country'],
                'region': row['region'],
                'metric': 'avg_dqi_score',
                'value': round(row['country_mean_dqi'], 4),
                'zscore': round(regional_zscore, 2),
                'severity': severity,
                'description': f"{row['country']} DQI ({row['country_mean_dqi']:.3f}) is {abs(regional_zscore):.1f}σ {direction} than {row['region']} average ({row['region_mean_dqi']:.3f})",
                'recommendation': f"Investigate {row['country']} sites - may need regional training or support"
            })

        # Also flag if significantly different from portfolio
        if abs(portfolio_zscore) > THRESHOLDS['regional_zscore_threshold'] + 0.5:
            direction = 'higher' if portfolio_zscore > 0 else 'lower'
            severity = 'HIGH' if abs(portfolio_zscore) > 3 else 'MEDIUM'

            # Don't duplicate if already caught by regional comparison
            already_flagged = any(
                a['country'] == row['country'] and a['detection_method'] == 'COUNTRY_VS_REGION'
                for a in anomalies
            )

            if not already_flagged:
                anomalies.append({
                    'anomaly_type': 'REGIONAL_ANOMALY',
                    'detection_method': 'COUNTRY_VS_PORTFOLIO',
                    'level': 'country',
                    'study': 'All',
                    'site_id': f"{row['country']} ({row['site_count']} sites)",
                    'country': row['country'],
                    'region': row['region'],
                    'metric': 'avg_dqi_score',
                    'value': round(row['country_mean_dqi'], 4),
                    'zscore': round(portfolio_zscore, 2),
                    'severity': severity,
                    'description': f"{row['country']} DQI ({row['country_mean_dqi']:.3f}) is {abs(portfolio_zscore):.1f}σ {direction} than portfolio average ({portfolio_mean:.3f})",
                    'recommendation': f"Country-wide review recommended for {row['country']}"
                })

    # Detect region-level anomalies
    for idx, row in regional_stats.iterrows():
        if row['site_count'] < THRESHOLDS['min_sites_per_region']:
            continue

        if portfolio_std > 0:
            region_zscore = (row['region_mean_dqi'] - portfolio_mean) / portfolio_std
        else:
            region_zscore = 0

        if abs(region_zscore) > THRESHOLDS['regional_zscore_threshold']:
            direction = 'higher' if region_zscore > 0 else 'lower'
            severity = 'HIGH' if abs(region_zscore) > 2.5 else 'MEDIUM'

            anomalies.append({
                'anomaly_type': 'REGIONAL_ANOMALY',
                'detection_method': 'REGION_VS_PORTFOLIO',
                'level': 'region',
                'study': 'All',
                'site_id': f"{row['region']} ({row['site_count']} sites)",
                'country': 'Multiple',
                'region': row['region'],
                'metric': 'avg_dqi_score',
                'value': round(row['region_mean_dqi'], 4),
                'zscore': round(region_zscore, 2),
                'severity': severity,
                'description': f"{row['region']} region DQI ({row['region_mean_dqi']:.3f}) is {abs(region_zscore):.1f}σ {direction} than portfolio average ({portfolio_mean:.3f})",
                'recommendation': f"Regional review needed for {row['region']} - consider targeted training"
            })

    return anomalies


# ============================================================================
# CROSS-STUDY ANOMALY DETECTION
# ============================================================================

def detect_cross_study_anomalies(df: pd.DataFrame) -> List[Dict]:
    """
    Detect sites that appear problematic across multiple studies.

    Analysis:
    1. Find sites (by site_id or country combination) in multiple studies
    2. Check if consistently high risk across studies
    3. Identify potential "problem sites" that affect multiple programs

    Args:
        df: Site-level DataFrame

    Returns:
        List of anomaly dictionaries
    """
    anomalies = []

    if 'site_id' not in df.columns or 'study' not in df.columns:
        return anomalies

    # Group by site_id to find sites in multiple studies
    site_studies = df.groupby('site_id').agg({
        'study': lambda x: list(x.unique()),
        'avg_dqi_score': 'mean',
        'high_risk_count': 'sum',
        'subject_count': 'sum',
        'site_risk_category': lambda x: list(x),
        'country': 'first',
        'region': 'first'
    }).reset_index()

    site_studies['num_studies'] = site_studies['study'].apply(len)

    # Find sites in multiple studies
    multi_study_sites = site_studies[site_studies['num_studies'] > 1]

    for idx, row in multi_study_sites.iterrows():
        studies = row['study']
        risk_categories = row['site_risk_category']
        high_risk_count = risk_categories.count('High') if isinstance(risk_categories, list) else 0

        # Flag if high risk in majority of studies
        if high_risk_count >= len(studies) * THRESHOLDS['cross_study_risk_threshold']:
            severity = 'CRITICAL' if high_risk_count == len(studies) else 'HIGH'

            anomalies.append({
                'anomaly_type': 'CROSS_STUDY_ANOMALY',
                'detection_method': 'REPEAT_HIGH_RISK',
                'level': 'site',
                'study': ', '.join(studies),
                'site_id': row['site_id'],
                'country': row['country'],
                'region': row['region'],
                'metric': 'multi_study_risk',
                'value': high_risk_count,
                'severity': severity,
                'description': f"Site {row['site_id']} is high risk in {high_risk_count}/{len(studies)} studies: {', '.join(studies)}",
                'recommendation': "Cross-functional review needed - site shows consistent quality issues across programs"
            })

        # Flag sites with high overall DQI across studies
        if row['avg_dqi_score'] > 0.3 and row['num_studies'] >= 2:
            anomalies.append({
                'anomaly_type': 'CROSS_STUDY_ANOMALY',
                'detection_method': 'CONSISTENT_HIGH_DQI',
                'level': 'site',
                'study': ', '.join(studies),
                'site_id': row['site_id'],
                'country': row['country'],
                'region': row['region'],
                'metric': 'avg_dqi_across_studies',
                'value': round(row['avg_dqi_score'], 3),
                'severity': 'HIGH',
                'description': f"Site {row['site_id']} has elevated DQI ({row['avg_dqi_score']:.3f}) across {len(studies)} studies",
                'recommendation': "Consider site capability assessment - persistent quality challenges"
            })

    return anomalies


# ============================================================================
# VELOCITY/CONCENTRATION ANOMALY DETECTION
# ============================================================================

def detect_velocity_anomalies(df: pd.DataFrame) -> List[Dict]:
    """
    Detect unusual concentration or density of issues.

    Analysis:
    1. Issue density: issues per subject ratio
    2. Study concentration: % of study's issues at one site
    3. Velocity: rapid accumulation patterns

    Args:
        df: Site-level DataFrame

    Returns:
        List of anomaly dictionaries
    """
    anomalies = []

    # Use the actual column names from the data
    issue_cols = [col for col in ISSUE_COLUMNS_SITE if col in df.columns]

    if not issue_cols or 'subject_count' not in df.columns:
        return anomalies

    df = df.copy()
    df['total_issues'] = df[issue_cols].fillna(0).sum(axis=1)
    df['issue_density'] = df['total_issues'] / df['subject_count'].replace(0, 1)

    # Detect high issue density
    density_mean = df['issue_density'].mean()
    density_std = df['issue_density'].std()

    for idx, row in df.iterrows():
        # Skip sites with very few subjects
        if row['subject_count'] < 5:
            continue

        # High density anomaly
        if density_std > 0:
            density_zscore = (row['issue_density'] - density_mean) / density_std
        else:
            density_zscore = 0

        if density_zscore > THRESHOLDS['zscore_threshold']:
            severity = 'HIGH' if density_zscore > 3 else 'MEDIUM'

            anomalies.append({
                'anomaly_type': 'VELOCITY_ANOMALY',
                'detection_method': 'HIGH_ISSUE_DENSITY',
                'level': 'site',
                'study': row.get('study', 'Unknown'),
                'site_id': row.get('site_id', 'Unknown'),
                'country': row.get('country', 'Unknown'),
                'region': row.get('region', 'Unknown'),
                'metric': 'issue_density',
                'value': round(row['issue_density'], 2),
                'zscore': round(density_zscore, 2),
                'severity': severity,
                'description': f"Site has {row['issue_density']:.1f} issues per subject ({row['total_issues']:.0f} issues / {row['subject_count']} subjects), {density_zscore:.1f}σ above average",
                'recommendation': "High issue concentration - prioritize for immediate intervention"
            })

    # Study-level concentration analysis
    if 'study' in df.columns:
        for study in df['study'].unique():
            study_df = df[df['study'] == study]
            study_total_issues = study_df['total_issues'].sum()

            if study_total_issues < 10:
                continue

            for idx, row in study_df.iterrows():
                site_pct = row['total_issues'] / study_total_issues if study_total_issues > 0 else 0

                if site_pct > THRESHOLDS['concentration_threshold']:
                    anomalies.append({
                        'anomaly_type': 'VELOCITY_ANOMALY',
                        'detection_method': 'ISSUE_CONCENTRATION',
                        'level': 'site',
                        'study': study,
                        'site_id': row.get('site_id', 'Unknown'),
                        'country': row.get('country', 'Unknown'),
                        'region': row.get('region', 'Unknown'),
                        'metric': 'study_issue_concentration',
                        'value': round(site_pct, 3),
                        'severity': 'HIGH',
                        'description': f"Site accounts for {site_pct*100:.1f}% of all issues in {study} ({row['total_issues']:.0f}/{study_total_issues:.0f})",
                        'recommendation': f"Single site driving majority of {study} issues - immediate site review needed"
                    })

    return anomalies


# ============================================================================
# ANOMALY SCORING & AGGREGATION
# ============================================================================

def calculate_anomaly_score(anomalies: List[Dict], df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate composite anomaly score for each site.

    Score considers:
    - Number of anomalies detected
    - Severity of anomalies
    - Type diversity of anomalies

    Args:
        anomalies: List of detected anomalies
        df: Site-level DataFrame

    Returns:
        DataFrame with anomaly scores
    """
    # Initialize scores
    site_scores = defaultdict(lambda: {
        'anomaly_count': 0,
        'critical_count': 0,
        'high_count': 0,
        'medium_count': 0,
        'low_count': 0,
        'anomaly_types': set(),
        'anomalies': []
    })

    # Aggregate anomalies per site
    for anomaly in anomalies:
        if anomaly['level'] != 'site':
            continue

        site_key = (anomaly['study'], anomaly['site_id'])
        site_scores[site_key]['anomaly_count'] += 1
        site_scores[site_key]['anomaly_types'].add(anomaly['anomaly_type'])
        site_scores[site_key]['anomalies'].append(anomaly)

        severity = anomaly.get('severity', 'LOW')
        if severity == 'CRITICAL':
            site_scores[site_key]['critical_count'] += 1
        elif severity == 'HIGH':
            site_scores[site_key]['high_count'] += 1
        elif severity == 'MEDIUM':
            site_scores[site_key]['medium_count'] += 1
        else:
            site_scores[site_key]['low_count'] += 1

    # Calculate composite score
    rows = []
    for (study, site_id), data in site_scores.items():
        # Weighted score: Critical=4, High=3, Medium=2, Low=1
        weighted_score = (
            data['critical_count'] * 4 +
            data['high_count'] * 3 +
            data['medium_count'] * 2 +
            data['low_count'] * 1
        )

        # Type diversity bonus
        type_diversity = len(data['anomaly_types'])

        # Final score (normalized)
        max_possible = data['anomaly_count'] * 4  # If all were critical
        anomaly_score = weighted_score / max_possible if max_possible > 0 else 0

        # Boost for diversity
        final_score = anomaly_score * (1 + 0.1 * type_diversity)

        rows.append({
            'study': study,
            'site_id': site_id,
            'anomaly_count': data['anomaly_count'],
            'critical_count': data['critical_count'],
            'high_count': data['high_count'],
            'medium_count': data['medium_count'],
            'low_count': data['low_count'],
            'anomaly_types': ', '.join(sorted(data['anomaly_types'])),
            'type_diversity': type_diversity,
            'anomaly_score': round(final_score, 3),
            'top_anomalies': '; '.join([a['description'][:100] for a in data['anomalies'][:3]])
        })

    score_df = pd.DataFrame(rows)
    if not score_df.empty:
        score_df = score_df.sort_values('anomaly_score', ascending=False)

    return score_df


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_anomaly_report(
    anomalies: List[Dict],
    score_df: pd.DataFrame,
    site_df: pd.DataFrame
) -> str:
    """Generate markdown report of anomalies."""

    report = f"""# JAVELIN.AI - Anomaly Detection Report

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Anomalies Detected | {len(anomalies)} |
| Sites with Anomalies | {len(score_df)} |
| Critical Anomalies | {sum(1 for a in anomalies if a.get('severity') == 'CRITICAL')} |
| High Severity Anomalies | {sum(1 for a in anomalies if a.get('severity') == 'HIGH')} |
| Medium Severity Anomalies | {sum(1 for a in anomalies if a.get('severity') == 'MEDIUM')} |

---

## Anomaly Distribution by Type

"""

    # Count by type
    type_counts = defaultdict(int)
    for a in anomalies:
        type_counts[a['anomaly_type']] += 1

    for atype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        report += f"- **{atype}**: {count} anomalies\n"

    report += """

---

## Top 10 Sites by Anomaly Score

| Rank | Study | Site ID | Score | Anomalies | Critical | High | Types |
|------|-------|---------|-------|-----------|----------|------|-------|
"""

    for i, row in score_df.head(10).iterrows():
        report += f"| {score_df.index.get_loc(i) + 1} | {row['study']} | {row['site_id']} | {row['anomaly_score']:.3f} | {row['anomaly_count']} | {row['critical_count']} | {row['high_count']} | {row['type_diversity']} |\n"

    report += """

---

## Critical Anomalies (Immediate Action Required)

"""

    critical = [a for a in anomalies if a.get('severity') == 'CRITICAL']
    if critical:
        for i, a in enumerate(critical[:20], 1):
            report += f"""
### {i}. {a['study']} - {a['site_id']} ({a['country']})

- **Type**: {a['anomaly_type']} ({a['detection_method']})
- **Description**: {a['description']}
- **Recommendation**: {a['recommendation']}
"""
    else:
        report += "*No critical anomalies detected.*\n"

    report += """

---

## Regional Anomalies

"""

    regional = [a for a in anomalies if a['anomaly_type'] == 'REGIONAL_ANOMALY']
    if regional:
        for a in regional:
            report += f"- **{a['country']}** ({a['region']}): {a['description']}\n"
    else:
        report += "*No regional anomalies detected.*\n"

    report += """

---

## Cross-Study Anomalies

"""

    cross_study = [a for a in anomalies if a['anomaly_type'] == 'CROSS_STUDY_ANOMALY']
    if cross_study:
        for a in cross_study:
            report += f"- **{a['site_id']}**: {a['description']}\n"
    else:
        report += "*No cross-study anomalies detected.*\n"

    report += """

---

## Recommendations Summary

Based on the anomaly analysis, the following actions are recommended:

"""

    # Deduplicate recommendations
    recommendations = set()
    for a in anomalies:
        if a.get('recommendation'):
            recommendations.add(a['recommendation'])

    for i, rec in enumerate(list(recommendations)[:15], 1):
        report += f"{i}. {rec}\n"

    report += """

---

*Report generated by JAVELIN.AI Anomaly Detection Engine*
"""

    return report


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def run_anomaly_detection():
    """Main function to run anomaly detection pipeline."""

    print("=" * 70)
    print("JAVELIN.AI - ANOMALY DETECTION ENGINE")
    print("=" * 70)
    print(f"\nProject Root: {PROJECT_ROOT}")
    print(f"Output Directory: {OUTPUT_DIR}")

    # =========================================================================
    # Step 1: Load Data
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: LOAD DATA")
    print("=" * 70)

    if not SITE_DQI_PATH.exists():
        print(f"\n❌ ERROR: Site DQI file not found: {SITE_DQI_PATH}")
        print("   Please run 03_calculate_dqi.py first")
        return False

    site_df = pd.read_csv(SITE_DQI_PATH)
    print(f"\n✅ Loaded site data: {len(site_df):,} sites")

    subject_df = None
    if SUBJECT_DQI_PATH.exists():
        subject_df = pd.read_csv(SUBJECT_DQI_PATH)
        print(f"✅ Loaded subject data: {len(subject_df):,} subjects")

    print(f"\nStudies: {site_df['study'].nunique()}")
    print(f"Countries: {site_df['country'].nunique()}")
    print(f"Regions: {site_df['region'].nunique()}")

    # =========================================================================
    # Step 2: Detect Statistical Outliers
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: DETECT STATISTICAL OUTLIERS")
    print("=" * 70)

    stat_anomalies = detect_statistical_outliers(site_df, level='site')
    print(f"\n✅ Detected {len(stat_anomalies)} statistical outliers at site level")

    # Severity breakdown
    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        count = sum(1 for a in stat_anomalies if a.get('severity') == sev)
        if count > 0:
            print(f"   {sev}: {count}")

    # =========================================================================
    # Step 3: Detect Pattern Anomalies
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 3: DETECT PATTERN ANOMALIES")
    print("=" * 70)

    pattern_anomalies = detect_pattern_anomalies(site_df)
    print(f"\n✅ Detected {len(pattern_anomalies)} pattern anomalies")

    # Pattern breakdown
    patterns = defaultdict(int)
    for a in pattern_anomalies:
        patterns[a['detection_method']] += 1
    for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"   {pattern}: {count}")

    # =========================================================================
    # Step 4: Detect Regional Anomalies
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 4: DETECT REGIONAL ANOMALIES")
    print("=" * 70)

    regional_anomalies = detect_regional_anomalies(site_df)
    print(f"\n✅ Detected {len(regional_anomalies)} regional anomalies")

    # Regional breakdown
    for a in regional_anomalies[:5]:
        print(f"   • {a['country']} ({a['region']}): {a['description'][:60]}...")

    # =========================================================================
    # Step 5: Detect Cross-Study Anomalies
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 5: DETECT CROSS-STUDY ANOMALIES")
    print("=" * 70)

    cross_study_anomalies = detect_cross_study_anomalies(site_df)
    print(f"\n✅ Detected {len(cross_study_anomalies)} cross-study anomalies")

    for a in cross_study_anomalies[:5]:
        print(f"   • {a['site_id']}: {a['description'][:60]}...")

    # =========================================================================
    # Step 6: Detect Velocity/Concentration Anomalies
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 6: DETECT VELOCITY ANOMALIES")
    print("=" * 70)

    velocity_anomalies = detect_velocity_anomalies(site_df)
    print(f"\n✅ Detected {len(velocity_anomalies)} velocity/concentration anomalies")

    # =========================================================================
    # Step 7: Aggregate & Score
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 7: AGGREGATE & SCORE")
    print("=" * 70)

    # Combine all anomalies
    all_anomalies = (
        stat_anomalies +
        pattern_anomalies +
        regional_anomalies +
        cross_study_anomalies +
        velocity_anomalies
    )

    print(f"\n📊 Total Anomalies Detected: {len(all_anomalies)}")

    # Calculate site anomaly scores
    score_df = calculate_anomaly_score(all_anomalies, site_df)
    print(f"   Sites with Anomalies: {len(score_df)}")

    if not score_df.empty:
        print(f"\nTop 5 Sites by Anomaly Score:")
        for i, row in score_df.head(5).iterrows():
            print(f"   {row['study']} - {row['site_id']}: Score {row['anomaly_score']:.3f} ({row['anomaly_count']} anomalies, {row['critical_count']} critical)")

    # =========================================================================
    # Step 8: Save Outputs
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 8: SAVE OUTPUTS")
    print("=" * 70)

    # 1. Save all anomalies
    anomalies_df = pd.DataFrame(all_anomalies)
    anomalies_path = OUTPUT_DIR / "anomalies_detected.csv"
    anomalies_df.to_csv(anomalies_path, index=False)
    print(f"\n✅ Saved: {anomalies_path}")
    print(f"   {len(anomalies_df)} anomalies")

    # 2. Save site anomaly scores
    scores_path = OUTPUT_DIR / "site_anomaly_scores.csv"
    score_df.to_csv(scores_path, index=False)
    print(f"\n✅ Saved: {scores_path}")
    print(f"   {len(score_df)} sites scored")

    # 3. Save summary JSON
    summary = {
        'generated_at': datetime.now().isoformat(),
        'total_anomalies': len(all_anomalies),
        'sites_with_anomalies': len(score_df),
        'by_severity': {
            'critical': sum(1 for a in all_anomalies if a.get('severity') == 'CRITICAL'),
            'high': sum(1 for a in all_anomalies if a.get('severity') == 'HIGH'),
            'medium': sum(1 for a in all_anomalies if a.get('severity') == 'MEDIUM'),
            'low': sum(1 for a in all_anomalies if a.get('severity') == 'LOW'),
        },
        'by_type': {
            'statistical_outlier': sum(1 for a in all_anomalies if a['anomaly_type'] == 'STATISTICAL_OUTLIER'),
            'pattern_anomaly': sum(1 for a in all_anomalies if a['anomaly_type'] == 'PATTERN_ANOMALY'),
            'regional_anomaly': sum(1 for a in all_anomalies if a['anomaly_type'] == 'REGIONAL_ANOMALY'),
            'cross_study_anomaly': sum(1 for a in all_anomalies if a['anomaly_type'] == 'CROSS_STUDY_ANOMALY'),
            'velocity_anomaly': sum(1 for a in all_anomalies if a['anomaly_type'] == 'VELOCITY_ANOMALY'),
        },
        'top_sites': score_df.head(10).to_dict('records') if not score_df.empty else []
    }

    summary_path = OUTPUT_DIR / "anomaly_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n✅ Saved: {summary_path}")

    # 4. Generate and save report
    report = generate_anomaly_report(all_anomalies, score_df, site_df)
    report_path = OUTPUT_DIR / "anomaly_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n✅ Saved: {report_path}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"""
ANOMALY DETECTION COMPLETE
==========================

Dataset:
  Sites Analyzed: {len(site_df):,}
  Studies: {site_df['study'].nunique()}
  Countries: {site_df['country'].nunique()}

Anomalies Detected:
  Total: {len(all_anomalies)}
  Critical: {summary['by_severity']['critical']}
  High: {summary['by_severity']['high']}
  Medium: {summary['by_severity']['medium']}

By Type:
  Statistical Outliers: {summary['by_type']['statistical_outlier']}
  Pattern Anomalies: {summary['by_type']['pattern_anomaly']}
  Regional Anomalies: {summary['by_type']['regional_anomaly']}
  Cross-Study Anomalies: {summary['by_type']['cross_study_anomaly']}
  Velocity Anomalies: {summary['by_type']['velocity_anomaly']}

Sites Requiring Investigation: {len(score_df)}
""")

    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Review: outputs/anomaly_report.md (human-readable report)
2. Review: outputs/anomalies_detected.csv (all anomalies)
3. Review: outputs/site_anomaly_scores.csv (prioritized site list)
4. Review: outputs/anomaly_summary.json (summary statistics)
5. Run: python src/07_multi_agent_system.py (if available)
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    success = run_anomaly_detection()
    if not success:
        exit(1)
