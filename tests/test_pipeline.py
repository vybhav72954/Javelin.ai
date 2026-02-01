"""
JAVELIN.AI - Comprehensive Pipeline Test Suite
=================================================

Tests: 10 classes, ~80 tests covering:
  - Configuration validation
  - Pre-flight checks
  - Output file existence & integrity
  - Data integrity & consistency
  - DQI scoring validation
  - Aggregation consistency
  - Anomaly detection validation
  - Site clustering validation
  - Root cause analysis validation
  - Recommendations & action items
  - Cross-phase consistency
  - K-Fold validation results
  - Dashboard readiness

Run:
  pytest tests/test_pipeline.py -v                    # All tests
  pytest tests/test_pipeline.py -v -m "not slow"      # Skip slow tests
  pytest tests/test_pipeline.py -v --cov=src          # With coverage

Author: JAVELIN.AI Team (Team CWTY)
"""

import sys
import json
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

# ============================================================================
# PATH SETUP
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

sys.path.insert(0, str(SRC_DIR))


# ============================================================================
# EXPECTED OUTPUTS - verified against actual pipeline output files
# ============================================================================

EXPECTED_OUTPUTS = {
    "phase00": {
        "files": ["diagnostics_report.txt", "diagnostics_details.json"],
        "required": False,  # Phase 00 is optional pre-flight
    },
    "phase01": {
        "files": ["file_mapping.csv", "column_report.csv", "discovery_issues.txt"],
        "required": True,
    },
    "phase02": {
        "files": ["master_subject.csv", "master_site.csv", "master_study.csv"],
        "required": True,
    },
    "phase03": {
        "files": [
            "master_subject_with_dqi.csv",
            "master_site_with_dqi.csv",
            "master_study_with_dqi.csv",
            "master_region_with_dqi.csv",
            "master_country_with_dqi.csv",
            "dqi_weights.csv",
            "dqi_model_report.txt",
        ],
        "required": True,
    },
    "phase04": {
        "files": [
            "knowledge_graph_nodes.csv",
            "knowledge_graph_edges.csv",
            "knowledge_graph_summary.json",
            "knowledge_graph_report.txt",
        ],
        "required": False,  # Phase 04 is optional
    },
    "phase05": {
        "files": [
            "recommendations_by_site.csv",
            "recommendations_by_country.csv",
            "recommendations_by_region.csv",
            "recommendations_report.md",
            "action_items.json",
            "executive_summary.txt",
        ],
        "required": True,
    },
    "phase06": {
        "files": [
            "anomalies_detected.csv",
            "site_anomaly_scores.csv",
            "anomaly_summary.json",
            "anomaly_report.md",
        ],
        "required": True,
    },
    "phase07": {
        "files": [
            "multi_agent_recommendations.csv",
            "agent_analysis.json",
            "multi_agent_report.md",
        ],
        "required": True,
    },
    "phase08": {
        "files": [
            "site_clusters.csv",
            "cluster_profiles.csv",
            "cluster_summary.json",
            "cluster_report.md",
            "cluster_distribution.png",
            "cluster_heatmap.png",
            "cluster_pca.png",
        ],
        "required": True,
    },
    "phase09": {
        "files": [
            "root_cause_analysis.csv",
            "root_cause_summary.json",
            "root_cause_report.md",
            "issue_cooccurrence.csv",
            "contributing_factors.csv",
            "geographic_patterns.csv",
        ],
        "required": True,
    },
}


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def subject_df():
    """Load Phase 03 subject-level data."""
    path = OUTPUT_DIR / "phase03" / "master_subject_with_dqi.csv"
    return pd.read_csv(path) if path.exists() else None


@pytest.fixture(scope="session")
def site_df():
    """Load Phase 03 site-level data."""
    path = OUTPUT_DIR / "phase03" / "master_site_with_dqi.csv"
    return pd.read_csv(path) if path.exists() else None


@pytest.fixture(scope="session")
def study_df():
    """Load Phase 03 study-level data."""
    path = OUTPUT_DIR / "phase03" / "master_study_with_dqi.csv"
    return pd.read_csv(path) if path.exists() else None


@pytest.fixture(scope="session")
def country_df():
    """Load Phase 03 country-level data."""
    path = OUTPUT_DIR / "phase03" / "master_country_with_dqi.csv"
    return pd.read_csv(path) if path.exists() else None


@pytest.fixture(scope="session")
def region_df():
    """Load Phase 03 region-level data."""
    path = OUTPUT_DIR / "phase03" / "master_region_with_dqi.csv"
    return pd.read_csv(path) if path.exists() else None


@pytest.fixture(scope="session")
def anomaly_summary():
    """Load Phase 06 anomaly summary."""
    path = OUTPUT_DIR / "phase06" / "anomaly_summary.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


@pytest.fixture(scope="session")
def cluster_summary():
    """Load Phase 08 cluster summary."""
    path = OUTPUT_DIR / "phase08" / "cluster_summary.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


@pytest.fixture(scope="session")
def root_cause_summary():
    """Load Phase 09 root cause summary."""
    path = OUTPUT_DIR / "phase09" / "root_cause_summary.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


