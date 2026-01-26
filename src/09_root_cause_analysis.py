"""
Javelin.AI - Step 9: Root Cause Analysis Engine
=================================================

WHAT THIS DOES:
---------------
Goes beyond detecting WHAT issues exist to understand WHY they occur.
Identifies underlying patterns, causal relationships, and systemic factors
that drive data quality problems.

ROOT CAUSE ANALYSIS TYPES:
--------------------------
1. ISSUE CO-OCCURRENCE    - Which issues appear together? (symptom clusters)
2. FACTOR ATTRIBUTION     - What factors predict issues? (region, study, volume)
3. CASCADE ANALYSIS       - What issues lead to other issues? (causal chains)
4. CONTRIBUTION BREAKDOWN - What's driving the DQI score? (component analysis)
5. SYSTEMIC PATTERNS      - Study-wide vs site-specific problems

KEY OUTPUTS:
------------
- Root cause identification for each high-risk site
- Systemic vs isolated issue classification
- Intervention recommendations targeting root causes
- Factor importance ranking

Usage:
    python src/09_root_cause_analysis.py
    python src/09_root_cause_analysis.py --top-sites 50

Outputs:
    - outputs/root_cause_analysis.csv       : Site-level root causes
    - outputs/root_cause_summary.json       : Summary statistics
    - outputs/root_cause_report.md          : Human-readable report
    - outputs/issue_cooccurrence.csv        : Issue co-occurrence matrix
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from collections import defaultdict, Counter
import json
import warnings

warnings.filterwarnings('ignore')

# Statistical imports
from scipy import stats
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
# Handle both production (src/ folder) and testing scenarios
if (SCRIPT_DIR / "outputs").exists():
    OUTPUT_DIR = SCRIPT_DIR / "outputs"
elif (PROJECT_ROOT / "outputs").exists():
    OUTPUT_DIR = PROJECT_ROOT / "outputs"
else:
    OUTPUT_DIR = SCRIPT_DIR / "outputs"
    OUTPUT_DIR.mkdir(exist_ok=True)

# Input files from previous steps
SITE_DQI_PATH = OUTPUT_DIR / "master_site_with_dqi.csv"
SUBJECT_DQI_PATH = OUTPUT_DIR / "master_subject_with_dqi.csv"
STUDY_DQI_PATH = OUTPUT_DIR / "master_study_with_dqi.csv"
REGION_DQI_PATH = OUTPUT_DIR / "master_region_with_dqi.csv"
COUNTRY_DQI_PATH = OUTPUT_DIR / "master_country_with_dqi.csv"
ANOMALIES_PATH = OUTPUT_DIR / "anomalies_detected.csv"
CLUSTERS_PATH = OUTPUT_DIR / "site_clusters.csv"
DQI_WEIGHTS_PATH = OUTPUT_DIR / "dqi_weights.csv"

# Analysis Configuration
TOP_SITES_TO_ANALYZE = 100  # Focus on top problematic sites
MIN_COOCCURRENCE_COUNT = 10  # Minimum count for co-occurrence significance
CORRELATION_THRESHOLD = 0.3  # Minimum correlation for factor attribution

# Issue columns for analysis
ISSUE_COLUMNS = [
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

# Human-readable issue names
ISSUE_NAMES = {
    'sae_pending_count_sum':'Pending SAE Reviews',
    'uncoded_meddra_count_sum':'Uncoded MedDRA Terms',
    'missing_visit_count_sum':'Missing Visits',
    'missing_pages_count_sum':'Missing CRF Pages',
    'lab_issues_count_sum':'Lab Data Issues',
    'max_days_outstanding_sum':'Stale Queries (Days)',
    'max_days_page_missing_sum':'Stale Missing Pages (Days)',
    'uncoded_whodd_count_sum':'Uncoded Drug Terms',
    'edrr_open_issues_sum':'Open EDRR Issues',
    'inactivated_forms_count_sum':'Inactivated Forms'
}

# Issue categories for grouping
ISSUE_CATEGORIES = {
    'SAFETY':['sae_pending_count_sum', 'uncoded_meddra_count_sum'],
    'COMPLETENESS':['missing_visit_count_sum', 'missing_pages_count_sum', 'lab_issues_count_sum'],
    'TIMELINESS':['max_days_outstanding_sum', 'max_days_page_missing_sum'],
    'CODING':['uncoded_whodd_count_sum', 'edrr_open_issues_sum'],
    'ADMINISTRATIVE':['inactivated_forms_count_sum']
}

# Root cause templates
ROOT_CAUSE_TEMPLATES = {
    'TRAINING_GAP':{
        'description':'Site staff may lack training on specific data entry requirements',
        'indicators':['multiple_issue_types', 'consistent_patterns'],
        'intervention':'Schedule targeted training session on identified gap areas'
    },
    'RESOURCE_CONSTRAINT':{
        'description':'Site appears under-resourced relative to subject volume',
        'indicators':['high_volume', 'timeliness_issues', 'backlog_growth'],
        'intervention':'Assess site capacity and consider workload redistribution'
    },
    'PROCESS_BREAKDOWN':{
        'description':'Systematic process failure in specific workflow area',
        'indicators':['single_category_dominance', 'repeated_patterns'],
        'intervention':'Review and remediate specific process workflow'
    },
    'TECHNOLOGY_ISSUE':{
        'description':'Potential EDC or system integration problems',
        'indicators':['inactivated_forms', 'edrr_issues', 'data_transfer_gaps'],
        'intervention':'Engage IT support for system diagnostics'
    },
    'OVERSIGHT_GAP':{
        'description':'Insufficient monitoring or follow-up on pending items',
        'indicators':['stale_queries', 'aged_issues', 'no_resolution'],
        'intervention':'Implement enhanced oversight and escalation procedures'
    },
    'REGULATORY_COMPLEXITY':{
        'description':'Safety reporting requirements creating bottlenecks',
        'indicators':['sae_pending', 'coding_backlog', 'safety_focus'],
        'intervention':'Provide pharmacovigilance support and expedited review'
    },
    'STUDY_DESIGN_ISSUE':{
        'description':'Study-wide pattern suggests protocol or design challenges',
        'indicators':['study_wide_pattern', 'multiple_sites_affected'],
        'intervention':'Escalate to study management for protocol review'
    },
    'REGIONAL_FACTOR':{
        'description':'Regional patterns suggest local factors (regulations, practices)',
        'indicators':['regional_concentration', 'country_cluster'],
        'intervention':'Engage regional management for local context assessment'
    }
}


# ============================================================================
# DATA LOADING
# ============================================================================

def load_data() -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Load all required data files including pre-computed aggregations."""
    print("  Loading site data...")
    site_df = pd.read_csv(SITE_DQI_PATH)
    print(f"    Loaded {len(site_df):,} sites")

    print("  Loading subject data...")
    subject_df = pd.read_csv(SUBJECT_DQI_PATH)
    print(f"    Loaded {len(subject_df):,} subjects")

    anomaly_df = None
    if ANOMALIES_PATH.exists():
        print("  Loading anomaly data...")
        anomaly_df = pd.read_csv(ANOMALIES_PATH)
        print(f"    Loaded {len(anomaly_df):,} anomalies")

    cluster_df = None
    if CLUSTERS_PATH.exists():
        print("  Loading cluster data...")
        cluster_df = pd.read_csv(CLUSTERS_PATH)
        print(f"    Loaded cluster assignments for {len(cluster_df):,} sites")

    # Load pre-computed aggregated data for context
    study_df = None
    region_df = None
    country_df = None

    if STUDY_DQI_PATH.exists():
        study_df = pd.read_csv(STUDY_DQI_PATH)
        print(f"    Loaded {len(study_df)} studies (pre-computed)")

    if REGION_DQI_PATH.exists():
        region_df = pd.read_csv(REGION_DQI_PATH)
        print(f"    Loaded {len(region_df)} regions (pre-computed)")

    if COUNTRY_DQI_PATH.exists():
        country_df = pd.read_csv(COUNTRY_DQI_PATH)
        print(f"    Loaded {len(country_df)} countries (pre-computed)")

    return site_df, subject_df, anomaly_df, cluster_df, study_df, region_df, country_df


