"""
Javelin.AI - Phase 06: Anomaly Detection
==============================================================

Detects anomalies and unusual patterns in site-level data quality metrics
using statistical methods and pattern recognition.

Prerequisites:
    - Run 03_calculate_dqi.py first
    - outputs/phase03/master_*_with_dqi.csv files must exist

Usage:
    python src/phases/06_anomaly_detection.py

Output:
    - outputs/phase06/anomalies_detected.csv            # All detected anomalies
    - outputs/phase06/site_anomaly_scores.csv           # Sites ranked by anomaly score
    - outputs/phase06/anomaly_summary.json              # Statistics and metadata
    - outputs/phase06/anomaly_report.md                 # Human-readable report

Anomaly Types:
    - Statistical Outliers: Z-score based detection
    - Pattern Anomalies: Unusual issue combinations
    - Regional Anomalies: Geographic deviations
    - Cross-Study Anomalies: Comparative patterns
    - Velocity Anomalies: Concentration patterns

Severity Levels:
    - CRITICAL: Immediate action required
    - HIGH: Priority investigation
    - MEDIUM: Monitor closely
    - LOW: Awareness only
"""

import sys
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
# PATH SETUP - Add src directory to path for config import
# ============================================================================

_SCRIPT_DIR = Path(__file__).parent.resolve()
_SRC_DIR = _SCRIPT_DIR.parent if _SCRIPT_DIR.name == 'phases' else _SCRIPT_DIR
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# ============================================================================
# CONFIGURATION - Import from config.py or use local fallbacks
# ============================================================================

try:
    from config import PROJECT_ROOT, OUTPUT_DIR, PHASE_DIRS
    _USING_CONFIG = True
except ImportError:
    _USING_CONFIG = False
    PROJECT_ROOT = _SRC_DIR.parent
    OUTPUT_DIR = PROJECT_ROOT / "outputs"
    # Fallback: flat structure
    PHASE_DIRS = {f'phase_{i:02d}': OUTPUT_DIR for i in range(10)}

# Phase-specific directories
PHASE_03_DIR = PHASE_DIRS.get('phase_03', OUTPUT_DIR)
PHASE_06_DIR = PHASE_DIRS.get('phase_06', OUTPUT_DIR)

# Input files from Phase 03
SUBJECT_DQI_PATH = PHASE_03_DIR / "master_subject_with_dqi.csv"
SITE_DQI_PATH = PHASE_03_DIR / "master_site_with_dqi.csv"
STUDY_DQI_PATH = PHASE_03_DIR / "master_study_with_dqi.csv"
REGION_DQI_PATH = PHASE_03_DIR / "master_region_with_dqi.csv"
COUNTRY_DQI_PATH = PHASE_03_DIR / "master_country_with_dqi.csv"

# Anomaly Detection Thresholds (v2.0 - tightened)
THRESHOLDS = {
    # Statistical outlier thresholds (tightened to reduce noise)
    'zscore_threshold': 3.0,          # Was 2.5 - now only significant outliers
    'zscore_critical': 4.0,           # New - for critical classification
    'zscore_extreme': 5.0,            # New - for extreme outliers
    'iqr_multiplier': 2.0,            # Was 1.5 - tightened
    'extreme_iqr_multiplier': 3.0,    # Extreme outlier threshold

    # Pattern anomaly thresholds
    'sae_not_flagged_threshold': 3,   # SAE count to trigger pattern check
    'zero_issues_subject_threshold': 30,  # Subjects to check zero-issue pattern
    'stale_days_threshold': 45,       # Days for stale data (was 60)
    'stale_issues_threshold': 5,      # Minimum issues to be considered stale
    'majority_high_risk_pct': 40,     # Was 50% - now catches more
    'single_issue_dominance_pct': 0.75,  # Was 0.8 - catches more
    'min_issues_for_dominance': 15,   # Was 20 - catches more

    # Regional anomaly thresholds (adjusted to find patterns)
    'regional_zscore_threshold': 1.5, # Was 2.0 - lowered to catch more
    'min_sites_per_region': 5,        # Was 3 - need more for statistical validity
    'min_sites_per_country': 3,       # Was 2 - need more sites
    'high_risk_rate_threshold': 0.25, # 25% high risk rate is anomalous

    # Cross-study thresholds
    'cross_study_min_studies': 2,     # Minimum studies to appear in
    'cross_study_high_risk_pct': 0.4, # 40% high risk across studies

    # Velocity/density thresholds
    'issue_density_zscore': 2.5,      # Z-score for density
    'concentration_threshold': 0.5,   # Was 0.7 - 50% of study issues
    'min_study_issues': 50,           # Minimum issues for concentration check
}

# Issue columns at site level (for statistical analysis)
# EXCLUDING avg_dqi_score - it's redundant with the DQI system
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

# Columns to analyze for statistical outliers (non-redundant with DQI)
STATISTICAL_OUTLIER_COLUMNS = [
    # Issue counts - these are interesting outliers
    'sae_pending_count_sum',
    'missing_visit_count_sum',
    'lab_issues_count_sum',
    'max_days_outstanding_sum',
    'max_days_page_missing_sum',
    'edrr_open_issues_sum',
    # Structural outliers
    'subject_count',
    'high_risk_count',
]

