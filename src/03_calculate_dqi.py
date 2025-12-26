"""
Javelin.AI - Step 3: Calculate Data Quality Index (DQI)
========================================================
This script calculates DQI scores using data-driven weights from TabPFN + SHAP.

Innovation: Instead of arbitrary weights, we:
1. Define "Critical Subject" as a proxy label from the data
2. Train TabPFN to predict critical subjects
3. Extract SHAP feature importance as weights
4. Use these weights to calculate DQI scores

Prerequisites:
    - Run 02_build_master_table.py first
    - outputs/master_subject.csv must exist

Usage:
    python src/03_calculate_dqi.py

Output:
    - outputs/master_subject_with_dqi.csv  : Subject table with DQI scores
    - outputs/master_site_with_dqi.csv     : Site table with aggregated DQI
    - outputs/dqi_weights.csv              : SHAP-derived feature weights
    - outputs/dqi_model_report.txt         : Model performance report
"""

# Set environment variable BEFORE any imports
import os
os.environ['TABPFN_ALLOW_CPU_LARGE_DATASET'] = '1'

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

# Features to use for DQI calculation
DQI_FEATURES = [
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

# Thresholds for defining "Critical Subject" (adjustable)
CRITICAL_THRESHOLDS = {
    'sae_pending_count': 1,        # Any pending SAE = critical
    'missing_visit_count': 1,      # Any missing visit = critical
    'missing_pages_count': 5,      # 5+ missing pages = critical
    'max_days_outstanding': 30,    # 30+ days outstanding = critical
    'max_days_page_missing': 30,   # 30+ days page missing = critical
    'edrr_open_issues': 3,         # 3+ open EDRR issues = critical
    'total_uncoded_count': 5,      # 5+ uncoded terms = critical
}

# Risk score thresholds for categorization
RISK_CATEGORIES = {
    'high': 0.7,      # DQI >= 0.7 = High Risk
    'medium': 0.4,    # DQI >= 0.4 = Medium Risk
    'low': 0.0,       # DQI < 0.4 = Low Risk
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_critical_label(df):
    """
    Create binary 'is_critical' label based on thresholds.
    A subject is critical if ANY threshold is exceeded.
    """
    df = df.copy()

    # Initialize as not critical
    df['is_critical'] = 0

    # Apply each threshold
    conditions = []

    if 'sae_pending_count' in df.columns:
        cond = df['sae_pending_count'] >= CRITICAL_THRESHOLDS['sae_pending_count']
        conditions.append(('SAE Pending', cond.sum()))
        df.loc[cond, 'is_critical'] = 1

    if 'missing_visit_count' in df.columns:
        cond = df['missing_visit_count'] >= CRITICAL_THRESHOLDS['missing_visit_count']
        conditions.append(('Missing Visits', cond.sum()))
        df.loc[cond, 'is_critical'] = 1

    if 'missing_pages_count' in df.columns:
        cond = df['missing_pages_count'] >= CRITICAL_THRESHOLDS['missing_pages_count']
        conditions.append(('Missing Pages >=5', cond.sum()))
        df.loc[cond, 'is_critical'] = 1

    if 'max_days_outstanding' in df.columns:
        cond = df['max_days_outstanding'] >= CRITICAL_THRESHOLDS['max_days_outstanding']
        conditions.append(('Days Outstanding >=30', cond.sum()))
        df.loc[cond, 'is_critical'] = 1

    if 'max_days_page_missing' in df.columns:
        cond = df['max_days_page_missing'] >= CRITICAL_THRESHOLDS['max_days_page_missing']
        conditions.append(('Days Page Missing >=30', cond.sum()))
        df.loc[cond, 'is_critical'] = 1

    if 'edrr_open_issues' in df.columns:
        cond = df['edrr_open_issues'] >= CRITICAL_THRESHOLDS['edrr_open_issues']
        conditions.append(('EDRR Issues >=3', cond.sum()))
        df.loc[cond, 'is_critical'] = 1

    if 'total_uncoded_count' in df.columns:
        cond = df['total_uncoded_count'] >= CRITICAL_THRESHOLDS['total_uncoded_count']
        conditions.append(('Uncoded >=5', cond.sum()))
        df.loc[cond, 'is_critical'] = 1

    return df, conditions


def normalize_features(df, features):
    """
    Normalize features using percentile-based approach.
    This handles outliers better than min-max.
    """
    df = df.copy()

    for feat in features:
        if feat in df.columns:
            # Use 99th percentile as max to handle outliers
            max_val = df[feat].quantile(0.99)
            if max_val > 0:
                df[f'{feat}_norm'] = df[feat].clip(upper=max_val) / max_val
            else:
                df[f'{feat}_norm'] = 0
            # Ensure values are between 0 and 1
            df[f'{feat}_norm'] = df[f'{feat}_norm'].clip(0, 1)

    return df


def calculate_dqi_with_weights(df, weights, features):
    """
    Calculate DQI score using weighted sum of normalized features.
    Higher DQI = more issues = higher risk.
    """
    df = df.copy()

    # Normalize features
    df = normalize_features(df, features)

    # Calculate weighted sum
    dqi_score = np.zeros(len(df))

    for feat in features:
        norm_col = f'{feat}_norm'
        if norm_col in df.columns and feat in weights:
            weight = weights[feat]
            dqi_score += df[norm_col].fillna(0) * weight

    # DQI is already 0-1 since weights sum to 1 and features are normalized
    df['dqi_score'] = dqi_score

    # Categorize risk based on percentiles
    # Top 10% = High, Next 20% = Medium, Bottom 70% = Low
    # But only if score > 0, otherwise it's truly Low risk
    high_threshold = df[df['dqi_score'] > 0]['dqi_score'].quantile(0.70) if (df['dqi_score'] > 0).any() else 0.5
    medium_threshold = df[df['dqi_score'] > 0]['dqi_score'].quantile(0.30) if (df['dqi_score'] > 0).any() else 0.2

    df['risk_category'] = 'Low'
    df.loc[df['dqi_score'] > medium_threshold, 'risk_category'] = 'Medium'
    df.loc[df['dqi_score'] > high_threshold, 'risk_category'] = 'High'

    return df


def try_tabpfn_shap(X, y):
    """
    Try to use TabPFN + Permutation Importance for data-driven weights.
    Returns weights dict or None if not available.
    """
    try:
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, roc_auc_score
        from sklearn.inspection import permutation_importance

        # Try importing TabPFN
        try:
            from tabpfn import TabPFNClassifier
        except ImportError:
            print("\n   ⚠️ TabPFN not installed. Install with: pip install tabpfn")
            return None, None

        print("\n   Using TabPFN + Permutation Importance for data-driven weights...")

        # Check for GPU
        import torch
        if torch.cuda.is_available():
            device = 'cuda'
            gpu_name = torch.cuda.get_device_name(0)
            print(f"   ✅ GPU detected: {gpu_name}")
            max_train = 8000  # Can use more samples with GPU
            max_test = 2000
        else:
            device = 'cpu'
            print("   ⚠️ No GPU detected, using CPU with reduced samples")
            max_train = 1000  # TabPFN limit on CPU
            max_test = 200

        # Stratified sample
        print(f"   Sampling up to {max_train + max_test} subjects for TabPFN (from {len(X)})...")

        # First split to get train/test
        X_temp, X_test_full, y_temp, y_test_full = train_test_split(
            X, y, test_size=0.3, random_state=42, stratify=y
        )

        # Sample training set
        if len(X_temp) > max_train:
            indices = np.random.choice(len(X_temp), max_train, replace=False)
            X_train = X_temp.iloc[indices].reset_index(drop=True)
            y_train = y_temp.iloc[indices].reset_index(drop=True)
        else:
            X_train = X_temp.reset_index(drop=True)
            y_train = y_temp.reset_index(drop=True)

        # Sample test set
        if len(X_test_full) > max_test:
            indices = np.random.choice(len(X_test_full), max_test, replace=False)
            X_test = X_test_full.iloc[indices].reset_index(drop=True)
            y_test = y_test_full.iloc[indices].reset_index(drop=True)
        else:
            X_test = X_test_full.reset_index(drop=True)
            y_test = y_test_full.reset_index(drop=True)

        print(f"   Training set: {len(X_train)} samples")
        print(f"   Test set: {len(X_test)} samples")
        print(f"   Positive class ratio: {y_train.mean():.2%}")

        # Train TabPFN
        print(f"   Training TabPFN classifier on {device.upper()}...")

        try:
            # Try with ignore_pretraining_limits for newer versions
            clf = TabPFNClassifier(device=device, ignore_pretraining_limits=True)
        except TypeError:
            try:
                # Try with N_ensemble_configurations for older versions
                clf = TabPFNClassifier(device=device, N_ensemble_configurations=32)
            except TypeError:
                # Fallback to defaults
                clf = TabPFNClassifier(device=device)

        clf.fit(X_train.values, y_train.values)
        print("   ✅ TabPFN trained successfully!")

        # Evaluate
        y_pred = clf.predict(X_test.values)
        y_prob = clf.predict_proba(X_test.values)[:, 1]

        accuracy = accuracy_score(y_test, y_pred)
        try:
            auc = roc_auc_score(y_test, y_prob)
        except:
            auc = 0.5

        print(f"   Model Accuracy: {accuracy:.2%}")
        print(f"   Model AUC-ROC: {auc:.3f}")

        # Get feature importance using permutation importance
        print("   Calculating feature importance (permutation)...")

        perm_importance = permutation_importance(
            clf, X_test.values, y_test.values,
            n_repeats=10, random_state=42, n_jobs=1  # n_jobs=1 for GPU compatibility
        )

        # Create weights dictionary from permutation importance
        importance_values = perm_importance.importances_mean
        importance_values = np.maximum(importance_values, 0)  # No negative weights

        weights = {}
        for i, feat in enumerate(X.columns):
            weights[feat] = importance_values[i]

        # Normalize weights to sum to 1
        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}
        else:
            # If all zero, use equal weights
            weights = {k: 1/len(weights) for k in weights.keys()}

        print("   ✅ TabPFN feature importance calculated successfully!")

        # Return model info for reporting
        model_info = {
            'accuracy': accuracy,
            'auc': auc,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'positive_ratio': y_train.mean(),
            'method': 'TabPFN + Permutation Importance'
        }

        return weights, model_info

    except ImportError as e:
        print(f"\n   ⚠️ Required package not available: {e}")
        print("   Falling back to heuristic weights...")
        return None, None
    except Exception as e:
        print(f"\n   ⚠️ Error in TabPFN: {e}")
        import traceback
        traceback.print_exc()
        print("   Falling back to heuristic weights...")
        return None, None


def get_heuristic_weights():
    """
    Fallback heuristic weights based on clinical importance.
    Used when TabPFN/SHAP is not available.
    """
    weights = {
        'sae_pending_count': 0.20,       # Safety issues - highest priority
        'sae_total_count': 0.10,         # Total SAE count
        'missing_visit_count': 0.12,     # Missing visits important
        'max_days_outstanding': 0.10,    # Days outstanding
        'missing_pages_count': 0.10,     # Missing pages
        'max_days_page_missing': 0.08,   # Days page missing
        'lab_issues_count': 0.08,        # Lab issues
        'uncoded_meddra_count': 0.06,    # Uncoded AE terms
        'uncoded_whodd_count': 0.06,     # Uncoded drug terms
        'edrr_open_issues': 0.05,        # EDRR issues
        'inactivated_forms_count': 0.05, # Inactivated forms
    }
    return weights


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def calculate_dqi():
    """Main function to calculate DQI scores."""

    print("=" * 70)
    print("JAVELIN.AI - CALCULATE DATA QUALITY INDEX (DQI)")
    print("=" * 70)

    # Check prerequisites
    if not MASTER_SUBJECT_PATH.exists():
        print(f"\n❌ ERROR: {MASTER_SUBJECT_PATH} not found!")
        print("   Run 02_build_master_table.py first.")
        return

    # Load master subject table
    print(f"\n📁 Loading {MASTER_SUBJECT_PATH}...")
    df = pd.read_csv(MASTER_SUBJECT_PATH)
    print(f"   Loaded {len(df)} subjects")

    # Step 1: Create Critical Subject label
    print("\n" + "=" * 70)
    print("STEP 1: CREATE CRITICAL SUBJECT LABEL")
    print("=" * 70)

    df, conditions = create_critical_label(df)

    print("\nCritical Subject Thresholds:")
    for name, count in conditions:
        print(f"   • {name}: {count} subjects")

    critical_count = df['is_critical'].sum()
    critical_pct = critical_count / len(df) * 100
    print(f"\n   TOTAL CRITICAL: {critical_count} / {len(df)} ({critical_pct:.1f}%)")

    # Check class balance
    if critical_pct < 5:
        print("   ⚠️ Warning: Low critical rate. Consider adjusting thresholds.")
    elif critical_pct > 50:
        print("   ⚠️ Warning: High critical rate. Consider tightening thresholds.")
    else:
        print("   ✅ Good class balance for modeling!")

    # Step 2: Get feature weights (TabPFN + SHAP or fallback)
    print("\n" + "=" * 70)
    print("STEP 2: CALCULATE FEATURE WEIGHTS")
    print("=" * 70)

    # Prepare features
    available_features = [f for f in DQI_FEATURES if f in df.columns]
    print(f"\n   Available features: {len(available_features)}")

    X = df[available_features].fillna(0)
    y = df['is_critical']

    # Try TabPFN + SHAP first
    weights, model_info = try_tabpfn_shap(X, y)

    if weights is None:
        # Fallback to heuristic weights
        print("\n   Using heuristic weights based on clinical importance...")
        weights = get_heuristic_weights()
        # Filter to available features
        weights = {k: v for k, v in weights.items() if k in available_features}
        # Renormalize
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
        model_info = None

    # Display weights
    print("\n   Feature Weights (sorted by importance):")
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    for feat, weight in sorted_weights:
        bar = "█" * int(weight * 50)
        print(f"   {feat:30s} {weight:.3f} {bar}")

    # Save weights
    weights_df = pd.DataFrame([
        {'feature': k, 'weight': v} for k, v in sorted_weights
    ])
    weights_df.to_csv(OUTPUT_DIR / "dqi_weights.csv", index=False)
    print(f"\n   ✅ Saved: outputs/dqi_weights.csv")

    # Step 3: Calculate DQI scores
    print("\n" + "=" * 70)
    print("STEP 3: CALCULATE DQI SCORES")
    print("=" * 70)

    df = calculate_dqi_with_weights(df, weights, available_features)

    print(f"\n   DQI Score Statistics:")
    print(f"   • Min: {df['dqi_score'].min():.3f}")
    print(f"   • Max: {df['dqi_score'].max():.3f}")
    print(f"   • Mean: {df['dqi_score'].mean():.3f}")
    print(f"   • Median: {df['dqi_score'].median():.3f}")

    print(f"\n   Risk Category Distribution:")
    risk_dist = df['risk_category'].value_counts()
    for cat in ['High', 'Medium', 'Low']:
        if cat in risk_dist.index:
            count = risk_dist[cat]
            pct = count / len(df) * 100
            print(f"   • {cat}: {count} ({pct:.1f}%)")

    # Step 4: Create Site-level DQI
    print("\n" + "=" * 70)
    print("STEP 4: AGGREGATE SITE-LEVEL DQI")
    print("=" * 70)

    site_agg = df.groupby(['study', 'site_id', 'country', 'region']).agg({
        'subject_id': 'count',
        'dqi_score': ['mean', 'max'],
        'is_critical': 'sum',
        'missing_visit_count': 'sum',
        'sae_pending_count': 'sum',
        'missing_pages_count': 'sum',
    }).reset_index()

    # Flatten column names
    site_agg.columns = ['study', 'site_id', 'country', 'region',
                        'subject_count', 'avg_dqi_score', 'max_dqi_score',
                        'critical_subjects', 'total_missing_visits',
                        'total_sae_pending', 'total_missing_pages']

    # Add site risk category based on percentiles
    high_threshold = site_agg['avg_dqi_score'].quantile(0.90)
    medium_threshold = site_agg['avg_dqi_score'].quantile(0.70)

    site_agg['site_risk_category'] = 'Low'
    site_agg.loc[site_agg['avg_dqi_score'] >= medium_threshold, 'site_risk_category'] = 'Medium'
    site_agg.loc[site_agg['avg_dqi_score'] >= high_threshold, 'site_risk_category'] = 'High'

    print(f"   ✅ Site-level DQI: {len(site_agg)} sites")

    print(f"\n   Site Risk Distribution:")
    site_risk_dist = site_agg['site_risk_category'].value_counts()
    for cat in ['High', 'Medium', 'Low']:
        if cat in site_risk_dist.index:
            count = site_risk_dist[cat]
            pct = count / len(site_agg) * 100
            print(f"   • {cat}: {count} ({pct:.1f}%)")

    # Step 5: Save outputs
    print("\n" + "=" * 70)
    print("SAVING OUTPUTS")
    print("=" * 70)

    # Save subject table with DQI
    df.to_csv(OUTPUT_DIR / "master_subject_with_dqi.csv", index=False)
    print(f"✅ Saved: outputs/master_subject_with_dqi.csv ({len(df)} subjects)")

    # Save site table with DQI
    site_agg.to_csv(OUTPUT_DIR / "master_site_with_dqi.csv", index=False)
    print(f"✅ Saved: outputs/master_site_with_dqi.csv ({len(site_agg)} sites)")

    # Save model report
    report_path = OUTPUT_DIR / "dqi_model_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("JAVELIN.AI - DQI MODEL REPORT\n")
        f.write("=" * 50 + "\n\n")

        f.write("DATASET SUMMARY\n")
        f.write("-" * 30 + "\n")
        f.write(f"Total Subjects: {len(df)}\n")
        f.write(f"Critical Subjects: {critical_count} ({critical_pct:.1f}%)\n")
        f.write(f"Features Used: {len(available_features)}\n\n")

        f.write("CRITICAL SUBJECT THRESHOLDS\n")
        f.write("-" * 30 + "\n")
        for name, count in conditions:
            f.write(f"  {name}: {count} subjects\n")
        f.write("\n")

        if model_info:
            f.write("TABPFN MODEL PERFORMANCE\n")
            f.write("-" * 30 + "\n")
            f.write(f"Training Samples: {model_info['train_size']}\n")
            f.write(f"Test Samples: {model_info['test_size']}\n")
            f.write(f"Accuracy: {model_info['accuracy']:.2%}\n")
            f.write(f"AUC-ROC: {model_info['auc']:.3f}\n\n")
        else:
            f.write("MODEL: Heuristic Weights (TabPFN not available)\n\n")

        f.write("FEATURE WEIGHTS (SHAP-derived or Heuristic)\n")
        f.write("-" * 30 + "\n")
        for feat, weight in sorted_weights:
            f.write(f"  {feat}: {weight:.4f}\n")
        f.write("\n")

        f.write("DQI SCORE STATISTICS\n")
        f.write("-" * 30 + "\n")
        f.write(f"Min: {df['dqi_score'].min():.3f}\n")
        f.write(f"Max: {df['dqi_score'].max():.3f}\n")
        f.write(f"Mean: {df['dqi_score'].mean():.3f}\n")
        f.write(f"Median: {df['dqi_score'].median():.3f}\n\n")

        f.write("RISK DISTRIBUTION\n")
        f.write("-" * 30 + "\n")
        for cat in ['High', 'Medium', 'Low']:
            if cat in risk_dist.index:
                count = risk_dist[cat]
                pct = count / len(df) * 100
                f.write(f"  {cat}: {count} ({pct:.1f}%)\n")

    print(f"✅ Saved: outputs/dqi_model_report.txt")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"""
Total Subjects: {len(df)}
Critical Subjects: {critical_count} ({critical_pct:.1f}%)

DQI Method: {'TabPFN + SHAP (Data-Driven)' if model_info else 'Heuristic Weights'}

Risk Distribution:
  • High Risk: {risk_dist.get('High', 0)} subjects
  • Medium Risk: {risk_dist.get('Medium', 0)} subjects  
  • Low Risk: {risk_dist.get('Low', 0)} subjects

Top 3 Risk Factors:
  1. {sorted_weights[0][0]}: {sorted_weights[0][1]:.1%}
  2. {sorted_weights[1][0]}: {sorted_weights[1][1]:.1%}
  3. {sorted_weights[2][0]}: {sorted_weights[2][1]:.1%}
""")

    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Review outputs/master_subject_with_dqi.csv
2. Review outputs/dqi_weights.csv for feature importance
3. Run: python src/04_build_knowledge_graph.py
""")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    calculate_dqi()
