"""
Javelin.AI - Step 8: Site Clustering & Segmentation
=====================================================

WHAT THIS DOES:
---------------
Uses unsupervised machine learning to group similar sites based on their
data quality profiles, enabling targeted interventions at the cluster level.

CLUSTERING METHODS:
-------------------
1. K-MEANS          - Fast, scalable, good for spherical clusters
2. HIERARCHICAL     - Shows nested structure, good for dendrograms
3. DBSCAN           - Density-based, finds outlier sites automatically
4. GAUSSIAN MIXTURE - Soft clustering, probabilistic membership

CLUSTER INSIGHTS:
-----------------
- Cluster profiles: What defines each group
- Risk concentration: Which clusters have most high-risk sites
- Regional patterns: Geographic clustering tendencies
- Study patterns: Which studies cluster together
- Actionable segments: Targeted intervention groups

WHY CLUSTERING:
---------------
1. Portfolio segmentation: Group sites for tiered monitoring
2. Resource allocation: Focus interventions on problematic clusters
3. Pattern discovery: Find non-obvious groupings
4. Benchmarking: Compare sites against cluster peers
5. Scalability: Manage 3,400 sites as ~6-8 actionable segments

Usage:
    python src/08_site_clustering.py
    python src/08_site_clustering.py --clusters 6
    python src/08_site_clustering.py --method dbscan

Outputs:
    - outputs/site_clusters.csv             : Site-to-cluster mapping
    - outputs/cluster_profiles.csv          : Cluster characteristics
    - outputs/cluster_summary.json          : Summary statistics
    - outputs/cluster_report.md             : Human-readable report
    - outputs/cluster_dendrogram.png        : Hierarchical visualization (optional)
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

# ML imports
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.decomposition import PCA
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from scipy.spatial.distance import pdist

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Input files from previous steps
SITE_DQI_PATH = OUTPUT_DIR / "master_site_with_dqi.csv"
SUBJECT_DQI_PATH = OUTPUT_DIR / "master_subject_with_dqi.csv"
ANOMALIES_PATH = OUTPUT_DIR / "anomalies_detected.csv"

# Clustering Configuration
DEFAULT_CLUSTERS = 6  # Default number of clusters for K-Means
MIN_CLUSTERS = 3
MAX_CLUSTERS = 12
RANDOM_STATE = 42

# Features for clustering (normalized issue metrics)
CLUSTERING_FEATURES = [
    # Risk metrics
    'avg_dqi_score',
    'high_risk_pct',  # Derived: high_risk_count / subject_count
    'medium_risk_pct',  # Derived

    # Safety metrics (normalized)
    'sae_rate',  # Derived: sae_pending_count_sum / subject_count
    'meddra_rate',  # Derived: uncoded_meddra_count_sum / subject_count

    # Completeness metrics (normalized)
    'missing_visit_rate',  # Derived
    'missing_pages_rate',  # Derived
    'lab_issues_rate',  # Derived

    # Timeliness metrics
    'avg_days_outstanding',  # Derived: max_days_outstanding_sum / subject_count
    'avg_days_page_missing',  # Derived

    # Volume metrics
    'log_subject_count',  # Log-transformed subject count
    'issue_diversity',  # Number of different issue types
]

# Cluster naming thresholds
CLUSTER_NAMING_RULES = {
    'HIGH_RISK':{'high_risk_pct':0.25, 'avg_dqi_score':0.15},
    'SAE_FOCUS':{'sae_rate':0.5},
    'COMPLETENESS_ISSUES':{'missing_pages_rate':0.3, 'missing_visit_rate':0.2},
    'TIMELINESS_ISSUES':{'avg_days_outstanding':30},
    'LOW_VOLUME':{'log_subject_count':1.5},
    'HIGH_VOLUME_CLEAN':{'log_subject_count':3.0, 'avg_dqi_score':0.03},
}


# ============================================================================
# DATA PREPARATION
# ============================================================================

def load_data() -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
    """Load all required data files."""
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

    return site_df, subject_df, anomaly_df


def prepare_features(site_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    """
    Prepare and normalize features for clustering.

    Returns:
        - feature_df: DataFrame with computed features
        - scaled_df: Scaled features for clustering
        - feature_names: List of feature column names
    """
    print("  Computing derived features...")

    df = site_df.copy()

    # Handle missing values in base columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)

    # Derived rate features (normalized by subject count)
    subject_count = df['subject_count'].replace(0, 1)  # Avoid division by zero

    # Risk percentages
    df['high_risk_pct'] = df['high_risk_count'] / subject_count
    df['medium_risk_pct'] = df['medium_risk_count'] / subject_count
    df['low_risk_pct'] = 1 - df['high_risk_pct'] - df['medium_risk_pct']

    # Safety rates
    df['sae_rate'] = df.get('sae_pending_count_sum', 0) / subject_count
    df['meddra_rate'] = df.get('uncoded_meddra_count_sum', 0) / subject_count

    # Completeness rates
    df['missing_visit_rate'] = df.get('missing_visit_count_sum', 0) / subject_count
    df['missing_pages_rate'] = df.get('missing_pages_count_sum', 0) / subject_count
    df['lab_issues_rate'] = df.get('lab_issues_count_sum', 0) / subject_count

    # Timeliness (average per subject)
    df['avg_days_outstanding'] = df.get('max_days_outstanding_sum', 0) / subject_count
    df['avg_days_page_missing'] = df.get('max_days_page_missing_sum', 0) / subject_count

    # Volume (log-transformed to handle skewness)
    df['log_subject_count'] = np.log1p(df['subject_count'])

    # Issue diversity (number of different issue types present)
    issue_cols = ['sae_pending_count_sum', 'uncoded_meddra_count_sum',
                  'missing_visit_count_sum', 'missing_pages_count_sum',
                  'lab_issues_count_sum', 'max_days_outstanding_sum',
                  'uncoded_whodd_count_sum', 'edrr_open_issues_sum']
    existing_issue_cols = [c for c in issue_cols if c in df.columns]
    df['issue_diversity'] = (df[existing_issue_cols] > 0).sum(axis=1)

    # Select features for clustering
    available_features = [f for f in CLUSTERING_FEATURES if f in df.columns]
    feature_df = df[available_features].copy()

    # Handle any remaining NaN/Inf values
    feature_df = feature_df.replace([np.inf, -np.inf], np.nan)
    feature_df = feature_df.fillna(0)

    print(f"    Computed {len(available_features)} features")

    # Scale features using RobustScaler (handles outliers better)
    print("  Scaling features...")
    scaler = RobustScaler()
    scaled_values = scaler.fit_transform(feature_df)
    scaled_df = pd.DataFrame(scaled_values, columns=available_features, index=df.index)

    # Store original features for profiling
    feature_df['study'] = df['study']
    feature_df['site_id'] = df['site_id']
    feature_df['country'] = df.get('country', 'Unknown')
    feature_df['region'] = df.get('region', 'Unknown')
    feature_df['subject_count'] = df['subject_count']
    feature_df['site_risk_category'] = df.get('site_risk_category', 'Unknown')

    return feature_df, scaled_df, available_features


# ============================================================================
# CLUSTERING ALGORITHMS
# ============================================================================

def find_optimal_clusters(scaled_df: pd.DataFrame,
                          min_k: int = MIN_CLUSTERS,
                          max_k: int = MAX_CLUSTERS) -> Tuple[int, Dict]:
    """
    Find optimal number of clusters using multiple metrics.

    Returns:
        - optimal_k: Recommended number of clusters
        - scores: Dictionary of scores for each k
    """
    print("  Finding optimal cluster count...")

    scores = {
        'silhouette':{},
        'calinski_harabasz':{},
        'davies_bouldin':{},
        'inertia':{}
    }

    X = scaled_df.values

    for k in range(min_k, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = kmeans.fit_predict(X)

        scores['silhouette'][k] = silhouette_score(X, labels)
        scores['calinski_harabasz'][k] = calinski_harabasz_score(X, labels)
        scores['davies_bouldin'][k] = davies_bouldin_score(X, labels)
        scores['inertia'][k] = kmeans.inertia_

    # Find optimal k using silhouette score (higher is better)
    optimal_k = max(scores['silhouette'], key=scores['silhouette'].get)

    print(f"    Silhouette scores: {', '.join([f'k={k}: {s:.3f}' for k, s in scores['silhouette'].items()])}")
    print(f"    Optimal clusters: {optimal_k} (silhouette: {scores['silhouette'][optimal_k]:.3f})")

    return optimal_k, scores


def cluster_kmeans(scaled_df: pd.DataFrame, n_clusters: int) -> np.ndarray:
    """Perform K-Means clustering."""
    print(f"  Running K-Means (k={n_clusters})...")

    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=RANDOM_STATE,
        n_init=20,
        max_iter=500
    )
    labels = kmeans.fit_predict(scaled_df.values)

    silhouette = silhouette_score(scaled_df.values, labels)
    print(f"    K-Means complete (silhouette: {silhouette:.3f})")

    return labels


def cluster_hierarchical(scaled_df: pd.DataFrame, n_clusters: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Perform Hierarchical clustering.

    Returns:
        - labels: Cluster assignments
        - linkage_matrix: For dendrogram visualization
    """
    print(f"  Running Hierarchical clustering (k={n_clusters})...")

    # Compute linkage matrix
    linkage_matrix = linkage(scaled_df.values, method='ward')

    # Get cluster labels
    labels = fcluster(linkage_matrix, n_clusters, criterion='maxclust') - 1

    silhouette = silhouette_score(scaled_df.values, labels)
    print(f"    Hierarchical complete (silhouette: {silhouette:.3f})")

    return labels, linkage_matrix