# Anomaly severity levels
SEVERITY_LEVELS = {
    'CRITICAL': 4,
    'HIGH': 3,
    'MEDIUM': 2,
    'LOW': 1
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_zscore(series: pd.Series) -> pd.Series:
    """Calculate z-scores for a series."""
    mean = series.mean()
    std = series.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0, index=series.index)
    return (series - mean) / std


def get_severity_from_zscore(zscore: float) -> str:
    """Determine severity based on z-score magnitude."""
    abs_z = abs(zscore)
    if abs_z >= THRESHOLDS['zscore_extreme']:
        return 'CRITICAL'
    elif abs_z >= THRESHOLDS['zscore_critical']:
        return 'HIGH'
    elif abs_z >= THRESHOLDS['zscore_threshold']:
        return 'MEDIUM'
    else:
        return 'LOW'


# ============================================================================
# STATISTICAL ANOMALY DETECTION (v2.0 - Focused)
# ============================================================================

def detect_statistical_outliers(df: pd.DataFrame) -> List[Dict]:
    """
    Detect statistical outliers using z-score method.

    v2.0 Changes:
    - Tighter thresholds (z >= 3.0)
    - Focus on issue counts, NOT DQI score (redundant)
    - Better severity classification

    Args:
        df: Site-level DataFrame

    Returns:
        List of anomaly dictionaries
    """
    anomalies = []

    # Only analyze specific columns (excluding avg_dqi_score - it's redundant)
    for col in STATISTICAL_OUTLIER_COLUMNS:
        if col not in df.columns:
            continue

        series = df[col].fillna(0)

        # Skip if no variance or all zeros
        if series.std() == 0 or series.max() == 0:
            continue

        # Calculate z-scores
        zscores = calculate_zscore(series)

        # Find outliers (z >= threshold AND positive - we care about HIGH values)
        # For most metrics, only high values are concerning
        outlier_mask = zscores >= THRESHOLDS['zscore_threshold']
        outliers = df[outlier_mask]

        for idx, row in outliers.iterrows():
            z = zscores[idx]
            severity = get_severity_from_zscore(z)

            # Format the metric name for readability
            metric_name = col.replace('_sum', '').replace('_', ' ').title()

            anomalies.append({
                'anomaly_type': 'STATISTICAL_OUTLIER',
                'detection_method': 'Z-Score',
                'level': 'site',
                'study': row.get('study', 'Unknown'),
                'site_id': row.get('site_id', 'Unknown'),
                'country': row.get('country', 'Unknown'),
                'region': row.get('region', 'Unknown'),
                'metric': col,
                'value': float(row[col]),
                'zscore': round(z, 2),
                'mean': round(series.mean(), 2),
                'std': round(series.std(), 2),
                'severity': severity,
                'description': f"{metric_name} is {z:.1f}σ above average ({row[col]:.0f} vs mean {series.mean():.1f})",
                'recommendation': f"Investigate elevated {metric_name.lower()} at this site"
            })

    return anomalies


# ============================================================================
# PATTERN ANOMALY DETECTION (v2.0 - More Patterns)
# ============================================================================