@pytest.fixture(scope="session")
def validation_details():
    """Load K-Fold validation details."""
    path = OUTPUT_DIR / "validation" / "kfold_validation_details.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


# ============================================================================
# TEST 1: CONFIGURATION
# ============================================================================

class TestConfiguration:
    """Validate config.py settings and consistency."""

    def test_config_imports(self):
        """Config module imports without error."""
        from config import PROJECT_ROOT, DATA_DIR, OUTPUT_DIR, PHASE_DIRS
        assert PROJECT_ROOT.exists()

    def test_dqi_weights_sum_to_one(self):
        """DQI feature weights must total exactly 1.0."""
        from config import DQI_WEIGHTS
        total = sum(w['weight'] for w in DQI_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}"

    def test_dqi_weights_all_positive(self):
        """Every DQI weight must be positive."""
        from config import DQI_WEIGHTS
        for feature, cfg in DQI_WEIGHTS.items():
            assert cfg['weight'] > 0, f"{feature} weight is {cfg['weight']}"

    def test_dqi_weights_have_tiers(self):
        """Each weight must declare a tier (Safety, Completeness, etc.)."""
        from config import DQI_WEIGHTS
        for feature, cfg in DQI_WEIGHTS.items():
            assert 'tier' in cfg, f"{feature} missing tier"
            assert cfg['tier'] in (
                'Safety', 'Completeness', 'Timeliness', 'Coding',
                'Reconciliation', 'Composite', 'Administrative'
            ), f"{feature} has unknown tier: {cfg['tier']}"

    def test_all_phase_scripts_exist(self):
        """Every phase script referenced in config must exist on disk."""
        from config import PHASE_METADATA, get_phase_script_path
        for phase_num in PHASE_METADATA:
            script_path = get_phase_script_path(phase_num)
            assert script_path.exists(), f"Missing: {script_path}"

    def test_phase_metadata_complete(self):
        """Each phase must have required metadata fields."""
        from config import PHASE_METADATA
        required_fields = ['name', 'script', 'optional', 'requires', 'outputs']
        for phase_num, meta in PHASE_METADATA.items():
            for field in required_fields:
                assert field in meta, f"Phase {phase_num} missing: {field}"

    def test_phase_metadata_covers_all_phases(self):
        """We must have metadata for phases 00-09."""
        from config import PHASE_METADATA
        for i in range(10):
            phase_key = f'{i:02d}'
            assert phase_key in PHASE_METADATA, f"Missing phase {phase_key}"

    def test_file_patterns_defined(self):
        """FILE_PATTERNS must cover all expected data file types."""
        from config import FILE_PATTERNS
        expected = [
            'edc_metrics', 'visit_tracker', 'missing_lab', 'sae_dashboard',
            'missing_pages', 'meddra_coding', 'whodd_coding', 'inactivated', 'edrr',
        ]
        for ft in expected:
            assert ft in FILE_PATTERNS, f"Missing pattern: {ft}"

    def test_thresholds_class_exists(self):
        """THRESHOLDS class with key parameters must exist."""
        from config import THRESHOLDS
        assert hasattr(THRESHOLDS, 'OUTLIER_IQR_MULTIPLIER')
        assert hasattr(THRESHOLDS, 'HIGH_RISK_PERCENTILE')
        assert hasattr(THRESHOLDS, 'VALIDATION_FOLDS')
        assert hasattr(THRESHOLDS, 'ANOMALY_CONTAMINATION')
        assert hasattr(THRESHOLDS, 'MAX_CLUSTERS')

    def test_numeric_issue_columns_defined(self):
        """NUMERIC_ISSUE_COLUMNS must list all 11 features."""
        from config import NUMERIC_ISSUE_COLUMNS
        assert len(NUMERIC_ISSUE_COLUMNS) == 11
        assert 'sae_pending_count' in NUMERIC_ISSUE_COLUMNS
        assert 'missing_visit_count' in NUMERIC_ISSUE_COLUMNS
        assert 'dqi_score' not in NUMERIC_ISSUE_COLUMNS  # DQI is derived, not raw

    def test_pipeline_defaults_exist(self):
        """PIPELINE_DEFAULTS should have entries for key phases."""
        from config import PIPELINE_DEFAULTS
        assert '05' in PIPELINE_DEFAULTS
        assert '07' in PIPELINE_DEFAULTS
        assert '08' in PIPELINE_DEFAULTS

    def test_validate_config_passes(self):
        """Full config validation must pass."""
        from config import validate_config
        assert validate_config() is True


# ============================================================================
# TEST 2: PRE-FLIGHT
# ============================================================================

