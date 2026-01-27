"""
JAVELIN.AI - Central Configuration
===================================

This file consolidates ALL configuration constants from the pipeline.
Importing from here ensures consistency across all phases.

USAGE:
------
    from config import (
        PROJECT_ROOT, DATA_DIR, OUTPUT_DIR,
        COLUMN_MAPPINGS, FILE_PATTERNS, DQI_WEIGHTS,
        THRESHOLDS, OUTPUT_FILES
    )

BACKWARD COMPATIBILITY:
-----------------------
    Existing scripts can continue to work without importing from config.
    This file is designed to be opt-in during the migration period.

Author: JAVELIN.AI Team
Version: 1.0.0
"""

from pathlib import Path
from typing import Dict, List, Any

# ============================================================================
# PATH CONFIGURATION
# ============================================================================

# Detect project root (works whether run from src/ or project root)
_THIS_FILE = Path(__file__).resolve()
if _THIS_FILE.parent.name == 'src':
    PROJECT_ROOT = _THIS_FILE.parent.parent
else:
    PROJECT_ROOT = _THIS_FILE.parent

# Core directories
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SRC_DIR = PROJECT_ROOT / "src"


# ============================================================================
# OUTPUT FILE PATHS
# ============================================================================

OUTPUT_FILES = {
    # Phase 01: Discovery
    'file_mapping': OUTPUT_DIR / "file_mapping.csv",
    'column_report': OUTPUT_DIR / "column_report.csv",
    'discovery_issues': OUTPUT_DIR / "discovery_issues.txt",

    # Phase 02: Master Tables
    'master_subject': OUTPUT_DIR / "master_subject.csv",
    'master_site': OUTPUT_DIR / "master_site.csv",
    'master_study': OUTPUT_DIR / "master_study.csv",

    # Phase 03: DQI
    'master_subject_with_dqi': OUTPUT_DIR / "master_subject_with_dqi.csv",
    'master_site_with_dqi': OUTPUT_DIR / "master_site_with_dqi.csv",
    'master_study_with_dqi': OUTPUT_DIR / "master_study_with_dqi.csv",
    'master_region_with_dqi': OUTPUT_DIR / "master_region_with_dqi.csv",
    'master_country_with_dqi': OUTPUT_DIR / "master_country_with_dqi.csv",
    'dqi_weights': OUTPUT_DIR / "dqi_weights.csv",
    'dqi_model_report': OUTPUT_DIR / "dqi_model_report.txt",

    # Phase 04: Knowledge Graph
    'knowledge_graph': OUTPUT_DIR / "knowledge_graph.graphml",
    'knowledge_graph_nodes': OUTPUT_DIR / "knowledge_graph_nodes.csv",
    'knowledge_graph_edges': OUTPUT_DIR / "knowledge_graph_edges.csv",
    'knowledge_graph_summary': OUTPUT_DIR / "knowledge_graph_summary.json",
    'knowledge_graph_report': OUTPUT_DIR / "knowledge_graph_report.txt",
    'subgraph_high_risk': OUTPUT_DIR / "subgraph_high_risk.graphml",

    # Phase 05: Recommendations
    'recommendations_by_site': OUTPUT_DIR / "recommendations_by_site.csv",
    'recommendations_by_region': OUTPUT_DIR / "recommendations_by_region.csv",
    'recommendations_by_country': OUTPUT_DIR / "recommendations_by_country.csv",
    'recommendations_report': OUTPUT_DIR / "recommendations_report.md",

    # Phase 06: Anomaly Detection
    'anomalies_detected': OUTPUT_DIR / "anomalies_detected.csv",
    'site_anomaly_scores': OUTPUT_DIR / "site_anomaly_scores.csv",
    'anomaly_report': OUTPUT_DIR / "anomaly_report.md",
    'anomaly_summary': OUTPUT_DIR / "anomaly_summary.json",

    # Phase 07: Multi-Agent
    'multi_agent_recommendations': OUTPUT_DIR / "multi_agent_recommendations.csv",
    'multi_agent_report': OUTPUT_DIR / "multi_agent_report.md",
    'agent_analysis': OUTPUT_DIR / "agent_analysis.json",
    'action_items': OUTPUT_DIR / "action_items.json",

    # Phase 08: Clustering
    'site_clusters': OUTPUT_DIR / "site_clusters.csv",
    'cluster_profiles': OUTPUT_DIR / "cluster_profiles.csv",
    'cluster_report': OUTPUT_DIR / "cluster_report.md",
    'cluster_summary': OUTPUT_DIR / "cluster_summary.json",
    'cluster_distribution': OUTPUT_DIR / "cluster_distribution.png",
    'cluster_heatmap': OUTPUT_DIR / "cluster_heatmap.png",
    'cluster_pca': OUTPUT_DIR / "cluster_pca.png",

    # Phase 09: Root Cause
    'root_cause_analysis': OUTPUT_DIR / "root_cause_analysis.csv",
    'root_cause_report': OUTPUT_DIR / "root_cause_report.md",
    'root_cause_summary': OUTPUT_DIR / "root_cause_summary.json",
    'issue_cooccurrence': OUTPUT_DIR / "issue_cooccurrence.csv",

    # Diagnostics (Phase 00)
    'diagnostics_report': OUTPUT_DIR / "diagnostics_report.txt",
    'diagnostics_details': OUTPUT_DIR / "diagnostics_details.json",
    'diagnostics_summary': OUTPUT_DIR / "diagnostics_summary.csv",

    # Validation
    'sensitivity_analysis_results': OUTPUT_DIR / "sensitivity_analysis_results.csv",
    'sensitivity_analysis_report': OUTPUT_DIR / "sensitivity_analysis_report.md",
}