def cluster_dbscan(scaled_df: pd.DataFrame, eps: float = 0.8, min_samples: int = 5) -> np.ndarray:
    """
    Perform DBSCAN clustering.

    Note: DBSCAN automatically determines cluster count and identifies outliers (label=-1).
    """
    print(f"  Running DBSCAN (eps={eps}, min_samples={min_samples})...")

    dbscan = DBSCAN(eps=eps, min_samples=min_samples, metric='euclidean')
    labels = dbscan.fit_predict(scaled_df.values)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_outliers = (labels==-1).sum()

    if n_clusters > 1:
        # Only compute silhouette for non-outliers
        mask = labels!=-1
        if mask.sum() > n_clusters:
            silhouette = silhouette_score(scaled_df.values[mask], labels[mask])
            print(f"    DBSCAN complete: {n_clusters} clusters, {n_outliers} outliers (silhouette: {silhouette:.3f})")
        else:
            print(f"    DBSCAN complete: {n_clusters} clusters, {n_outliers} outliers")
    else:
        print(f"    DBSCAN found only {n_clusters} cluster(s) and {n_outliers} outliers")

    return labels


def cluster_gmm(scaled_df: pd.DataFrame, n_clusters: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Perform Gaussian Mixture Model clustering.

    Returns:
        - labels: Hard cluster assignments
        - probabilities: Soft membership probabilities
    """
    print(f"  Running Gaussian Mixture Model (k={n_clusters})...")

    gmm = GaussianMixture(
        n_components=n_clusters,
        random_state=RANDOM_STATE,
        n_init=5,
        covariance_type='full'
    )
    labels = gmm.fit_predict(scaled_df.values)
    probabilities = gmm.predict_proba(scaled_df.values)

    silhouette = silhouette_score(scaled_df.values, labels)
    print(f"    GMM complete (silhouette: {silhouette:.3f})")

    return labels, probabilities


# ============================================================================
# CLUSTER PROFILING & ANALYSIS
# ============================================================================

def profile_clusters(feature_df: pd.DataFrame,
                     labels: np.ndarray,
                     feature_names: List[str]) -> pd.DataFrame:
    """
    Create detailed profiles for each cluster.

    Returns:
        DataFrame with cluster statistics and characteristics.
    """
    print("  Generating cluster profiles...")

    df = feature_df.copy()
    df['cluster'] = labels

    profiles = []

    for cluster_id in sorted(df['cluster'].unique()):
        if cluster_id==-1:  # DBSCAN outliers
            cluster_name = "Outliers"
        else:
            cluster_name = f"Cluster_{cluster_id}"

        cluster_data = df[df['cluster']==cluster_id]
        n_sites = len(cluster_data)

        profile = {
            'cluster_id':cluster_id,
            'cluster_name':cluster_name,
            'n_sites':n_sites,
            'pct_of_total':n_sites / len(df) * 100,
        }

        # Feature statistics
        for feature in feature_names:
            if feature in cluster_data.columns:
                profile[f'{feature}_mean'] = cluster_data[feature].mean()
                profile[f'{feature}_std'] = cluster_data[feature].std()
                profile[f'{feature}_median'] = cluster_data[feature].median()

        # Risk distribution
        if 'site_risk_category' in cluster_data.columns:
            risk_counts = cluster_data['site_risk_category'].value_counts()
            profile['high_risk_sites'] = risk_counts.get('High', 0)
            profile['medium_risk_sites'] = risk_counts.get('Medium', 0)
            profile['low_risk_sites'] = risk_counts.get('Low', 0)
            profile['high_risk_rate'] = profile['high_risk_sites'] / n_sites if n_sites > 0 else 0

        # Subject volume
        profile['total_subjects'] = cluster_data['subject_count'].sum()
        profile['avg_subjects_per_site'] = cluster_data['subject_count'].mean()

        # Geographic distribution
        if 'country' in cluster_data.columns:
            top_countries = cluster_data['country'].value_counts().head(5)
            profile['top_countries'] = ', '.join([f"{c}({n})" for c, n in top_countries.items()])
            profile['n_countries'] = cluster_data['country'].nunique()

        # Regional distribution
        if 'region' in cluster_data.columns:
            region_counts = cluster_data['region'].value_counts()
            profile['region_distribution'] = ', '.join([f"{r}({n})" for r, n in region_counts.items()])

        # Study distribution
        if 'study' in cluster_data.columns:
            profile['n_studies'] = cluster_data['study'].nunique()
            top_studies = cluster_data['study'].value_counts().head(3)
            profile['top_studies'] = ', '.join([f"{s}({n})" for s, n in top_studies.items()])

        profiles.append(profile)

    profiles_df = pd.DataFrame(profiles)
    print(f"    Generated profiles for {len(profiles)} clusters")

    return profiles_df


def name_clusters(profiles_df: pd.DataFrame, feature_df: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """
    Assign meaningful names to clusters based on their characteristics.
    """
    print("  Assigning cluster names...")

    df = feature_df.copy()
    df['cluster'] = labels

    # Calculate global averages for comparison
    global_means = {}
    for col in ['avg_dqi_score', 'high_risk_pct', 'sae_rate', 'missing_pages_rate',
                'missing_visit_rate', 'avg_days_outstanding', 'log_subject_count']:
        if col in df.columns:
            global_means[col] = df[col].mean()

    cluster_names = {}

    for idx, row in profiles_df.iterrows():
        cluster_id = row['cluster_id']

        if cluster_id==-1:
            cluster_names[cluster_id] = "Outlier_Sites"
            continue

        # Get cluster data
        cluster_data = df[df['cluster']==cluster_id]

        # Determine name based on dominant characteristic
        name_parts = []

        # Check high risk concentration
        if row.get('high_risk_rate', 0) > 0.30:
            name_parts.append("High_Risk")
        elif row.get('high_risk_rate', 0) < 0.05:
            name_parts.append("Low_Risk")

        # Check DQI score
        avg_dqi = row.get('avg_dqi_score_mean', 0)
        if avg_dqi > global_means.get('avg_dqi_score', 0) * 2:
            name_parts.append("Elevated_DQI")
        elif avg_dqi < global_means.get('avg_dqi_score', 0) * 0.3:
            name_parts.append("Clean")

        # Check SAE focus
        sae_rate = row.get('sae_rate_mean', 0)
        if sae_rate > global_means.get('sae_rate', 0) * 3:
            name_parts.append("SAE_Focus")

        # Check completeness issues
        missing_rate = row.get('missing_pages_rate_mean', 0) + row.get('missing_visit_rate_mean', 0)
        if missing_rate > 0.5:
            name_parts.append("Completeness_Issues")

        # Check timeliness
        days_out = row.get('avg_days_outstanding_mean', 0)
        if days_out > 50:
            name_parts.append("Stale_Data")

        # Check volume
        log_subj = row.get('log_subject_count_mean', 0)
        if log_subj > global_means.get('log_subject_count', 0) * 1.5:
            name_parts.append("High_Volume")
        elif log_subj < global_means.get('log_subject_count', 0) * 0.5:
            name_parts.append("Low_Volume")

        # Assign name
        if name_parts:
            cluster_names[cluster_id] = f"Cluster_{cluster_id}_{'_'.join(name_parts[:2])}"
        else:
            cluster_names[cluster_id] = f"Cluster_{cluster_id}_Average"

    # Update profiles with names
    profiles_df['cluster_name'] = profiles_df['cluster_id'].map(cluster_names)

    print(f"    Named {len(cluster_names)} clusters")

    return profiles_df


def analyze_cluster_patterns(feature_df: pd.DataFrame,
                             labels: np.ndarray,
                             anomaly_df: Optional[pd.DataFrame] = None) -> Dict:
    """
    Analyze patterns within and across clusters.

    Returns:
        Dictionary with pattern analysis results.
    """
    print("  Analyzing cluster patterns...")

    df = feature_df.copy()
    df['cluster'] = labels

    patterns = {
        'cluster_stability':{},
        'inter_cluster_distances':{},
        'feature_importance':{},
        'anomaly_concentration':{},
        'regional_patterns':{},
        'study_patterns':{}
    }

    # Feature importance (which features differ most between clusters)
    feature_cols = [c for c in df.columns if c not in ['study', 'site_id', 'country', 'region',
                                                       'subject_count', 'site_risk_category', 'cluster']]

    feature_variance = {}
    for col in feature_cols:
        cluster_means = df.groupby('cluster')[col].mean()
        global_mean = df[col].mean()
        variance = ((cluster_means - global_mean) ** 2).mean()
        feature_variance[col] = variance

    # Sort by variance (importance)
    patterns['feature_importance'] = dict(sorted(feature_variance.items(),
                                                 key=lambda x:x[1], reverse=True)[:10])

    # Regional patterns - which regions dominate which clusters
    if 'region' in df.columns:
        for cluster_id in sorted(df['cluster'].unique()):
            cluster_data = df[df['cluster']==cluster_id]
            region_pcts = (cluster_data['region'].value_counts(normalize=True) * 100).to_dict()
            patterns['regional_patterns'][f'cluster_{cluster_id}'] = region_pcts

    # Study patterns - which studies are concentrated in which clusters
    if 'study' in df.columns:
        study_cluster = df.groupby(['study', 'cluster']).size().unstack(fill_value=0)
        for study in study_cluster.index:
            dominant_cluster = study_cluster.loc[study].idxmax()
            dominant_pct = study_cluster.loc[study].max() / study_cluster.loc[study].sum() * 100
            if dominant_pct > 50:  # More than half of study's sites in one cluster
                patterns['study_patterns'][study] = {
                    'dominant_cluster':int(dominant_cluster),
                    'concentration':f'{dominant_pct:.1f}%'
                }

    # Anomaly concentration
    if anomaly_df is not None and len(anomaly_df) > 0:
        # Match anomalies to sites
        site_anomaly_counts = anomaly_df.groupby('site_id').size()
        df['anomaly_count'] = df['site_id'].map(site_anomaly_counts).fillna(0)

        for cluster_id in sorted(df['cluster'].unique()):
            cluster_data = df[df['cluster']==cluster_id]
            patterns['anomaly_concentration'][f'cluster_{cluster_id}'] = {
                'total_anomalies':int(cluster_data['anomaly_count'].sum()),
                'sites_with_anomalies':int((cluster_data['anomaly_count'] > 0).sum()),
                'avg_anomalies_per_site':float(cluster_data['anomaly_count'].mean())
            }

    print(f"    Identified patterns across {len(df['cluster'].unique())} clusters")

    return patterns


def generate_cluster_recommendations(profiles_df: pd.DataFrame,
                                     patterns: Dict) -> List[Dict]:
    """
    Generate actionable recommendations for each cluster.
    """
    print("  Generating cluster recommendations...")

    recommendations = []

    for idx, row in profiles_df.iterrows():
        cluster_id = row['cluster_id']
        cluster_name = row['cluster_name']

        if cluster_id==-1:
            # Outlier recommendations
            recommendations.append({
                'cluster_id':cluster_id,
                'cluster_name':cluster_name,
                'priority':'HIGH',
                'recommendation':'Review outlier sites individually - they may have unique issues or data errors',
                'action_type':'INVESTIGATION',
                'estimated_effort':'Medium - requires individual site review'
            })
            continue

        recs = []
        priority = 'MEDIUM'

        # High risk cluster
        if row.get('high_risk_rate', 0) > 0.25:
            priority = 'CRITICAL'
            recs.append(
                f"CRITICAL: {row['high_risk_sites']:.0f} high-risk sites ({row['high_risk_rate'] * 100:.1f}%) - prioritize for immediate intervention")

        # SAE issues
        if row.get('sae_rate_mean', 0) > 0.3:
            priority = 'CRITICAL' if priority!='CRITICAL' else priority
            recs.append(f"SAE Alert: Cluster has elevated SAE rate - expedite pharmacovigilance review")

        # Completeness issues
        missing_rate = row.get('missing_pages_rate_mean', 0) + row.get('missing_visit_rate_mean', 0)
        if missing_rate > 0.3:
            recs.append(f"Data Completeness: High missing data rate - implement targeted data entry support")

        # Timeliness issues
        if row.get('avg_days_outstanding_mean', 0) > 45:
            recs.append(
                f"Timeliness: Stale queries averaging {row.get('avg_days_outstanding_mean', 0):.0f} days - escalate query resolution")

        # Volume-based recommendations
        if row.get('avg_subjects_per_site', 0) > 30 and row.get('high_risk_rate', 0) < 0.1:
            recs.append(f"Efficiency: High-volume, low-risk cluster - consider reduced monitoring frequency")

        # Regional concentration
        if row.get('n_countries', 0)==1:
            recs.append(f"Regional: Single-country cluster - consider country-specific training or support")

        # Default recommendation
        if not recs:
            recs.append("Monitor: Cluster within normal parameters - maintain standard oversight")
            priority = 'LOW'

        recommendations.append({
            'cluster_id':cluster_id,
            'cluster_name':cluster_name,
            'priority':priority,
            'n_sites':row['n_sites'],
            'recommendation':'; '.join(recs),
            'action_type':'INTERVENTION' if priority in ['CRITICAL', 'HIGH'] else 'MONITORING',
            'estimated_effort':'High' if row['n_sites'] > 100 else 'Medium' if row['n_sites'] > 30 else 'Low'
        })

    print(f"    Generated recommendations for {len(recommendations)} clusters")

    return recommendations


# ============================================================================
# VISUALIZATION (Optional - requires matplotlib)
# ============================================================================

def create_cluster_visualizations(feature_df: pd.DataFrame,
                                  scaled_df: pd.DataFrame,
                                  labels: np.ndarray,
                                  linkage_matrix: Optional[np.ndarray] = None) -> Dict[str, Path]:
    """
    Create cluster visualizations.

    Returns:
        Dictionary of visualization file paths.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
    except ImportError:
        print("    matplotlib not available - skipping visualizations")
        return {}

    print("  Creating visualizations...")

    viz_paths = {}

    # 1. PCA Scatter Plot
    try:
        pca = PCA(n_components=2)
        pca_coords = pca.fit_transform(scaled_df.values)

        fig, ax = plt.subplots(figsize=(12, 8))
        scatter = ax.scatter(pca_coords[:, 0], pca_coords[:, 1],
                             c=labels, cmap='Set1', alpha=0.6, s=30)
        ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0] * 100:.1f}% variance)')
        ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1] * 100:.1f}% variance)')
        ax.set_title('Site Clusters - PCA Projection')
        plt.colorbar(scatter, label='Cluster')

        pca_path = OUTPUT_DIR / "cluster_pca.png"
        plt.savefig(pca_path, dpi=150, bbox_inches='tight')
        plt.close()

        viz_paths['pca'] = pca_path
        print(f"    Saved PCA plot: {pca_path}")
    except Exception as e:
        print(f"    PCA plot failed: {e}")

    # 2. Dendrogram (if hierarchical clustering was used)
    if linkage_matrix is not None:
        try:
            fig, ax = plt.subplots(figsize=(16, 8))
            dendrogram(linkage_matrix, ax=ax, truncate_mode='level', p=5,
                       leaf_rotation=90, leaf_font_size=8)
            ax.set_title('Hierarchical Clustering Dendrogram')
            ax.set_xlabel('Site Index (or cluster size)')
            ax.set_ylabel('Distance')

            dendro_path = OUTPUT_DIR / "cluster_dendrogram.png"
            plt.savefig(dendro_path, dpi=150, bbox_inches='tight')
            plt.close()

            viz_paths['dendrogram'] = dendro_path
            print(f"    Saved dendrogram: {dendro_path}")
        except Exception as e:
            print(f"    Dendrogram failed: {e}")

    # 3. Cluster Size Distribution
    try:
        unique_labels, counts = np.unique(labels, return_counts=True)

        fig, ax = plt.subplots(figsize=(10, 6))
        colors = plt.cm.Set1(np.linspace(0, 1, len(unique_labels)))
        bars = ax.bar([f'Cluster {l}' if l >= 0 else 'Outliers' for l in unique_labels],
                      counts, color=colors)
        ax.set_xlabel('Cluster')
        ax.set_ylabel('Number of Sites')
        ax.set_title('Cluster Size Distribution')

        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                    str(count), ha='center', va='bottom', fontsize=10)

        dist_path = OUTPUT_DIR / "cluster_distribution.png"
        plt.savefig(dist_path, dpi=150, bbox_inches='tight')
        plt.close()

        viz_paths['distribution'] = dist_path
        print(f"    Saved distribution plot: {dist_path}")
    except Exception as e:
        print(f"    Distribution plot failed: {e}")

    # 4. Feature Heatmap by Cluster
    try:
        df = feature_df.copy()
        df['cluster'] = labels

        feature_cols = ['avg_dqi_score', 'high_risk_pct', 'sae_rate',
                        'missing_pages_rate', 'missing_visit_rate',
                        'avg_days_outstanding', 'log_subject_count']
        available_cols = [c for c in feature_cols if c in df.columns]

        cluster_means = df.groupby('cluster')[available_cols].mean()

        # Normalize for heatmap
        cluster_means_norm = (cluster_means - cluster_means.min()) / (cluster_means.max() - cluster_means.min())

        fig, ax = plt.subplots(figsize=(12, 6))
        im = ax.imshow(cluster_means_norm.values, cmap='RdYlGn_r', aspect='auto')

        ax.set_xticks(np.arange(len(available_cols)))
        ax.set_yticks(np.arange(len(cluster_means_norm)))
        ax.set_xticklabels([c.replace('_', '\n') for c in available_cols], rotation=45, ha='right')
        ax.set_yticklabels([f'Cluster {i}' if i >= 0 else 'Outliers' for i in cluster_means_norm.index])
        ax.set_title('Cluster Characteristics Heatmap (Normalized)')

        plt.colorbar(im, label='Normalized Value')

        heatmap_path = OUTPUT_DIR / "cluster_heatmap.png"
        plt.savefig(heatmap_path, dpi=150, bbox_inches='tight')
        plt.close()

        viz_paths['heatmap'] = heatmap_path
        print(f"    Saved heatmap: {heatmap_path}")
    except Exception as e:
        print(f"    Heatmap failed: {e}")

    return viz_paths


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_cluster_report(profiles_df: pd.DataFrame,
                            patterns: Dict,
                            recommendations: List[Dict],
                            scores: Dict,
                            n_clusters: int,
                            method: str) -> str:
    """Generate markdown report for clustering analysis."""

    report = []

    report.append("# JAVELIN.AI - Site Clustering Report\n")
    report.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    report.append("---\n")

    # Executive Summary
    report.append("## Executive Summary\n")
    report.append("| Metric | Value |")
    report.append("|--------|-------|")
    report.append(f"| Clustering Method | {method.upper()} |")
    report.append(f"| Number of Clusters | {n_clusters} |")
    report.append(f"| Total Sites | {profiles_df['n_sites'].sum():,} |")
    report.append(f"| Best Silhouette Score | {max(scores.get('silhouette', {0:0}).values()):.3f} |")
    report.append("")

    # Cluster Overview
    report.append("## Cluster Overview\n")
    report.append("| Cluster | Sites | % Total | High Risk | Avg DQI | Top Countries |")
    report.append("|---------|-------|---------|-----------|---------|---------------|")

    for idx, row in profiles_df.iterrows():
        name = row['cluster_name']
        sites = row['n_sites']
        pct = row['pct_of_total']
        high_risk = row.get('high_risk_sites', 0)
        avg_dqi = row.get('avg_dqi_score_mean', 0)
        countries = row.get('top_countries', 'N/A')[:40]

        report.append(f"| {name} | {sites:,} | {pct:.1f}% | {high_risk:.0f} | {avg_dqi:.3f} | {countries} |")

    report.append("")

    # Risk Concentration
    report.append("## Risk Concentration by Cluster\n")

    critical_clusters = profiles_df[profiles_df.get('high_risk_rate', 0) > 0.20]
    if len(critical_clusters) > 0:
        report.append("### High-Risk Clusters (>20% high-risk sites)\n")
        for idx, row in critical_clusters.iterrows():
            report.append(f"- **{row['cluster_name']}**: {row.get('high_risk_rate', 0) * 100:.1f}% high-risk " +
                          f"({row.get('high_risk_sites', 0):.0f}/{row['n_sites']} sites)")
        report.append("")

    # Feature Importance
    report.append("## Key Differentiating Features\n")
    report.append("Features that most distinguish clusters from each other:\n")

    for i, (feature, variance) in enumerate(patterns.get('feature_importance', {}).items()):
        if i < 5:
            report.append(f"{i + 1}. **{feature.replace('_', ' ').title()}** (variance: {variance:.4f})")
    report.append("")

    # Recommendations
    report.append("## Cluster-Level Recommendations\n")

    # Sort by priority
    priority_order = {'CRITICAL':0, 'HIGH':1, 'MEDIUM':2, 'LOW':3}
    sorted_recs = sorted(recommendations, key=lambda x:priority_order.get(x['priority'], 4))

    for rec in sorted_recs:
        priority_marker = {'CRITICAL':'[!!!]', 'HIGH':'[!!]', 'MEDIUM':'[!]', 'LOW':'[-]'}.get(rec['priority'], '[?]')
        report.append(f"### {priority_marker} {rec['cluster_name']}\n")
        report.append(f"- **Sites**: {rec.get('n_sites', 'N/A')}")
        report.append(f"- **Priority**: {rec['priority']}")
        report.append(f"- **Recommendation**: {rec['recommendation']}")
        report.append(f"- **Action Type**: {rec['action_type']}")
        report.append(f"- **Effort**: {rec['estimated_effort']}")
        report.append("")

    # Study Patterns
    if patterns.get('study_patterns'):
        report.append("## Study Concentration Patterns\n")
        report.append("Studies with >50% of sites in a single cluster:\n")
        for study, info in patterns['study_patterns'].items():
            report.append(f"- **{study}**: {info['concentration']} in Cluster {info['dominant_cluster']}")
        report.append("")

    # Anomaly Concentration
    if patterns.get('anomaly_concentration'):
        report.append("## Anomaly Distribution\n")
        report.append("| Cluster | Total Anomalies | Sites with Anomalies | Avg per Site |")
        report.append("|---------|-----------------|----------------------|--------------|")

        for cluster_key, info in patterns['anomaly_concentration'].items():
            report.append(f"| {cluster_key} | {info['total_anomalies']:,} | " +
                          f"{info['sites_with_anomalies']:,} | {info['avg_anomalies_per_site']:.2f} |")
        report.append("")

    report.append("---\n")
    report.append("*Report generated by JAVELIN.AI Site Clustering Engine*\n")

    return '\n'.join(report)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_site_clustering(n_clusters: Optional[int] = None,
                        method: str = 'kmeans',
                        auto_optimal: bool = True) -> bool:
    """
    Main function to run site clustering analysis.

    Args:
        n_clusters: Number of clusters (None = auto-detect)
        method: Clustering method ('kmeans', 'hierarchical', 'dbscan', 'gmm')
        auto_optimal: If True, find optimal cluster count

    Returns:
        True if successful, False otherwise
    """
    print("=" * 70)
    print("JAVELIN.AI - SITE CLUSTERING & SEGMENTATION")
    print("=" * 70)
    print(f"\nProject Root: {PROJECT_ROOT}\n")

    # =========================================================================
    # Step 1: Load Data
    # =========================================================================
    print("[1/5] Loading data...")
    try:
        site_df, subject_df, anomaly_df = load_data()
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        print("  Make sure to run previous pipeline steps first.")
        return False

    # =========================================================================
    # Step 2: Prepare Features
    # =========================================================================
    print("\n[2/5] Preparing features...")
    feature_df, scaled_df, feature_names = prepare_features(site_df)
    print(f"  Prepared {len(feature_names)} features for {len(scaled_df):,} sites")

    # =========================================================================
    # Step 3: Determine Optimal Clusters
    # =========================================================================
    print("\n[3/5] Determining cluster count...")

    if auto_optimal and n_clusters is None:
        optimal_k, scores = find_optimal_clusters(scaled_df)
        n_clusters = optimal_k
    else:
        n_clusters = n_clusters or DEFAULT_CLUSTERS
        scores = {}
        # Still compute scores for the chosen k
        kmeans = KMeans(n_clusters=n_clusters, random_state=RANDOM_STATE, n_init=10)
        labels_temp = kmeans.fit_predict(scaled_df.values)
        scores['silhouette'] = {n_clusters:silhouette_score(scaled_df.values, labels_temp)}
        print(f"  Using specified {n_clusters} clusters")

    # =========================================================================
    # Step 4: Run Clustering
    # =========================================================================
    print(f"\n[4/5] Running {method.upper()} clustering...")

    linkage_matrix = None
    probabilities = None

    if method=='kmeans':
        labels = cluster_kmeans(scaled_df, n_clusters)
    elif method=='hierarchical':
        labels, linkage_matrix = cluster_hierarchical(scaled_df, n_clusters)
    elif method=='dbscan':
        labels = cluster_dbscan(scaled_df)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    elif method=='gmm':
        labels, probabilities = cluster_gmm(scaled_df, n_clusters)
    else:
        print(f"  Unknown method: {method}")
        return False

    # =========================================================================
    # Step 5: Analyze & Profile Clusters
    # =========================================================================
    print("\n[5/5] Analyzing clusters...")

    # Profile clusters
    profiles_df = profile_clusters(feature_df, labels, feature_names)
    profiles_df = name_clusters(profiles_df, feature_df, labels)

    # Analyze patterns
    patterns = analyze_cluster_patterns(feature_df, labels, anomaly_df)

    # Generate recommendations
    recommendations = generate_cluster_recommendations(profiles_df, patterns)

    # Create visualizations
    viz_paths = create_cluster_visualizations(feature_df, scaled_df, labels, linkage_matrix)

    # =========================================================================
    # Save Outputs
    # =========================================================================
    print("\n" + "=" * 70)
    print("SAVING OUTPUTS")
    print("=" * 70)

    # 1. Site-to-cluster mapping
    site_clusters = site_df[['study', 'site_id', 'country', 'region', 'subject_count',
                             'site_risk_category']].copy()
    site_clusters['cluster_id'] = labels
    site_clusters['cluster_name'] = site_clusters['cluster_id'].map(
        dict(zip(profiles_df['cluster_id'], profiles_df['cluster_name']))
    )

    # Add cluster probabilities if available (GMM)
    if probabilities is not None:
        for i in range(probabilities.shape[1]):
            site_clusters[f'prob_cluster_{i}'] = probabilities[:, i]

    site_clusters_path = OUTPUT_DIR / "site_clusters.csv"
    site_clusters.to_csv(site_clusters_path, index=False)
    print(f"\nSaved: {site_clusters_path}")

    # 2. Cluster profiles
    profiles_path = OUTPUT_DIR / "cluster_profiles.csv"
    profiles_df.to_csv(profiles_path, index=False)
    print(f"Saved: {profiles_path}")

    # 3. Summary JSON
    summary = {
        'generated_at':datetime.now().isoformat(),
        'method':method,
        'n_clusters':n_clusters,
        'total_sites':len(site_df),
        'features_used':feature_names,
        'scores':{k:{str(kk):float(vv) for kk, vv in v.items()}
                  for k, v in scores.items()} if scores else {},
        'cluster_sizes':dict(zip(
            [f"cluster_{l}" for l in sorted(set(labels))],
            [int((labels==l).sum()) for l in sorted(set(labels))]
        )),
        'patterns':patterns,
        'recommendations':recommendations
    }

    summary_path = OUTPUT_DIR / "cluster_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Saved: {summary_path}")

    # 4. Markdown report
    report = generate_cluster_report(profiles_df, patterns, recommendations, scores, n_clusters, method)
    report_path = OUTPUT_DIR / "cluster_report.md"
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
SITE CLUSTERING COMPLETE
========================