class TestPreFlight:
    """Verify data directory and environment setup."""

    def test_data_directory_exists(self):
        assert DATA_DIR.exists(), f"Data dir missing: {DATA_DIR}"

    def test_data_has_study_folders(self):
        folders = [f for f in DATA_DIR.iterdir() if f.is_dir()]
        assert len(folders) > 0, "No study folders in data/"

    def test_data_has_excel_files(self):
        files = list(DATA_DIR.rglob("*.xlsx")) + list(DATA_DIR.rglob("*.xls"))
        assert len(files) > 0, "No Excel files found"

    def test_required_packages_installed(self):
        """Core packages are importable."""
        required = {
            'pandas': 'pandas',
            'numpy': 'numpy',
            'scikit-learn': 'sklearn',
            'matplotlib': 'matplotlib',
            'plotly': 'plotly',
            'streamlit': 'streamlit',
        }
        missing = []
        for name, import_name in required.items():
            try:
                __import__(import_name)
            except ImportError:
                missing.append(name)
        assert not missing, f"Missing packages: {missing}"

    def test_utils_importable(self):
        """Utility modules import without error."""
        from utils.dqi_calculator import calculate_dqi_with_weights, get_risk_distribution
        from utils.aggregation import aggregate_to_site, aggregate_to_study
        from utils.data_loader import read_excel_smart, standardize_columns
        from utils.validation import validate_required_columns


# ============================================================================
# TEST 3: OUTPUT FILES
# ============================================================================

class TestOutputFiles:
    """Verify all pipeline phases produced expected output files."""

    @pytest.mark.parametrize("phase,config", EXPECTED_OUTPUTS.items())
    def test_phase_outputs_exist(self, phase, config):
        if not config["required"]:
            phase_dir = OUTPUT_DIR / phase
            if not phase_dir.exists():
                pytest.skip(f"{phase} is optional and was not run")

        phase_dir = OUTPUT_DIR / phase
        assert phase_dir.exists(), f"Directory missing: {phase_dir}"

        missing = [f for f in config["files"] if not (phase_dir / f).exists()]
        assert not missing, f"{phase} missing files: {missing}"

    @pytest.mark.parametrize("phase,config", EXPECTED_OUTPUTS.items())
    def test_phase_outputs_not_empty(self, phase, config):
        phase_dir = OUTPUT_DIR / phase
        if not phase_dir.exists():
            pytest.skip(f"{phase} not run")

        for fname in config["files"]:
            fpath = phase_dir / fname
            if fpath.exists():
                assert fpath.stat().st_size > 0, f"{phase}/{fname} is empty"

    def test_log_file_created(self):
        logs_dir = OUTPUT_DIR / "logs"
        if logs_dir.exists():
            logs = list(logs_dir.glob("pipeline_run_*.log"))
            assert len(logs) > 0, "No pipeline log files found"

    def test_validation_outputs_exist(self):
        """K-Fold validation outputs must exist."""
        val_dir = OUTPUT_DIR / "validation"
        if not val_dir.exists():
            pytest.skip("Validation directory not present (run validation.py separately)")

        expected = [
            "kfold_validation_details.json",
            "kfold_validation_results.csv",
            "kfold_validation_report.md",
            "VALIDATION_METHODOLOGY.md",
        ]
        missing = [f for f in expected if not (val_dir / f).exists()]
        assert not missing, f"Validation missing: {missing}"


# ============================================================================
# TEST 4: DATA INTEGRITY
# ============================================================================

class TestDataIntegrity:
    """Verify core data tables have expected shape and completeness."""

    def test_subject_count_reasonable(self, subject_df):
        assert subject_df is not None, "subject_df not loaded"
        assert len(subject_df) >= 50000, f"Only {len(subject_df)} subjects"

    def test_site_count_reasonable(self, site_df):
        assert site_df is not None, "site_df not loaded"
        assert len(site_df) >= 3000, f"Only {len(site_df)} sites"

    def test_study_count_reasonable(self, study_df):
        assert study_df is not None, "study_df not loaded"
        assert len(study_df) >= 20, f"Only {len(study_df)} studies"

    def test_no_duplicate_subjects(self, subject_df):
        assert subject_df is not None
        dups = subject_df.duplicated(subset=['study', 'subject_id'], keep=False).sum()
        assert dups == 0, f"Found {dups} duplicate (study, subject_id) rows"

    def test_all_subjects_have_study(self, subject_df):
        assert subject_df is not None
        missing = subject_df['study'].isna().sum()
        assert missing == 0, f"{missing} subjects missing study"

    def test_all_subjects_have_site(self, subject_df):
        assert subject_df is not None
        missing = subject_df['site_id'].isna().sum()
        assert missing == 0, f"{missing} subjects missing site_id"

    def test_all_subjects_have_country(self, subject_df):
        assert subject_df is not None
        missing = subject_df['country'].isna().sum()
        assert missing == 0, f"{missing} subjects missing country"

    def test_subject_schema_complete(self, subject_df):
        """Subject table must have all expected columns."""
        assert subject_df is not None
        required_cols = [
            'study', 'subject_id', 'site_id', 'country', 'region',
            'dqi_score', 'risk_category', 'has_issues',
            'sae_pending_count', 'missing_visit_count', 'lab_issues_count',
            'missing_pages_count', 'uncoded_meddra_count', 'uncoded_whodd_count',
            'max_days_outstanding', 'max_days_page_missing',
            'edrr_open_issues', 'inactivated_forms_count', 'n_issue_types',
        ]
        missing = [c for c in required_cols if c not in subject_df.columns]
        assert not missing, f"Subject table missing columns: {missing}"

    def test_site_schema_complete(self, site_df):
        """Site table must have all expected columns."""
        assert site_df is not None
        required_cols = [
            'study', 'site_id', 'country', 'region', 'subject_count',
            'avg_dqi_score', 'max_dqi_score',
            'high_risk_count', 'medium_risk_count',
            'site_risk_category',
        ]
        missing = [c for c in required_cols if c not in site_df.columns]
        assert not missing, f"Site table missing columns: {missing}"

    def test_study_schema_complete(self, study_df):
        """Study table must have all expected columns."""
        assert study_df is not None
        required_cols = [
            'study', 'site_count', 'subject_count',
            'avg_dqi_score', 'high_risk_subjects', 'medium_risk_subjects',
            'high_risk_rate', 'study_risk_category',
        ]
        missing = [c for c in required_cols if c not in study_df.columns]
        assert not missing, f"Study table missing columns: {missing}"

    def test_country_and_region_tables_exist(self, country_df, region_df):
        """Country and region aggregation tables must exist."""
        assert country_df is not None, "Country table missing"
        assert region_df is not None, "Region table missing"
        assert len(country_df) >= 50, f"Only {len(country_df)} countries"
        assert len(region_df) >= 3, f"Only {len(region_df)} regions"


