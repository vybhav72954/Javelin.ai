"""
Javelin.AI - Phase 09: Root Cause Analysis
==============================================================

Analyzes patterns across sites and clusters to identify root causes of
data quality issues and generate actionable insights.

Prerequisites:
    - Run 03_calculate_dqi.py (Phase 03)
    - Run 06_anomaly_detection.py (Phase 06)
    - Run 08_site_clustering.py (Phase 08) - optional
    - outputs/phase03/master_*_with_dqi.csv must exist
    - outputs/phase06/anomalies_detected.csv must exist

Usage:
    python src/phases/09_root_cause_analysis.py
    python src/phases/09_root_cause_analysis.py --top-sites 10
    python src/phases/09_root_cause_analysis.py --include-clusters
    python src/phases/09_root_cause_analysis.py --no-clusters

CLI Options:
    --include-clusters  Include cluster analysis from Phase 08 (default: True)
    --no-clusters       Skip cluster integration
    --top-sites         Number of top issues to analyze (default: 10)

Output:
    - outputs/phase09/root_cause_analysis.csv           # Identified root causes
    - outputs/phase09/root_cause_report.md              # Human-readable report
    - outputs/phase09/root_cause_summary.json           # Statistics
    - outputs/phase09/issue_cooccurrence.csv            # Issue co-occurrence matrix
    - outputs/phase09/geographic_patterns.csv           # Regional patterns
    - outputs/phase09/contributing_factors.csv          # Factor analysis

Root Cause Methodology:
    1. Issue Co-occurrence Analysis: Which issues appear together?
    2. Temporal Pattern Detection: Time-based correlations
    3. Geographic/Organizational Patterns: Country/region/study patterns
    4. Site Characteristic Correlation: Size, experience factors
    5. Cluster-Based Root Cause: Why do certain archetypes emerge?

Categories:
    - Safety: SAE processes, adverse event handling
    - Completeness: Data entry, documentation
    - Timeliness: Query resolution, delays
    - Systemic: Organizational, process issues
    - Geographic: Location-specific challenges
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================================
# PATH SETUP
# ============================================================================

_SCRIPT_DIR = Path(__file__).parent.resolve()
_SRC_DIR = _SCRIPT_DIR.parent if _SCRIPT_DIR.name=='phases' else _SCRIPT_DIR
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# ============================================================================
# CONFIGURATION - With PHASE_DIRS Integration
# ============================================================================

try:
    from config import PROJECT_ROOT, OUTPUT_DIR, PHASE_DIRS, DQI_WEIGHTS

    _USING_CONFIG = True
except ImportError:
    _USING_CONFIG = False
    PROJECT_ROOT = _SRC_DIR.parent
    OUTPUT_DIR = PROJECT_ROOT / "outputs"
    PHASE_DIRS = {f'phase_{i:02d}':OUTPUT_DIR for i in range(10)}

    # Simplified DQI weights for root cause analysis
    DQI_WEIGHTS = {
        'sae_pending_count':{'weight':0.20, 'tier':'Safety'},
        'uncoded_meddra_count':{'weight':0.15, 'tier':'Safety'},
        'missing_visit_count':{'weight':0.12, 'tier':'Completeness'},
        'missing_pages_count':{'weight':0.10, 'tier':'Completeness'},
        'lab_issues_count':{'weight':0.10, 'tier':'Completeness'},
        'max_days_outstanding':{'weight':0.08, 'tier':'Timeliness'},
        'max_days_page_missing':{'weight':0.06, 'tier':'Timeliness'},
        'uncoded_whodd_count':{'weight':0.06, 'tier':'Coding'},
        'edrr_open_issues':{'weight':0.05, 'tier':'Reconciliation'},
        'inactivated_forms_count':{'weight':0.03, 'tier':'Administrative'},
    }

# Phase-specific directories
PHASE_03_DIR = PHASE_DIRS.get('phase_03', OUTPUT_DIR)
PHASE_06_DIR = PHASE_DIRS.get('phase_06', OUTPUT_DIR)
PHASE_08_DIR = PHASE_DIRS.get('phase_08', OUTPUT_DIR)
PHASE_09_DIR = PHASE_DIRS.get('phase_09', OUTPUT_DIR)

# Input paths
SUBJECT_DQI_PATH = PHASE_03_DIR / "master_subject_with_dqi.csv"
SITE_DQI_PATH = PHASE_03_DIR / "master_site_with_dqi.csv"
STUDY_DQI_PATH = PHASE_03_DIR / "master_study_with_dqi.csv"
REGION_DQI_PATH = PHASE_03_DIR / "master_region_with_dqi.csv"
COUNTRY_DQI_PATH = PHASE_03_DIR / "master_country_with_dqi.csv"
ANOMALIES_PATH = PHASE_06_DIR / "anomalies_detected.csv"
SITE_CLUSTERS_PATH = PHASE_08_DIR / "site_clusters.csv"
CLUSTER_PROFILES_PATH = PHASE_08_DIR / "cluster_profiles.csv"

# Output paths
ROOT_CAUSE_PATH = PHASE_09_DIR / "root_cause_analysis.csv"
ROOT_CAUSE_REPORT_PATH = PHASE_09_DIR / "root_cause_report.md"
ROOT_CAUSE_SUMMARY_PATH = PHASE_09_DIR / "root_cause_summary.json"
COOCCURRENCE_PATH = PHASE_09_DIR / "issue_cooccurrence.csv"
GEOGRAPHIC_PATH = PHASE_09_DIR / "geographic_patterns.csv"
FACTORS_PATH = PHASE_09_DIR / "contributing_factors.csv"

# Issue columns for analysis
ISSUE_COLUMNS = [
    'sae_pending_count',
    'missing_visit_count',
    'missing_pages_count',
    'lab_issues_count',
    'uncoded_meddra_count',
    'uncoded_whodd_count',
    'edrr_open_issues',
    'inactivated_forms_count',
    'max_days_outstanding',
    'max_days_page_missing',
]

# Site-level issue columns (with _sum suffix)
SITE_ISSUE_COLUMNS = [f"{col}_sum" if not col.startswith('max_') else col for col in ISSUE_COLUMNS]


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class RootCause:
    """Identified root cause with evidence."""
    cause_id: str
    category: str  # Safety, Completeness, Timeliness, Systemic, Geographic
    description: str
    severity: str  # Critical, High, Medium, Low
    confidence: float  # 0-1
    affected_sites: int
    affected_subjects: int
    evidence: List[str] = field(default_factory=list)
    contributing_factors: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CooccurrencePattern:
    """Pattern of issues occurring together."""
    issue_a: str
    issue_b: str
    cooccurrence_count: int
    cooccurrence_rate: float
    lift: float  # Ratio of observed to expected
    correlation: float
    interpretation: str


@dataclass
class GeographicPattern:
    """Geographic pattern of issues."""
    level: str  # Region, Country
    location: str
    dominant_issue: str
    issue_rate: float
    comparison_to_avg: float
    site_count: int
    risk_category: str


# ============================================================================
# ISSUE CO-OCCURRENCE ANALYSIS
# ============================================================================

def analyze_issue_cooccurrence(subject_df: pd.DataFrame) -> Tuple[List[CooccurrencePattern], pd.DataFrame]:
    """
    Analyze which issues tend to occur together.

    Uses lift metric: lift = P(A and B) / (P(A) * P(B))
    - lift > 1: Issues occur together more than expected
    - lift = 1: Independent
    - lift < 1: Issues occur together less than expected

    Returns:
        Tuple of (list of patterns, cooccurrence matrix DataFrame)
    """
    print("  Analyzing issue co-occurrence...")

    # Get binary presence of each issue
    issue_cols = [col for col in ISSUE_COLUMNS if col in subject_df.columns]

    if len(issue_cols) < 2:
        print("    [WARN] Not enough issue columns for co-occurrence analysis")
        return [], pd.DataFrame()

    # Create binary matrix
    binary_df = (subject_df[issue_cols] > 0).astype(int)
    n_subjects = len(binary_df)

    # Calculate individual issue rates
    issue_rates = binary_df.mean()

    patterns = []
    cooccurrence_matrix = pd.DataFrame(index=issue_cols, columns=issue_cols, dtype=float)

    for i, col_a in enumerate(issue_cols):
        for j, col_b in enumerate(issue_cols):
            if i >= j:
                # Diagonal and below - set to 1 for diagonal, mirror for below
                if i==j:
                    cooccurrence_matrix.loc[col_a, col_b] = 1.0
                continue

            # Calculate co-occurrence
            both = ((binary_df[col_a]==1) & (binary_df[col_b]==1)).sum()
            rate_a = issue_rates[col_a]
            rate_b = issue_rates[col_b]

            if rate_a==0 or rate_b==0:
                lift = 0
                correlation = 0
            else:
                observed_rate = both / n_subjects
                expected_rate = rate_a * rate_b
                lift = observed_rate / expected_rate if expected_rate > 0 else 0

                # Pearson correlation
                correlation = binary_df[col_a].corr(binary_df[col_b])

            cooccurrence_matrix.loc[col_a, col_b] = lift
            cooccurrence_matrix.loc[col_b, col_a] = lift

            # Only record significant patterns
            if lift > 1.2 and both >= 10:
                interpretation = _interpret_cooccurrence(col_a, col_b, lift, correlation)

                pattern = CooccurrencePattern(
                    issue_a=col_a,
                    issue_b=col_b,
                    cooccurrence_count=int(both),
                    cooccurrence_rate=round(both / n_subjects, 4),
                    lift=round(lift, 3),
                    correlation=round(correlation, 3) if not np.isnan(correlation) else 0,
                    interpretation=interpretation
                )
                patterns.append(pattern)

    # Sort by lift
    patterns.sort(key=lambda x:-x.lift)

    print(f"    Found {len(patterns)} significant co-occurrence patterns")

    return patterns, cooccurrence_matrix


def _interpret_cooccurrence(issue_a: str, issue_b: str, lift: float, correlation: float) -> str:
    """Generate human-readable interpretation of co-occurrence."""

    # Map issue names to readable names
    name_map = {
        'sae_pending_count':'SAE backlogs',
        'missing_visit_count':'missing visits',
        'missing_pages_count':'missing CRF pages',
        'lab_issues_count':'lab data issues',
        'uncoded_meddra_count':'uncoded adverse events',
        'uncoded_whodd_count':'uncoded medications',
        'edrr_open_issues':'reconciliation issues',
        'inactivated_forms_count':'form corrections',
        'max_days_outstanding':'data entry delays',
        'max_days_page_missing':'long-outstanding pages',
    }

    name_a = name_map.get(issue_a, issue_a)
    name_b = name_map.get(issue_b, issue_b)

    strength = "strongly" if lift > 2 else "moderately" if lift > 1.5 else "slightly"

    # Common interpretations
    if 'sae' in issue_a.lower() and 'meddra' in issue_b.lower():
        return f"Safety data entry backlog: Sites with {name_a} are {strength} likely to also have {name_b}, suggesting resource constraints in safety data processing."

    if 'missing_visit' in issue_a and 'missing_pages' in issue_b:
        return f"General data entry issues: {name_a.title()} and {name_b} {strength} co-occur, indicating systemic site capacity problems."

    if 'days' in issue_a.lower() or 'days' in issue_b.lower():
        return f"Timeliness correlation: Sites with {name_a} are {strength} likely to have {name_b}, suggesting chronic data entry delays."

    if 'uncoded' in issue_a.lower() and 'uncoded' in issue_b.lower():
        return f"Coding backlog: Both {name_a} and {name_b} {strength} co-occur, indicating coding resource constraints."

    return f"Sites with {name_a} are {lift:.1f}x more likely to also have {name_b}."


# ============================================================================
# GEOGRAPHIC PATTERN ANALYSIS
# ============================================================================

def analyze_geographic_patterns(site_df: pd.DataFrame,
                                country_df: pd.DataFrame = None,
                                region_df: pd.DataFrame = None) -> List[GeographicPattern]:
    """
    Identify geographic patterns in data quality issues.

    Returns:
        List of GeographicPattern objects
    """
    print("  Analyzing geographic patterns...")

    patterns = []

    # Get issue columns available in site data
    issue_cols = [col for col in SITE_ISSUE_COLUMNS if col in site_df.columns]

    # Also check for non-suffixed versions
    for col in ISSUE_COLUMNS:
        if col in site_df.columns and col not in issue_cols:
            issue_cols.append(col)

    if not issue_cols:
        print("    [WARN] No issue columns found in site data")
        return patterns

    # Portfolio averages
    portfolio_avgs = {}
    for col in issue_cols:
        if col in site_df.columns:
            # Rate of sites with this issue
            portfolio_avgs[col] = (site_df[col] > 0).mean()

    # Country-level analysis
    if 'country' in site_df.columns:
        countries = site_df['country'].unique()

        for country in countries:
            country_sites = site_df[site_df['country']==country]
            n_sites = len(country_sites)

            if n_sites < 3:
                continue

            # Find dominant issue
            issue_rates = {}
            for col in issue_cols:
                if col in country_sites.columns:
                    issue_rates[col] = (country_sites[col] > 0).mean()

            if not issue_rates:
                continue

            dominant_issue = max(issue_rates, key=issue_rates.get)
            dominant_rate = issue_rates[dominant_issue]
            portfolio_rate = portfolio_avgs.get(dominant_issue, 0)

            comparison = dominant_rate / portfolio_rate if portfolio_rate > 0 else 1.0

            # Only record if significantly different from portfolio
            if comparison > 1.3 or comparison < 0.7:
                # Determine risk category
                risk_cat = "High" if comparison > 1.5 else "Medium" if comparison > 1.3 else "Low"

                # Get country risk from country_df if available
                if country_df is not None and 'country_risk_category' in country_df.columns:
                    country_row = country_df[country_df['country']==country]
                    if not country_row.empty:
                        risk_cat = country_row['country_risk_category'].iloc[0]

                pattern = GeographicPattern(
                    level="Country",
                    location=country,
                    dominant_issue=dominant_issue,
                    issue_rate=round(dominant_rate, 4),
                    comparison_to_avg=round(comparison, 2),
                    site_count=n_sites,
                    risk_category=risk_cat
                )
                patterns.append(pattern)

    # Region-level analysis
    if 'region' in site_df.columns:
        regions = site_df['region'].unique()

        for region in regions:
            region_sites = site_df[site_df['region']==region]
            n_sites = len(region_sites)

            if n_sites < 5:
                continue

            # Find dominant issue
            issue_rates = {}
            for col in issue_cols:
                if col in region_sites.columns:
                    issue_rates[col] = (region_sites[col] > 0).mean()

            if not issue_rates:
                continue

            dominant_issue = max(issue_rates, key=issue_rates.get)
            dominant_rate = issue_rates[dominant_issue]
            portfolio_rate = portfolio_avgs.get(dominant_issue, 0)

            comparison = dominant_rate / portfolio_rate if portfolio_rate > 0 else 1.0

            if comparison > 1.2 or comparison < 0.8:
                risk_cat = "High" if comparison > 1.5 else "Medium" if comparison > 1.2 else "Low"

                if region_df is not None and 'region_risk_category' in region_df.columns:
                    region_row = region_df[region_df['region']==region]
                    if not region_row.empty:
                        risk_cat = region_row['region_risk_category'].iloc[0]

                pattern = GeographicPattern(
                    level="Region",
                    location=region,
                    dominant_issue=dominant_issue,
                    issue_rate=round(dominant_rate, 4),
                    comparison_to_avg=round(comparison, 2),
                    site_count=n_sites,
                    risk_category=risk_cat
                )
                patterns.append(pattern)

    # Sort by comparison ratio (highest deviation first)
    patterns.sort(key=lambda x:-abs(x.comparison_to_avg - 1))

    print(f"    Found {len(patterns)} geographic patterns")

    return patterns


# ============================================================================
# CONTRIBUTING FACTOR ANALYSIS
# ============================================================================

def analyze_contributing_factors(site_df: pd.DataFrame,
                                 subject_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Analyze factors that contribute to data quality issues.

    Factors examined:
    - Site size (subject count)
    - Geographic location
    - Study participation
    - Issue complexity (number of issue types)

    Returns:
        DataFrame with factor analysis results
    """
    print("  Analyzing contributing factors...")

    results = []

    # Factor 1: Site Size
    if 'subject_count' in site_df.columns and 'avg_dqi_score' in site_df.columns:
        # Bin sites by size
        size_bins = pd.qcut(site_df['subject_count'], q=4, labels=['Small', 'Medium', 'Large', 'Very Large'],
                            duplicates='drop')

        for size_label in size_bins.unique():
            if pd.isna(size_label):
                continue
            size_sites = site_df[size_bins==size_label]

            results.append({
                'factor':'Site Size',
                'category':str(size_label),
                'site_count':len(size_sites),
                'avg_dqi_score':round(size_sites['avg_dqi_score'].mean(), 4),
                'high_risk_rate':round((size_sites['site_risk_category']=='High').mean(),
                                       4) if 'site_risk_category' in size_sites else 0,
                'interpretation':_interpret_size_factor(str(size_label), size_sites)
            })

    # Factor 2: Study
    if 'study' in site_df.columns and 'avg_dqi_score' in site_df.columns:
        study_stats = site_df.groupby('study').agg({
            'site_id':'count',
            'avg_dqi_score':'mean',
            'high_risk_count':'sum' if 'high_risk_count' in site_df else 'size',
            'subject_count':'sum' if 'subject_count' in site_df else 'size'
        }).reset_index()

        for _, row in study_stats.iterrows():
            results.append({
                'factor':'Study',
                'category':row['study'],
                'site_count':int(row['site_id']),
                'avg_dqi_score':round(row['avg_dqi_score'], 4),
                'high_risk_rate':round(row['high_risk_count'] / max(row['subject_count'], 1),
                                       4) if 'high_risk_count' in row else 0,
                'interpretation':f"Study {row['study']} has {row['site_id']} sites with avg DQI {row['avg_dqi_score']:.4f}"
            })

    # Factor 3: Region
    if 'region' in site_df.columns and 'avg_dqi_score' in site_df.columns:
        region_stats = site_df.groupby('region').agg({
            'site_id':'count',
            'avg_dqi_score':'mean'
        }).reset_index()

        portfolio_avg = site_df['avg_dqi_score'].mean()

        for _, row in region_stats.iterrows():
            deviation = (row['avg_dqi_score'] - portfolio_avg) / portfolio_avg if portfolio_avg > 0 else 0

            results.append({
                'factor':'Region',
                'category':row['region'],
                'site_count':int(row['site_id']),
                'avg_dqi_score':round(row['avg_dqi_score'], 4),
                'high_risk_rate':round(deviation, 4),
                'interpretation':f"{row['region']}: {'Above' if deviation > 0 else 'Below'} portfolio average by {abs(deviation) * 100:.1f}%"
            })

    # Factor 4: Issue Complexity
    if 'n_issue_types' in site_df.columns or any(col in site_df.columns for col in SITE_ISSUE_COLUMNS):
        # Calculate issue complexity if not present
        if 'n_issue_types' not in site_df.columns:
            issue_cols = [col for col in SITE_ISSUE_COLUMNS if col in site_df.columns]
            site_df['n_issue_types'] = (site_df[issue_cols] > 0).sum(axis=1)

        complexity_bins = pd.cut(site_df['n_issue_types'], bins=[-1, 0, 2, 4, 100],
                                 labels=['None', 'Low', 'Medium', 'High'])

        for complexity in complexity_bins.unique():
            if pd.isna(complexity):
                continue
            complexity_sites = site_df[complexity_bins==complexity]

            results.append({
                'factor':'Issue Complexity',
                'category':str(complexity),
                'site_count':len(complexity_sites),
                'avg_dqi_score':round(complexity_sites['avg_dqi_score'].mean(),
                                      4) if 'avg_dqi_score' in complexity_sites else 0,
                'high_risk_rate':round((complexity_sites['site_risk_category']=='High').mean(),
                                       4) if 'site_risk_category' in complexity_sites else 0,
                'interpretation':_interpret_complexity_factor(str(complexity), complexity_sites)
            })

    factors_df = pd.DataFrame(results)
    print(f"    Analyzed {len(results)} factor categories")

    return factors_df