def detect_pattern_anomalies(df: pd.DataFrame) -> List[Dict]:
    """
    Detect unusual patterns/combinations of issues.

    v2.0 Patterns:
    1. SAE_NOT_FLAGGED - High SAE but site not High risk (CRITICAL)
    2. ZERO_ISSUES_HIGH_VOLUME - Many subjects but no issues (suspicious)
    3. STALE_MISSING_DATA - Missing data outstanding too long
    4. MAJORITY_HIGH_RISK - Most subjects at site are high risk
    5. SINGLE_ISSUE_DOMINANCE - One issue type dominates
    6. HIGH_SAE_LOW_MEDDRA - SAE pending but no uncoded MedDRA (unusual)

    Args:
        df: Site-level DataFrame

    Returns:
        List of anomaly dictionaries
    """
    anomalies = []

    for idx, row in df.iterrows():
        site_anomalies = []

        # Get values with defaults
        sae = row.get('sae_pending_count_sum', 0) or 0
        meddra = row.get('uncoded_meddra_count_sum', 0) or 0
        missing_visits = row.get('missing_visit_count_sum', 0) or 0
        missing_pages = row.get('missing_pages_count_sum', 0) or 0
        lab_issues = row.get('lab_issues_count_sum', 0) or 0
        inactivated = row.get('inactivated_forms_count_sum', 0) or 0
        subjects = row.get('subject_count', 1) or 1
        dqi = row.get('avg_dqi_score', 0) or 0
        high_risk = row.get('high_risk_count', 0) or 0
        max_days = row.get('max_days_outstanding_sum', 0) or 0
        max_page_days = row.get('max_days_page_missing_sum', 0) or 0
        site_risk = row.get('site_risk_category', 'Unknown')

        # Pattern 1: SAE_NOT_FLAGGED (CRITICAL)
        # Site has pending SAE but isn't flagged as High risk
        if sae >= THRESHOLDS['sae_not_flagged_threshold'] and site_risk != 'High':
            site_anomalies.append({
                'pattern': 'SAE_NOT_FLAGGED',
                'severity': 'CRITICAL',
                'description': f"Site has {sae} pending SAE reviews but is classified as '{site_risk}' risk (should be High)",
                'recommendation': "URGENT: Review site risk classification - pending SAE should trigger High risk"
            })

        # Pattern 2: ZERO_ISSUES_HIGH_VOLUME (MEDIUM - suspicious)
        if subjects >= THRESHOLDS['zero_issues_subject_threshold'] and dqi == 0:
            site_anomalies.append({
                'pattern': 'ZERO_ISSUES_HIGH_VOLUME',
                'severity': 'MEDIUM',
                'description': f"Site has {subjects} subjects but zero DQI issues - verify data completeness",
                'recommendation': "Verify all data sources are being captured for this site"
            })

        # Pattern 3: STALE_MISSING_DATA (HIGH)
        total_missing = missing_visits + missing_pages
        max_outstanding = max(max_days, max_page_days)
        if total_missing >= THRESHOLDS['stale_issues_threshold'] and max_outstanding >= THRESHOLDS['stale_days_threshold']:
            site_anomalies.append({
                'pattern': 'STALE_MISSING_DATA',
                'severity': 'HIGH',
                'description': f"Site has {total_missing} missing items outstanding for {max_outstanding:.0f}+ days",
                'recommendation': "Escalate to site - missing data not being resolved in timely manner"
            })

        # Pattern 4: MAJORITY_HIGH_RISK (HIGH)
        high_risk_pct = (high_risk / subjects * 100) if subjects > 0 else 0
        if subjects >= 10 and high_risk_pct >= THRESHOLDS['majority_high_risk_pct']:
            site_anomalies.append({
                'pattern': 'MAJORITY_HIGH_RISK',
                'severity': 'HIGH',
                'description': f"{high_risk_pct:.0f}% of subjects ({high_risk}/{subjects}) are high risk - systemic issue",
                'recommendation': "Site-wide quality intervention needed - majority of subjects have issues"
            })

        # Pattern 5: SINGLE_ISSUE_DOMINANCE (MEDIUM)
        issue_counts = {
            'SAE Pending': sae,
            'Missing Visits': missing_visits,
            'Missing Pages': missing_pages,
            'Lab Issues': lab_issues,
            'Inactivated Forms': inactivated
        }
        total_issues = sum(issue_counts.values())

        if total_issues >= THRESHOLDS['min_issues_for_dominance']:
            for issue_type, count in issue_counts.items():
                if count / total_issues >= THRESHOLDS['single_issue_dominance_pct']:
                    site_anomalies.append({
                        'pattern': 'SINGLE_ISSUE_DOMINANCE',
                        'severity': 'MEDIUM',
                        'description': f"{issue_type} represents {count/total_issues*100:.0f}% of all issues ({count}/{total_issues})",
                        'recommendation': f"Focus intervention specifically on {issue_type.lower()} - appears to be root cause"
                    })
                    break  # Only report one dominant issue per site

        # Pattern 6: HIGH_SAE_LOW_MEDDRA (MEDIUM - unusual pattern)
        # If site has many SAE pending but no uncoded MedDRA, that's unusual
        # (SAE should generate adverse event terms needing coding)
        if sae >= 5 and meddra == 0:
            site_anomalies.append({
                'pattern': 'SAE_WITHOUT_CODING',
                'severity': 'MEDIUM',
                'description': f"Site has {sae} pending SAE but 0 uncoded MedDRA terms - verify coding workflow",
                'recommendation': "Check if SAE adverse event terms are being routed to coding team"
            })

        # Add all site anomalies
        for anomaly in site_anomalies:
            anomalies.append({
                'anomaly_type': 'PATTERN_ANOMALY',
                'detection_method': anomaly['pattern'],
                'level': 'site',
                'study': row.get('study', 'Unknown'),
                'site_id': row.get('site_id', 'Unknown'),
                'country': row.get('country', 'Unknown'),
                'region': row.get('region', 'Unknown'),
                'metric': anomaly['pattern'],
                'value': None,
                'zscore': None,
                'severity': anomaly['severity'],
                'description': anomaly['description'],
                'recommendation': anomaly['recommendation']
            })

    return anomalies


# ============================================================================
# REGIONAL ANOMALY DETECTION (v2.0 - Fixed)
# ============================================================================