# ============================================================================
# TEST 5: DQI VALIDATION
# ============================================================================

class TestDQIValidation:
    """Validate DQI scoring logic and risk categorization."""

    def test_dqi_scores_in_valid_range(self, subject_df):
        """DQI scores must be in [0, 1]."""
        assert subject_df is not None
        assert subject_df['dqi_score'].min() >= 0.0, "DQI below 0"
        assert subject_df['dqi_score'].max() <= 1.0, "DQI above 1"

    def test_risk_categories_valid(self, subject_df):
        """Only High / Medium / Low categories allowed."""
        assert subject_df is not None
        valid = {'High', 'Medium', 'Low'}
        actual = set(subject_df['risk_category'].unique())
        assert actual.issubset(valid), f"Invalid categories: {actual - valid}"

    def test_risk_pyramid_shape(self, subject_df):
        """Low > Medium and Low > High (healthy distribution)."""
        assert subject_df is not None
        counts = subject_df['risk_category'].value_counts()
        high = counts.get('High', 0)
        medium = counts.get('Medium', 0)
        low = counts.get('Low', 0)
        assert low > medium, f"Low ({low}) should > Medium ({medium})"
        assert low > high, f"Low ({low}) should > High ({high})"

    def test_sae_capture_rate_100_percent(self, subject_df):
        """CRITICAL: Every subject with pending SAEs must be High risk."""
        assert subject_df is not None
        if 'sae_pending_count' not in subject_df.columns:
            pytest.skip("No sae_pending_count column")

        sae_subjects = subject_df[subject_df['sae_pending_count'] > 0]
        if len(sae_subjects) == 0:
            pytest.skip("No SAE subjects found")

        high_risk_sae = sae_subjects[sae_subjects['risk_category'] == 'High']
        capture_rate = len(high_risk_sae) / len(sae_subjects)

        assert capture_rate == 1.0, (
            f"SAE capture rate: {capture_rate:.2%} "
            f"({len(high_risk_sae)}/{len(sae_subjects)}) — must be 100%"
        )

    def test_high_risk_subjects_have_issues(self, subject_df):
        """All High-risk subjects must have a positive DQI or pending SAEs."""
        assert subject_df is not None
        high = subject_df[subject_df['risk_category'] == 'High']
        if len(high) == 0:
            pytest.skip("No high-risk subjects")

        has_dqi = high['dqi_score'] > 0
        has_sae = high['sae_pending_count'] > 0
        assert (has_dqi | has_sae).all(), "Some High-risk subjects have no issues"

    def test_low_risk_subjects_no_issues(self, subject_df):
        """Low-risk subjects must have DQI = 0 (no issues)."""
        assert subject_df is not None
        low = subject_df[subject_df['risk_category'] == 'Low']
        if len(low) == 0:
            pytest.skip("No low-risk subjects")

        with_score = low[low['dqi_score'] > 0]
        assert len(with_score) == 0, f"{len(with_score)} Low-risk subjects have DQI > 0"

    def test_dqi_component_columns_exist(self, subject_df):
        """Each DQI weight must have a _component column."""
        assert subject_df is not None
        from config import DQI_WEIGHTS
        for feature in DQI_WEIGHTS:
            comp_col = f"{feature}_component"
            assert comp_col in subject_df.columns, f"Missing component: {comp_col}"

    def test_dqi_weights_csv_matches_config(self):
        """dqi_weights.csv must match config.py weights."""
        path = OUTPUT_DIR / "phase03" / "dqi_weights.csv"
        if not path.exists():
            pytest.skip("No dqi_weights.csv")

        from config import DQI_WEIGHTS
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            feature = row['feature']
            if feature in DQI_WEIGHTS:
                expected = DQI_WEIGHTS[feature]['weight']
                actual = row['weight']
                assert abs(expected - actual) < 0.001, (
                    f"{feature}: config={expected}, file={actual}"
                )

    def test_has_issues_flag_consistency(self, subject_df):
        """has_issues=1 iff dqi_score > 0."""
        assert subject_df is not None
        with_issues = subject_df[subject_df['has_issues'] == 1]
        assert (with_issues['dqi_score'] > 0).all(), "has_issues=1 but DQI=0"

        no_issues = subject_df[subject_df['has_issues'] == 0]
        assert (no_issues['dqi_score'] == 0).all(), "has_issues=0 but DQI>0"