# ============================================================================
# FILE TYPE PATTERNS
# ============================================================================
# Used by 01_data_discovery.py to classify files
# Order matters - first match wins

FILE_PATTERNS: Dict[str, List[str]] = {
    'edc_metrics': [
        r'CPID.*EDC.*Metrics',
        r'EDC.*Metrics',
        r'CPID_EDC',
    ],
    'visit_tracker': [
        r'Visit.*Projection.*Tracker',
        r'Visit.*Tracker',
        r'Missing.*visit',
    ],
    'missing_lab': [
        r'Missing.*Lab.*Name',
        r'Missing.*LNR',
        r'Lab.*Range',
        r'Missing_Lab',
    ],
    'sae_dashboard': [
        r'eSAE.*Dashboard',
        r'SAE.*Dashboard',
        r'SAE_Dashboard',
        r'eSAE_',
    ],
    'missing_pages': [
        r'Missing.*Pages.*Report',
        r'Global.*Missing.*Pages',
        r'Missing.*Page.*Report',
        r'Missing_page',
    ],
    'meddra_coding': [
        r'GlobalCodingReport.*MedDRA',
        r'MedDRA',
        r'Medra',
    ],
    'whodd_coding': [
        r'GlobalCodingReport.*WHODD',
        r'GlobalCodingReport.*WHODrug',
        r'WHODD',
        r'WHODrug',
        r'WHOdra',
    ],
    'inactivated': [
        r'Inactivated.*Folders',
        r'Inactivated.*Forms',
        r'Inactivated.*Report',
        r'Inactivated',
        r'inactivated',
    ],
    'edrr': [
        r'Compiled.*EDRR',
        r'EDRR',
        r'Compiled_EDRR',
    ],
}


# ============================================================================
# COLUMN MAPPINGS
# ============================================================================
# Maps canonical column names to possible variations found in source files