# ============================================================================
# ISSUE CO-OCCURRENCE ANALYSIS
# ============================================================================

def analyze_issue_cooccurrence(site_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Analyze which issues tend to appear together.

    Returns:
        - cooccurrence_matrix: DataFrame showing issue co-occurrence counts
        - patterns: Dictionary of significant co-occurrence patterns
    """
    print("  Analyzing issue co-occurrence patterns...")

    # Create binary issue presence matrix
    available_cols = [c for c in ISSUE_COLUMNS if c in site_df.columns]
    binary_matrix = (site_df[available_cols] > 0).astype(int)

    # Calculate co-occurrence matrix
    n_issues = len(available_cols)
    cooccurrence = np.zeros((n_issues, n_issues))

    for i, col1 in enumerate(available_cols):
        for j, col2 in enumerate(available_cols):
            if i <= j:
                count = ((binary_matrix[col1]==1) & (binary_matrix[col2]==1)).sum()
                cooccurrence[i, j] = count
                cooccurrence[j, i] = count

    cooccurrence_df = pd.DataFrame(
        cooccurrence,
        index=[ISSUE_NAMES.get(c, c) for c in available_cols],
        columns=[ISSUE_NAMES.get(c, c) for c in available_cols]
    )

    # Identify significant patterns
    patterns = {
        'strong_associations':[],
        'symptom_clusters':[],
        'independent_issues':[]
    }

    # Find strong associations (high co-occurrence relative to individual rates)
    for i, col1 in enumerate(available_cols):
        col1_count = binary_matrix[col1].sum()
        for j, col2 in enumerate(available_cols):
            if i < j:
                col2_count = binary_matrix[col2].sum()
                cooc_count = cooccurrence[i, j]

                if col1_count > 0 and col2_count > 0 and cooc_count >= MIN_COOCCURRENCE_COUNT:
                    # Calculate lift (observed / expected)
                    expected = (col1_count * col2_count) / len(site_df)
                    lift = cooc_count / expected if expected > 0 else 0

                    if lift > 1.5:  # Significantly more likely to occur together
                        patterns['strong_associations'].append({
                            'issue_1':ISSUE_NAMES.get(col1, col1),
                            'issue_2':ISSUE_NAMES.get(col2, col2),
                            'cooccurrence_count':int(cooc_count),
                            'lift':round(lift, 2),
                            'interpretation':f"Sites with {ISSUE_NAMES.get(col1, col1)} are {lift:.1f}x more likely to have {ISSUE_NAMES.get(col2, col2)}"
                        })

    # Sort by lift
    patterns['strong_associations'] = sorted(
        patterns['strong_associations'],
        key=lambda x:x['lift'],
        reverse=True
    )[:10]

    print(f"    Found {len(patterns['strong_associations'])} strong issue associations")

    return cooccurrence_df, patterns


# ============================================================================
# FACTOR ATTRIBUTION ANALYSIS
# ============================================================================

def analyze_factor_attribution(site_df: pd.DataFrame,
                               study_df: pd.DataFrame = None,
                               region_df: pd.DataFrame = None,
                               country_df: pd.DataFrame = None) -> Dict:
    """
    Identify what factors (region, study, volume, etc.) predict issues.

    Enhanced to use pre-computed study/region/country data when available.

    Returns:
        Dictionary of factor importance and correlations.
    """
    print("  Analyzing factor attribution...")

    results = {
        'regional_factors':{},
        'study_factors':{},
        'country_factors':{},
        'volume_factors':{},
        'factor_importance':[]
    }

    # Ensure we have DQI score
    if 'avg_dqi_score' not in site_df.columns:
        print("    Warning: avg_dqi_score not found")
        return results

    overall_mean = site_df['avg_dqi_score'].mean()

    # Regional analysis - use pre-computed if available
    if region_df is not None and len(region_df) > 0:
        print("    Using pre-computed region data...")
        for _, row in region_df.iterrows():
            region = row['region']
            region_mean = row['avg_dqi_score']
            if region_mean > overall_mean * 1.5:
                results['regional_factors'][region] = {
                    'avg_dqi':float(region_mean),
                    'vs_overall':f"{(region_mean / overall_mean - 1) * 100:.1f}% higher than average",
                    'site_count':int(row['site_count']),
                    'high_risk_rate':f"{row['high_risk_rate'] * 100:.1f}%",
                    'risk_category':row['region_risk_category']
                }
    elif 'region' in site_df.columns:
        regional_stats = site_df.groupby('region').agg({
            'avg_dqi_score':['mean', 'std', 'count'],
            'high_risk_count':'sum',
            'subject_count':'sum'
        }).round(4)

        regional_stats.columns = ['avg_dqi', 'std_dqi', 'site_count', 'high_risk_sites', 'subjects']
        regional_stats['high_risk_rate'] = (
                    regional_stats['high_risk_sites'] / regional_stats['site_count'] * 100).round(1)

        for region in regional_stats.index:
            region_mean = regional_stats.loc[region, 'avg_dqi']
            if region_mean > overall_mean * 1.5:
                results['regional_factors'][region] = {
                    'avg_dqi':float(region_mean),
                    'vs_overall':f"{(region_mean / overall_mean - 1) * 100:.1f}% higher than average",
                    'site_count':int(regional_stats.loc[region, 'site_count']),
                    'high_risk_rate':f"{regional_stats.loc[region, 'high_risk_rate']:.1f}%"
                }

    # Study analysis - use pre-computed if available
    if study_df is not None and len(study_df) > 0:
        print("    Using pre-computed study data...")
        for _, row in study_df.iterrows():
            study = row['study']
            study_mean = row['avg_dqi_score']
            if study_mean > overall_mean * 2:  # More than 2x average
                results['study_factors'][study] = {
                    'avg_dqi':float(study_mean),
                    'vs_overall':f"{(study_mean / overall_mean - 1) * 100:.1f}% higher than average",
                    'site_count':int(row['site_count']),
                    'high_risk_rate':f"{row['high_risk_rate'] * 100:.1f}%",
                    'risk_category':row['study_risk_category'],
                    'classification':'STUDY_WIDE_ISSUE'
                }
    elif 'study' in site_df.columns:
        study_stats = site_df.groupby('study').agg({
            'avg_dqi_score':['mean', 'std'],
            'high_risk_count':'sum',
            'subject_count':'sum'
        }).round(4)

        study_stats.columns = ['avg_dqi', 'std_dqi', 'high_risk_sites', 'subjects']
        site_counts = site_df.groupby('study').size()
        study_stats['site_count'] = site_counts
        study_stats['high_risk_rate'] = (study_stats['high_risk_sites'] / study_stats['site_count'] * 100).round(1)

        for study in study_stats.index:
            study_mean = study_stats.loc[study, 'avg_dqi']
            if study_mean > overall_mean * 2:
                results['study_factors'][study] = {
                    'avg_dqi':float(study_mean),
                    'vs_overall':f"{(study_mean / overall_mean - 1) * 100:.1f}% higher than average",
                    'site_count':int(study_stats.loc[study, 'site_count']),
                    'high_risk_rate':f"{study_stats.loc[study, 'high_risk_rate']:.1f}%",
                    'classification':'STUDY_WIDE_ISSUE'
                }

    # Country analysis - use pre-computed if available
    if country_df is not None and len(country_df) > 0:
        print("    Using pre-computed country data...")
        for _, row in country_df.iterrows():
            country = row['country']
            country_mean = row['avg_dqi_score']
            if country_mean > overall_mean * 1.8 and row['site_count'] >= 3:  # At least 3 sites
                results['country_factors'][country] = {
                    'avg_dqi':float(country_mean),
                    'vs_overall':f"{(country_mean / overall_mean - 1) * 100:.1f}% higher than average",
                    'site_count':int(row['site_count']),
                    'region':row['region'],
                    'high_risk_rate':f"{row['high_risk_rate'] * 100:.1f}%",
                    'risk_category':row['country_risk_category']
                }

    # Volume analysis - correlation between subject count and issues
    if 'subject_count' in site_df.columns:
        site_df_copy = site_df.copy()
        site_df_copy['issues_per_subject'] = site_df_copy['avg_dqi_score']

        corr = site_df['subject_count'].corr(site_df['avg_dqi_score'])
        results['volume_factors']['volume_dqi_correlation'] = round(corr, 3)

        if abs(corr) > CORRELATION_THRESHOLD:
            results['volume_factors']['interpretation'] = (
                f"{'Positive' if corr > 0 else 'Negative'} correlation ({corr:.2f}) between site volume and DQI - "
                f"{'larger sites tend to have more issues' if corr > 0 else 'smaller sites tend to have more issues'}"
            )
        else:
            results['volume_factors']['interpretation'] = "No significant correlation between site volume and DQI"

    # Calculate factor importance using variance explained
    factors = []
    total_variance = site_df['avg_dqi_score'].var()

    if 'region' in site_df.columns:
        region_variance = site_df.groupby('region')['avg_dqi_score'].mean().var()
        factors.append({
            'factor':'Region',
            'variance_explained':round(region_variance / total_variance * 100, 1) if total_variance > 0 else 0
        })

    if 'study' in site_df.columns:
        study_variance = site_df.groupby('study')['avg_dqi_score'].mean().var()
        factors.append({
            'factor':'Study',
            'variance_explained':round(study_variance / total_variance * 100, 1) if total_variance > 0 else 0
        })

    if 'country' in site_df.columns:
        country_variance = site_df.groupby('country')['avg_dqi_score'].mean().var()
        total_variance = site_df['avg_dqi_score'].var()
        factors.append({
            'factor':'Country',
            'variance_explained':round(country_variance / total_variance * 100, 1) if total_variance > 0 else 0
        })

    results['factor_importance'] = sorted(factors, key=lambda x:x['variance_explained'], reverse=True)

    print(f"    Identified {len(results['regional_factors'])} high-risk regions")
    print(f"    Identified {len(results['study_factors'])} problematic studies")

    return results


# ============================================================================
# DQI CONTRIBUTION ANALYSIS
# ============================================================================

def analyze_dqi_contribution(site_df: pd.DataFrame) -> Dict:
    """
    Break down what's driving DQI scores for high-risk sites.

    Returns:
        Dictionary with contribution analysis by category.
    """
    print("  Analyzing DQI score contributions...")

    results = {
        'category_contributions':{},
        'top_drivers':[],
        'portfolio_breakdown':{}
    }

    # Get high-risk sites
    high_risk_sites = site_df[site_df.get('site_risk_category', '')=='High']

    if len(high_risk_sites)==0:
        high_risk_sites = site_df.nlargest(100, 'avg_dqi_score')

    # Analyze by category
    for category, columns in ISSUE_CATEGORIES.items():
        available_cols = [c for c in columns if c in site_df.columns]
        if not available_cols:
            continue

        # Count sites with issues in this category
        has_category_issue = (site_df[available_cols] > 0).any(axis=1)

        results['category_contributions'][category] = {
            'sites_affected':int(has_category_issue.sum()),
            'pct_of_portfolio':round(has_category_issue.sum() / len(site_df) * 100, 1),
            'avg_in_high_risk':round(high_risk_sites[available_cols].sum(axis=1).mean(), 2) if len(
                high_risk_sites) > 0 else 0,
            'issues':[ISSUE_NAMES.get(c, c) for c in available_cols]
        }

    # Find top drivers across portfolio
    available_issue_cols = [c for c in ISSUE_COLUMNS if c in site_df.columns]

    for col in available_issue_cols:
        sites_with_issue = (site_df[col] > 0).sum()
        if sites_with_issue > 0:
            # Calculate average value among sites with this issue
            avg_value = site_df[site_df[col] > 0][col].mean()
            results['top_drivers'].append({
                'issue':ISSUE_NAMES.get(col, col),
                'column':col,
                'sites_affected':int(sites_with_issue),
                'pct_affected':round(sites_with_issue / len(site_df) * 100, 1),
                'avg_value':round(avg_value, 2)
            })

    # Sort by sites affected
    results['top_drivers'] = sorted(
        results['top_drivers'],
        key=lambda x:x['sites_affected'],
        reverse=True
    )

    # Portfolio-level breakdown
    total_issues = sum(
        (site_df[col] > 0).sum()
        for col in available_issue_cols
        if col in site_df.columns
    )

    for category, columns in ISSUE_CATEGORIES.items():
        available_cols = [c for c in columns if c in site_df.columns]
        category_issues = sum((site_df[col] > 0).sum() for col in available_cols)
        results['portfolio_breakdown'][category] = {
            'issue_instances':int(category_issues),
            'pct_of_total':round(category_issues / total_issues * 100, 1) if total_issues > 0 else 0
        }

    print(f"    Analyzed contributions across {len(ISSUE_CATEGORIES)} categories")

    return results


# ============================================================================
# SITE-LEVEL ROOT CAUSE ANALYSIS
# ============================================================================

def identify_site_root_causes(site_df: pd.DataFrame,
                              anomaly_df: Optional[pd.DataFrame],
                              factor_results: Dict,
                              top_n: int = 100) -> List[Dict]:
    """
    Identify root causes for individual high-risk sites.

    Returns:
        List of site-level root cause analyses.
    """
    print(f"  Identifying root causes for top {top_n} sites...")

    # Select sites to analyze
    if 'site_risk_category' in site_df.columns:
        high_risk = site_df[site_df['site_risk_category']=='High'].copy()
        if len(high_risk) < top_n:
            # Add more from top DQI scores
            remaining = site_df[site_df['site_risk_category']!='High'].nlargest(
                top_n - len(high_risk), 'avg_dqi_score'
            )
            analysis_sites = pd.concat([high_risk, remaining])
        else:
            analysis_sites = high_risk.nlargest(top_n, 'avg_dqi_score')
    else:
        analysis_sites = site_df.nlargest(top_n, 'avg_dqi_score')

    # Get anomaly counts per site if available
    site_anomalies = {}
    if anomaly_df is not None:
        site_anomalies = anomaly_df.groupby('site_id').agg({
            'anomaly_type':lambda x:list(x),
            'severity':lambda x:list(x)
        }).to_dict('index')

    # Check for study-wide patterns
    study_wide_issues = set(factor_results.get('study_factors', {}).keys())

    root_causes = []

    for idx, site in analysis_sites.iterrows():
        site_analysis = {
            'study':site.get('study', 'Unknown'),
            'site_id':site.get('site_id', 'Unknown'),
            'country':site.get('country', 'Unknown'),
            'region':site.get('region', 'Unknown'),
            'dqi_score':round(site.get('avg_dqi_score', 0), 4),
            'risk_category':site.get('site_risk_category', 'Unknown'),
            'subject_count':int(site.get('subject_count', 0)),
            'root_causes':[],
            'primary_root_cause':None,
            'issue_breakdown':{},
            'recommended_interventions':[]
        }

        # Analyze issue breakdown
        available_cols = [c for c in ISSUE_COLUMNS if c in site.index]
        issue_values = {ISSUE_NAMES.get(c, c):site[c] for c in available_cols if site[c] > 0}
        site_analysis['issue_breakdown'] = issue_values

        # Determine issue categories present
        categories_affected = []
        for category, columns in ISSUE_CATEGORIES.items():
            if any(site.get(c, 0) > 0 for c in columns if c in site.index):
                categories_affected.append(category)

        site_analysis['categories_affected'] = categories_affected

        # ROOT CAUSE IDENTIFICATION LOGIC

        # Check 1: Study-wide issue
        if site.get('study') in study_wide_issues:
            site_analysis['root_causes'].append({
                'cause_type':'STUDY_DESIGN_ISSUE',
                'confidence':'HIGH',
                'evidence':f"Study {site.get('study')} has portfolio-wide elevated DQI",
                'details':ROOT_CAUSE_TEMPLATES['STUDY_DESIGN_ISSUE']
            })

        # Check 2: Safety/regulatory issues dominating
        safety_cols = [c for c in ISSUE_CATEGORIES['SAFETY'] if c in site.index]
        safety_issues = sum(1 for c in safety_cols if site.get(c, 0) > 0)
        if safety_issues > 0 and site.get('sae_pending_count_sum', 0) > 5:
            site_analysis['root_causes'].append({
                'cause_type':'REGULATORY_COMPLEXITY',
                'confidence':'HIGH',
                'evidence':f"{site.get('sae_pending_count_sum', 0)} pending SAE reviews",
                'details':ROOT_CAUSE_TEMPLATES['REGULATORY_COMPLEXITY']
            })

        # Check 3: Timeliness issues (oversight gap)
        if site.get('max_days_outstanding_sum', 0) > 60 or site.get('max_days_page_missing_sum', 0) > 60:
            days_out = max(site.get('max_days_outstanding_sum', 0), site.get('max_days_page_missing_sum', 0))
            site_analysis['root_causes'].append({
                'cause_type':'OVERSIGHT_GAP',
                'confidence':'HIGH' if days_out > 90 else 'MEDIUM',
                'evidence':f"Data outstanding for {days_out:.0f} days without resolution",
                'details':ROOT_CAUSE_TEMPLATES['OVERSIGHT_GAP']
            })

        # Check 4: Single category dominance (process breakdown)
        if len(categories_affected)==1:
            site_analysis['root_causes'].append({
                'cause_type':'PROCESS_BREAKDOWN',
                'confidence':'MEDIUM',
                'evidence':f"Issues concentrated in {categories_affected[0]} category only",
                'details':ROOT_CAUSE_TEMPLATES['PROCESS_BREAKDOWN']
            })

        # Check 5: Multiple categories (training gap)
        if len(categories_affected) >= 3:
            site_analysis['root_causes'].append({
                'cause_type':'TRAINING_GAP',
                'confidence':'MEDIUM',
                'evidence':f"Issues across {len(categories_affected)} categories: {', '.join(categories_affected)}",
                'details':ROOT_CAUSE_TEMPLATES['TRAINING_GAP']
            })

        # Check 6: High volume with issues (resource constraint)
        portfolio_avg_subjects = site_df['subject_count'].mean()
        if site.get('subject_count', 0) > portfolio_avg_subjects * 1.5 and site.get('avg_dqi_score', 0) > 0.1:
            site_analysis['root_causes'].append({
                'cause_type':'RESOURCE_CONSTRAINT',
                'confidence':'MEDIUM',
                'evidence':f"Site has {site.get('subject_count', 0)} subjects ({site.get('subject_count', 0) / portfolio_avg_subjects:.1f}x portfolio average) with elevated issues",
                'details':ROOT_CAUSE_TEMPLATES['RESOURCE_CONSTRAINT']
            })

        # Check 7: Technology indicators
        if site.get('inactivated_forms_count_sum', 0) > 50 or site.get('edrr_open_issues_sum', 0) > 20:
            site_analysis['root_causes'].append({
                'cause_type':'TECHNOLOGY_ISSUE',
                'confidence':'MEDIUM',
                'evidence':f"High inactivated forms ({site.get('inactivated_forms_count_sum', 0)}) or EDRR issues ({site.get('edrr_open_issues_sum', 0)})",
                'details':ROOT_CAUSE_TEMPLATES['TECHNOLOGY_ISSUE']
            })

        # Check 8: Regional pattern
        region = site.get('region')
        if region in factor_results.get('regional_factors', {}):
            site_analysis['root_causes'].append({
                'cause_type':'REGIONAL_FACTOR',
                'confidence':'MEDIUM',
                'evidence':f"Site is in {region}, which has elevated DQI across portfolio",
                'details':ROOT_CAUSE_TEMPLATES['REGIONAL_FACTOR']
            })

        # Determine primary root cause (highest confidence, most specific)
        if site_analysis['root_causes']:
            # Priority order for primary cause
            priority_order = ['REGULATORY_COMPLEXITY', 'STUDY_DESIGN_ISSUE', 'OVERSIGHT_GAP',
                              'RESOURCE_CONSTRAINT', 'PROCESS_BREAKDOWN', 'TRAINING_GAP',
                              'TECHNOLOGY_ISSUE', 'REGIONAL_FACTOR']

            for cause_type in priority_order:
                matching = [rc for rc in site_analysis['root_causes'] if rc['cause_type']==cause_type]
                if matching:
                    site_analysis['primary_root_cause'] = matching[0]['cause_type']
                    break

            # Compile recommended interventions
            seen_interventions = set()
            for rc in site_analysis['root_causes']:
                intervention = rc['details']['intervention']
                if intervention not in seen_interventions:
                    site_analysis['recommended_interventions'].append(intervention)
                    seen_interventions.add(intervention)
        else:
            site_analysis['primary_root_cause'] = 'UNKNOWN'
            site_analysis['recommended_interventions'] = ['Conduct detailed site assessment to identify root cause']

        root_causes.append(site_analysis)

    print(f"    Completed root cause analysis for {len(root_causes)} sites")

    return root_causes


# ============================================================================
# SYSTEMIC PATTERN ANALYSIS
# ============================================================================

def analyze_systemic_patterns(site_df: pd.DataFrame,
                              root_causes: List[Dict],
                              factor_results: Dict) -> Dict:
    """
    Identify portfolio-wide systemic patterns vs isolated issues.

    Returns:
        Dictionary with systemic pattern analysis.
    """
    print("  Analyzing systemic patterns...")

    results = {
        'systemic_issues':[],
        'isolated_issues':[],
        'root_cause_distribution':{},
        'intervention_priority':[]
    }

    # Count root cause types
    root_cause_counts = Counter()
    for site in root_causes:
        if site['primary_root_cause']:
            root_cause_counts[site['primary_root_cause']] += 1

    results['root_cause_distribution'] = dict(root_cause_counts)

    # Identify systemic issues (affecting >10% of analyzed sites)
    threshold = len(root_causes) * 0.1

    for cause_type, count in root_cause_counts.items():
        if count >= threshold:
            results['systemic_issues'].append({
                'cause_type':cause_type,
                'sites_affected':count,
                'pct_of_analyzed':round(count / len(root_causes) * 100, 1),
                'description':ROOT_CAUSE_TEMPLATES.get(cause_type, {}).get('description', 'Unknown'),
                'portfolio_intervention':ROOT_CAUSE_TEMPLATES.get(cause_type, {}).get('intervention', 'Review required')
            })
        else:
            results['isolated_issues'].append({
                'cause_type':cause_type,
                'sites_affected':count,
                'pct_of_analyzed':round(count / len(root_causes) * 100, 1)
            })

    # Sort systemic issues by impact
    results['systemic_issues'] = sorted(
        results['systemic_issues'],
        key=lambda x:x['sites_affected'],
        reverse=True
    )

    # Generate prioritized intervention list
    intervention_counts = Counter()
    for site in root_causes:
        for intervention in site.get('recommended_interventions', []):
            intervention_counts[intervention] += 1

    for intervention, count in intervention_counts.most_common(10):
        results['intervention_priority'].append({
            'intervention':intervention,
            'sites_benefiting':count,
            'priority':'HIGH' if count > len(root_causes) * 0.2 else 'MEDIUM' if count > len(
                root_causes) * 0.1 else 'LOW'
        })

    print(f"    Identified {len(results['systemic_issues'])} systemic issues")
    print(f"    Identified {len(results['isolated_issues'])} isolated issue types")

    return results


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_root_cause_report(cooccurrence_patterns: Dict,
                               factor_results: Dict,
                               contribution_results: Dict,
                               root_causes: List[Dict],
                               systemic_patterns: Dict) -> str:
    """Generate markdown report for root cause analysis."""

    report = []

    report.append("# JAVELIN.AI - Root Cause Analysis Report\n")
    report.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    report.append("---\n")

    # Executive Summary
    report.append("## Executive Summary\n")
    report.append("| Metric | Value |")
    report.append("|--------|-------|")
    report.append(f"| Sites Analyzed | {len(root_causes)} |")
    report.append(f"| Systemic Issues Identified | {len(systemic_patterns.get('systemic_issues', []))} |")
    report.append(f"| Root Cause Types Found | {len(systemic_patterns.get('root_cause_distribution', {}))} |")
    report.append(f"| Prioritized Interventions | {len(systemic_patterns.get('intervention_priority', []))} |")
    report.append("")

    # Root Cause Distribution
    report.append("## Root Cause Distribution\n")
    report.append("| Root Cause | Sites | % of Analyzed | Classification |")
    report.append("|------------|-------|---------------|----------------|")

    for cause_type, count in sorted(
            systemic_patterns.get('root_cause_distribution', {}).items(),
            key=lambda x:x[1],
            reverse=True
    ):
        pct = count / len(root_causes) * 100 if root_causes else 0
        classification = 'SYSTEMIC' if pct >= 10 else 'ISOLATED'
        report.append(f"| {cause_type} | {count} | {pct:.1f}% | {classification} |")
    report.append("")

    # Systemic Issues
    if systemic_patterns.get('systemic_issues'):
        report.append("## Systemic Issues (Portfolio-Wide)\n")
        report.append(
            "These issues affect a significant portion of the portfolio and require coordinated intervention:\n")

        for issue in systemic_patterns['systemic_issues']:
            report.append(f"### {issue['cause_type']}\n")
            report.append(f"- **Sites Affected**: {issue['sites_affected']} ({issue['pct_of_analyzed']}%)")
            report.append(f"- **Description**: {issue['description']}")
            report.append(f"- **Recommended Action**: {issue['portfolio_intervention']}")
            report.append("")

    # Issue Co-occurrence Patterns
    if cooccurrence_patterns.get('strong_associations'):
        report.append("## Issue Co-occurrence Patterns\n")
        report.append("Issues that frequently appear together (potential common root causes):\n")

        for assoc in cooccurrence_patterns['strong_associations'][:5]:
            report.append(
                f"- **{assoc['issue_1']}** + **{assoc['issue_2']}**: {assoc['cooccurrence_count']} sites (lift: {assoc['lift']}x)")
        report.append("")

    # Factor Attribution
    report.append("## Factor Attribution\n")

    if factor_results.get('factor_importance'):
        report.append("### Variance Explained by Factor\n")
        for factor in factor_results['factor_importance']:
            report.append(f"- **{factor['factor']}**: {factor['variance_explained']}% of DQI variance")
        report.append("")

    if factor_results.get('study_factors'):
        report.append("### Problematic Studies\n")
        for study, info in list(factor_results['study_factors'].items())[:5]:
            report.append(f"- **{study}**: {info['vs_overall']} (high-risk rate: {info['high_risk_rate']})")
        report.append("")

    # DQI Contribution Breakdown
    report.append("## DQI Score Drivers\n")
    report.append("### By Category\n")
    report.append("| Category | Sites Affected | % of Portfolio |")
    report.append("|----------|----------------|----------------|")

    for category, info in contribution_results.get('category_contributions', {}).items():
        report.append(f"| {category} | {info['sites_affected']:,} | {info['pct_of_portfolio']}% |")
    report.append("")

    # Prioritized Interventions
    report.append("## Prioritized Interventions\n")
    report.append("| Intervention | Sites Benefiting | Priority |")
    report.append("|--------------|------------------|----------|")

    for intervention in systemic_patterns.get('intervention_priority', [])[:10]:
        priority_marker = {'HIGH':'[!!!]', 'MEDIUM':'[!!]', 'LOW':'[!]'}.get(intervention['priority'], '')
        report.append(
            f"| {intervention['intervention'][:60]}... | {intervention['sites_benefiting']} | {priority_marker} {intervention['priority']} |")
    report.append("")

    # Top 10 Sites with Root Causes
    report.append("## Top 10 Sites - Root Cause Details\n")

    for i, site in enumerate(root_causes[:10], 1):
        report.append(f"### {i}. {site['study']} - {site['site_id']} ({site['country']})\n")
        report.append(f"- **DQI Score**: {site['dqi_score']}")
        report.append(f"- **Primary Root Cause**: {site['primary_root_cause']}")
        report.append(f"- **Categories Affected**: {', '.join(site.get('categories_affected', []))}")

        if site.get('issue_breakdown'):
            issues_str = ', '.join([f"{k}: {v}" for k, v in list(site['issue_breakdown'].items())[:3]])
            report.append(f"- **Top Issues**: {issues_str}")

        if site.get('recommended_interventions'):
            report.append(f"- **Recommended**: {site['recommended_interventions'][0]}")
        report.append("")

    report.append("---\n")
    report.append("*Report generated by JAVELIN.AI Root Cause Analysis Engine*\n")

    return '\n'.join(report)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_root_cause_analysis(top_sites: int = TOP_SITES_TO_ANALYZE) -> bool:
    """
    Main function to run root cause analysis.

    Args:
        top_sites: Number of top sites to analyze in detail

    Returns:
        True if successful, False otherwise
    """
    print("=" * 70)
    print("JAVELIN.AI - ROOT CAUSE ANALYSIS ENGINE")
    print("=" * 70)
    print(f"\nProject Root: {PROJECT_ROOT}\n")

    # =========================================================================
    # Step 1: Load Data
    # =========================================================================
    print("[1/6] Loading data...")
    try:
        site_df, subject_df, anomaly_df, cluster_df, study_df, region_df, country_df = load_data()
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        print("  Make sure to run previous pipeline steps first.")
        return False

    # Enrich site data with hierarchical risk context
    if study_df is not None:
        study_risk_map = study_df.set_index('study')['study_risk_category'].to_dict()
        site_df['study_risk_category'] = site_df['study'].map(study_risk_map).fillna('Unknown')
        print(f"  Enriched with study risk categories")

    if country_df is not None:
        country_risk_map = country_df.set_index('country')['country_risk_category'].to_dict()
        site_df['country_risk_category'] = site_df['country'].map(country_risk_map).fillna('Unknown')
        print(f"  Enriched with country risk categories")

    if region_df is not None:
        region_risk_map = region_df.set_index('region')['region_risk_category'].to_dict()
        site_df['region_risk_category'] = site_df['region'].map(region_risk_map).fillna('Unknown')
        print(f"  Enriched with region risk categories")

    # =========================================================================
    # Step 2: Issue Co-occurrence Analysis
    # =========================================================================
    print("\n[2/6] Analyzing issue co-occurrence...")
    cooccurrence_df, cooccurrence_patterns = analyze_issue_cooccurrence(site_df)

    # =========================================================================
    # Step 3: Factor Attribution
    # =========================================================================
    print("\n[3/6] Analyzing factor attribution...")
    factor_results = analyze_factor_attribution(site_df, study_df, region_df, country_df)

    # =========================================================================
    # Step 4: DQI Contribution Analysis
    # =========================================================================
    print("\n[4/6] Analyzing DQI contributions...")
    contribution_results = analyze_dqi_contribution(site_df)

    # =========================================================================
    # Step 5: Site-Level Root Cause Identification
    # =========================================================================
    print(f"\n[5/6] Identifying root causes for top {top_sites} sites...")
    root_causes = identify_site_root_causes(site_df, anomaly_df, factor_results, top_sites)

    # =========================================================================
    # Step 6: Systemic Pattern Analysis
    # =========================================================================
    print("\n[6/6] Analyzing systemic patterns...")
    systemic_patterns = analyze_systemic_patterns(site_df, root_causes, factor_results)

    # =========================================================================
    # Save Outputs
    # =========================================================================
    print("\n" + "=" * 70)
    print("SAVING OUTPUTS")
    print("=" * 70)

    # 1. Site-level root causes CSV
    root_cause_rows = []
    for site in root_causes:
        row = {
            'study':site['study'],
            'site_id':site['site_id'],
            'country':site['country'],
            'region':site['region'],
            'dqi_score':site['dqi_score'],
            'risk_category':site['risk_category'],
            'subject_count':site['subject_count'],
            'primary_root_cause':site['primary_root_cause'],
            'all_root_causes':'; '.join([rc['cause_type'] for rc in site['root_causes']]),
            'categories_affected':'; '.join(site.get('categories_affected', [])),
            'top_intervention':site['recommended_interventions'][0] if site['recommended_interventions'] else '',
            'n_issues':len(site.get('issue_breakdown', {}))
        }
        root_cause_rows.append(row)

    root_cause_csv_path = OUTPUT_DIR / "root_cause_analysis.csv"
    pd.DataFrame(root_cause_rows).to_csv(root_cause_csv_path, index=False)
    print(f"\nSaved: {root_cause_csv_path}")

    # 2. Co-occurrence matrix
    cooccurrence_path = OUTPUT_DIR / "issue_cooccurrence.csv"
    cooccurrence_df.to_csv(cooccurrence_path)
    print(f"Saved: {cooccurrence_path}")

    # 3. Summary JSON
    summary = {
        'generated_at':datetime.now().isoformat(),
        'sites_analyzed':len(root_causes),
        'cooccurrence_patterns':cooccurrence_patterns,
        'factor_attribution':factor_results,
        'dqi_contributions':contribution_results,
        'systemic_patterns':systemic_patterns,
        'root_cause_summary':{
            cause_type:count
            for cause_type, count in systemic_patterns.get('root_cause_distribution', {}).items()
        }
    }

    summary_path = OUTPUT_DIR / "root_cause_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Saved: {summary_path}")

    # 4. Markdown report
    report = generate_root_cause_report(
        cooccurrence_patterns, factor_results, contribution_results,
        root_causes, systemic_patterns
    )
    report_path = OUTPUT_DIR / "root_cause_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Saved: {report_path}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"""
ROOT CAUSE ANALYSIS COMPLETE
============================

Sites Analyzed: {len(root_causes)}

Root Cause Distribution:""")

    for cause_type, count in sorted(
            systemic_patterns.get('root_cause_distribution', {}).items(),
            key=lambda x:x[1],
            reverse=True
    ):
        pct = count / len(root_causes) * 100 if root_causes else 0
        marker = "[SYSTEMIC]" if pct >= 10 else ""
        print(f"  - {cause_type}: {count} sites ({pct:.1f}%) {marker}")

    print(f"""
Systemic Issues (>10% of sites):
  {len(systemic_patterns.get('systemic_issues', []))} portfolio-wide patterns identified

Top Interventions:""")

    for intervention in systemic_patterns.get('intervention_priority', [])[:3]:
        print(f"  - {intervention['intervention'][:50]}... ({intervention['sites_benefiting']} sites)")

    print("\n" + "=" * 70)
    print("OUTPUTS")
    print("=" * 70)
    print(f"""
1. {root_cause_csv_path}
2. {cooccurrence_path}
3. {summary_path}
4. {report_path}
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__=="__main__":
    import sys

    top_sites = TOP_SITES_TO_ANALYZE

    # Parse arguments
    if "--top-sites" in sys.argv:
        try:
            idx = sys.argv.index("--top-sites")
            top_sites = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            pass

    if "--help" in sys.argv or "-h" in sys.argv:
        print("""
JAVELIN.AI Root Cause Analysis

Usage:
    python 09_root_cause_analysis.py [options]

Options:
    --top-sites N     Number of sites to analyze in detail (default: 100)
    --help, -h        Show this help message

Examples:
    python 09_root_cause_analysis.py
    python 09_root_cause_analysis.py --top-sites 50
    python 09_root_cause_analysis.py --top-sites 200
""")
        sys.exit(0)

    success = run_root_cause_analysis(top_sites=top_sites)

    if not success:
        sys.exit(1)