# ============================================================================
# TEST 6: AGGREGATION CONSISTENCY
# ============================================================================

class TestAggregationConsistency:
    """Verify subject → site → study aggregation math."""

    def test_site_subject_count_matches(self, subject_df, site_df):
        """Each site's subject_count must equal count of subjects in that site."""
        assert subject_df is not None and site_df is not None
        actual = subject_df.groupby(['study', 'site_id']).size()

        mismatches = 0
        for _, site in site_df.iterrows():
            key = (site['study'], site['site_id'])
            if key in actual.index:
                if actual[key] != site['subject_count']:
                    mismatches += 1
        assert mismatches == 0, f"{mismatches} site subject_count mismatches"

    def test_total_subjects_consistent(self, subject_df, site_df, study_df):
        """Total subjects must be consistent across all tables."""
        assert subject_df is not None
        total = len(subject_df)

        if site_df is not None:
            site_total = site_df['subject_count'].sum()
            assert total == site_total, f"Subject ({total}) ≠ Site sum ({site_total})"

        if study_df is not None:
            study_total = study_df['subject_count'].sum()
            assert total == study_total, f"Subject ({total}) ≠ Study sum ({study_total})"

    def test_study_site_count_matches(self, site_df, study_df):
        """Study-level site_count must match the number of distinct sites."""
        assert site_df is not None and study_df is not None
        actual_sites = site_df.groupby('study').size()

        mismatches = 0
        for _, study in study_df.iterrows():
            if study['study'] in actual_sites.index:
                if actual_sites[study['study']] != study['site_count']:
                    mismatches += 1
        assert mismatches == 0, f"{mismatches} study site_count mismatches"

    def test_high_risk_count_aggregation(self, subject_df, site_df):
        """Site high_risk_count must match count of High-risk subjects."""
        assert subject_df is not None and site_df is not None
        actual_high = subject_df[subject_df['risk_category'] == 'High'] \
            .groupby(['study', 'site_id']).size()

        mismatches = 0
        for _, site in site_df.iterrows():
            key = (site['study'], site['site_id'])
            expected = actual_high.get(key, 0)
            if expected != site['high_risk_count']:
                mismatches += 1
        assert mismatches == 0, f"{mismatches} high_risk_count mismatches"


# ============================================================================
# TEST 7: ANOMALY DETECTION (Phase 06)
# ============================================================================

class TestAnomalyDetection:
    """Validate anomaly detection outputs."""

    def test_anomaly_summary_valid(self, anomaly_summary):
        if anomaly_summary is None:
            pytest.skip("No anomaly summary")

        assert 'total_anomalies' in anomaly_summary
        assert anomaly_summary['total_anomalies'] >= 0

    def test_anomaly_severity_breakdown(self, anomaly_summary):
        """Summary must include severity breakdown."""
        if anomaly_summary is None:
            pytest.skip("No anomaly summary")

        assert 'by_severity' in anomaly_summary
        by_sev = anomaly_summary['by_severity']
        assert 'critical' in by_sev
        assert 'high' in by_sev

    def test_anomaly_type_breakdown(self, anomaly_summary):
        """Summary must include anomaly type breakdown."""
        if anomaly_summary is None:
            pytest.skip("No anomaly summary")

        assert 'by_type' in anomaly_summary
        by_type = anomaly_summary['by_type']
        assert len(by_type) > 0, "No anomaly types"

    def test_anomaly_severity_sums(self, anomaly_summary):
        """Sum of severities must equal total_anomalies."""
        if anomaly_summary is None:
            pytest.skip("No anomaly summary")

        total = anomaly_summary['total_anomalies']
        sev_sum = sum(anomaly_summary['by_severity'].values())
        assert total == sev_sum, f"Total ({total}) ≠ severity sum ({sev_sum})"

    def test_anomalies_detected_csv_valid(self):
        path = OUTPUT_DIR / "phase06" / "anomalies_detected.csv"
        if not path.exists():
            pytest.skip("No anomalies_detected.csv")

        df = pd.read_csv(path)
        required_cols = ['anomaly_type', 'detection_method', 'severity', 'site_id']
        missing = [c for c in required_cols if c not in df.columns]
        assert not missing, f"Missing columns: {missing}"

    def test_site_anomaly_scores_valid(self):
        path = OUTPUT_DIR / "phase06" / "site_anomaly_scores.csv"
        if not path.exists():
            pytest.skip("No site_anomaly_scores.csv")

        df = pd.read_csv(path)
        assert 'anomaly_score' in df.columns or 'is_anomaly' in df.columns, \
            f"Missing score/flag column. Cols: {df.columns.tolist()}"

    def test_top_anomalous_sites_reported(self, anomaly_summary):
        """Summary must include top anomalous sites."""
        if anomaly_summary is None:
            pytest.skip("No anomaly summary")

        assert 'top_sites' in anomaly_summary
        assert len(anomaly_summary['top_sites']) > 0, "No top sites"