COLUMN_MAPPINGS: Dict[str, Dict[str, List[str]]] = {
    'edc_metrics': {
        'subject_id': ['Subject ID', 'Subject', 'SubjectID', 'SUBJECT ID'],
        'site_id': ['Site ID', 'Site', 'SiteID', 'SITE ID', 'Site Number'],
        'country': ['Country', 'COUNTRY'],
        'region': ['Region', 'REGION'],
        'subject_status': ['Subject Status', 'Status', 'Subject Status (Source: PRIMARY Form)'],
        'latest_visit': ['Latest Visit', 'Latest Visit (SV)', 'Latest Visit (SV) (Source: Rave EDC: BO4)'],
    },
    'visit_tracker': {
        'subject_id': ['Subject', 'Subject ID', 'SubjectID'],
        'site_id': ['Site', 'Site ID', 'Site Number'],
        'country': ['Country'],
        'visit': ['Visit', 'Visit Name'],
        'days_outstanding': ['# Days Outstanding', 'Days Outstanding', 'Days_Outstanding'],
    },
    'missing_lab': {
        'subject_id': ['Subject', 'Subject ID'],
        'site_id': ['Site number', 'Site', 'Site ID'],
        'country': ['Country'],
        'issue': ['Issue', 'Issue Type'],
    },
    'sae_dashboard': {
        'subject_id': ['Patient ID', 'Subject', 'Subject ID', 'PatientID'],
        'site_id': ['Site', 'Site ID'],
        'country': ['Country'],
        'review_status': ['Review Status', 'ReviewStatus'],
        'action_status': ['Action Status', 'ActionStatus'],
    },
    'missing_pages': {
        'subject_id': ['Subject Name', 'SubjectName', 'Subject', 'Subject ID'],
        'site_id': ['Site Number', 'SiteNumber', 'SiteGroupName(CountryName)', 'SiteGroupName', 'Site', 'Site ID'],
        'days_missing': ['No. #Days Page Missing', '# of Days Missing', 'Days Missing', '#Days Page Missing'],
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
        'open_issues': ['Total Open issue Count per subject', 'Open Issues', 'Open Issue Count'],
    },
}

# Alias for backward compatibility
EXPECTED_COLUMNS = COLUMN_MAPPINGS


# ============================================================================
# DQI FEATURE WEIGHTS
# ============================================================================
# Weights based on clinical importance
# Rationale: Safety > Completeness > Timeliness > Administrative
#
# VALIDATED: Sensitivity analysis confirms stability under +/-30% perturbation