def detect_regional_anomalies(df: pd.DataFrame, region_df: pd.DataFrame = None, country_df: pd.DataFrame = None) -> List[Dict]:
    """
    Detect countries/regions with unusual data quality patterns.

    v2.0 Fixes:
    - Use high_risk_rate instead of raw DQI for comparison
    - Properly handle NaN/missing regions
    - Add issue-specific regional comparisons

    v3.0 Enhancement:
    - Optionally use pre-computed region/country data for consistency

    Args:
        df: Site-level DataFrame
        region_df: Pre-computed region-level data (optional)
        country_df: Pre-computed country-level data (optional)

    Returns:
        List of anomaly dictionaries
    """
    anomalies = []

    # Need high_risk_rate column
    if 'high_risk_rate' not in df.columns:
        if 'high_risk_count' in df.columns and 'subject_count' in df.columns:
            df = df.copy()
            df['high_risk_rate'] = df['high_risk_count'] / df['subject_count'].replace(0, 1)
        else:
            return anomalies

    # Clean up region/country data
    df_clean = df.copy()
    df_clean['region'] = df_clean['region'].fillna('Unknown').replace('', 'Unknown')
    df_clean['country'] = df_clean['country'].fillna('Unknown').replace('', 'Unknown')

    # Calculate portfolio-wide statistics
    portfolio_mean_dqi = df_clean['avg_dqi_score'].mean()
    portfolio_std_dqi = df_clean['avg_dqi_score'].std()
    portfolio_mean_risk_rate = df_clean['high_risk_rate'].mean()
    portfolio_std_risk_rate = df_clean['high_risk_rate'].std()

    # -------------------------------------------------------------------------
    # COUNTRY-LEVEL ANALYSIS
    # -------------------------------------------------------------------------
    if country_df is not None and len(country_df) > 0:
        # Use pre-computed country data
        country_stats = country_df.copy()
        country_stats = country_stats.rename(columns={
            'avg_dqi_score': 'country_mean_dqi',
            'high_risk_rate': 'country_mean_risk_rate',
            'high_risk_subjects': 'country_high_risk',
            'subject_count': 'country_subjects'
        })
        country_stats = country_stats[country_stats['site_count'] >= THRESHOLDS['min_sites_per_country']]
    else:
        # Compute from site data (original logic)
        country_stats = df_clean.groupby(['country', 'region']).agg({
            'avg_dqi_score': 'mean',
            'high_risk_rate': 'mean',
            'high_risk_count': 'sum',
            'subject_count': 'sum',
            'site_id': 'count'
        }).reset_index()
        country_stats.columns = ['country', 'region', 'country_mean_dqi', 'country_mean_risk_rate',
                                 'country_high_risk', 'country_subjects', 'site_count']
        country_stats = country_stats[country_stats['site_count'] >= THRESHOLDS['min_sites_per_country']]

    for idx, row in country_stats.iterrows():
        # Calculate z-scores vs portfolio
        if portfolio_std_dqi > 0:
            dqi_zscore = (row['country_mean_dqi'] - portfolio_mean_dqi) / portfolio_std_dqi
        else:
            dqi_zscore = 0

        if portfolio_std_risk_rate > 0:
            risk_zscore = (row['country_mean_risk_rate'] - portfolio_mean_risk_rate) / portfolio_std_risk_rate
        else:
            risk_zscore = 0

        # Flag countries with high DQI or high risk rate
        if dqi_zscore >= THRESHOLDS['regional_zscore_threshold']:
            severity = 'HIGH' if dqi_zscore >= 2.5 else 'MEDIUM'
            anomalies.append({
                'anomaly_type': 'REGIONAL_ANOMALY',
                'detection_method': 'COUNTRY_HIGH_DQI',
                'level': 'country',
                'study': 'Portfolio',
                'site_id': f"{row['country']} ({int(row['site_count'])} sites)",
                'country': row['country'],
                'region': row['region'],
                'metric': 'country_avg_dqi',
                'value': round(row['country_mean_dqi'], 4),
                'zscore': round(dqi_zscore, 2),
                'severity': severity,
                'description': f"{row['country']} average DQI ({row['country_mean_dqi']:.3f}) is {dqi_zscore:.1f}σ above portfolio average ({portfolio_mean_dqi:.3f})",
                'recommendation': f"Country-wide review for {row['country']} - elevated data quality issues across {int(row['site_count'])} sites"
            })

        # Flag countries with high risk rate
        if row['country_mean_risk_rate'] >= THRESHOLDS['high_risk_rate_threshold']:
            actual_rate = row['country_mean_risk_rate'] * 100
            anomalies.append({
                'anomaly_type': 'REGIONAL_ANOMALY',
                'detection_method': 'COUNTRY_HIGH_RISK_RATE',
                'level': 'country',
                'study': 'Portfolio',
                'site_id': f"{row['country']} ({row['site_count']} sites)",
                'country': row['country'],
                'region': row['region'],
                'metric': 'high_risk_rate',
                'value': round(row['country_mean_risk_rate'], 4),
                'zscore': round(risk_zscore, 2),
                'severity': 'HIGH',
                'description': f"{row['country']} has {actual_rate:.1f}% high-risk subject rate ({int(row['country_high_risk'])}/{int(row['country_subjects'])} subjects)",
                'recommendation': f"Prioritize {row['country']} for regional training and site support"
            })

    # -------------------------------------------------------------------------
    # REGION-LEVEL ANALYSIS
    # -------------------------------------------------------------------------
    if region_df is not None and len(region_df) > 0:
        # Use pre-computed region data
        region_stats = region_df.copy()
        region_stats = region_stats.rename(columns={
            'avg_dqi_score': 'region_mean_dqi',
            'high_risk_rate': 'region_mean_risk_rate',
            'high_risk_subjects': 'region_high_risk',
            'subject_count': 'region_subjects'
        })
        region_stats = region_stats[region_stats['site_count'] >= THRESHOLDS['min_sites_per_region']]
    else:
        # Compute from site data (original logic)
        region_stats = df_clean.groupby('region').agg({
            'avg_dqi_score': 'mean',
            'high_risk_rate': 'mean',
            'high_risk_count': 'sum',
            'subject_count': 'sum',
            'site_id': 'count'
        }).reset_index()
        region_stats.columns = ['region', 'region_mean_dqi', 'region_mean_risk_rate',
                                'region_high_risk', 'region_subjects', 'site_count']
        region_stats = region_stats[region_stats['site_count'] >= THRESHOLDS['min_sites_per_region']]

    # Compare regions to each other
    if len(region_stats) >= 2:
        region_dqi_mean = region_stats['region_mean_dqi'].mean()
        region_dqi_std = region_stats['region_mean_dqi'].std()

        for idx, row in region_stats.iterrows():
            if region_dqi_std > 0:
                region_zscore = (row['region_mean_dqi'] - region_dqi_mean) / region_dqi_std
            else:
                region_zscore = 0

            if abs(region_zscore) >= 1.0:  # Lower threshold for region comparison
                direction = 'above' if region_zscore > 0 else 'below'
                severity = 'HIGH' if region_zscore > 0 else 'MEDIUM'  # Above average is worse

                anomalies.append({
                    'anomaly_type': 'REGIONAL_ANOMALY',
                    'detection_method': 'REGION_COMPARISON',
                    'level': 'region',
                    'study': 'Portfolio',
                    'site_id': f"{row['region']} ({int(row['site_count'])} sites)",
                    'country': 'Multiple',
                    'region': row['region'],
                    'metric': 'region_avg_dqi',
                    'value': round(row['region_mean_dqi'], 4),
                    'zscore': round(region_zscore, 2),
                    'severity': severity,
                    'description': f"{row['region']} region DQI ({row['region_mean_dqi']:.3f}) is {abs(region_zscore):.1f}σ {direction} other regions",
                    'recommendation': f"Regional strategy review for {row['region']}"
                })

    return anomalies