# ============================================================================
# TEST 8: SITE CLUSTERING (Phase 08)
# ============================================================================

class TestClustering:
    """Validate GMM clustering outputs."""

    def test_cluster_summary_valid(self, cluster_summary):
        if cluster_summary is None:
            pytest.skip("No cluster summary")

        assert 'n_clusters' in cluster_summary
        assert 0 < cluster_summary['n_clusters'] <= 15
        assert 'algorithm' in cluster_summary
        assert 'total_sites' in cluster_summary

    def test_all_sites_have_cluster(self):
        path = OUTPUT_DIR / "phase08" / "site_clusters.csv"
        if not path.exists():
            pytest.skip("No site_clusters.csv")

        df = pd.read_csv(path)
        assert 'cluster_id' in df.columns, f"No cluster_id column. Cols: {df.columns.tolist()}"
        missing = df['cluster_id'].isna().sum()
        assert missing == 0, f"{missing} sites missing cluster"

    def test_cluster_profiles_complete(self):
        """Each cluster must have a profile with risk level and actions."""
        path = OUTPUT_DIR / "phase08" / "cluster_profiles.csv"
        if not path.exists():
            pytest.skip("No cluster_profiles.csv")

        df = pd.read_csv(path)
        required = [
            'cluster_id', 'cluster_name', 'site_count', 'pct_of_total',
            'avg_dqi_score', 'risk_level', 'intervention_priority',
        ]
        missing = [c for c in required if c not in df.columns]
        assert not missing, f"Cluster profiles missing: {missing}"

    def test_cluster_site_counts_sum(self, cluster_summary):
        """Sum of cluster site counts must equal total_sites."""
        if cluster_summary is None:
            pytest.skip("No cluster summary")

        total = cluster_summary['total_sites']
        # Cluster entries use 'sites' key for count
        cluster_total = sum(
            c.get('sites', c.get('site_count', 0))
            for c in cluster_summary.get('cluster_summary', [])
        )
        assert total == cluster_total, f"Total ({total}) ≠ cluster sum ({cluster_total})"

    def test_cluster_names_assigned(self):
        """Every cluster must have a human-readable name."""
        path = OUTPUT_DIR / "phase08" / "site_clusters.csv"
        if not path.exists():
            pytest.skip("No site_clusters.csv")

        df = pd.read_csv(path)
        assert 'cluster_name' in df.columns, "No cluster_name column"
        unnamed = df['cluster_name'].isna().sum()
        assert unnamed == 0, f"{unnamed} sites without cluster name"


# ============================================================================
# TEST 9: ROOT CAUSE ANALYSIS (Phase 09)
# ============================================================================

class TestRootCauseAnalysis:
    """Validate root cause identification and supporting evidence."""

    def test_root_cause_summary_valid(self, root_cause_summary):
        if root_cause_summary is None:
            pytest.skip("No root cause summary")

        assert 'root_causes_count' in root_cause_summary
        assert root_cause_summary['root_causes_count'] > 0

    def test_root_causes_have_required_fields(self):
        path = OUTPUT_DIR / "phase09" / "root_cause_analysis.csv"
        if not path.exists():
            pytest.skip("No root_cause_analysis.csv")

        df = pd.read_csv(path)
        required = [
            'cause_id', 'category', 'description', 'severity', 'confidence',
            'affected_sites', 'affected_subjects', 'evidence',
            'recommended_actions',
        ]
        missing = [c for c in required if c not in df.columns]
        assert not missing, f"Root cause missing columns: {missing}"

    def test_root_cause_severity_valid(self):
        path = OUTPUT_DIR / "phase09" / "root_cause_analysis.csv"
        if not path.exists():
            pytest.skip("No root_cause_analysis.csv")

        df = pd.read_csv(path)
        valid_severities = {'Critical', 'High', 'Medium', 'Low'}
        actual = set(df['severity'].unique())
        assert actual.issubset(valid_severities), f"Invalid severities: {actual}"

    def test_root_cause_confidence_range(self):
        """Confidence must be in (0, 1]."""
        path = OUTPUT_DIR / "phase09" / "root_cause_analysis.csv"
        if not path.exists():
            pytest.skip("No root_cause_analysis.csv")

        df = pd.read_csv(path)
        assert df['confidence'].min() > 0, "Confidence must be > 0"
        assert df['confidence'].max() <= 1.0, "Confidence must be ≤ 1"

    def test_cooccurrence_matrix_valid(self):
        """Issue co-occurrence matrix must be square and non-negative."""
        path = OUTPUT_DIR / "phase09" / "issue_cooccurrence.csv"
        if not path.exists():
            pytest.skip("No issue_cooccurrence.csv")

        df = pd.read_csv(path, index_col=0)
        assert df.shape[0] == df.shape[1], "Co-occurrence must be square"
        assert (df.values >= 0).all(), "Co-occurrence values must be ≥ 0"

    def test_contributing_factors_valid(self):
        path = OUTPUT_DIR / "phase09" / "contributing_factors.csv"
        if not path.exists():
            pytest.skip("No contributing_factors.csv")

        df = pd.read_csv(path)
        required = ['factor', 'category', 'site_count', 'interpretation']
        missing = [c for c in required if c not in df.columns]
        assert not missing, f"Contributing factors missing: {missing}"

    def test_geographic_patterns_valid(self):
        path = OUTPUT_DIR / "phase09" / "geographic_patterns.csv"
        if not path.exists():
            pytest.skip("No geographic_patterns.csv")

        df = pd.read_csv(path)
        assert len(df) > 0, "Geographic patterns is empty"