DQI_WEIGHTS: Dict[str, Dict[str, Any]] = {
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

# Validate weights sum to 1.0
_total_weight = sum(w['weight'] for w in DQI_WEIGHTS.values())
assert abs(_total_weight - 1.0) < 0.001, f"DQI weights must sum to 1.0, got {_total_weight}"

# Extract just the weight values (for backward compatibility)
DQI_WEIGHT_VALUES: Dict[str, float] = {k: v['weight'] for k, v in DQI_WEIGHTS.items()}


# ============================================================================
# THRESHOLDS AND PARAMETERS
# ============================================================================

class THRESHOLDS:
    """Configurable thresholds used across the pipeline."""

    # Outlier handling (02_build_master_table.py)
    OUTLIER_IQR_MULTIPLIER = 3.0
    MAX_DAYS_CAP = 1825  # 5 years

    # DQI calculation (03_calculate_dqi.py)
    MIN_SAMPLES_FOR_PERCENTILE = 20
    HIGH_RISK_PERCENTILE = 0.90
    MIN_HIGH_THRESHOLD = 0.10

    # Site-level risk
    SITE_HIGH_PERCENTILE = 0.85
    SITE_MEDIUM_PERCENTILE = 0.50

    # Study/Region/Country risk
    STUDY_HIGH_PERCENTILE = 0.85
    STUDY_MEDIUM_PERCENTILE = 0.50
    REGION_HIGH_PERCENTILE = 0.85
    REGION_MEDIUM_PERCENTILE = 0.50
    COUNTRY_HIGH_PERCENTILE = 0.85
    COUNTRY_MEDIUM_PERCENTILE = 0.50

    # Validation
    VALIDATION_FOLDS = 5
    STABILITY_THRESHOLD = 0.05

    # Anomaly detection
    ANOMALY_CONTAMINATION = 0.05
    ZSCORE_THRESHOLD = 3.0

    # Clustering
    MAX_CLUSTERS = 10
    MIN_CLUSTER_SIZE = 5


# ============================================================================
# FEATURE LISTS
# ============================================================================

NUMERIC_ISSUE_COLUMNS = [
    'missing_visit_count',
    'max_days_outstanding',
    'lab_issues_count',
    'sae_total_count',
    'sae_pending_count',
    'missing_pages_count',
    'max_days_page_missing',
    'uncoded_meddra_count',
    'uncoded_whodd_count',
    'inactivated_forms_count',
    'edrr_open_issues',
]

OUTLIER_CAP_COLUMNS = [
    'max_days_outstanding',
    'max_days_page_missing',
    'lab_issues_count',
    'inactivated_forms_count',
]

CATEGORICAL_COLUMNS = [
    'country',
    'region',
    'subject_status',
]

CLUSTERING_FEATURES = [
    'avg_dqi_score',
    'subject_count',
    'high_risk_rate',
    'sae_pending_count',
    'missing_visit_count',
    'lab_issues_count',
    'missing_pages_count',
    'uncoded_meddra_count',
    'uncoded_whodd_count',
]

ANOMALY_FEATURES = [
    'avg_dqi_score',
    'max_dqi_score',
    'high_risk_rate',
    'subject_count',
]

HEADER_PATTERNS = [
    'Subject ID', 'Subject', 'Patient ID',
    'Site ID', 'Site Number', 'Site',
    'Visit', 'Days Outstanding',
    'Issue', 'Missing',
    'Review Status', 'Action Status',
    'Coding Status',
    'Open', 'Total',
    'Country', 'Region',
]

RISK_CATEGORIES = ['High', 'Medium', 'Low']

RISK_COLORS = {
    'High': '#FF4444',
    'Medium': '#FFAA00',
    'Low': '#44BB44',
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def ensure_output_dirs():
    """Create output directory if it doesn't exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_output_file(file_key: str) -> Path:
    """Get the path for a specific output file."""
    if file_key in OUTPUT_FILES:
        return OUTPUT_FILES[file_key]
    raise KeyError(f"Unknown output file key: {file_key}")


# ============================================================================
# VALIDATION
# ============================================================================

def validate_config():
    """Validate configuration consistency."""
    errors = []

    # Check DQI weights sum to 1
    total = sum(w['weight'] for w in DQI_WEIGHTS.values())
    if abs(total - 1.0) > 0.001:
        errors.append(f"DQI weights sum to {total}, expected 1.0")

    if errors:
        raise ValueError("Configuration validation failed:\n" + "\n".join(errors))

    return True


# ============================================================================
# MODULE INITIALIZATION
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("JAVELIN.AI - CONFIGURATION SUMMARY")
    print("=" * 70)

    print(f"\nPROJECT_ROOT: {PROJECT_ROOT}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"OUTPUT_DIR: {OUTPUT_DIR}")

    print(f"\nFile Types: {len(FILE_PATTERNS)}")
    for ft in FILE_PATTERNS:
        print(f"  - {ft}")

    print(f"\nDQI Features: {len(DQI_WEIGHTS)}")
    for feature, cfg in sorted(DQI_WEIGHTS.items(), key=lambda x: -x[1]['weight']):
        print(f"  - {feature}: {cfg['weight']:.0%} ({cfg['tier']})")

    print(f"\nThresholds:")
    print(f"  - Outlier IQR multiplier: {THRESHOLDS.OUTLIER_IQR_MULTIPLIER}")
    print(f"  - High risk percentile: {THRESHOLDS.HIGH_RISK_PERCENTILE}")
    print(f"  - Min samples for percentile: {THRESHOLDS.MIN_SAMPLES_FOR_PERCENTILE}")

    print("\nValidating configuration...")
    try:
        validate_config()
        print("[OK] Configuration is valid!")
    except ValueError as e:
        print(f"[ERROR] {e}")