Configuration:
  Method: {method.upper()}
  Clusters: {n_clusters}
  Sites Analyzed: {len(site_df):,}
  Features Used: {len(feature_names)}

Cluster Distribution:""")

    for idx, row in profiles_df.iterrows():
        cluster_name = row['cluster_name']
        n_sites = row['n_sites']
        pct = row['pct_of_total']
        high_risk = row.get('high_risk_sites', 0)
        print(f"  • {cluster_name}: {n_sites:,} sites ({pct:.1f}%) - {high_risk:.0f} high-risk")

    # Priority summary
    critical_recs = [r for r in recommendations if r['priority']=='CRITICAL']
    high_recs = [r for r in recommendations if r['priority']=='HIGH']

    print(f"""
Priority Actions:
  CRITICAL clusters: {len(critical_recs)}
  HIGH priority clusters: {len(high_recs)}
""")

    if critical_recs:
        print("CRITICAL CLUSTERS:")
        for r in critical_recs:
            print(f"  • {r['cluster_name']}: {r['recommendation'][:80]}...")

    print("\n" + "=" * 70)
    print("OUTPUTS")
    print("=" * 70)
    print(f"""
1. {site_clusters_path}
2. {profiles_path}
3. {summary_path}
4. {report_path}
""")

    if viz_paths:
        print("Visualizations:")
        for name, path in viz_paths.items():
            print(f"  • {path}")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__=="__main__":
    import sys

    n_clusters = None
    method = 'kmeans'
    auto_optimal = True

    # Parse arguments
    if "--clusters" in sys.argv or "-k" in sys.argv:
        try:
            idx = sys.argv.index("--clusters") if "--clusters" in sys.argv else sys.argv.index("-k")
            n_clusters = int(sys.argv[idx + 1])
            auto_optimal = False
        except (IndexError, ValueError):
            pass

    if "--method" in sys.argv or "-m" in sys.argv:
        try:
            idx = sys.argv.index("--method") if "--method" in sys.argv else sys.argv.index("-m")
            method = sys.argv[idx + 1].lower()
        except (IndexError, ValueError):
            pass

    if "--no-auto" in sys.argv:
        auto_optimal = False
        if n_clusters is None:
            n_clusters = DEFAULT_CLUSTERS

    if "--help" in sys.argv or "-h" in sys.argv:
        print("""
JAVELIN.AI Site Clustering

Usage:
    python 08_site_clustering.py [options]

Options:
    --clusters N, -k N    Number of clusters (default: auto-detect)
    --method METHOD, -m   Clustering method (default: kmeans)
                          Options: kmeans, hierarchical, dbscan, gmm
    --no-auto             Don't auto-detect optimal cluster count
    --help, -h            Show this help message

Examples:
    python 08_site_clustering.py
    python 08_site_clustering.py --clusters 8
    python 08_site_clustering.py --method hierarchical
    python 08_site_clustering.py --method dbscan
    python 08_site_clustering.py -k 6 -m gmm
""")
        sys.exit(0)

    success = run_site_clustering(
        n_clusters=n_clusters,
        method=method,
        auto_optimal=auto_optimal
    )

    if not success:
        sys.exit(1)