# ============================================================================
# TEST 10: RECOMMENDATIONS & ACTION ITEMS (Phase 05)
# ============================================================================

class TestRecommendations:
    """Validate recommendations engine output."""

    def test_recommendations_by_site_exist(self):
        """Site-level recommendations must exist."""
        path = OUTPUT_DIR / "phase05" / "recommendations_by_site.csv"
        assert path.exists(), "recommendations_by_site.csv missing"

        df = pd.read_csv(path)
        assert len(df) > 0, "No site recommendations"

    def test_action_items_json_valid(self):
        """action_items.json must have all recommendation levels."""
        path = OUTPUT_DIR / "phase05" / "action_items.json"
        assert path.exists(), "action_items.json missing"

        with open(path) as f:
            data = json.load(f)

        assert 'site_recommendations' in data
        assert 'study_recommendations' in data
        assert 'region_recommendations' in data
        assert 'country_recommendations' in data
        assert len(data['site_recommendations']) > 0, "No site recommendations"
        assert len(data['study_recommendations']) > 0, "No study recommendations"

    def test_action_items_have_structure(self):
        """Each recommendation must have priority, issues, recommendations."""
        path = OUTPUT_DIR / "phase05" / "action_items.json"
        if not path.exists():
            pytest.skip("No action_items.json")

        with open(path) as f:
            data = json.load(f)

        for rec in data['site_recommendations'][:5]:
            assert 'priority' in rec, "Site rec missing priority"
            assert 'issues' in rec, "Site rec missing issues"
            assert 'recommendations' in rec, "Site rec missing recommendations"
            assert rec['priority'] in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW'), \
                f"Invalid priority: {rec['priority']}"

    def test_executive_summary_exists(self):
        path = OUTPUT_DIR / "phase05" / "executive_summary.txt"
        assert path.exists(), "executive_summary.txt missing"
        assert path.stat().st_size > 100, "Executive summary too short"

    def test_action_items_summary_counts(self):
        """Summary must report total counts."""
        path = OUTPUT_DIR / "phase05" / "action_items.json"
        if not path.exists():
            pytest.skip("No action_items.json")

        with open(path) as f:
            data = json.load(f)

        assert 'summary' in data
        summary = data['summary']
        assert 'total_subjects' in summary
        assert 'critical_items' in summary


# ============================================================================
# TEST 11: MULTI-AGENT SYSTEM (Phase 07)
# ============================================================================

class TestMultiAgent:
    """Validate multi-agent analysis outputs."""

    def test_multi_agent_recommendations_valid(self):
        path = OUTPUT_DIR / "phase07" / "multi_agent_recommendations.csv"
        if not path.exists():
            pytest.skip("No multi_agent_recommendations.csv")

        df = pd.read_csv(path)
        required = [
            'site_id', 'study', 'risk_category', 'composite_score',
            'agent_consensus', 'escalation_required',
        ]
        missing = [c for c in required if c not in df.columns]
        assert not missing, f"Multi-agent missing: {missing}"

    def test_agent_analysis_json_valid(self):
        path = OUTPUT_DIR / "phase07" / "agent_analysis.json"
        if not path.exists():
            pytest.skip("No agent_analysis.json")

        with open(path) as f:
            data = json.load(f)

        assert 'sites_analyzed' in data
        assert 'site_analyses' in data
        # site_analyses is a dict keyed by site identifier
        assert isinstance(data['site_analyses'], (dict, list)), \
            f"site_analyses is {type(data['site_analyses']).__name__}"
        assert len(data['site_analyses']) > 0, "No site analyses"


# ============================================================================
# TEST 12: CROSS-PHASE CONSISTENCY
# ============================================================================

class TestCrossPhaseConsistency:
    """Verify data flows correctly between pipeline phases."""

    def test_phase03_sites_match_phase08_clusters(self, site_df):
        """All sites from Phase 03 should appear in Phase 08 clusters."""
        if site_df is None:
            pytest.skip("No site data")

        path = OUTPUT_DIR / "phase08" / "site_clusters.csv"
        if not path.exists():
            pytest.skip("No site_clusters.csv")

        clusters = pd.read_csv(path)
        assert len(clusters) == len(site_df), (
            f"Phase 03 sites ({len(site_df)}) ≠ Phase 08 clusters ({len(clusters)})"
        )

    def test_anomaly_scores_cover_flagged_sites(self, site_df, anomaly_summary):
        """Site anomaly scores should match the number of sites with anomalies."""
        if site_df is None or anomaly_summary is None:
            pytest.skip("Missing data")

        path = OUTPUT_DIR / "phase06" / "site_anomaly_scores.csv"
        if not path.exists():
            pytest.skip("No site_anomaly_scores.csv")

        scores = pd.read_csv(path)
        expected = anomaly_summary.get('sites_with_anomalies', 0)
        assert len(scores) == expected, (
            f"Anomaly scores ({len(scores)}) ≠ sites_with_anomalies ({expected})"
        )
        # Must not exceed total sites
        assert len(scores) <= len(site_df), (
            f"Anomaly scores ({len(scores)}) > total sites ({len(site_df)})"
        )

    def test_root_cause_sites_within_total(self, site_df, root_cause_summary):
        """Root cause affected_sites should not exceed total sites."""
        if site_df is None or root_cause_summary is None:
            pytest.skip("Missing data")

        total_sites = len(site_df)
        for rc in root_cause_summary.get('root_causes', []):
            raw = rc.get('affected_sites', 0)
            # Handle string or int values
            affected = int(raw) if raw is not None else 0
            assert affected <= total_sites, (
                f"Root cause affects {affected} sites but only {total_sites} exist"
            )