# ============================================================================
# CROSS-STUDY ANOMALY DETECTION (v2.0 - Enhanced)
# ============================================================================

def detect_cross_study_anomalies(df: pd.DataFrame) -> List[Dict]:
    """
    Detect sites that are problematic across multiple studies.

    v2.0 Enhancements:
    - Identify "repeat offender" sites
    - Track which studies each site is high-risk in
    - Calculate cross-study risk consistency

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
        'study': list,
        'site_risk_category': list,
        'avg_dqi_score': 'mean',
        'high_risk_count': 'sum',
        'subject_count': 'sum',
        'country': 'first',
        'region': 'first'
    }).reset_index()

    site_studies['num_studies'] = site_studies['study'].apply(len)

    # Filter to sites in multiple studies
    multi_study_sites = site_studies[site_studies['num_studies'] >= THRESHOLDS['cross_study_min_studies']]

    for idx, row in multi_study_sites.iterrows():
        studies = row['study']
        risk_categories = row['site_risk_category']
        num_studies = len(studies)

        # Count how many studies the site is High risk in
        high_risk_studies = [s for s, r in zip(studies, risk_categories) if r == 'High']
        num_high_risk = len(high_risk_studies)
        high_risk_pct = num_high_risk / num_studies

        # Pattern 1: High risk in majority of studies (REPEAT OFFENDER)
        if high_risk_pct >= THRESHOLDS['cross_study_high_risk_pct']:
            severity = 'CRITICAL' if num_high_risk == num_studies else 'HIGH'

            anomalies.append({
                'anomaly_type': 'CROSS_STUDY_ANOMALY',
                'detection_method': 'REPEAT_OFFENDER',
                'level': 'site',
                'study': ', '.join(studies),
                'site_id': row['site_id'],
                'country': row['country'],
                'region': row['region'],
                'metric': 'cross_study_high_risk',
                'value': num_high_risk,
                'zscore': None,
                'severity': severity,
                'description': f"Site is high risk in {num_high_risk}/{num_studies} studies: {', '.join(high_risk_studies)}",
                'recommendation': "Cross-program site review - consistent quality issues across multiple studies"
            })

        # Pattern 2: High average DQI across studies
        if row['avg_dqi_score'] >= 0.2 and num_studies >= 2:
            # Only flag if not already caught as repeat offender
            if high_risk_pct < THRESHOLDS['cross_study_high_risk_pct']:
                anomalies.append({
                    'anomaly_type': 'CROSS_STUDY_ANOMALY',
                    'detection_method': 'ELEVATED_DQI_MULTI_STUDY',
                    'level': 'site',
                    'study': ', '.join(studies),
                    'site_id': row['site_id'],
                    'country': row['country'],
                    'region': row['region'],
                    'metric': 'avg_dqi_across_studies',
                    'value': round(row['avg_dqi_score'], 3),
                    'zscore': None,
                    'severity': 'MEDIUM',
                    'description': f"Site has elevated average DQI ({row['avg_dqi_score']:.3f}) across {num_studies} studies",
                    'recommendation': "Monitor site performance across programs"
                })

    return anomalies


# ============================================================================
# VELOCITY/CONCENTRATION ANOMALY DETECTION
# ============================================================================

def detect_velocity_anomalies(df: pd.DataFrame) -> List[Dict]:
    """
    Detect unusual concentration or density of issues.

    v2.0:
    - Issue density per subject
    - Single site dominating study issues
    - Concentration analysis

    Args:
        df: Site-level DataFrame

    Returns:
        List of anomaly dictionaries
    """
    anomalies = []

    # Calculate total issues per site
    issue_cols = [col for col in ISSUE_COLUMNS_SITE if col in df.columns]

    if not issue_cols or 'subject_count' not in df.columns:
        return anomalies

    df = df.copy()
    df['total_issues'] = df[issue_cols].fillna(0).sum(axis=1)
    df['issue_density'] = df['total_issues'] / df['subject_count'].replace(0, 1)

    # -------------------------------------------------------------------------
    # HIGH ISSUE DENSITY DETECTION
    # -------------------------------------------------------------------------
    density_mean = df['issue_density'].mean()
    density_std = df['issue_density'].std()

    if density_std > 0:
        df['density_zscore'] = (df['issue_density'] - density_mean) / density_std

        # Find high density sites
        high_density = df[df['density_zscore'] >= THRESHOLDS['issue_density_zscore']]

        for idx, row in high_density.iterrows():
            if row['subject_count'] < 5:  # Skip tiny sites
                continue

            severity = 'HIGH' if row['density_zscore'] >= 3.5 else 'MEDIUM'

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
                'zscore': round(row['density_zscore'], 2),
                'severity': severity,
                'description': f"Site has {row['issue_density']:.1f} issues per subject ({row['total_issues']:.0f} issues / {row['subject_count']} subjects)",
                'recommendation': "High issue concentration - prioritize for intervention"
            })

    # -------------------------------------------------------------------------
    # STUDY CONCENTRATION DETECTION
    # -------------------------------------------------------------------------
    if 'study' in df.columns:
        for study in df['study'].unique():
            study_df = df[df['study'] == study]
            study_total = study_df['total_issues'].sum()

            if study_total < THRESHOLDS['min_study_issues']:
                continue

            for idx, row in study_df.iterrows():
                site_pct = row['total_issues'] / study_total if study_total > 0 else 0

                if site_pct >= THRESHOLDS['concentration_threshold']:
                    anomalies.append({
                        'anomaly_type': 'VELOCITY_ANOMALY',
                        'detection_method': 'STUDY_CONCENTRATION',
                        'level': 'site',
                        'study': study,
                        'site_id': row.get('site_id', 'Unknown'),
                        'country': row.get('country', 'Unknown'),
                        'region': row.get('region', 'Unknown'),
                        'metric': 'study_issue_pct',
                        'value': round(site_pct, 3),
                        'zscore': None,
                        'severity': 'HIGH',
                        'description': f"Site accounts for {site_pct*100:.0f}% of all {study} issues ({row['total_issues']:.0f}/{study_total:.0f})",
                        'recommendation': f"Critical - single site driving majority of {study} data quality issues"
                    })

    return anomalies


# ============================================================================
# ANOMALY SCORING & AGGREGATION
# ============================================================================

def calculate_anomaly_score(anomalies: List[Dict], df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate composite anomaly score for each site.
    """
    site_scores = defaultdict(lambda: {
        'anomaly_count': 0,
        'critical_count': 0,
        'high_count': 0,
        'medium_count': 0,
        'low_count': 0,
        'anomaly_types': set(),
        'anomalies': []
    })

    for anomaly in anomalies:
        if anomaly['level'] not in ['site']:
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

    rows = []
    for (study, site_id), data in site_scores.items():
        weighted_score = (
            data['critical_count'] * 4 +
            data['high_count'] * 3 +
            data['medium_count'] * 2 +
            data['low_count'] * 1
        )

        type_diversity = len(data['anomaly_types'])
        max_possible = data['anomaly_count'] * 4
        anomaly_score = weighted_score / max_possible if max_possible > 0 else 0
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

    # Count by severity
    critical_count = sum(1 for a in anomalies if a.get('severity') == 'CRITICAL')
    high_count = sum(1 for a in anomalies if a.get('severity') == 'HIGH')
    medium_count = sum(1 for a in anomalies if a.get('severity') == 'MEDIUM')

    report = f"""# JAVELIN.AI - Anomaly Detection Report

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Anomalies Detected | {len(anomalies)} |
| Sites with Anomalies | {len(score_df)} |
| Critical Anomalies | {critical_count} |
| High Severity Anomalies | {high_count} |
| Medium Severity Anomalies | {medium_count} |

---

## Anomaly Distribution by Type

"""

    type_counts = defaultdict(int)
    for a in anomalies:
        type_counts[a['anomaly_type']] += 1

    for atype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        report += f"- **{atype}**: {count} anomalies\n"

    # Pattern breakdown
    report += "\n### Pattern Anomaly Breakdown\n\n"
    pattern_counts = defaultdict(int)
    for a in anomalies:
        if a['anomaly_type'] == 'PATTERN_ANOMALY':
            pattern_counts[a['detection_method']] += 1

    for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        report += f"- {pattern}: {count}\n"

    report += """

---

## Top 15 Sites by Anomaly Score

| Rank | Study | Site ID | Country | Score | Anomalies | Critical | High | Types |
|------|-------|---------|---------|-------|-----------|----------|------|-------|
"""

    for i, (idx, row) in enumerate(score_df.head(15).iterrows(), 1):
        study_short = row['study'][:20] + '...' if len(str(row['study'])) > 20 else row['study']
        report += f"| {i} | {study_short} | {row['site_id']} | - | {row['anomaly_score']:.3f} | {row['anomaly_count']} | {row['critical_count']} | {row['high_count']} | {row['type_diversity']} |\n"

    report += """

---

## Critical Anomalies (Immediate Action Required)

"""

    critical = [a for a in anomalies if a.get('severity') == 'CRITICAL']
    if critical:
        for i, a in enumerate(critical[:25], 1):
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

