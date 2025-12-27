"""
Javelin.AI - Step 3: Calculate Data Quality Index (DQI)
========================================================

REVISED METHODOLOGY (Based on Data Analysis):
---------------------------------------------
After analyzing the data, we found that:
1. DQ issues do NOT predict SAE (negative correlation)
2. This is because subject_status drives both metrics differently
3. Trying to use ML to "learn" weights gives meaningless results

CORRECT APPROACH:
Instead of predicting SAE, we directly measure Data Quality Risk using:
1. Domain knowledge weights (clinical importance of each issue type)
2. Severity scaling (more issues = exponentially worse)
3. Timeliness factors (days outstanding matters)

The DQI answers: "How much data quality risk does this subject/site have?"
NOT: "Will this subject have an SAE?"

This is more honest and more actionable.

Usage:
    python src/03_calculate_dqi.py

Output:
    - outputs/master_subject_with_dqi.csv
    - outputs/master_site_with_dqi.csv
    - outputs/dqi_weights.csv
    - outputs/dqi_model_report.txt
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

OUTPUT_DIR = Path("outputs")
MASTER_SUBJECT_PATH = OUTPUT_DIR / "master_subject.csv"

# Domain-knowledge based weights
# These reflect CLINICAL IMPORTANCE of each data quality issue
# Rationale provided for each

DQI_WEIGHTS = {
    # SAFETY-RELATED (Highest Priority)
    'sae_pending_count': {
        'weight': 0.25,
        'rationale': 'Pending SAE reviews are critical safety signals requiring immediate attention'
    },
    'uncoded_meddra_count': {
        'weight': 0.15,
        'rationale': 'Uncoded adverse events = untracked safety signals'
    },

    # COMPLETENESS (High Priority)
    'missing_visit_count': {
        'weight': 0.12,
        'rationale': 'Missing visits = missing safety monitoring touchpoints'
    },
    'missing_pages_count': {
        'weight': 0.10,
        'rationale': 'Missing CRF pages = incomplete subject record'
    },
    'lab_issues_count': {
        'weight': 0.10,
        'rationale': 'Lab issues can mask safety signals in bloodwork'
    },

    # TIMELINESS (Medium Priority)
    'max_days_outstanding': {
        'weight': 0.08,
        'rationale': 'Delayed data entry reduces real-time safety visibility'
    },
    'max_days_page_missing': {
        'weight': 0.06,
        'rationale': 'Long-missing pages indicate systemic site issues'
    },

    # CODING & RECONCILIATION (Lower Priority)
    'uncoded_whodd_count': {
        'weight': 0.06,
        'rationale': 'Uncoded drug terms affect medication tracking'
    },
    'edrr_open_issues': {
        'weight': 0.05,
        'rationale': 'External data reconciliation issues'
    },
    'inactivated_forms_count': {
        'weight': 0.03,
        'rationale': 'Inactivated forms indicate data corrections (lower risk)'
    },
}

# Verify weights sum to 1
assert abs(sum(w['weight'] for w in DQI_WEIGHTS.values()) - 1.0) < 0.001, "Weights must sum to 1"


# ============================================================================
# DQI CALCULATION FUNCTIONS
# ============================================================================

def normalize_feature(series, method='robust'):
    """
    Normalize a feature to 0-1 scale.
    Uses robust scaling (percentile-based) to handle outliers.
    """
    if series.max() == 0:
        return pd.Series(0, index=series.index)

    if method == 'robust':
        # Use 95th percentile as max to reduce outlier impact
        p95 = series.quantile(0.95)
        if p95 > 0:
            normalized = series.clip(upper=p95) / p95
        else:
            normalized = series / series.max()
    else:
        # Simple min-max
        normalized = series / series.max()

    return normalized.clip(0, 1).fillna(0)


def calculate_subject_dqi(df):
    """
    Calculate DQI score for each subject.

    DQI = Weighted sum of normalized issue counts
    Higher DQI = More data quality issues = Higher risk
    """
    df = df.copy()

    # Initialize score
    df['dqi_score'] = 0.0

    # Calculate weighted components
    components = {}
    for feature, config in DQI_WEIGHTS.items():
        if feature in df.columns:
            # Normalize the feature
            normalized = normalize_feature(df[feature])
            weighted = normalized * config['weight']

            df[f'{feature}_component'] = weighted
            df['dqi_score'] += weighted

            components[feature] = {
                'weight': config['weight'],
                'non_zero_subjects': (df[feature] > 0).sum(),
                'mean_raw': df[feature].mean(),
                'mean_component': weighted.mean()
            }

    # Add severity multiplier for subjects with multiple issue types
    issue_features = [f for f in DQI_WEIGHTS.keys() if f in df.columns]
    df['n_issue_types'] = (df[issue_features] > 0).sum(axis=1)

    # Subjects with 3+ issue types get a severity boost
    df['severity_multiplier'] = 1.0
    df.loc[df['n_issue_types'] >= 3, 'severity_multiplier'] = 1.3
    df.loc[df['n_issue_types'] >= 5, 'severity_multiplier'] = 1.5

    df['dqi_score_adjusted'] = df['dqi_score'] * df['severity_multiplier']

    # Cap at 1.0
    df['dqi_score_adjusted'] = df['dqi_score_adjusted'].clip(0, 1)

    return df, components


def assign_risk_categories(df, score_column='dqi_score_adjusted'):
    """
    Assign risk categories based on DQI score distribution.

    Strategy:
    - Subjects with ZERO issues = "Low" (no action needed)
    - Among subjects WITH issues, stratify into High/Medium/Low

    Categories:
    - High: Top 15% of subjects with issues
    - Medium: Next 35% of subjects with issues
    - Low: Everyone else (including zero-issue subjects)
    """
    df = df.copy()

    # First, identify subjects with any issues
    df['has_issues'] = (df[score_column] > 0).astype(int)

    # Get thresholds from subjects WITH issues only
    scores_with_issues = df[df['has_issues'] == 1][score_column]

    if len(scores_with_issues) > 0:
        # Top 15% = High, Next 35% = Medium, Bottom 50% of those with issues = Low
        high_threshold = scores_with_issues.quantile(0.85)
        medium_threshold = scores_with_issues.quantile(0.50)

        # Ensure minimum thresholds make sense
        high_threshold = max(high_threshold, 0.10)
        medium_threshold = max(medium_threshold, 0.02)
    else:
        high_threshold = 0.10
        medium_threshold = 0.02

    # Assign categories
    df['risk_category'] = 'Low'
    df.loc[(df[score_column] > 0) & (df[score_column] <= medium_threshold), 'risk_category'] = 'Low'
    df.loc[df[score_column] > medium_threshold, 'risk_category'] = 'Medium'
    df.loc[df[score_column] > high_threshold, 'risk_category'] = 'High'

    return df, high_threshold, medium_threshold


def aggregate_site_dqi(df):
    """
    Aggregate subject-level DQI to site level.
    """
    # Define aggregations
    agg_dict = {
        'subject_id': 'count',
        'dqi_score': ['mean', 'max', 'std'],
        'dqi_score_adjusted': ['mean', 'max'],
        'n_issue_types': 'mean',
    }

    # Add issue counts
    for feature in DQI_WEIGHTS.keys():
        if feature in df.columns:
            agg_dict[feature] = 'sum'

    # Add SAE for reference
    if 'sae_total_count' in df.columns:
        agg_dict['sae_total_count'] = 'sum'

    site_agg = df.groupby(['study', 'site_id', 'country', 'region']).agg(agg_dict).reset_index()

    # Flatten column names
    site_agg.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col
                        for col in site_agg.columns]

    # Rename for clarity
    site_agg = site_agg.rename(columns={
        'subject_id_count': 'subject_count',
        'dqi_score_mean': 'avg_dqi_score',
        'dqi_score_max': 'max_dqi_score',
        'dqi_score_std': 'std_dqi_score',
        'dqi_score_adjusted_mean': 'avg_dqi_adjusted',
        'dqi_score_adjusted_max': 'max_dqi_adjusted',
        'n_issue_types_mean': 'avg_issue_types',
    })

    # Site risk category based on average adjusted score
    # Use percentiles among sites WITH any issues
    sites_with_issues = site_agg[site_agg['avg_dqi_adjusted'] > 0]['avg_dqi_adjusted']
    if len(sites_with_issues) > 0:
        high_threshold = sites_with_issues.quantile(0.85)
        medium_threshold = sites_with_issues.quantile(0.50)
        high_threshold = max(high_threshold, 0.05)
        medium_threshold = max(medium_threshold, 0.01)
    else:
        high_threshold = 0.05
        medium_threshold = 0.01

    site_agg['site_risk_category'] = 'Low'
    site_agg.loc[site_agg['avg_dqi_adjusted'] > medium_threshold, 'site_risk_category'] = 'Medium'
    site_agg.loc[site_agg['avg_dqi_adjusted'] > high_threshold, 'site_risk_category'] = 'High'

    return site_agg


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def calculate_dqi():
    """Main function to calculate DQI scores."""

    print("=" * 70)
    print("JAVELIN.AI - DATA QUALITY INDEX (DQI) CALCULATION")
    print("=" * 70)

    print("\nMethodology: Domain-Knowledge Based Scoring")
    print("           (ML prediction not appropriate - see analysis)")

    # Check prerequisites
    if not MASTER_SUBJECT_PATH.exists():
        print(f"\nERROR: {MASTER_SUBJECT_PATH} not found!")
        print("   Run 02_build_master_table.py first.")
        return

    # Load data
    print(f"\nLoading {MASTER_SUBJECT_PATH}...")
    df = pd.read_csv(MASTER_SUBJECT_PATH)
    print(f"   Loaded {len(df):,} subjects from {df['study'].nunique()} studies")

    # =========================================================================
    # STEP 1: Display weight rationale
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: DQI COMPONENT WEIGHTS (Domain Knowledge)")
    print("=" * 70)

    print(f"\n{'Feature':<30} {'Weight':>8}  Rationale")
    print("-" * 80)
    for feature, config in sorted(DQI_WEIGHTS.items(), key=lambda x: -x[1]['weight']):
        print(f"{feature:<30} {config['weight']:>7.0%}  {config['rationale']}")

    # =========================================================================
    # STEP 2: Calculate subject-level DQI
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: CALCULATE SUBJECT-LEVEL DQI")
    print("=" * 70)

    df, components = calculate_subject_dqi(df)

    print("\nFeature contributions:")
    print(f"{'Feature':<30} {'Weight':>8} {'Subjects':>10} {'Avg Raw':>10}")
    print("-" * 65)
    for feature, stats in sorted(components.items(), key=lambda x: -DQI_WEIGHTS[x[0]]['weight']):
        print(f"{feature:<30} {stats['weight']:>7.0%} {stats['non_zero_subjects']:>10,} {stats['mean_raw']:>10.2f}")

    # =========================================================================
    # STEP 3: Assign risk categories
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 3: ASSIGN RISK CATEGORIES")
    print("=" * 70)

    df, high_thresh, med_thresh = assign_risk_categories(df)

    print(f"\nThresholds:")
    print(f"  High Risk:   DQI > {high_thresh:.3f}")
    print(f"  Medium Risk: DQI > {med_thresh:.3f}")
    print(f"  Low Risk:    DQI <= {med_thresh:.3f}")

    print(f"\nDQI Score Statistics:")
    print(f"  Min:    {df['dqi_score_adjusted'].min():.3f}")
    print(f"  Max:    {df['dqi_score_adjusted'].max():.3f}")
    print(f"  Mean:   {df['dqi_score_adjusted'].mean():.3f}")
    print(f"  Median: {df['dqi_score_adjusted'].median():.3f}")
    print(f"  Std:    {df['dqi_score_adjusted'].std():.3f}")

    risk_dist = df['risk_category'].value_counts()
    print(f"\nRisk Distribution:")
    for cat in ['High', 'Medium', 'Low']:
        count = risk_dist.get(cat, 0)
        pct = count / len(df) * 100
        print(f"  {cat}: {count:,} subjects ({pct:.1f}%)")

    # =========================================================================
    # STEP 4: Aggregate to site level
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 4: AGGREGATE TO SITE LEVEL")
    print("=" * 70)

    site_agg = aggregate_site_dqi(df)
    print(f"\nAggregated to {len(site_agg):,} sites")

    site_risk_dist = site_agg['site_risk_category'].value_counts()
    print(f"\nSite Risk Distribution:")
    for cat in ['High', 'Medium', 'Low']:
        count = site_risk_dist.get(cat, 0)
        pct = count / len(site_agg) * 100
        print(f"  {cat}: {count} sites ({pct:.1f}%)")

    # Top 10 highest risk sites
    print(f"\nTop 10 Highest Risk Sites:")
    top_sites = site_agg.nlargest(10, 'avg_dqi_adjusted')[
        ['study', 'site_id', 'subject_count', 'avg_dqi_adjusted', 'site_risk_category']
    ]
    print(top_sites.to_string(index=False))

    # =========================================================================
    # STEP 5: Save outputs
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 5: SAVE OUTPUTS")
    print("=" * 70)

    # Save subject table
    df.to_csv(OUTPUT_DIR / "master_subject_with_dqi.csv", index=False)
    print(f"Saved: outputs/master_subject_with_dqi.csv ({len(df):,} subjects)")

    # Save site table
    site_agg.to_csv(OUTPUT_DIR / "master_site_with_dqi.csv", index=False)
    print(f"Saved: outputs/master_site_with_dqi.csv ({len(site_agg):,} sites)")

    # Save weights
    weights_df = pd.DataFrame([
        {'feature': k, 'weight': v['weight'], 'rationale': v['rationale']}
        for k, v in DQI_WEIGHTS.items()
    ]).sort_values('weight', ascending=False)
    weights_df.to_csv(OUTPUT_DIR / "dqi_weights.csv", index=False)
    print(f"Saved: outputs/dqi_weights.csv")

    # Save report
    report_path = OUTPUT_DIR / "dqi_model_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("JAVELIN.AI - DQI MODEL REPORT\n")
        f.write("=" * 60 + "\n\n")

        f.write("METHODOLOGY\n")
        f.write("-" * 40 + "\n")
        f.write("Approach: Domain-Knowledge Based Scoring\n")
        f.write("Reason: Signal analysis showed DQ metrics do not predict SAE.\n")
        f.write("        ML-based weights would be meaningless.\n")
        f.write("        Domain knowledge provides actionable, interpretable weights.\n\n")

        f.write("WEIGHT RATIONALE\n")
        f.write("-" * 40 + "\n")
        for feature, config in sorted(DQI_WEIGHTS.items(), key=lambda x: -x[1]['weight']):
            f.write(f"{feature}: {config['weight']:.0%}\n")
            f.write(f"  {config['rationale']}\n\n")

        f.write("DATASET SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total Subjects: {len(df):,}\n")
        f.write(f"Total Sites: {len(site_agg):,}\n")
        f.write(f"Studies: {df['study'].nunique()}\n\n")

        f.write("DQI SCORE DISTRIBUTION\n")
        f.write("-" * 40 + "\n")
        f.write(f"Min: {df['dqi_score_adjusted'].min():.3f}\n")
        f.write(f"Max: {df['dqi_score_adjusted'].max():.3f}\n")
        f.write(f"Mean: {df['dqi_score_adjusted'].mean():.3f}\n")
        f.write(f"Median: {df['dqi_score_adjusted'].median():.3f}\n\n")

        f.write("RISK DISTRIBUTION\n")
        f.write("-" * 40 + "\n")
        for cat in ['High', 'Medium', 'Low']:
            count = risk_dist.get(cat, 0)
            pct = count / len(df) * 100
            f.write(f"  {cat}: {count:,} ({pct:.1f}%)\n")

    print(f"Saved: outputs/dqi_model_report.txt")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"""
Dataset:
  - Total Subjects: {len(df):,}
  - Total Sites: {len(site_agg):,}
  - Studies: {df['study'].nunique()}

Methodology:
  - Domain-knowledge based weights (not ML)
  - Severity multiplier for subjects with multiple issue types
  - Interpretable and actionable

Top 3 DQI Components:
  1. sae_pending_count: 25% (pending SAE reviews)
  2. uncoded_meddra_count: 15% (uncoded adverse events)
  3. missing_visit_count: 12% (missing visits)

Risk Distribution:
  - High Risk: {risk_dist.get('High', 0):,} subjects ({risk_dist.get('High', 0)/len(df)*100:.1f}%)
  - Medium Risk: {risk_dist.get('Medium', 0):,} subjects
  - Low Risk: {risk_dist.get('Low', 0):,} subjects
""")

    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Review outputs/dqi_weights.csv - Domain-knowledge weights with rationale
2. Review outputs/master_subject_with_dqi.csv - Subject-level DQI scores
3. Review outputs/master_site_with_dqi.csv - Site-level aggregation
4. Run: python src/04_build_knowledge_graph.py
""")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    calculate_dqi()