# ============================================================================
# TEST 13: K-FOLD VALIDATION
# ============================================================================

class TestKFoldValidation:
    """Validate the K-Fold cross-validation results."""

    def test_validation_completed(self, validation_details):
        if validation_details is None:
            pytest.skip("No validation results")

        assert validation_details['n_folds'] == 5
        assert validation_details['n_subjects'] > 50000

    def test_category_agreement_above_99_percent(self, validation_details):
        """Category agreement across folds must be ≥ 99%."""
        if validation_details is None:
            pytest.skip("No validation results")

        agreement = validation_details['category_agreement']['agreement_rate']
        assert agreement >= 0.99, f"Agreement {agreement:.4f} < 99%"

    def test_sae_capture_100_all_folds(self, validation_details):
        """SAE capture must be 100% in every single fold."""
        if validation_details is None:
            pytest.skip("No validation results")

        sae = validation_details['sae_capture']
        assert sae['all_100_pct'] is True, "Not all folds achieved 100% SAE capture"
        assert sae['mean'] == 1.0, f"Mean SAE capture: {sae['mean']}"

    def test_threshold_stability_low_cv(self, validation_details):
        """Threshold coefficient of variation must be < 5%."""
        if validation_details is None:
            pytest.skip("No validation results")

        cv = validation_details['threshold_stability']['cv']
        assert cv < 0.05, f"Threshold CV {cv:.4f} ≥ 5% — unstable"

    def test_fold_details_complete(self, validation_details):
        """Each fold must have detailed metrics."""
        if validation_details is None:
            pytest.skip("No validation results")

        folds = validation_details.get('fold_details', [])
        assert len(folds) == 5, f"Expected 5 folds, got {len(folds)}"


# ============================================================================
# TEST 14: DASHBOARD READINESS
# ============================================================================

class TestDashboardReadiness:
    """Verify all files required by the Streamlit dashboard exist."""

    def test_core_dashboard_files_exist(self):
        """Minimum files needed for the dashboard to load."""
        required = [
            "phase03/master_subject_with_dqi.csv",
            "phase03/master_site_with_dqi.csv",
            "phase03/master_study_with_dqi.csv",
            "phase03/master_country_with_dqi.csv",
            "phase03/master_region_with_dqi.csv",
            "phase05/action_items.json",
            "phase05/recommendations_by_site.csv",
            "phase06/anomaly_summary.json",
            "phase06/anomalies_detected.csv",
            "phase07/multi_agent_recommendations.csv",
            "phase07/agent_analysis.json",
            "phase08/cluster_profiles.csv",
            "phase08/cluster_summary.json",
            "phase09/root_cause_analysis.csv",
            "phase09/root_cause_summary.json",
            "phase09/issue_cooccurrence.csv",
            "phase09/contributing_factors.csv",
        ]
        missing = [f for f in required if not (OUTPUT_DIR / f).exists()]
        assert not missing, f"Dashboard cannot load — missing: {missing}"

    def test_app_file_exists(self):
        """app.py must exist and be valid Python."""
        app_path = SRC_DIR / "app.py"
        assert app_path.exists(), "app.py not found in src/"

        with open(app_path, 'r', encoding='utf-8') as f:
            code = f.read()

        try:
            compile(code, str(app_path), 'exec')
        except SyntaxError as e:
            pytest.fail(f"Syntax error in app.py: {e}")

    def test_app_imports_config(self):
        """app.py must import from config module."""
        app_path = SRC_DIR / "app.py"
        if not app_path.exists():
            pytest.skip("No app.py")

        with open(app_path, 'r', encoding='utf-8') as f:
            code = f.read()

        assert 'from config' in code or 'import config' in code, \
            "app.py does not import config"

    def test_app_has_four_screens(self):
        """Dashboard must define 4 main page functions."""
        app_path = SRC_DIR / "app.py"
        if not app_path.exists():
            pytest.skip("No app.py")

        with open(app_path, 'r', encoding='utf-8') as f:
            code = f.read()

        screens = [
            'page_command_center',
            'page_risk_landscape',
            'page_root_causes',
            'page_action_center',
        ]
        missing = [s for s in screens if s not in code]
        assert not missing, f"Dashboard missing screens: {missing}"


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