## Cross-Study Anomalies (Repeat Offender Sites)

"""

    cross_study = [a for a in anomalies if a['anomaly_type'] == 'CROSS_STUDY_ANOMALY']
    if cross_study:
        for a in cross_study:
            report += f"- **{a['site_id']}** ({a['country']}): {a['description']}\n"
    else:
        report += "*No cross-study anomalies detected.*\n"

    report += """

---

## Recommendations Summary

Based on the anomaly analysis, key actions:

"""

    # Prioritized recommendations
    recs_by_severity = defaultdict(set)
    for a in anomalies:
        if a.get('recommendation'):
            recs_by_severity[a['severity']].add(a['recommendation'])

    for severity in ['CRITICAL', 'HIGH', 'MEDIUM']:
        if recs_by_severity[severity]:
            report += f"\n### {severity} Priority\n\n"
            for rec in list(recs_by_severity[severity])[:5]:
                report += f"- {rec}\n"

    report += """

---

*Report generated by JAVELIN.AI Anomaly Detection Engine v2.0*
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
    print(f"Input Directory: {PHASE_03_DIR}")
    print(f"Output Directory: {PHASE_06_DIR}")
    if _USING_CONFIG:
        print("(Using centralized config)")

    # =========================================================================
    # Step 1: Load Data
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: LOAD DATA")
    print("=" * 70)

    if not SITE_DQI_PATH.exists():
        print(f"\n[ERROR] Site DQI file not found: {SITE_DQI_PATH}")
        print("   Please run 03_calculate_dqi.py first")
        return False

    site_df = pd.read_csv(SITE_DQI_PATH)
    print(f"\n[OK] Loaded site data: {len(site_df):,} sites")

    subject_df = None
    if SUBJECT_DQI_PATH.exists():
        subject_df = pd.read_csv(SUBJECT_DQI_PATH)
        print(f"[OK] Loaded subject data: {len(subject_df):,} subjects")

    # Load pre-computed aggregated data (optional - enhances regional analysis)
    study_df = None
    region_df = None
    country_df = None

    if STUDY_DQI_PATH.exists():
        study_df = pd.read_csv(STUDY_DQI_PATH)
        print(f"[OK] Loaded study data: {len(study_df)} studies (pre-computed)")

    if REGION_DQI_PATH.exists():
        region_df = pd.read_csv(REGION_DQI_PATH)
        print(f"[OK] Loaded region data: {len(region_df)} regions (pre-computed)")

    if COUNTRY_DQI_PATH.exists():
        country_df = pd.read_csv(COUNTRY_DQI_PATH)
        print(f"[OK] Loaded country data: {len(country_df)} countries (pre-computed)")

    print(f"\nStudies: {site_df['study'].nunique()}")
    print(f"Countries: {site_df['country'].nunique()}")
    print(f"Regions: {site_df['region'].nunique()}")

    # =========================================================================
    # Step 2: Detect Statistical Outliers
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: DETECT STATISTICAL OUTLIERS (z >= 3.0)")
    print("=" * 70)

    stat_anomalies = detect_statistical_outliers(site_df)
    print(f"\n[OK] Detected {len(stat_anomalies)} statistical outliers")

    for sev in ['CRITICAL', 'HIGH', 'MEDIUM']:
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
    print(f"\n[OK] Detected {len(pattern_anomalies)} pattern anomalies")

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

    regional_anomalies = detect_regional_anomalies(site_df, region_df, country_df)
    print(f"\n[OK] Detected {len(regional_anomalies)} regional anomalies")

    for a in regional_anomalies[:5]:
        print(f"   * {a['country']} ({a['region']}): {a['description'][:60]}...")

    # =========================================================================
    # Step 5: Detect Cross-Study Anomalies
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 5: DETECT CROSS-STUDY ANOMALIES")
    print("=" * 70)

    cross_study_anomalies = detect_cross_study_anomalies(site_df)
    print(f"\n[OK] Detected {len(cross_study_anomalies)} cross-study anomalies")

    for a in cross_study_anomalies[:5]:
        print(f"   * {a['site_id']}: {a['description'][:60]}...")

    # =========================================================================
    # Step 6: Detect Velocity/Concentration Anomalies
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 6: DETECT VELOCITY ANOMALIES")
    print("=" * 70)

    velocity_anomalies = detect_velocity_anomalies(site_df)
    print(f"\n[OK] Detected {len(velocity_anomalies)} velocity/concentration anomalies")

    # =========================================================================
    # Step 7: Aggregate & Score
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 7: AGGREGATE & SCORE")
    print("=" * 70)

    all_anomalies = (
        stat_anomalies +
        pattern_anomalies +
        regional_anomalies +
        cross_study_anomalies +
        velocity_anomalies
    )

    print(f"\n[INFO] Total Anomalies Detected: {len(all_anomalies)}")

    score_df = calculate_anomaly_score(all_anomalies, site_df)
    print(f"   Sites with Anomalies: {len(score_df)}")

    if not score_df.empty:
        print(f"\nTop 5 Sites by Anomaly Score:")
        for i, (idx, row) in enumerate(score_df.head(5).iterrows(), 1):
            print(f"   {i}. {row['study'][:30]} - {row['site_id']}: Score {row['anomaly_score']:.3f} ({row['anomaly_count']} anomalies, {row['critical_count']} critical)")

    # =========================================================================
    # Step 8: Save Outputs
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 8: SAVE OUTPUTS")
    print("=" * 70)

    PHASE_06_DIR.mkdir(parents=True, exist_ok=True)

    # Save all anomalies
    anomalies_df = pd.DataFrame(all_anomalies)
    anomalies_path = PHASE_06_DIR / "anomalies_detected.csv"
    anomalies_df.to_csv(anomalies_path, index=False)
    print(f"\n[OK] Saved: {anomalies_path}")
    print(f"   {len(anomalies_df)} anomalies")

    # Save site scores
    if 'anomaly_score' in score_df.columns and len(score_df) > 0:
        score_df['is_anomaly'] = score_df['anomaly_score'] > 0
    else:
        score_df['is_anomaly'] = False
    scores_path = PHASE_06_DIR / "site_anomaly_scores.csv"
    score_df.to_csv(scores_path, index=False)
    print(f"\n[OK] Saved: {scores_path}")
    print(f"   {len(score_df)} sites scored")

    # Save summary
    summary = {
        'generated_at': datetime.now().isoformat(),
        'version': '2.0',
        'thresholds': {
            'zscore': THRESHOLDS['zscore_threshold'],
            'zscore_critical': THRESHOLDS['zscore_critical'],
        },
        'total_anomalies': len(all_anomalies),
        'sites_with_anomalies': len(score_df),
        'by_severity': {
            'critical': sum(1 for a in all_anomalies if a.get('severity') == 'CRITICAL'),
            'high': sum(1 for a in all_anomalies if a.get('severity') == 'HIGH'),
            'medium': sum(1 for a in all_anomalies if a.get('severity') == 'MEDIUM'),
            'low': sum(1 for a in all_anomalies if a.get('severity') == 'LOW'),
        },
        'by_type': {
            'statistical_outlier': len(stat_anomalies),
            'pattern_anomaly': len(pattern_anomalies),
            'regional_anomaly': len(regional_anomalies),
            'cross_study_anomaly': len(cross_study_anomalies),
            'velocity_anomaly': len(velocity_anomalies),
        },
        'top_sites': score_df.head(10).to_dict('records') if not score_df.empty else []
    }

    summary_path = PHASE_06_DIR / "anomaly_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n[OK] Saved: {summary_path}")

    # Save report
    report = generate_anomaly_report(all_anomalies, score_df, site_df)
    report_path = PHASE_06_DIR / "anomaly_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n[OK] Saved: {report_path}")

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
  Statistical Outliers: {len(stat_anomalies)}
  Pattern Anomalies: {len(pattern_anomalies)}
  Regional Anomalies: {len(regional_anomalies)}
  Cross-Study Anomalies: {len(cross_study_anomalies)}
  Velocity Anomalies: {len(velocity_anomalies)}

Sites Requiring Investigation: {len(score_df)}
""")

    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Review: outputs/phase_06/anomaly_report.md (human-readable report)
2. Review: outputs/phase_06/anomalies_detected.csv (all anomalies)
3. Review: outputs/phase_06/site_anomaly_scores.csv (prioritized site list)
4. Review: outputs/phase_06/anomaly_summary.json (summary statistics)
5. Run: python src/phases/07_multi_agent_system.py
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    success = run_anomaly_detection()
    if not success:
        exit(1)
