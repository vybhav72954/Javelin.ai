"""
Javelin.AI - Phase 08: Site Clustering Analysis
==============================================================

Clusters clinical trial sites based on data quality patterns to identify
site archetypes and enable targeted intervention strategies.

Prerequisites:
    - Run 03_calculate_dqi.py (Phase 03)
    - Run 06_anomaly_detection.py (Phase 06) - optional
    - outputs/phase03/master_site_with_dqi.csv must exist

Usage:
    python src/phases/08_site_clustering.py
    python src/phases/08_site_clustering.py --algorithm gmm --n-clusters 5
    python src/phases/08_site_clustering.py --algorithm kmeans
    python src/phases/08_site_clustering.py --algorithm dbscan --eps 0.5

CLI Options:
    --algorithm     'gmm' (default), 'kmeans', or 'dbscan'
    --n-clusters    Number of clusters (auto-detect if not specified)
    --auto          Force auto-detection of optimal clusters
    --eps           DBSCAN epsilon parameter (default: 0.5)
    --min-samples   DBSCAN min_samples parameter (default: 5)

Output:
    - outputs/phase08/site_clusters.csv                 # Sites with cluster assignments
    - outputs/phase08/cluster_profiles.csv              # Cluster characteristics
    - outputs/phase08/cluster_report.md                 # Human-readable report
    - outputs/phase08/cluster_summary.json              # Statistics
    - outputs/phase08/cluster_distribution.png          # Visual: cluster sizes
    - outputs/phase08/cluster_heatmap.png               # Visual: feature heatmap
    - outputs/phase08/cluster_pca.png                   # Visual: PCA projection

Clustering Algorithms:
    - GMM (default): Gaussian Mixture Models - soft clustering, probabilistic
    - K-Means: Fast, hard clustering, centroid-based
    - DBSCAN: Density-based, auto-detects clusters

Typical Cluster Profiles:
    - High Performers: Low DQI, few issues
    - Safety Concerns: High SAE/coding issues
    - Data Laggards: Missing visits/pages
    - Systemic Issues: Multiple problem types
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
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
    from config import PROJECT_ROOT, OUTPUT_DIR, PHASE_DIRS, CLUSTERING_FEATURES

    _USING_CONFIG = True
except ImportError:
    _USING_CONFIG = False
    PROJECT_ROOT = _SRC_DIR.parent
    OUTPUT_DIR = PROJECT_ROOT / "outputs"
    PHASE_DIRS = {f'phase_{i:02d}':OUTPUT_DIR for i in range(10)}

    # Default clustering features
    CLUSTERING_FEATURES = [
        'avg_dqi_score',
        'subject_count',
        'high_risk_count',
        'sae_pending_count_sum',
        'missing_visit_count_sum',
        'lab_issues_count_sum',
        'missing_pages_count_sum',
        'uncoded_meddra_count_sum',
        'uncoded_whodd_count_sum',
    ]

# Phase-specific directories
PHASE_03_DIR = PHASE_DIRS.get('phase_03', OUTPUT_DIR)
PHASE_06_DIR = PHASE_DIRS.get('phase_06', OUTPUT_DIR)
PHASE_08_DIR = PHASE_DIRS.get('phase_08', OUTPUT_DIR)

# Input paths
SITE_DQI_PATH = PHASE_03_DIR / "master_site_with_dqi.csv"
SITE_ANOMALY_PATH = PHASE_06_DIR / "site_anomaly_scores.csv"

# Output paths
SITE_CLUSTERS_PATH = PHASE_08_DIR / "site_clusters.csv"
CLUSTER_PROFILES_PATH = PHASE_08_DIR / "cluster_profiles.csv"
CLUSTER_REPORT_PATH = PHASE_08_DIR / "cluster_report.md"
CLUSTER_SUMMARY_PATH = PHASE_08_DIR / "cluster_summary.json"
CLUSTER_DISTRIBUTION_PATH = PHASE_08_DIR / "cluster_distribution.png"
CLUSTER_HEATMAP_PATH = PHASE_08_DIR / "cluster_heatmap.png"
CLUSTER_PCA_PATH = PHASE_08_DIR / "cluster_pca.png"

# Default parameters
DEFAULT_N_CLUSTERS = 5
DEFAULT_ALGORITHM = 'gmm'
MIN_CLUSTER_SIZE = 5


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ClusterProfile:
    """Profile describing a cluster's characteristics."""
    cluster_id: int
    cluster_name: str
    site_count: int
    pct_of_total: float
    avg_dqi_score: float
    avg_subject_count: float
    avg_high_risk_rate: float
    dominant_issues: List[str] = field(default_factory=list)
    risk_level: str = "Medium"
    intervention_priority: int = 3
    recommended_actions: List[str] = field(default_factory=list)
    feature_means: Dict[str, float] = field(default_factory=dict)