def _interpret_size_factor(size_label: str, sites: pd.DataFrame) -> str:
    """Interpret site size factor."""
    avg_dqi = sites['avg_dqi_score'].mean() if 'avg_dqi_score' in sites else 0

    if size_label=='Small':
        return f"Small sites (avg DQI: {avg_dqi:.4f}) may lack dedicated data management resources"
    elif size_label=='Very Large':
        return f"Very large sites (avg DQI: {avg_dqi:.4f}) handle high volume but may have process efficiencies"
    else:
        return f"{size_label} sites have average DQI of {avg_dqi:.4f}"


def _interpret_complexity_factor(complexity: str, sites: pd.DataFrame) -> str:
    """Interpret issue complexity factor."""
    n_sites = len(sites)

    if complexity=='None':
        return f"{n_sites} sites have no active issues - potential best practice sources"
    elif complexity=='High':
        return f"{n_sites} sites have multiple concurrent issues requiring systemic intervention"
    else:
        return f"{n_sites} sites with {complexity.lower()} issue complexity"


# ============================================================================
# ROOT CAUSE IDENTIFICATION
# ============================================================================

def identify_root_causes(site_df: pd.DataFrame,
                         subject_df: pd.DataFrame,
                         cooccurrence_patterns: List[CooccurrencePattern],
                         geographic_patterns: List[GeographicPattern],
                         factors_df: pd.DataFrame,
                         cluster_df: pd.DataFrame = None) -> List[RootCause]:
    """
    Synthesize all analyses to identify root causes.

    Returns:
        List of RootCause objects
    """
    print("  Identifying root causes...")

    root_causes = []
    cause_counter = 1

    # Get portfolio stats
    total_sites = len(site_df)
    total_subjects = len(subject_df) if subject_df is not None else site_df['subject_count'].sum()

    # -------------------------------------------------------------------------
    # Root Cause 1: Safety Data Processing Backlog
    # -------------------------------------------------------------------------
    sae_col = 'sae_pending_count_sum' if 'sae_pending_count_sum' in site_df.columns else 'sae_pending_count'
    meddra_col = 'uncoded_meddra_count_sum' if 'uncoded_meddra_count_sum' in site_df.columns else 'uncoded_meddra_count'

    if sae_col in site_df.columns:
        sae_sites = (site_df[sae_col] > 0).sum()
        sae_rate = sae_sites / total_sites

        if sae_rate > 0.1:
            # Check for co-occurrence with MedDRA
            cooccur_with_meddra = any(
                p for p in cooccurrence_patterns
                if ('sae' in p.issue_a.lower() or 'sae' in p.issue_b.lower()) and
                ('meddra' in p.issue_a.lower() or 'meddra' in p.issue_b.lower())
            )

            evidence = [
                f"{sae_sites} sites ({sae_rate * 100:.1f}%) have pending SAE reviews",
            ]

            if cooccur_with_meddra:
                evidence.append("SAE and MedDRA coding issues frequently co-occur")

            contributing = [
                "Insufficient safety data management resources",
                "Complex adverse event narratives requiring specialist review",
                "Training gaps in safety reporting procedures"
            ]

            actions = [
                "Hire additional safety data specialists",
                "Implement SAE triage system to prioritize reviews",
                "Deploy automated coding suggestions for common terms",
                "Weekly SAE backlog review meetings"
            ]

            root_causes.append(RootCause(
                cause_id=f"RC{cause_counter:03d}",
                category="Safety",
                description="Safety data processing backlog causing SAE review delays and coding gaps",
                severity="Critical" if sae_rate > 0.2 else "High",
                confidence=0.85,
                affected_sites=sae_sites,
                affected_subjects=int(
                    site_df[site_df[sae_col] > 0]['subject_count'].sum()) if 'subject_count' in site_df else 0,
                evidence=evidence,
                contributing_factors=contributing,
                recommended_actions=actions,
                metrics={'sae_site_rate':round(sae_rate, 4)}
            ))
            cause_counter += 1

    # -------------------------------------------------------------------------
    # Root Cause 2: Data Entry Capacity Issues
    # -------------------------------------------------------------------------
    visit_col = 'missing_visit_count_sum' if 'missing_visit_count_sum' in site_df.columns else 'missing_visit_count'
    pages_col = 'missing_pages_count_sum' if 'missing_pages_count_sum' in site_df.columns else 'missing_pages_count'

    if visit_col in site_df.columns and pages_col in site_df.columns:
        visit_sites = (site_df[visit_col] > 0).sum()
        pages_sites = (site_df[pages_col] > 0).sum()
        both_sites = ((site_df[visit_col] > 0) & (site_df[pages_col] > 0)).sum()

        visit_rate = visit_sites / total_sites
        pages_rate = pages_sites / total_sites

        if visit_rate > 0.15 or pages_rate > 0.15:
            evidence = [
                f"{visit_sites} sites ({visit_rate * 100:.1f}%) have missing visit data",
                f"{pages_sites} sites ({pages_rate * 100:.1f}%) have missing CRF pages",
            ]

            if both_sites > 0:
                evidence.append(f"{both_sites} sites have both issues simultaneously")

            contributing = [
                "Understaffed clinical sites",
                "Complex EDC system requiring extensive training",
                "High patient enrollment outpacing data entry capacity",
                "Competing priorities at investigator sites"
            ]

            actions = [
                "Assess site data management staffing levels",
                "Provide targeted EDC re-training",
                "Implement data entry reminders and escalation workflows",
                "Consider centralized data entry support for high-volume sites"
            ]

            root_causes.append(RootCause(
                cause_id=f"RC{cause_counter:03d}",
                category="Completeness",
                description="Insufficient site data entry capacity causing missing visit and CRF data",
                severity="High" if (visit_rate > 0.2 or pages_rate > 0.2) else "Medium",
                confidence=0.80,
                affected_sites=max(visit_sites, pages_sites),
                affected_subjects=int(site_df[(site_df[visit_col] > 0) | (site_df[pages_col] > 0)][
                                          'subject_count'].sum()) if 'subject_count' in site_df else 0,
                evidence=evidence,
                contributing_factors=contributing,
                recommended_actions=actions,
                metrics={'visit_site_rate':round(visit_rate, 4), 'pages_site_rate':round(pages_rate, 4)}
            ))
            cause_counter += 1

    # -------------------------------------------------------------------------
    # Root Cause 3: Geographic/Regional Issues
    # -------------------------------------------------------------------------
    high_risk_regions = [p for p in geographic_patterns if p.comparison_to_avg > 1.5 and p.level=="Region"]
    high_risk_countries = [p for p in geographic_patterns if p.comparison_to_avg > 1.5 and p.level=="Country"]

    if high_risk_regions or high_risk_countries:
        evidence = []
        affected_locations = []

        for pattern in high_risk_regions[:3]:
            evidence.append(
                f"Region {pattern.location}: {pattern.dominant_issue} rate is {pattern.comparison_to_avg:.1f}x portfolio average")
            affected_locations.append(pattern.location)

        for pattern in high_risk_countries[:3]:
            evidence.append(
                f"Country {pattern.location}: {pattern.dominant_issue} rate is {pattern.comparison_to_avg:.1f}x portfolio average")
            affected_locations.append(pattern.location)

        affected_site_count = \
        site_df[site_df['region'].isin(affected_locations) | site_df['country'].isin(affected_locations)][
            'site_id'].count() if 'region' in site_df else 0

        contributing = [
            "Regional regulatory requirements affecting data collection",
            "Language barriers impacting training effectiveness",
            "Local infrastructure limitations",
            "Cultural differences in clinical trial conduct"
        ]

        actions = [
            "Deploy region-specific training programs",
            "Assign dedicated regional monitors",
            "Translate key documentation to local languages",
            "Establish regional data management hubs"
        ]

        root_causes.append(RootCause(
            cause_id=f"RC{cause_counter:03d}",
            category="Geographic",
            description=f"Regional/country-specific issues in {', '.join(affected_locations[:3])}",
            severity="High" if len(high_risk_regions) > 1 or len(high_risk_countries) > 2 else "Medium",
            confidence=0.75,
            affected_sites=affected_site_count,
            affected_subjects=0,
            evidence=evidence,
            contributing_factors=contributing,
            recommended_actions=actions,
            metrics={'high_risk_regions':len(high_risk_regions), 'high_risk_countries':len(high_risk_countries)}
        ))
        cause_counter += 1

    # -------------------------------------------------------------------------
    # Root Cause 4: Timeliness/Staleness Issues
    # -------------------------------------------------------------------------
    days_col = 'max_days_outstanding' if 'max_days_outstanding' in site_df.columns else None

    if days_col:
        stale_sites = (site_df[days_col] > 30).sum()
        very_stale_sites = (site_df[days_col] > 60).sum()
        stale_rate = stale_sites / total_sites

        if stale_rate > 0.1:
            evidence = [
                f"{stale_sites} sites ({stale_rate * 100:.1f}%) have data outstanding > 30 days",
                f"{very_stale_sites} sites have data outstanding > 60 days"
            ]

            contributing = [
                "Lack of real-time data entry expectations",
                "No automated reminders for overdue data",
                "Site workload imbalances",
                "Query resolution bottlenecks"
            ]

            actions = [
                "Implement automated stale data alerts",
                "Set and communicate data entry SLAs",
                "Weekly data currency reviews with site coordinators",
                "Prioritize query resolution to unblock data entry"
            ]

            root_causes.append(RootCause(
                cause_id=f"RC{cause_counter:03d}",
                category="Timeliness",
                description="Chronic data entry delays resulting in stale trial data",
                severity="High" if very_stale_sites > 10 else "Medium",
                confidence=0.85,
                affected_sites=stale_sites,
                affected_subjects=int(
                    site_df[site_df[days_col] > 30]['subject_count'].sum()) if 'subject_count' in site_df else 0,
                evidence=evidence,
                contributing_factors=contributing,
                recommended_actions=actions,
                metrics={'stale_site_rate':round(stale_rate, 4), 'very_stale_sites':very_stale_sites}
            ))
            cause_counter += 1

    # -------------------------------------------------------------------------
    # Root Cause 5: Systemic Multi-Issue Sites
    # -------------------------------------------------------------------------
    if 'n_issue_types' in site_df.columns or cluster_df is not None:
        if cluster_df is not None and 'cluster_name' in cluster_df.columns:
            systemic_sites = cluster_df[
                cluster_df['cluster_name'].str.contains('Systemic|Issues', case=False, na=False)]
            n_systemic = len(systemic_sites)
        else:
            issue_cols = [col for col in SITE_ISSUE_COLUMNS if col in site_df.columns]
            site_df['_n_issues'] = (site_df[issue_cols] > 0).sum(axis=1)
            n_systemic = (site_df['_n_issues'] >= 4).sum()
            systemic_sites = site_df[site_df['_n_issues'] >= 4]

        if n_systemic > 5:
            evidence = [
                f"{n_systemic} sites have 4+ concurrent issue types",
                "These sites require comprehensive intervention rather than targeted fixes"
            ]

            contributing = [
                "Fundamental site capability gaps",
                "Inadequate site selection/qualification",
                "Loss of key site personnel",
                "Lack of sponsor oversight"
            ]

            actions = [
                "Conduct site capability assessments",
                "Implement intensive monitoring protocols",
                "Consider site remediation plans or replacement",
                "Assign dedicated site managers"
            ]

            root_causes.append(RootCause(
                cause_id=f"RC{cause_counter:03d}",
                category="Systemic",
                description="Sites with multiple concurrent issues indicating fundamental capability gaps",
                severity="Critical" if n_systemic > 20 else "High",
                confidence=0.90,
                affected_sites=n_systemic,
                affected_subjects=int(
                    systemic_sites['subject_count'].sum()) if 'subject_count' in systemic_sites else 0,
                evidence=evidence,
                contributing_factors=contributing,
                recommended_actions=actions,
                metrics={'systemic_site_count':n_systemic}
            ))
            cause_counter += 1

    # Sort by severity and confidence
    severity_order = {'Critical':0, 'High':1, 'Medium':2, 'Low':3}
    root_causes.sort(key=lambda x:(severity_order.get(x.severity, 4), -x.confidence))

    print(f"    Identified {len(root_causes)} root causes")

    return root_causes


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_report(root_causes: List[RootCause],
                    cooccurrence_patterns: List[CooccurrencePattern],
                    geographic_patterns: List[GeographicPattern],
                    factors_df: pd.DataFrame,
                    site_df: pd.DataFrame) -> str:
    """Generate markdown report for root cause analysis."""
    lines = []

    lines.append("# JAVELIN.AI Root Cause Analysis Report")
    lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"\n**Sites Analyzed:** {len(site_df):,}")
    lines.append(f"**Root Causes Identified:** {len(root_causes)}")

    # Executive Summary
    lines.append("\n## Executive Summary\n")

    critical_causes = [rc for rc in root_causes if rc.severity=="Critical"]
    high_causes = [rc for rc in root_causes if rc.severity=="High"]

    lines.append(f"This analysis identified **{len(root_causes)} root causes** of data quality issues:")
    lines.append(f"- 🔴 Critical: {len(critical_causes)}")
    lines.append(f"- 🟠 High: {len(high_causes)}")
    lines.append(f"- 🟡 Medium: {len([rc for rc in root_causes if rc.severity=='Medium'])}")

    if critical_causes:
        lines.append("\n### Immediate Attention Required\n")
        for rc in critical_causes:
            lines.append(f"- **{rc.description}** ({rc.affected_sites} sites affected)")

    # Detailed Root Causes
    lines.append("\n## Identified Root Causes\n")

    for rc in root_causes:
        severity_emoji = {"Critical":"🔴", "High":"🟠", "Medium":"🟡", "Low":"🟢"}.get(rc.severity, "⚪")

        lines.append(f"### {rc.cause_id}: {rc.description} {severity_emoji}")
        lines.append(f"\n**Category:** {rc.category}")
        lines.append(f"**Severity:** {rc.severity}")
        lines.append(f"**Confidence:** {rc.confidence * 100:.0f}%")
        lines.append(f"**Affected Sites:** {rc.affected_sites:,}")

        if rc.evidence:
            lines.append("\n**Evidence:**")
            for e in rc.evidence:
                lines.append(f"- {e}")

        if rc.contributing_factors:
            lines.append("\n**Contributing Factors:**")
            for f in rc.contributing_factors:
                lines.append(f"- {f}")

        if rc.recommended_actions:
            lines.append("\n**Recommended Actions:**")
            for i, a in enumerate(rc.recommended_actions, 1):
                lines.append(f"{i}. {a}")

        lines.append("")

    # Issue Co-occurrence Patterns
    if cooccurrence_patterns:
        lines.append("\n## Issue Co-occurrence Patterns\n")
        lines.append("These patterns show which issues tend to appear together, suggesting common underlying causes.\n")

        lines.append("| Issue A | Issue B | Lift | Correlation | Interpretation |")
        lines.append("|---------|---------|------|-------------|----------------|")

        for p in cooccurrence_patterns[:10]:
            lines.append(
                f"| {p.issue_a[:20]} | {p.issue_b[:20]} | {p.lift:.2f} | {p.correlation:.2f} | {p.interpretation[:50]}... |")

    # Geographic Patterns
    if geographic_patterns:
        lines.append("\n## Geographic Patterns\n")

        region_patterns = [p for p in geographic_patterns if p.level=="Region"]
        country_patterns = [p for p in geographic_patterns if p.level=="Country"]

        if region_patterns:
            lines.append("### Regional Patterns\n")
            lines.append("| Region | Dominant Issue | vs. Portfolio | Sites | Risk |")
            lines.append("|--------|---------------|---------------|-------|------|")
            for p in region_patterns[:5]:
                lines.append(
                    f"| {p.location} | {p.dominant_issue} | {p.comparison_to_avg:.1f}x | {p.site_count} | {p.risk_category} |")

        if country_patterns:
            lines.append("\n### Country Patterns\n")
            lines.append("| Country | Dominant Issue | vs. Portfolio | Sites | Risk |")
            lines.append("|---------|---------------|---------------|-------|------|")
            for p in country_patterns[:10]:
                lines.append(
                    f"| {p.location} | {p.dominant_issue} | {p.comparison_to_avg:.1f}x | {p.site_count} | {p.risk_category} |")

    # Contributing Factors Summary
    if not factors_df.empty:
        lines.append("\n## Contributing Factor Analysis\n")

        for factor in factors_df['factor'].unique():
            factor_data = factors_df[factors_df['factor']==factor]
            lines.append(f"\n### {factor}\n")

            lines.append("| Category | Sites | Avg DQI | High-Risk Rate |")
            lines.append("|----------|-------|---------|----------------|")

            for _, row in factor_data.iterrows():
                lines.append(
                    f"| {row['category']} | {row['site_count']} | {row['avg_dqi_score']:.4f} | {row['high_risk_rate'] * 100:.1f}% |")

    # Action Plan Summary
    lines.append("\n## Consolidated Action Plan\n")

    all_actions = []
    for rc in root_causes:
        for action in rc.recommended_actions:
            all_actions.append({
                'action':action,
                'severity':rc.severity,
                'category':rc.category,
                'cause':rc.cause_id
            })

    # Group by category
    actions_by_category = defaultdict(list)
    for a in all_actions:
        actions_by_category[a['category']].append(a)

    for category, actions in actions_by_category.items():
        lines.append(f"\n### {category} Actions\n")
        seen = set()
        for a in actions:
            if a['action'] not in seen:
                priority = "🔴" if a['severity']=="Critical" else "🟠" if a['severity']=="High" else "🟡"
                lines.append(f"- {priority} {a['action']}")
                seen.add(a['action'])

    lines.append("\n---")
    lines.append(f"\n*Report generated by JAVELIN.AI Root Cause Analysis Module*")

    return "\n".join(lines)


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_root_cause_analysis(include_clusters: bool = True,
                            top_issues: int = 10) -> bool:
    """
    Main function to run root cause analysis.

    Args:
        include_clusters: Whether to incorporate cluster analysis from Phase 08
        top_issues: Number of top issues to analyze

    Returns:
        True if successful
    """
    print("=" * 70)
    print("JAVELIN.AI - ROOT CAUSE ANALYSIS")
    print("=" * 70)

    if _USING_CONFIG:
        print("(Using centralized config with PHASE_DIRS)")

    print(f"\nInput Directory (Phase 03): {PHASE_03_DIR}")
    print(f"Input Directory (Phase 08): {PHASE_08_DIR}")
    print(f"Output Directory (Phase 09): {PHASE_09_DIR}")

    # Load data
    print("\n" + "=" * 70)
    print("STEP 1: LOAD DATA")
    print("=" * 70)

    if not SITE_DQI_PATH.exists():
        print(f"\n[ERROR] Site DQI file not found: {SITE_DQI_PATH}")
        print("Please run Phase 03 first.")
        return False

    site_df = pd.read_csv(SITE_DQI_PATH)
    print(f"  [OK] Loaded {len(site_df):,} sites")

    # Load subject data if available
    subject_df = None
    if SUBJECT_DQI_PATH.exists():
        subject_df = pd.read_csv(SUBJECT_DQI_PATH)
        print(f"  [OK] Loaded {len(subject_df):,} subjects")

    # Load region/country data if available
    region_df = pd.read_csv(REGION_DQI_PATH) if REGION_DQI_PATH.exists() else None
    country_df = pd.read_csv(COUNTRY_DQI_PATH) if COUNTRY_DQI_PATH.exists() else None

    if region_df is not None:
        print(f"  [OK] Loaded {len(region_df)} regions")
    if country_df is not None:
        print(f"  [OK] Loaded {len(country_df)} countries")

    # Load cluster data if available
    cluster_df = None
    if include_clusters and SITE_CLUSTERS_PATH.exists():
        cluster_df = pd.read_csv(SITE_CLUSTERS_PATH)
        print(f"  [OK] Loaded cluster assignments for {len(cluster_df)} sites")

    # Issue Co-occurrence Analysis
    print("\n" + "=" * 70)
    print("STEP 2: ISSUE CO-OCCURRENCE ANALYSIS")
    print("=" * 70)

    if subject_df is not None:
        cooccurrence_patterns, cooccurrence_matrix = analyze_issue_cooccurrence(subject_df)
    else:
        cooccurrence_patterns, cooccurrence_matrix = [], pd.DataFrame()

    if cooccurrence_patterns:
        print(f"\n  Top Co-occurrence Patterns:")
        for p in cooccurrence_patterns[:5]:
            print(f"    {p.issue_a} + {p.issue_b}: lift={p.lift:.2f}")

    # Geographic Pattern Analysis
    print("\n" + "=" * 70)
    print("STEP 3: GEOGRAPHIC PATTERN ANALYSIS")
    print("=" * 70)

    geographic_patterns = analyze_geographic_patterns(site_df, country_df, region_df)

    if geographic_patterns:
        print(f"\n  Top Geographic Patterns:")
        for p in geographic_patterns[:5]:
            print(f"    {p.level} {p.location}: {p.dominant_issue} ({p.comparison_to_avg:.1f}x avg)")

    # Contributing Factor Analysis
    print("\n" + "=" * 70)
    print("STEP 4: CONTRIBUTING FACTOR ANALYSIS")
    print("=" * 70)

    factors_df = analyze_contributing_factors(site_df, subject_df)

    # Root Cause Identification
    print("\n" + "=" * 70)
    print("STEP 5: ROOT CAUSE IDENTIFICATION")
    print("=" * 70)

    root_causes = identify_root_causes(
        site_df=site_df,
        subject_df=subject_df,
        cooccurrence_patterns=cooccurrence_patterns,
        geographic_patterns=geographic_patterns,
        factors_df=factors_df,
        cluster_df=cluster_df
    )

    print(f"\n  Identified Root Causes:")
    for rc in root_causes:
        severity_emoji = {"Critical":"🔴", "High":"🟠", "Medium":"🟡", "Low":"🟢"}.get(rc.severity, "⚪")
        print(f"    {severity_emoji} {rc.cause_id}: {rc.description[:60]}...")

    # Save outputs
    print("\n" + "=" * 70)
    print("STEP 6: SAVE OUTPUTS")
    print("=" * 70)

    PHASE_09_DIR.mkdir(parents=True, exist_ok=True)

    # Save root causes
    root_causes_data = [asdict(rc) for rc in root_causes]
    root_causes_df = pd.DataFrame(root_causes_data)
    root_causes_df.to_csv(ROOT_CAUSE_PATH, index=False, encoding='utf-8')
    print(f"  [OK] Saved: {ROOT_CAUSE_PATH}")

    # Save co-occurrence matrix
    if not cooccurrence_matrix.empty:
        cooccurrence_matrix.to_csv(COOCCURRENCE_PATH, encoding='utf-8')
        print(f"  [OK] Saved: {COOCCURRENCE_PATH}")

    # Save geographic patterns
    if geographic_patterns:
        geo_df = pd.DataFrame([asdict(p) for p in geographic_patterns])
        geo_df.to_csv(GEOGRAPHIC_PATH, index=False, encoding='utf-8')
        print(f"  [OK] Saved: {GEOGRAPHIC_PATH}")

    # Save contributing factors
    if not factors_df.empty:
        factors_df.to_csv(FACTORS_PATH, index=False)
        print(f"  [OK] Saved: {FACTORS_PATH}")

    # Save summary JSON
    summary = {
        'generated':datetime.now().isoformat(),
        'total_sites':len(site_df),
        'total_subjects':len(subject_df) if subject_df is not None else 0,
        'root_causes_count':len(root_causes),
        'critical_causes':len([rc for rc in root_causes if rc.severity=="Critical"]),
        'high_causes':len([rc for rc in root_causes if rc.severity=="High"]),
        'cooccurrence_patterns':len(cooccurrence_patterns),
        'geographic_patterns':len(geographic_patterns),
        'root_causes':[
            {
                'id':rc.cause_id,
                'category':rc.category,
                'description':rc.description,
                'severity':rc.severity,
                'affected_sites':rc.affected_sites
            }
            for rc in root_causes
        ]
    }

    with open(ROOT_CAUSE_SUMMARY_PATH, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"  [OK] Saved: {ROOT_CAUSE_SUMMARY_PATH}")

    # Generate report
    report = generate_report(root_causes, cooccurrence_patterns, geographic_patterns, factors_df, site_df)
    with open(ROOT_CAUSE_REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  [OK] Saved: {ROOT_CAUSE_REPORT_PATH}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    critical = len([rc for rc in root_causes if rc.severity=="Critical"])
    high = len([rc for rc in root_causes if rc.severity=="High"])
    medium = len([rc for rc in root_causes if rc.severity=="Medium"])

    print(f"""
Root Causes Identified: {len(root_causes)}

Severity Distribution:
  🔴 Critical: {critical}
  🟠 High: {high}
  🟡 Medium: {medium}

Analysis Components:
  - Co-occurrence Patterns: {len(cooccurrence_patterns)}
  - Geographic Patterns: {len(geographic_patterns)}
  - Contributing Factors: {len(factors_df)} categories
""")

    if root_causes:
        print("Top Root Causes:")
        for rc in root_causes[:3]:
            print(f"  - {rc.cause_id}: {rc.description[:50]}...")

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"""
All phases completed! Review the outputs:

Phase 03: DQI Scores
  - {PHASE_03_DIR}/master_*_with_dqi.csv

Phase 06: Anomaly Detection
  - {PHASE_06_DIR}/anomalies_detected.csv

Phase 08: Site Clustering
  - {PHASE_08_DIR}/site_clusters.csv

Phase 09: Root Cause Analysis
  - {PHASE_09_DIR}/root_cause_report.md

For a comprehensive view, start with:
  {ROOT_CAUSE_REPORT_PATH}
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description="JAVELIN.AI Root Cause Analysis")
    parser.add_argument("--include-clusters", action="store_true", default=True,
                        help="Include cluster analysis from Phase 08")
    parser.add_argument("--no-clusters", action="store_true",
                        help="Skip cluster integration")
    parser.add_argument("--top-sites", type=int, default=10,
                        help="Number of top issues to analyze")

    args = parser.parse_args()

    success = run_root_cause_analysis(
        include_clusters=not args.no_clusters,
        top_issues=args.top_sites
    )

    if not success:
        exit(1)