@dataclass
class ClusteringResult:
    """Complete clustering analysis result."""
    algorithm: str
    n_clusters: int
    total_sites: int
    features_used: List[str]
    silhouette_score: float
    calinski_harabasz_score: float
    davies_bouldin_score: float
    cluster_profiles: List[ClusterProfile] = field(default_factory=list)
    convergence_info: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def prepare_clustering_features(site_df: pd.DataFrame,
                                feature_list: List[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    """
    Prepare and normalize features for clustering.

    Args:
        site_df: Site-level DataFrame
        feature_list: List of features to use (uses defaults if None)

    Returns:
        Tuple of (normalized feature DataFrame, list of feature names used)
    """
    if feature_list is None:
        feature_list = CLUSTERING_FEATURES.copy()

    # Filter to available features
    available_features = [f for f in feature_list if f in site_df.columns]

    if len(available_features) < 3:
        print(f"  [WARN] Only {len(available_features)} features available, adding derived features")
        # Add derived features if we don't have enough
        if 'high_risk_count' in site_df.columns and 'subject_count' in site_df.columns:
            site_df['high_risk_rate'] = site_df['high_risk_count'] / site_df['subject_count'].clip(lower=1)
            if 'high_risk_rate' not in available_features:
                available_features.append('high_risk_rate')

        if 'subjects_with_issues' in site_df.columns and 'subject_count' in site_df.columns:
            site_df['issue_rate'] = site_df['subjects_with_issues'] / site_df['subject_count'].clip(lower=1)
            if 'issue_rate' not in available_features:
                available_features.append('issue_rate')

    print(f"  Using {len(available_features)} features: {available_features[:5]}...")

    # Extract features
    X = site_df[available_features].copy()

    # Handle missing values
    X = X.fillna(0)

    # Handle infinite values
    X = X.replace([np.inf, -np.inf], 0)

    # Normalize features (StandardScaler equivalent)
    X_normalized = X.copy()
    for col in X.columns:
        col_std = X[col].std()
        col_mean = X[col].mean()
        if col_std > 0:
            X_normalized[col] = (X[col] - col_mean) / col_std
        else:
            X_normalized[col] = 0

    return X_normalized, available_features


# ============================================================================
# CLUSTERING ALGORITHMS
# ============================================================================

def cluster_gmm(X: np.ndarray, n_clusters: int = DEFAULT_N_CLUSTERS,
                random_state: int = 42) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """
    Gaussian Mixture Model clustering (DEFAULT).

    Returns:
        Tuple of (cluster labels, cluster probabilities, convergence info)
    """
    try:
        from sklearn.mixture import GaussianMixture

        gmm = GaussianMixture(
            n_components=n_clusters,
            covariance_type='full',
            n_init=10,
            max_iter=200,
            random_state=random_state
        )

        labels = gmm.fit_predict(X)
        probabilities = gmm.predict_proba(X)

        convergence_info = {
            'converged':gmm.converged_,
            'n_iter':gmm.n_iter_,
            'lower_bound':float(gmm.lower_bound_),
            'bic':float(gmm.bic(X)),
            'aic':float(gmm.aic(X))
        }

        return labels, probabilities, convergence_info

    except ImportError:
        print("  [WARN] sklearn not available, using simplified GMM")
        return _simple_kmeans(X, n_clusters, random_state)


def cluster_kmeans(X: np.ndarray, n_clusters: int = DEFAULT_N_CLUSTERS,
                   random_state: int = 42) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """
    K-Means clustering.

    Returns:
        Tuple of (cluster labels, distance to centroids, convergence info)
    """
    try:
        from sklearn.cluster import KMeans

        kmeans = KMeans(
            n_clusters=n_clusters,
            n_init=10,
            max_iter=300,
            random_state=random_state
        )

        labels = kmeans.fit_predict(X)

        # Calculate distances to all centroids (pseudo-probabilities)
        distances = kmeans.transform(X)
        # Convert to probability-like scores (inverse distance, normalized)
        inv_distances = 1 / (distances + 1e-10)
        probabilities = inv_distances / inv_distances.sum(axis=1, keepdims=True)

        convergence_info = {
            'inertia':float(kmeans.inertia_),
            'n_iter':kmeans.n_iter_
        }

        return labels, probabilities, convergence_info

    except ImportError:
        print("  [WARN] sklearn not available, using simplified K-Means")
        return _simple_kmeans(X, n_clusters, random_state)


def cluster_dbscan(X: np.ndarray, eps: float = 0.5,
                   min_samples: int = 5) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """
    DBSCAN density-based clustering.

    Returns:
        Tuple of (cluster labels, core sample mask, convergence info)
    """
    try:
        from sklearn.cluster import DBSCAN

        dbscan = DBSCAN(
            eps=eps,
            min_samples=min_samples,
            metric='euclidean'
        )

        labels = dbscan.fit_predict(X)

        # For DBSCAN, probabilities are binary (core vs border)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        probabilities = np.zeros((len(labels), max(n_clusters, 1)))
        for i, label in enumerate(labels):
            if label >= 0:
                probabilities[i, label] = 1.0

        n_noise = (labels==-1).sum()

        convergence_info = {
            'n_clusters_found':n_clusters,
            'n_noise_points':int(n_noise),
            'eps':eps,
            'min_samples':min_samples
        }

        return labels, probabilities, convergence_info

    except ImportError:
        print("  [WARN] sklearn not available for DBSCAN, falling back to K-Means")
        return _simple_kmeans(X, DEFAULT_N_CLUSTERS, 42)


def _simple_kmeans(X: np.ndarray, n_clusters: int, random_state: int) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """Simplified K-Means implementation when sklearn unavailable."""
    np.random.seed(random_state)
    n_samples = X.shape[0]

    # Random initialization
    idx = np.random.choice(n_samples, n_clusters, replace=False)
    centroids = X[idx].copy()

    labels = np.zeros(n_samples, dtype=int)

    for iteration in range(100):
        # Assign to nearest centroid
        old_labels = labels.copy()
        for i in range(n_samples):
            distances = np.linalg.norm(X[i] - centroids, axis=1)
            labels[i] = np.argmin(distances)

        # Update centroids
        for k in range(n_clusters):
            mask = labels==k
            if mask.sum() > 0:
                centroids[k] = X[mask].mean(axis=0)

        # Check convergence
        if np.array_equal(labels, old_labels):
            break

    # Calculate pseudo-probabilities
    probabilities = np.zeros((n_samples, n_clusters))
    for i in range(n_samples):
        distances = np.linalg.norm(X[i] - centroids, axis=1)
        inv_dist = 1 / (distances + 1e-10)
        probabilities[i] = inv_dist / inv_dist.sum()

    convergence_info = {'n_iter':iteration + 1, 'method':'simple_kmeans'}

    return labels, probabilities, convergence_info


# ============================================================================
# CLUSTER EVALUATION
# ============================================================================

def evaluate_clustering(X: np.ndarray, labels: np.ndarray) -> Dict[str, float]:
    """
    Evaluate clustering quality using multiple metrics.

    Returns:
        Dictionary of metric names and values
    """
    metrics = {
        'silhouette_score':0.0,
        'calinski_harabasz_score':0.0,
        'davies_bouldin_score':999.0
    }

    # Need at least 2 clusters for metrics
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    if n_clusters < 2:
        return metrics

    # Filter out noise points (label == -1) for evaluation
    valid_mask = labels >= 0
    if valid_mask.sum() < 10:
        return metrics

    X_valid = X[valid_mask]
    labels_valid = labels[valid_mask]

    try:
        from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score

        metrics['silhouette_score'] = float(silhouette_score(X_valid, labels_valid))
        metrics['calinski_harabasz_score'] = float(calinski_harabasz_score(X_valid, labels_valid))
        metrics['davies_bouldin_score'] = float(davies_bouldin_score(X_valid, labels_valid))

    except ImportError:
        # Simplified silhouette calculation
        metrics['silhouette_score'] = _simple_silhouette(X_valid, labels_valid)

    return metrics


def _simple_silhouette(X: np.ndarray, labels: np.ndarray) -> float:
    """Simplified silhouette score calculation."""
    n_samples = len(labels)
    if n_samples < 10:
        return 0.0

    silhouettes = []
    unique_labels = np.unique(labels)

    for i in range(min(n_samples, 500)):  # Sample for speed
        label_i = labels[i]

        # a(i) = mean distance to same cluster
        same_cluster = X[labels==label_i]
        if len(same_cluster) > 1:
            a_i = np.mean(np.linalg.norm(X[i] - same_cluster, axis=1))
        else:
            a_i = 0

        # b(i) = min mean distance to other clusters
        b_i = np.inf
        for label in unique_labels:
            if label!=label_i:
                other_cluster = X[labels==label]
                if len(other_cluster) > 0:
                    mean_dist = np.mean(np.linalg.norm(X[i] - other_cluster, axis=1))
                    b_i = min(b_i, mean_dist)

        if b_i==np.inf:
            b_i = a_i

        # Silhouette
        s_i = (b_i - a_i) / max(a_i, b_i, 1e-10)
        silhouettes.append(s_i)

    return float(np.mean(silhouettes))


def find_optimal_clusters(X: np.ndarray, max_clusters: int = 10,
                          algorithm: str = 'gmm') -> int:
    """
    Find optimal number of clusters using BIC (for GMM) or silhouette.

    Returns:
        Optimal number of clusters
    """
    print("  Finding optimal number of clusters...")

    best_score = -np.inf
    best_n = DEFAULT_N_CLUSTERS

    for n in range(2, min(max_clusters + 1, len(X) // MIN_CLUSTER_SIZE)):
        if algorithm=='gmm':
            labels, _, info = cluster_gmm(X, n)
            # Lower BIC is better, so negate
            score = -info.get('bic', np.inf)
        else:
            labels, _, _ = cluster_kmeans(X, n)
            metrics = evaluate_clustering(X, labels)
            score = metrics['silhouette_score']

        if score > best_score:
            best_score = score
            best_n = n

    print(f"  Optimal clusters: {best_n} (score: {best_score:.4f})")
    return best_n


# ============================================================================
# CLUSTER PROFILING
# ============================================================================

def profile_clusters(site_df: pd.DataFrame, labels: np.ndarray,
                     feature_names: List[str], probabilities: np.ndarray = None) -> List[ClusterProfile]:
    """
    Create detailed profiles for each cluster.

    Returns:
        List of ClusterProfile objects
    """
    profiles = []
    total_sites = len(site_df)
    unique_labels = sorted(set(labels))

    # Filter out noise (-1) for profiling
    unique_labels = [l for l in unique_labels if l >= 0]

    for cluster_id in unique_labels:
        mask = labels==cluster_id
        cluster_sites = site_df[mask]
        n_sites = len(cluster_sites)

        if n_sites==0:
            continue

        # Calculate feature means
        feature_means = {}
        for feat in feature_names:
            if feat in cluster_sites.columns:
                feature_means[feat] = float(cluster_sites[feat].mean())

        # Core metrics
        avg_dqi = cluster_sites['avg_dqi_score'].mean() if 'avg_dqi_score' in cluster_sites else 0
        avg_subjects = cluster_sites['subject_count'].mean() if 'subject_count' in cluster_sites else 0

        high_risk_rate = 0
        if 'high_risk_count' in cluster_sites and 'subject_count' in cluster_sites:
            total_hr = cluster_sites['high_risk_count'].sum()
            total_subj = cluster_sites['subject_count'].sum()
            high_risk_rate = total_hr / max(total_subj, 1)

        # Identify dominant issues
        dominant_issues = []
        issue_cols = {
            'sae_pending_count_sum':'SAE Pending',
            'missing_visit_count_sum':'Missing Visits',
            'missing_pages_count_sum':'Missing Pages',
            'lab_issues_count_sum':'Lab Issues',
            'uncoded_meddra_count_sum':'Uncoded MedDRA',
            'uncoded_whodd_count_sum':'Uncoded WHODD',
            'edrr_open_issues_sum':'Open EDRR Issues'
        }

        issue_rates = {}
        for col, name in issue_cols.items():
            if col in cluster_sites.columns:
                rate = (cluster_sites[col] > 0).mean()
                issue_rates[name] = rate

        # Top 3 issues by prevalence
        sorted_issues = sorted(issue_rates.items(), key=lambda x:-x[1])
        dominant_issues = [f"{name} ({rate * 100:.0f}%)" for name, rate in sorted_issues[:3] if rate > 0.1]

        # Determine cluster name and risk level
        cluster_name, risk_level, priority, actions = _classify_cluster(
            avg_dqi, high_risk_rate, feature_means, issue_rates
        )

        profile = ClusterProfile(
            cluster_id=cluster_id,
            cluster_name=cluster_name,
            site_count=n_sites,
            pct_of_total=round(n_sites / total_sites * 100, 1),
            avg_dqi_score=round(avg_dqi, 4),
            avg_subject_count=round(avg_subjects, 1),
            avg_high_risk_rate=round(high_risk_rate, 4),
            dominant_issues=dominant_issues,
            risk_level=risk_level,
            intervention_priority=priority,
            recommended_actions=actions,
            feature_means=feature_means
        )

        profiles.append(profile)

    # Sort by intervention priority
    profiles.sort(key=lambda p:p.intervention_priority)

    return profiles


def _classify_cluster(avg_dqi: float, high_risk_rate: float,
                      feature_means: Dict, issue_rates: Dict) -> Tuple[str, str, int, List[str]]:
    """
    Classify cluster into archetype and determine intervention strategy.

    Returns:
        Tuple of (cluster_name, risk_level, priority, recommended_actions)
    """
    actions = []

    # Check for safety concerns first
    sae_rate = issue_rates.get('SAE Pending', 0)
    meddra_rate = issue_rates.get('Uncoded MedDRA', 0)

    if sae_rate > 0.3 or meddra_rate > 0.4:
        name = "Safety Concerns"
        risk_level = "Critical"
        priority = 1
        actions = [
            "Immediate SAE review completion",
            "MedDRA coding backlog clearance",
            "Safety officer escalation",
            "Enhanced monitoring protocol"
        ]
        return name, risk_level, priority, actions

    # Check for data laggards (missing data issues)
    visit_rate = issue_rates.get('Missing Visits', 0)
    page_rate = issue_rates.get('Missing Pages', 0)

    if visit_rate > 0.4 or page_rate > 0.4:
        name = "Data Laggards"
        risk_level = "High"
        priority = 2
        actions = [
            "Data entry training program",
            "Weekly compliance check-ins",
            "CRA monitoring frequency increase",
            "SDV prioritization"
        ]
        return name, risk_level, priority, actions

    # Check for systemic issues (multiple problem types)
    issues_present = sum(1 for rate in issue_rates.values() if rate > 0.2)

    if issues_present >= 3 or (avg_dqi > 0.15 and high_risk_rate > 0.2):
        name = "Systemic Issues"
        risk_level = "High"
        priority = 2
        actions = [
            "Root cause analysis required",
            "Site capability assessment",
            "Process improvement plan",
            "Consider triggered audit"
        ]
        return name, risk_level, priority, actions

    # Check for high performers
    if avg_dqi < 0.05 and high_risk_rate < 0.05 and issues_present <= 1:
        name = "High Performers"
        risk_level = "Low"
        priority = 5
        actions = [
            "Maintain current practices",
            "Share best practices with portfolio",
            "Reduced monitoring frequency eligible"
        ]
        return name, risk_level, priority, actions

    # Moderate performers (default)
    if avg_dqi < 0.1:
        name = "Moderate Performers"
        risk_level = "Low"
        priority = 4
        actions = [
            "Standard monitoring protocol",
            "Periodic quality reviews"
        ]
        return name, risk_level, priority, actions

    # Needs improvement
    name = "Needs Improvement"
    risk_level = "Medium"
    priority = 3
    actions = [
        "Targeted intervention for top issues",
        "Monthly progress tracking",
        "Site engagement call"
    ]
    return name, risk_level, priority, actions


# ============================================================================
# VISUALIZATION
# ============================================================================

def create_visualizations(site_df: pd.DataFrame, labels: np.ndarray,
                          X_normalized: pd.DataFrame, profiles: List[ClusterProfile],
                          output_dir: Path):
    """
    Create cluster visualization plots.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt

        _HAS_MATPLOTLIB = True
    except ImportError:
        print("  [WARN] matplotlib not available, skipping visualizations")
        return

    print("\n  Creating visualizations...")

    # 1. Cluster Distribution Pie Chart
    try:
        fig, ax = plt.subplots(figsize=(10, 8))

        cluster_counts = pd.Series(labels).value_counts().sort_index()
        cluster_names = [p.cluster_name for p in sorted(profiles, key=lambda x:x.cluster_id)]

        colors = ['#2ecc71', '#f39c12', '#e74c3c', '#9b59b6', '#3498db', '#1abc9c', '#e67e22']

        wedges, texts, autotexts = ax.pie(
            cluster_counts.values,
            labels=cluster_names[:len(cluster_counts)],
            autopct='%1.1f%%',
            colors=colors[:len(cluster_counts)],
            explode=[0.05] * len(cluster_counts)
        )

        ax.set_title('Site Distribution by Cluster', fontsize=14, fontweight='bold')

        plt.tight_layout()
        plt.savefig(output_dir / "cluster_distribution.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"    [OK] Saved cluster_distribution.png")

    except Exception as e:
        print(f"    [WARN] Could not create distribution plot: {e}")

    # 2. Feature Heatmap
    try:
        fig, ax = plt.subplots(figsize=(12, 8))

        # Calculate cluster means for key features
        feature_cols = ['avg_dqi_score', 'high_risk_count', 'sae_pending_count_sum',
                        'missing_visit_count_sum', 'missing_pages_count_sum', 'lab_issues_count_sum']
        feature_cols = [f for f in feature_cols if f in site_df.columns]

        cluster_means = site_df.copy()
        cluster_means['cluster'] = labels
        cluster_means = cluster_means.groupby('cluster')[feature_cols].mean()

        # Normalize for heatmap
        cluster_means_norm = (cluster_means - cluster_means.min()) / (cluster_means.max() - cluster_means.min() + 1e-10)

        im = ax.imshow(cluster_means_norm.values, cmap='RdYlGn_r', aspect='auto')

        ax.set_xticks(range(len(feature_cols)))
        ax.set_xticklabels([f.replace('_', '\n')[:15] for f in feature_cols], rotation=45, ha='right')
        ax.set_yticks(range(len(cluster_means)))
        cluster_labels = [f"C{i}: {profiles[i].cluster_name if i < len(profiles) else 'Unknown'}"
                          for i in range(len(cluster_means))]
        ax.set_yticklabels(cluster_labels)

        plt.colorbar(im, ax=ax, label='Normalized Value')
        ax.set_title('Cluster Feature Heatmap', fontsize=14, fontweight='bold')

        plt.tight_layout()
        plt.savefig(output_dir / "cluster_heatmap.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"    [OK] Saved cluster_heatmap.png")

    except Exception as e:
        print(f"    [WARN] Could not create heatmap: {e}")

    # 3. PCA Scatter Plot
    try:
        from sklearn.decomposition import PCA

        fig, ax = plt.subplots(figsize=(10, 8))

        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X_normalized.values)

        scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], c=labels, cmap='tab10', alpha=0.6, s=50)

        # Add cluster centers
        for cluster_id in set(labels):
            if cluster_id >= 0:
                mask = labels==cluster_id
                center_x = X_pca[mask, 0].mean()
                center_y = X_pca[mask, 1].mean()
                ax.scatter(center_x, center_y, c='black', marker='X', s=200, edgecolors='white', linewidths=2)
                if cluster_id < len(profiles):
                    ax.annotate(profiles[cluster_id].cluster_name, (center_x, center_y),
                                fontsize=9, fontweight='bold', ha='center', va='bottom')

        ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0] * 100:.1f}%)')
        ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1] * 100:.1f}%)')
        ax.set_title('Site Clusters (PCA Projection)', fontsize=14, fontweight='bold')

        plt.colorbar(scatter, ax=ax, label='Cluster ID')
        plt.tight_layout()
        plt.savefig(output_dir / "cluster_pca.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"    [OK] Saved cluster_pca.png")

    except ImportError:
        print("    [WARN] sklearn not available for PCA visualization")
    except Exception as e:
        print(f"    [WARN] Could not create PCA plot: {e}")


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_report(result: ClusteringResult, site_df: pd.DataFrame, labels: np.ndarray) -> str:
    """Generate markdown report for clustering analysis."""
    lines = []

    lines.append("# JAVELIN.AI Site Clustering Analysis Report")
    lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"\n**Algorithm:** {result.algorithm.upper()}")
    lines.append(f"**Clusters Found:** {result.n_clusters}")
    lines.append(f"**Total Sites:** {result.total_sites}")

    # Methodology
    lines.append("\n## Methodology\n")
    lines.append(f"- **Algorithm:** {result.algorithm.upper()}")
    if result.algorithm=='gmm':
        lines.append("- **Type:** Soft clustering (probabilistic assignment)")
        lines.append("- **Covariance:** Full covariance matrices")
    elif result.algorithm=='kmeans':
        lines.append("- **Type:** Hard clustering (centroid-based)")
    elif result.algorithm=='dbscan':
        lines.append("- **Type:** Density-based clustering")

    lines.append(f"- **Features Used:** {len(result.features_used)}")
    for feat in result.features_used[:10]:
        lines.append(f"  - {feat}")
    if len(result.features_used) > 10:
        lines.append(f"  - ... and {len(result.features_used) - 10} more")

    # Evaluation Metrics
    lines.append("\n## Clustering Quality Metrics\n")
    lines.append("| Metric | Value | Interpretation |")
    lines.append("|--------|-------|----------------|")

    sil = result.silhouette_score
    sil_interp = "Excellent" if sil > 0.5 else "Good" if sil > 0.25 else "Fair" if sil > 0 else "Poor"
    lines.append(f"| Silhouette Score | {sil:.4f} | {sil_interp} |")

    ch = result.calinski_harabasz_score
    lines.append(f"| Calinski-Harabasz | {ch:.2f} | Higher = better separation |")

    db = result.davies_bouldin_score
    db_interp = "Good" if db < 1 else "Fair" if db < 2 else "Poor"
    lines.append(f"| Davies-Bouldin | {db:.4f} | {db_interp} (lower = better) |")

    # Cluster Profiles
    lines.append("\n## Cluster Profiles\n")

    for profile in result.cluster_profiles:
        risk_emoji = {"Critical":"🔴", "High":"🟠", "Medium":"🟡", "Low":"🟢"}.get(profile.risk_level, "⚪")

        lines.append(f"### Cluster {profile.cluster_id}: {profile.cluster_name} {risk_emoji}")
        lines.append(f"\n**Sites:** {profile.site_count} ({profile.pct_of_total}%)")
        lines.append(f"**Risk Level:** {profile.risk_level}")
        lines.append(f"**Intervention Priority:** {profile.intervention_priority}/5")
        lines.append(f"\n**Key Metrics:**")
        lines.append(f"- Average DQI Score: {profile.avg_dqi_score:.4f}")
        lines.append(f"- Average Subject Count: {profile.avg_subject_count:.1f}")
        lines.append(f"- High-Risk Rate: {profile.avg_high_risk_rate * 100:.1f}%")

        if profile.dominant_issues:
            lines.append(f"\n**Dominant Issues:**")
            for issue in profile.dominant_issues:
                lines.append(f"- {issue}")

        if profile.recommended_actions:
            lines.append(f"\n**Recommended Actions:**")
            for action in profile.recommended_actions:
                lines.append(f"- {action}")

        lines.append("")

    # Summary Table
    lines.append("\n## Cluster Summary Table\n")
    lines.append("| Cluster | Name | Sites | DQI | High-Risk % | Priority |")
    lines.append("|---------|------|-------|-----|-------------|----------|")

    for p in result.cluster_profiles:
        lines.append(
            f"| {p.cluster_id} | {p.cluster_name} | {p.site_count} | {p.avg_dqi_score:.4f} | {p.avg_high_risk_rate * 100:.1f}% | {p.intervention_priority} |")

    # Intervention Strategy
    lines.append("\n## Recommended Intervention Strategy\n")

    critical_clusters = [p for p in result.cluster_profiles if p.risk_level=="Critical"]
    high_clusters = [p for p in result.cluster_profiles if p.risk_level=="High"]

    if critical_clusters:
        lines.append("### Immediate Action Required (Critical)\n")
        for p in critical_clusters:
            lines.append(f"**{p.cluster_name}** ({p.site_count} sites)")
            for action in p.recommended_actions[:2]:
                lines.append(f"- {action}")
            lines.append("")

    if high_clusters:
        lines.append("### High Priority (This Week)\n")
        for p in high_clusters:
            lines.append(f"**{p.cluster_name}** ({p.site_count} sites)")
            for action in p.recommended_actions[:2]:
                lines.append(f"- {action}")
            lines.append("")

    lines.append("\n---")
    lines.append(f"\n*Report generated by JAVELIN.AI Site Clustering Module*")

    return "\n".join(lines)


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_site_clustering(algorithm: str = DEFAULT_ALGORITHM,
                        n_clusters: int = None,
                        auto_clusters: bool = False,
                        eps: float = 0.5,
                        min_samples: int = 5) -> bool:
    """
    Main function to run site clustering analysis.

    Args:
        algorithm: 'gmm' (default), 'kmeans', or 'dbscan'
        n_clusters: Number of clusters (None = auto-detect for GMM/KMeans)
        auto_clusters: Force auto-detection of optimal clusters
        eps: DBSCAN epsilon parameter
        min_samples: DBSCAN min_samples parameter

    Returns:
        True if successful
    """
    print("=" * 70)
    print("JAVELIN.AI - SITE CLUSTERING ANALYSIS")
    print("=" * 70)

    if _USING_CONFIG:
        print("(Using centralized config with PHASE_DIRS)")

    print(f"\nInput Directory (Phase 03): {PHASE_03_DIR}")
    print(f"Input Directory (Phase 06): {PHASE_06_DIR}")
    print(f"Output Directory (Phase 08): {PHASE_08_DIR}")
    print(f"\nAlgorithm: {algorithm.upper()}")

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

    # Load anomaly scores if available
    if SITE_ANOMALY_PATH.exists():
        anomaly_df = pd.read_csv(SITE_ANOMALY_PATH)
        site_df = site_df.merge(
            anomaly_df[['study', 'site_id', 'anomaly_score', 'is_anomaly']],
            on=['study', 'site_id'],
            how='left'
        )
        site_df['anomaly_score'] = site_df['anomaly_score'].fillna(0)
        site_df['is_anomaly'] = site_df['is_anomaly'].fillna(False)
        print(f"  [OK] Merged anomaly scores")

    # Prepare features
    print("\n" + "=" * 70)
    print("STEP 2: PREPARE FEATURES")
    print("=" * 70)

    X_normalized, feature_names = prepare_clustering_features(site_df)
    X = X_normalized.values

    print(f"  Feature matrix shape: {X.shape}")

    # Determine number of clusters
    print("\n" + "=" * 70)
    print("STEP 3: DETERMINE CLUSTER COUNT")
    print("=" * 70)

    if algorithm=='dbscan':
        print("  DBSCAN auto-determines clusters based on density")
        effective_n_clusters = None
    elif n_clusters is None or auto_clusters:
        effective_n_clusters = find_optimal_clusters(X, max_clusters=10, algorithm=algorithm)
    else:
        effective_n_clusters = n_clusters
        print(f"  Using specified n_clusters: {effective_n_clusters}")

    # Run clustering
    print("\n" + "=" * 70)
    print("STEP 4: RUN CLUSTERING")
    print("=" * 70)

    print(f"  Running {algorithm.upper()} clustering...")

    if algorithm=='gmm':
        labels, probabilities, convergence_info = cluster_gmm(X, effective_n_clusters)
    elif algorithm=='kmeans':
        labels, probabilities, convergence_info = cluster_kmeans(X, effective_n_clusters)
    elif algorithm=='dbscan':
        labels, probabilities, convergence_info = cluster_dbscan(X, eps, min_samples)
        effective_n_clusters = convergence_info.get('n_clusters_found', 0)
    else:
        print(f"  [ERROR] Unknown algorithm: {algorithm}")
        return False

    n_clusters_found = len(set(labels)) - (1 if -1 in labels else 0)
    print(f"  [OK] Found {n_clusters_found} clusters")

    if 'converged' in convergence_info:
        print(f"  Convergence: {'Yes' if convergence_info['converged'] else 'No'}")
    if 'n_iter' in convergence_info:
        print(f"  Iterations: {convergence_info['n_iter']}")

    # Evaluate clustering
    print("\n" + "=" * 70)
    print("STEP 5: EVALUATE CLUSTERING")
    print("=" * 70)

    metrics = evaluate_clustering(X, labels)

    print(f"  Silhouette Score: {metrics['silhouette_score']:.4f}")
    print(f"  Calinski-Harabasz: {metrics['calinski_harabasz_score']:.2f}")
    print(f"  Davies-Bouldin: {metrics['davies_bouldin_score']:.4f}")

    # Profile clusters
    print("\n" + "=" * 70)
    print("STEP 6: PROFILE CLUSTERS")
    print("=" * 70)

    profiles = profile_clusters(site_df, labels, feature_names, probabilities)

    print(f"\n  Cluster Summary:")
    print(f"  {'ID':<4} {'Name':<20} {'Sites':<8} {'DQI':<10} {'Risk':<10}")
    print("  " + "-" * 56)

    for p in profiles:
        print(f"  {p.cluster_id:<4} {p.cluster_name:<20} {p.site_count:<8} {p.avg_dqi_score:<10.4f} {p.risk_level:<10}")

    # Create result object
    result = ClusteringResult(
        algorithm=algorithm,
        n_clusters=n_clusters_found,
        total_sites=len(site_df),
        features_used=feature_names,
        silhouette_score=metrics['silhouette_score'],
        calinski_harabasz_score=metrics['calinski_harabasz_score'],
        davies_bouldin_score=metrics['davies_bouldin_score'],
        cluster_profiles=profiles,
        convergence_info=convergence_info
    )

    # Save outputs
    print("\n" + "=" * 70)
    print("STEP 7: SAVE OUTPUTS")
    print("=" * 70)

    PHASE_08_DIR.mkdir(parents=True, exist_ok=True)

    # Add cluster info to site dataframe
    site_df['cluster_id'] = labels
    site_df['cluster_probability'] = probabilities.max(axis=1) if probabilities.ndim > 1 else 1.0

    # Map cluster names
    cluster_name_map = {p.cluster_id:p.cluster_name for p in profiles}
    site_df['cluster_name'] = site_df['cluster_id'].map(cluster_name_map).fillna('Noise')

    # Save site clusters
    site_df.to_csv(SITE_CLUSTERS_PATH, index=False, encoding='utf-8')
    print(f"  [OK] Saved: {SITE_CLUSTERS_PATH}")

    # Save cluster profiles
    profiles_df = pd.DataFrame([asdict(p) for p in profiles])
    profiles_df.to_csv(CLUSTER_PROFILES_PATH, index=False, encoding='utf-8')
    print(f"  [OK] Saved: {CLUSTER_PROFILES_PATH}")

    # Save summary JSON
    summary = {
        'generated':datetime.now().isoformat(),
        'algorithm':algorithm,
        'n_clusters':n_clusters_found,
        'total_sites':len(site_df),
        'features_used':feature_names,
        'metrics':metrics,
        'convergence':convergence_info,
        'cluster_summary':[
            {
                'cluster_id':p.cluster_id,
                'name':p.cluster_name,
                'sites':p.site_count,
                'pct':p.pct_of_total,
                'risk_level':p.risk_level,
                'priority':p.intervention_priority
            }
            for p in profiles
        ]
    }

    with open(CLUSTER_SUMMARY_PATH, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"  [OK] Saved: {CLUSTER_SUMMARY_PATH}")

    # Generate report
    report = generate_report(result, site_df, labels)
    with open(CLUSTER_REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  [OK] Saved: {CLUSTER_REPORT_PATH}")

    # Create visualizations
    create_visualizations(site_df, labels, X_normalized, profiles, PHASE_08_DIR)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    critical_count = sum(1 for p in profiles if p.risk_level=="Critical")
    high_count = sum(1 for p in profiles if p.risk_level=="High")

    print(f"""
Algorithm: {algorithm.upper()}
Clusters Found: {n_clusters_found}
Total Sites: {len(site_df):,}

Cluster Risk Distribution:
  Critical: {critical_count} clusters
  High: {high_count} clusters
  Medium: {sum(1 for p in profiles if p.risk_level=="Medium")} clusters
  Low: {sum(1 for p in profiles if p.risk_level=="Low")} clusters

Quality Metrics:
  Silhouette: {metrics['silhouette_score']:.4f}
  Calinski-Harabasz: {metrics['calinski_harabasz_score']:.2f}
  Davies-Bouldin: {metrics['davies_bouldin_score']:.4f}
""")

    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print(f"""
1. Review: {CLUSTER_REPORT_PATH}
2. Check visualizations in {PHASE_08_DIR}
3. Run: python src/09_root_cause_analysis.py
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description="JAVELIN.AI Site Clustering Analysis")
    parser.add_argument("--algorithm", type=str, default=DEFAULT_ALGORITHM,
                        choices=['gmm', 'kmeans', 'dbscan'],
                        help="Clustering algorithm (default: gmm)")
    parser.add_argument("--n-clusters", type=int, default=None,
                        help="Number of clusters (auto-detect if not specified)")
    parser.add_argument("--auto", action="store_true",
                        help="Force auto-detection of optimal clusters")
    parser.add_argument("--eps", type=float, default=0.5,
                        help="DBSCAN epsilon parameter")
    parser.add_argument("--min-samples", type=int, default=5,
                        help="DBSCAN min_samples parameter")

    args = parser.parse_args()

    success = run_site_clustering(
        algorithm=args.algorithm,
        n_clusters=args.n_clusters,
        auto_clusters=args.auto,
        eps=args.eps,
        min_samples=args.min_samples
    )

    if not success:
        exit(1)