"""
Javelin.AI - Step 6: Gen AI Recommendations Engine
===================================================

This module generates actionable recommendations from DQI scores
using domain knowledge and LLM-powered insights.

LLM Integration: Ollama (open-source, runs locally)
Supported Models: llama3, mistral, phi3, gemma2

Setup Instructions:
------------------
1. Install Ollama: https://ollama.ai/download
2. Pull a model: ollama pull mistral
3. Run: ollama serve (starts local API on port 11434)
4. Then run this script

Usage:
    python src/06_recommendations_engine.py
    python src/06_recommendations_engine.py --model phi3
"""

import pandas as pd
import numpy as np
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

SUBJECT_DQI_PATH = OUTPUT_DIR / "master_subject_with_dqi.csv"
SITE_DQI_PATH = OUTPUT_DIR / "master_site_with_dqi.csv"
WEIGHTS_PATH = OUTPUT_DIR / "dqi_weights.csv"

# Ollama Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "mistral"

# Recommendation thresholds
THRESHOLDS = {
    'critical_dqi': 0.4,
    'high_dqi': 0.2,
    'medium_dqi': 0.1,
    'high_risk_site_pct': 0.15,
    'sae_pending_critical': 1,
}

# Issue type to action mapping
ISSUE_ACTIONS = {
    'sae_pending_count': {
        'priority': 'CRITICAL',
        'action': 'Immediate SAE review and regulatory submission required',
        'owner': 'Medical Monitor / Pharmacovigilance',
        'sla': '24 hours'
    },
    'uncoded_meddra_count': {
        'priority': 'HIGH',
        'action': 'Code adverse event terms to MedDRA dictionary',
        'owner': 'Medical Coding Team',
        'sla': '48 hours'
    },
    'missing_visit_count': {
        'priority': 'HIGH',
        'action': 'Contact site to schedule missed visits or document reason',
        'owner': 'Clinical Operations / CRA',
        'sla': '72 hours'
    },
    'missing_pages_count': {
        'priority': 'MEDIUM',
        'action': 'Issue data query for missing CRF pages',
        'owner': 'Data Management',
        'sla': '5 business days'
    },
    'lab_issues_count': {
        'priority': 'MEDIUM',
        'action': 'Reconcile lab data with central lab vendor',
        'owner': 'Data Management / Lab Vendor',
        'sla': '5 business days'
    },
    'max_days_outstanding': {
        'priority': 'MEDIUM',
        'action': 'Escalate data entry delays to site',
        'owner': 'CRA / Site Manager',
        'sla': '1 week'
    },
    'uncoded_whodd_count': {
        'priority': 'LOW',
        'action': 'Code medication terms to WHODrug dictionary',
        'owner': 'Medical Coding Team',
        'sla': '1 week'
    },
    'edrr_open_issues': {
        'priority': 'LOW',
        'action': 'Resolve external data reconciliation discrepancies',
        'owner': 'Data Management',
        'sla': '2 weeks'
    },
    'inactivated_forms_count': {
        'priority': 'LOW',
        'action': 'Review inactivated forms for audit trail compliance',
        'owner': 'QA / Data Management',
        'sla': '2 weeks'
    }
}


# ============================================================================
# OLLAMA LLM INTEGRATION
# ============================================================================

class OllamaLLM:
    """Local LLM integration using Ollama."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.available = False
        self._check_and_validate()

    def _check_and_validate(self):
        """Check if Ollama is running and model is available."""
        try:
            # Check if Ollama is running
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code != 200:
                print(f"  [WARNING] Ollama not responding")
                return

            # Get available models
            models = response.json().get('models', [])
            if not models:
                print(f"  [WARNING] No models installed in Ollama")
                print(f"            Run: ollama pull {self.model}")
                return

            model_names = [m['name'].split(':')[0] for m in models]

            # Check if requested model is available
            if self.model not in model_names:
                print(f"  [WARNING] Model '{self.model}' not found")
                print(f"            Available models: {', '.join(model_names)}")
                # Use first available model
                self.model = model_names[0]
                print(f"            Using: {self.model}")

            # Test actual generation with a simple prompt
            test_response = self._test_generation()
            if test_response:
                self.available = True
            else:
                print(f"  [WARNING] Model loaded but generation failed")

        except requests.exceptions.ConnectionError:
            print(f"  [WARNING] Cannot connect to Ollama at localhost:11434")
            print(f"            Run: ollama serve")
        except Exception as e:
            print(f"  [WARNING] Ollama error: {str(e)[:50]}")

    def _test_generation(self) -> bool:
        """Test if model can actually generate."""
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": self.model,
                    "prompt": "Reply with just: OK",
                    "stream": False,
                    "options": {"num_predict": 10}
                },
                timeout=30
            )
            return response.status_code == 200 and len(response.json().get('response', '')) > 0
        except:
            return False

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """Generate text using Ollama."""
        if not self.available:
            return None

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7
                    }
                },
                timeout=120
            )
            if response.status_code == 200:
                return response.json().get('response', '').strip()
        except Exception as e:
            pass  # Silent fail, return None
        return None


def generate_site_insight(llm: OllamaLLM, site_data: Dict) -> str:
    """Generate natural language insight for a site using LLM."""

    issues_text = []
    for issue in site_data.get('issues', [])[:5]:
        issues_text.append(f"- {issue['type'].replace('_', ' ')}: {issue['total_count']} instances")

    prompt = f"""You are a clinical trial data quality analyst. Generate a brief, actionable insight (2-3 sentences) for this site.

Site: {site_data['site_id']} in {site_data['country']}
Study: {site_data['study']}
Risk Level: {site_data['priority']}
DQI Score: {site_data['avg_dqi_score']:.3f} (0=perfect, 1=critical issues)
Subjects: {site_data['subject_count']} total, {site_data['high_risk_count']} high-risk

Top Issues:
{chr(10).join(issues_text) if issues_text else 'No major issues identified'}

Write a specific, actionable recommendation focusing on the root cause and immediate next steps. Be concise and professional."""

    return llm.generate(prompt, max_tokens=200)


def generate_executive_insight(llm: OllamaLLM, summary_data: Dict) -> str:
    """Generate executive summary insight using LLM."""

    prompt = f"""You are a clinical operations director reviewing data quality across a clinical trial portfolio. Write a brief executive summary (3-4 sentences).

Portfolio Overview:
- Total Subjects: {summary_data['total_subjects']:,}
- Total Sites: {summary_data['total_sites']}
- Studies: {summary_data['n_studies']}

Risk Status:
- High Risk Subjects: {summary_data['high_risk_subjects']:,} ({summary_data['high_risk_pct']:.1f}%)
- Critical Sites: {summary_data['critical_sites']}
- Pending SAE Reviews: {summary_data['pending_sae']}

Top Issue Categories:
1. {summary_data['top_issues'][0] if summary_data['top_issues'] else 'None'}
2. {summary_data['top_issues'][1] if len(summary_data['top_issues']) > 1 else 'None'}
3. {summary_data['top_issues'][2] if len(summary_data['top_issues']) > 2 else 'None'}

Write a professional executive summary highlighting key risks and recommended priorities for this week. Be specific about actions."""

    return llm.generate(prompt, max_tokens=300)


def generate_study_insight(llm: OllamaLLM, study_data: Dict) -> str:
    """Generate study-level insight using LLM."""

    prompt = f"""You are a clinical trial manager. Generate a brief insight (2 sentences) for this study's data quality status.

Study: {study_data['study']}
Sites: {study_data['n_sites']}
Subjects: {study_data['n_subjects']}
Average DQI: {study_data['avg_dqi']:.3f}
High Risk Subjects: {study_data['total_high_risk']}
Pending SAE: {study_data.get('total_sae_pending', 0)}

Provide a specific assessment and one key action item."""

    return llm.generate(prompt, max_tokens=150)


# ============================================================================
# DATA LOADING
# ============================================================================

def load_data() -> Dict[str, pd.DataFrame]:
    """Load all required data files."""
    data = {}

    if SUBJECT_DQI_PATH.exists():
        data['subjects'] = pd.read_csv(SUBJECT_DQI_PATH)
        print(f"  Loaded {len(data['subjects']):,} subjects")
    else:
        raise FileNotFoundError(f"{SUBJECT_DQI_PATH} not found. Run 03_calculate_dqi.py first.")

    if SITE_DQI_PATH.exists():
        data['sites'] = pd.read_csv(SITE_DQI_PATH)
        print(f"  Loaded {len(data['sites']):,} sites")

    if WEIGHTS_PATH.exists():
        data['weights'] = pd.read_csv(WEIGHTS_PATH)

    return data


# ============================================================================
# RECOMMENDATION GENERATION
# ============================================================================

def generate_subject_recommendations(df: pd.DataFrame) -> List[Dict]:
    """Generate recommendations for high-risk subjects."""
    recommendations = []

    high_risk = df[df['risk_category'] == 'High'].copy()

    for _, row in high_risk.iterrows():
        rec = {
            'level': 'SUBJECT',
            'study': row['study'],
            'site_id': row['site_id'],
            'subject_id': row['subject_id'],
            'country': row.get('country', 'Unknown'),
            'dqi_score': round(row['dqi_score'], 3),
            'risk_category': row['risk_category'],
            'issues': [],
            'actions': []
        }

        for issue_type, config in ISSUE_ACTIONS.items():
            if issue_type in row and row[issue_type] > 0:
                rec['issues'].append({
                    'type': issue_type,
                    'count': int(row[issue_type]),
                    'priority': config['priority'],
                    'action': config['action'],
                    'owner': config['owner'],
                    'sla': config['sla']
                })

        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        rec['issues'].sort(key=lambda x: priority_order.get(x['priority'], 4))

        if rec['issues']:
            rec['priority'] = rec['issues'][0]['priority']
        else:
            rec['priority'] = 'LOW'

        recommendations.append(rec)

    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    recommendations.sort(key=lambda x: (priority_order.get(x['priority'], 4), -x['dqi_score']))

    return recommendations


def generate_site_recommendations(df: pd.DataFrame, llm: Optional[OllamaLLM] = None) -> List[Dict]:
    """Generate recommendations for sites requiring attention."""
    recommendations = []

    flagged_sites = df[
        (df['site_risk_category'] == 'High') |
        (df['avg_dqi_score'] > THRESHOLDS['high_dqi'])
    ].copy()

    # Sort by DQI score first so top sites get LLM insights
    flagged_sites = flagged_sites.sort_values('avg_dqi_score', ascending=False)

    for idx, (_, row) in enumerate(flagged_sites.iterrows()):
        rec = {
            'level': 'SITE',
            'study': row['study'],
            'site_id': row['site_id'],
            'country': row.get('country', 'Unknown'),
            'region': row.get('region', 'Unknown'),
            'subject_count': int(row['subject_count']),
            'avg_dqi_score': round(row['avg_dqi_score'], 3),
            'max_dqi_score': round(row['max_dqi_score'], 3),
            'high_risk_count': int(row.get('high_risk_count', 0)),
            'site_risk_category': row['site_risk_category'],
            'issues': [],
            'root_causes': [],
            'recommendations': [],
            'ai_insight': None
        }

        issue_columns = [
            'sae_pending_count_sum', 'uncoded_meddra_count_sum',
            'missing_visit_count_sum', 'missing_pages_count_sum',
            'lab_issues_count_sum', 'uncoded_whodd_count_sum',
            'edrr_open_issues_sum', 'inactivated_forms_count_sum'
        ]

        for col in issue_columns:
            if col in row and row[col] > 0:
                issue_type = col.replace('_sum', '')
                if issue_type in ISSUE_ACTIONS:
                    config = ISSUE_ACTIONS[issue_type]
                    rec['issues'].append({
                        'type': issue_type,
                        'total_count': int(row[col]),
                        'priority': config['priority'],
                        'action': config['action']
                    })

        # Generate root cause hypotheses
        if row.get('avg_issue_types', 0) > 3:
            rec['root_causes'].append("Systemic site quality issues - multiple issue types indicate training gaps")
        if row.get('max_days_outstanding_sum', 0) > 100:
            rec['root_causes'].append("Data entry backlog - site may be under-resourced")
        if row.get('missing_visit_count_sum', 0) > 5:
            rec['root_causes'].append("Protocol compliance issues - subjects missing scheduled visits")
        if row.get('sae_pending_count_sum', 0) > 0:
            rec['root_causes'].append("Safety reporting delays - requires immediate escalation")

        # Generate recommendations
        if row['site_risk_category'] == 'High':
            rec['recommendations'].append("Schedule urgent site quality call within 48 hours")
            rec['recommendations'].append("Consider triggered monitoring visit")
        if row.get('high_risk_count', 0) > row['subject_count'] * 0.2:
            rec['recommendations'].append("Review site training records and re-train if needed")
        if row.get('subjects_with_issues', 0) / max(row['subject_count'], 1) > 0.5:
            rec['recommendations'].append("Implement enhanced oversight procedures")

        # Set priority
        if row.get('sae_pending_count_sum', 0) > 0:
            rec['priority'] = 'CRITICAL'
        elif row['site_risk_category'] == 'High':
            rec['priority'] = 'HIGH'
        else:
            rec['priority'] = 'MEDIUM'

        # Generate LLM insight for top 20 sites only
        if llm and llm.available and idx < 20:
            insight = generate_site_insight(llm, rec)
            if insight:
                rec['ai_insight'] = insight

        recommendations.append(rec)

    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    recommendations.sort(key=lambda x: (priority_order.get(x['priority'], 4), -x['avg_dqi_score']))

    return recommendations


def generate_study_recommendations(site_df: pd.DataFrame, llm: Optional[OllamaLLM] = None) -> List[Dict]:
    """Generate study-level recommendations."""
    recommendations = []

    study_summary = site_df.groupby('study').agg({
        'site_id': 'count',
        'subject_count': 'sum',
        'avg_dqi_score': 'mean',
        'high_risk_count': 'sum',
        'sae_pending_count_sum': 'sum',
        'missing_visit_count_sum': 'sum',
        'uncoded_meddra_count_sum': 'sum'
    }).reset_index()

    study_summary.columns = ['study', 'n_sites', 'n_subjects', 'avg_dqi',
                             'total_high_risk', 'total_sae_pending',
                             'total_missing_visits', 'total_uncoded_meddra']

    for idx, (_, row) in enumerate(study_summary.iterrows()):
        rec = {
            'level': 'STUDY',
            'study': row['study'],
            'n_sites': int(row['n_sites']),
            'n_subjects': int(row['n_subjects']),
            'avg_dqi': round(row['avg_dqi'], 3),
            'total_high_risk': int(row['total_high_risk']),
            'key_metrics': {},
            'recommendations': [],
            'ai_insight': None
        }

        rec['key_metrics'] = {
            'high_risk_rate': round(row['total_high_risk'] / max(row['n_subjects'], 1) * 100, 1),
            'pending_sae': int(row['total_sae_pending']),
            'missing_visits': int(row['total_missing_visits']),
            'uncoded_ae': int(row['total_uncoded_meddra'])
        }

        if row['total_sae_pending'] > 0:
            rec['recommendations'].append(f"URGENT: {int(row['total_sae_pending'])} pending SAE reviews require immediate attention")
            rec['priority'] = 'CRITICAL'
        elif row['total_high_risk'] > row['n_subjects'] * 0.1:
            rec['recommendations'].append(f"High-risk subject rate ({rec['key_metrics']['high_risk_rate']}%) exceeds threshold")
            rec['priority'] = 'HIGH'
        else:
            rec['priority'] = 'MEDIUM'

        if row['total_missing_visits'] > 10:
            rec['recommendations'].append(f"Address {int(row['total_missing_visits'])} missing visits across sites")

        if row['total_uncoded_meddra'] > 5:
            rec['recommendations'].append(f"Clear {int(row['total_uncoded_meddra'])} uncoded adverse event terms")

        # Generate LLM insight
        if llm and llm.available and idx < 10:
            insight = generate_study_insight(llm, rec)
            if insight:
                rec['ai_insight'] = insight

        recommendations.append(rec)

    return recommendations


def generate_region_recommendations(site_df: pd.DataFrame, llm: Optional[OllamaLLM] = None) -> List[Dict]:
    """
    Generate region-level recommendations.

    This addresses Issue 2: Solution focuses on sites, ignores studies and regions.
    Regional analysis can identify systemic issues affecting entire geographic areas.
    """
    recommendations = []

    # Aggregate to region level
    region_summary = site_df.groupby('region').agg({
        'site_id': 'count',
        'subject_count': 'sum',
        'avg_dqi_score': ['mean', 'max', 'std'],
        'high_risk_count': 'sum',
        'medium_risk_count': 'sum',
        'sae_pending_count_sum': 'sum',
        'missing_visit_count_sum': 'sum',
        'missing_pages_count_sum': 'sum',
        'study': 'nunique',
        'country': 'nunique',
    }).reset_index()

    # Flatten columns
    region_summary.columns = ['region', 'n_sites', 'n_subjects', 'avg_dqi', 'max_dqi', 'std_dqi',
                              'high_risk_subjects', 'medium_risk_subjects',
                              'pending_sae', 'missing_visits', 'missing_pages',
                              'n_studies', 'n_countries']

    # Calculate metrics
    region_summary['high_risk_rate'] = region_summary['high_risk_subjects'] / region_summary['n_subjects'] * 100
    region_summary['avg_subjects_per_site'] = region_summary['n_subjects'] / region_summary['n_sites']

    # Count high-risk sites per region
    high_risk_sites = site_df[site_df['site_risk_category'] == 'High'].groupby('region').size()
    region_summary['high_risk_sites'] = region_summary['region'].map(high_risk_sites).fillna(0).astype(int)
    region_summary['high_risk_site_rate'] = region_summary['high_risk_sites'] / region_summary['n_sites'] * 100

    # Portfolio averages for comparison
    portfolio_avg_dqi = site_df['avg_dqi_score'].mean()
    portfolio_high_risk_rate = (site_df['high_risk_count'].sum() / site_df['subject_count'].sum()) * 100

    for _, row in region_summary.iterrows():
        rec = {
            'level': 'REGION',
            'region': row['region'],
            'n_countries': int(row['n_countries']),
            'n_sites': int(row['n_sites']),
            'n_subjects': int(row['n_subjects']),
            'n_studies': int(row['n_studies']),
            'avg_dqi': round(row['avg_dqi'], 4),
            'max_dqi': round(row['max_dqi'], 4),
            'key_metrics': {},
            'comparison_to_portfolio': {},
            'recommendations': [],
            'ai_insight': None
        }

        rec['key_metrics'] = {
            'high_risk_rate': round(row['high_risk_rate'], 1),
            'high_risk_site_rate': round(row['high_risk_site_rate'], 1),
            'pending_sae': int(row['pending_sae']),
            'missing_visits': int(row['missing_visits']),
            'missing_pages': int(row['missing_pages']),
            'avg_subjects_per_site': round(row['avg_subjects_per_site'], 1),
        }

        # Compare to portfolio
        dqi_diff = ((row['avg_dqi'] / portfolio_avg_dqi) - 1) * 100 if portfolio_avg_dqi > 0 else 0
        risk_diff = row['high_risk_rate'] - portfolio_high_risk_rate

        rec['comparison_to_portfolio'] = {
            'dqi_vs_portfolio': f"{'+' if dqi_diff > 0 else ''}{dqi_diff:.1f}%",
            'risk_vs_portfolio': f"{'+' if risk_diff > 0 else ''}{risk_diff:.1f}pp",
            'is_above_average': dqi_diff > 10,  # 10% worse than portfolio
        }

        # Determine priority and generate recommendations
        if row['pending_sae'] > 10:
            rec['priority'] = 'CRITICAL'
            rec['recommendations'].append(f"CRITICAL: {int(row['pending_sae'])} pending SAE reviews across {row['region']}")
        elif row['high_risk_rate'] > 15 or dqi_diff > 20:
            rec['priority'] = 'HIGH'
            rec['recommendations'].append(f"Region has elevated risk rate ({row['high_risk_rate']:.1f}%) vs portfolio ({portfolio_high_risk_rate:.1f}%)")
        elif row['high_risk_rate'] > 10 or dqi_diff > 10:
            rec['priority'] = 'MEDIUM'
        else:
            rec['priority'] = 'LOW'

        if row['high_risk_site_rate'] > 20:
            rec['recommendations'].append(f"{row['high_risk_site_rate']:.0f}% of sites in {row['region']} are high-risk - consider regional training initiative")

        if row['missing_visits'] > 50:
            rec['recommendations'].append(f"Address {int(row['missing_visits'])} missing visits - may indicate regional protocol compliance issues")

        if row['std_dqi'] > 0.1:
            rec['recommendations'].append(f"High variability in data quality (σ={row['std_dqi']:.3f}) - some sites need targeted support")

        if not rec['recommendations']:
            rec['recommendations'].append(f"{row['region']} performing within acceptable range")

        # Generate LLM insight for regions
        if llm and llm.available:
            prompt = f"""Provide a brief regional analysis insight (2-3 sentences):

Region: {row['region']}
Coverage: {int(row['n_countries'])} countries, {int(row['n_sites'])} sites, {int(row['n_subjects'])} subjects
DQI Score: {row['avg_dqi']:.3f} (portfolio avg: {portfolio_avg_dqi:.3f})
High-Risk Rate: {row['high_risk_rate']:.1f}% (portfolio: {portfolio_high_risk_rate:.1f}%)
High-Risk Sites: {int(row['high_risk_sites'])} of {int(row['n_sites'])} ({row['high_risk_site_rate']:.1f}%)

Focus on actionable regional-level insights."""

            try:
                insight = llm.generate(prompt, max_tokens=150)
                rec['ai_insight'] = insight.strip() if insight else None
            except:
                pass

        recommendations.append(rec)

    # Sort by priority
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    recommendations.sort(key=lambda x: (priority_order.get(x['priority'], 4), -x['avg_dqi']))

    return recommendations


def generate_country_recommendations(site_df: pd.DataFrame, llm: Optional[OllamaLLM] = None) -> List[Dict]:
    """
    Generate country-level recommendations.

    Country-level analysis identifies localized issues that may require
    country-specific interventions (training, regulatory, CRO issues).
    """
    recommendations = []

    # Aggregate to country level
    country_summary = site_df.groupby(['country', 'region']).agg({
        'site_id': 'count',
        'subject_count': 'sum',
        'avg_dqi_score': ['mean', 'max'],
        'high_risk_count': 'sum',
        'sae_pending_count_sum': 'sum',
        'missing_visit_count_sum': 'sum',
        'study': 'nunique',
    }).reset_index()

    # Flatten columns
    country_summary.columns = ['country', 'region', 'n_sites', 'n_subjects', 'avg_dqi', 'max_dqi',
                               'high_risk_subjects', 'pending_sae', 'missing_visits', 'n_studies']

    # Filter to countries with at least 2 sites (enough for meaningful analysis)
    country_summary = country_summary[country_summary['n_sites'] >= 2]

    # Calculate metrics
    country_summary['high_risk_rate'] = country_summary['high_risk_subjects'] / country_summary['n_subjects'] * 100

    # Count high-risk sites per country
    high_risk_sites = site_df[site_df['site_risk_category'] == 'High'].groupby('country').size()
    country_summary['high_risk_sites'] = country_summary['country'].map(high_risk_sites).fillna(0).astype(int)
    country_summary['high_risk_site_rate'] = country_summary['high_risk_sites'] / country_summary['n_sites'] * 100

    # Portfolio average
    portfolio_avg_dqi = site_df['avg_dqi_score'].mean()

    # Only generate recommendations for countries with issues
    flagged_countries = country_summary[
        (country_summary['avg_dqi'] > portfolio_avg_dqi * 1.2) |  # 20% worse than avg
        (country_summary['high_risk_rate'] > 15) |
        (country_summary['pending_sae'] > 5) |
        (country_summary['high_risk_site_rate'] > 25)
    ].copy()

    for _, row in flagged_countries.iterrows():
        rec = {
            'level': 'COUNTRY',
            'country': row['country'],
            'region': row['region'],
            'n_sites': int(row['n_sites']),
            'n_subjects': int(row['n_subjects']),
            'n_studies': int(row['n_studies']),
            'avg_dqi': round(row['avg_dqi'], 4),
            'key_metrics': {
                'high_risk_rate': round(row['high_risk_rate'], 1),
                'high_risk_sites': int(row['high_risk_sites']),
                'high_risk_site_rate': round(row['high_risk_site_rate'], 1),
                'pending_sae': int(row['pending_sae']),
                'missing_visits': int(row['missing_visits']),
            },
            'recommendations': [],
            'ai_insight': None
        }

        # Determine priority
        if row['pending_sae'] > 5:
            rec['priority'] = 'CRITICAL'
            rec['recommendations'].append(f"URGENT: {int(row['pending_sae'])} pending SAE reviews in {row['country']}")
        elif row['high_risk_rate'] > 20 or row['high_risk_site_rate'] > 30:
            rec['priority'] = 'HIGH'
        elif row['high_risk_rate'] > 10:
            rec['priority'] = 'MEDIUM'
        else:
            rec['priority'] = 'LOW'

        if row['high_risk_site_rate'] > 30:
            rec['recommendations'].append(f"{row['high_risk_site_rate']:.0f}% of sites are high-risk - investigate country-specific factors (CRO, training, regulatory)")

        if row['avg_dqi'] > portfolio_avg_dqi * 1.5:
            rec['recommendations'].append(f"DQI significantly above portfolio average - prioritize for quality improvement")

        if row['missing_visits'] > 20:
            rec['recommendations'].append(f"Address {int(row['missing_visits'])} missing visits across {int(row['n_sites'])} sites")

        recommendations.append(rec)

    # Sort by priority
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    recommendations.sort(key=lambda x: (priority_order.get(x['priority'], 4), -x['avg_dqi']))

    return recommendations


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_executive_summary(
    subject_recs: List[Dict],
    site_recs: List[Dict],
    study_recs: List[Dict],
    data: Dict[str, pd.DataFrame],
    llm: Optional[OllamaLLM] = None,
    region_recs: List[Dict] = None,
    country_recs: List[Dict] = None
) -> str:
    """Generate an executive summary of data quality status."""

    subjects_df = data['subjects']
    sites_df = data['sites']

    total_subjects = len(subjects_df)
    high_risk_subjects = len(subjects_df[subjects_df['risk_category'] == 'High'])
    medium_risk_subjects = len(subjects_df[subjects_df['risk_category'] == 'Medium'])

    total_sites = len(sites_df)
    high_risk_sites = len(sites_df[sites_df['site_risk_category'] == 'High'])

    critical_count = sum(1 for r in subject_recs if r.get('priority') == 'CRITICAL')
    critical_sites = sum(1 for r in site_recs if r.get('priority') == 'CRITICAL')

    pending_sae = int(subjects_df['sae_pending_count'].sum()) if 'sae_pending_count' in subjects_df.columns else 0

    # Aggregate issues
    all_issues = []
    for rec in subject_recs:
        all_issues.extend(rec.get('issues', []))

    issue_counts = {}
    for issue in all_issues:
        issue_type = issue['type']
        if issue_type not in issue_counts:
            issue_counts[issue_type] = 0
        issue_counts[issue_type] += issue['count']

    top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_issue_names = [f"{k.replace('_', ' ').title()}: {v}" for k, v in top_issues]

    # Generate LLM executive insight
    ai_executive_insight = None
    if llm and llm.available:
        summary_data = {
            'total_subjects': total_subjects,
            'total_sites': total_sites,
            'n_studies': subjects_df['study'].nunique(),
            'high_risk_subjects': high_risk_subjects,
            'high_risk_pct': high_risk_subjects / total_subjects * 100,
            'critical_sites': critical_sites,
            'pending_sae': pending_sae,
            'top_issues': top_issue_names
        }
        ai_executive_insight = generate_executive_insight(llm, summary_data)

    summary = f"""
================================================================================
JAVELIN.AI - DATA QUALITY EXECUTIVE SUMMARY
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

OVERVIEW
--------
Total Subjects: {total_subjects:,}
Total Sites: {total_sites:,}
Studies: {subjects_df['study'].nunique()}

RISK DISTRIBUTION
-----------------
Subject Level:
  * High Risk: {high_risk_subjects:,} subjects ({high_risk_subjects/total_subjects*100:.1f}%)
  * Medium Risk: {medium_risk_subjects:,} subjects ({medium_risk_subjects/total_subjects*100:.1f}%)
  * Low Risk: {total_subjects - high_risk_subjects - medium_risk_subjects:,} subjects

Site Level:
  * High Risk Sites: {high_risk_sites} ({high_risk_sites/total_sites*100:.1f}%)

"""

    # Add Regional Analysis section
    if region_recs:
        summary += """REGIONAL ANALYSIS
-----------------
"""
        for rec in region_recs:
            status = "⚠️" if rec['priority'] in ['HIGH', 'CRITICAL'] else "✓"
            summary += f"  {status} {rec['region']}: {rec['n_countries']} countries, {rec['n_sites']} sites, {rec['n_subjects']:,} subjects\n"
            summary += f"     DQI: {rec['avg_dqi']:.3f} | High-risk rate: {rec['key_metrics']['high_risk_rate']:.1f}%"
            summary += f" | vs Portfolio: {rec['comparison_to_portfolio']['dqi_vs_portfolio']}\n"
        summary += "\n"

    # Add Country Flags section
    if country_recs and len(country_recs) > 0:
        summary += """COUNTRIES REQUIRING ATTENTION
-----------------------------
"""
        for rec in country_recs[:10]:  # Top 10 countries
            summary += f"  [{rec['priority']}] {rec['country']} ({rec['region']}): {rec['n_sites']} sites, "
            summary += f"DQI={rec['avg_dqi']:.3f}, High-risk={rec['key_metrics']['high_risk_rate']:.1f}%\n"
            if rec['recommendations']:
                summary += f"        → {rec['recommendations'][0]}\n"
        summary += "\n"

    # Add AI insight if available
    if ai_executive_insight:
        summary += f"""AI-GENERATED INSIGHT
--------------------
{ai_executive_insight}

"""

    summary += f"""CRITICAL ITEMS REQUIRING IMMEDIATE ACTION
-----------------------------------------
"""

    if pending_sae > 0:
        summary += f"[!] PENDING SAE REVIEWS: {pending_sae} subjects have SAE records awaiting review\n"
        summary += "    Action: Immediate pharmacovigilance review required\n\n"

    if critical_count > 0:
        summary += f"[!] CRITICAL SUBJECTS: {critical_count} subjects require immediate intervention\n"

    if critical_sites > 0:
        summary += f"[!] CRITICAL SITES: {critical_sites} sites flagged for urgent quality review\n"

    if pending_sae == 0 and critical_count == 0 and critical_sites == 0:
        summary += "[OK] No critical items requiring immediate action\n"

    summary += """
TOP PRIORITIES THIS WEEK
------------------------
"""

    for i, rec in enumerate(site_recs[:5], 1):
        summary += f"{i}. [{rec['priority']}] {rec['study']} - {rec['site_id']} ({rec['country']})\n"
        summary += f"   DQI Score: {rec['avg_dqi_score']:.3f} | High-risk subjects: {rec['high_risk_count']}\n"
        if rec.get('ai_insight'):
            insight = rec['ai_insight'][:200] + "..." if len(rec['ai_insight']) > 200 else rec['ai_insight']
            summary += f"   AI Insight: {insight}\n"
        elif rec['recommendations']:
            summary += f"   Action: {rec['recommendations'][0]}\n"
        summary += "\n"

    summary += """
RECOMMENDATIONS BY CATEGORY
---------------------------
"""

    for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
        if issue_type in ISSUE_ACTIONS:
            info = ISSUE_ACTIONS[issue_type]
            summary += f"* {issue_type.replace('_', ' ').title()}: {count} instances\n"
            summary += f"  Priority: {info['priority']} | Action: {info['action']}\n\n"

    summary += """
================================================================================
"""

    return summary


def generate_site_action_report(site_recs: List[Dict]) -> str:
    """Generate a detailed action report for sites."""

    report = """
================================================================================
SITE-LEVEL ACTION REPORT
================================================================================
"""

    for i, rec in enumerate(site_recs[:50], 1):
        report += f"""
--------------------------------------------------------------------------------
{i}. {rec['study']} - {rec['site_id']} ({rec['country']}, {rec['region']})
--------------------------------------------------------------------------------
Priority: {rec['priority']}
Subjects: {rec['subject_count']} | High-Risk: {rec['high_risk_count']}
Average DQI: {rec['avg_dqi_score']:.3f} | Max DQI: {rec['max_dqi_score']:.3f}
"""

        if rec.get('ai_insight'):
            report += f"""
AI Analysis:
{rec['ai_insight']}
"""

        report += "\nIssues Identified:\n"
        for issue in rec['issues'][:5]:
            report += f"  * {issue['type'].replace('_', ' ').title()}: {issue['total_count']} instances [{issue['priority']}]\n"
            report += f"    Action: {issue['action']}\n"

        if rec['root_causes']:
            report += "\nPotential Root Causes:\n"
            for cause in rec['root_causes']:
                report += f"  * {cause}\n"

        if rec['recommendations']:
            report += "\nRecommended Actions:\n"
            for action in rec['recommendations']:
                report += f"  - {action}\n"

        report += "\n"

    return report


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def save_outputs(
    subject_recs: List[Dict],
    site_recs: List[Dict],
    study_recs: List[Dict],
    executive_summary: str,
    site_report: str,
    data: Dict[str, pd.DataFrame],
    llm_model: str = None,
    region_recs: List[Dict] = None,
    country_recs: List[Dict] = None
):
    """Save all outputs."""

    # 1. Executive Summary
    with open(OUTPUT_DIR / "executive_summary.txt", 'w', encoding='utf-8') as f:
        f.write(executive_summary)
    print(f"  Saved: outputs/executive_summary.txt")

    # 2. Site Action Report
    with open(OUTPUT_DIR / "recommendations_report.md", 'w', encoding='utf-8') as f:
        f.write("# Javelin.AI - Data Quality Recommendations Report\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        if llm_model:
            f.write(f"*Enhanced with AI Analysis ({llm_model})*\n")
        f.write("\n## Executive Summary\n\n")
        f.write("```\n")
        f.write(executive_summary)
        f.write("```\n\n")

        # Add Regional Analysis section to report
        if region_recs:
            f.write("## Regional Analysis\n\n")
            for rec in region_recs:
                f.write(f"### {rec['region']}\n")
                f.write(f"- **Coverage:** {rec['n_countries']} countries, {rec['n_sites']} sites, {rec['n_subjects']:,} subjects\n")
                f.write(f"- **DQI Score:** {rec['avg_dqi']:.4f} (Max: {rec['max_dqi']:.4f})\n")
                f.write(f"- **High-Risk Rate:** {rec['key_metrics']['high_risk_rate']:.1f}%\n")
                f.write(f"- **vs Portfolio:** {rec['comparison_to_portfolio']['dqi_vs_portfolio']}\n")
                f.write(f"- **Priority:** {rec['priority']}\n")
                if rec['recommendations']:
                    f.write("- **Recommendations:**\n")
                    for r in rec['recommendations']:
                        f.write(f"  - {r}\n")
                if rec.get('ai_insight'):
                    f.write(f"- **AI Insight:** {rec['ai_insight']}\n")
                f.write("\n")

        # Add Country Flags section
        if country_recs:
            f.write("## Countries Requiring Attention\n\n")
            for rec in country_recs:
                f.write(f"### {rec['country']} ({rec['region']})\n")
                f.write(f"- **Sites:** {rec['n_sites']} | **Subjects:** {rec['n_subjects']:,}\n")
                f.write(f"- **DQI Score:** {rec['avg_dqi']:.4f}\n")
                f.write(f"- **High-Risk Rate:** {rec['key_metrics']['high_risk_rate']:.1f}%\n")
                f.write(f"- **Priority:** {rec['priority']}\n")
                if rec['recommendations']:
                    for r in rec['recommendations']:
                        f.write(f"- {r}\n")
                f.write("\n")

        f.write("## Detailed Site Recommendations\n\n")
        f.write(site_report)
    print(f"  Saved: outputs/recommendations_report.md")

    # 3. Site Recommendations CSV
    site_csv_data = []
    for rec in site_recs:
        site_csv_data.append({
            'study': rec['study'],
            'site_id': rec['site_id'],
            'country': rec['country'],
            'region': rec['region'],
            'priority': rec['priority'],
            'subject_count': rec['subject_count'],
            'high_risk_count': rec['high_risk_count'],
            'avg_dqi_score': rec['avg_dqi_score'],
            'top_issue': rec['issues'][0]['type'] if rec['issues'] else '',
            'top_recommendation': rec['recommendations'][0] if rec['recommendations'] else '',
            'ai_insight': rec.get('ai_insight', '')[:500] if rec.get('ai_insight') else ''
        })
    pd.DataFrame(site_csv_data).to_csv(OUTPUT_DIR / "recommendations_by_site.csv", index=False)
    print(f"  Saved: outputs/recommendations_by_site.csv")

    # 4. Region Recommendations CSV (NEW)
    if region_recs:
        region_csv_data = []
        for rec in region_recs:
            region_csv_data.append({
                'region': rec['region'],
                'n_countries': rec['n_countries'],
                'n_sites': rec['n_sites'],
                'n_subjects': rec['n_subjects'],
                'n_studies': rec['n_studies'],
                'avg_dqi_score': rec['avg_dqi'],
                'max_dqi_score': rec['max_dqi'],
                'high_risk_rate': rec['key_metrics']['high_risk_rate'],
                'high_risk_site_rate': rec['key_metrics']['high_risk_site_rate'],
                'pending_sae': rec['key_metrics']['pending_sae'],
                'priority': rec['priority'],
                'vs_portfolio': rec['comparison_to_portfolio']['dqi_vs_portfolio'],
                'top_recommendation': rec['recommendations'][0] if rec['recommendations'] else '',
                'ai_insight': rec.get('ai_insight', '')[:500] if rec.get('ai_insight') else ''
            })
        pd.DataFrame(region_csv_data).to_csv(OUTPUT_DIR / "recommendations_by_region.csv", index=False)
        print(f"  Saved: outputs/recommendations_by_region.csv")

    # 5. Country Recommendations CSV (NEW)
    if country_recs:
        country_csv_data = []
        for rec in country_recs:
            country_csv_data.append({
                'country': rec['country'],
                'region': rec['region'],
                'n_sites': rec['n_sites'],
                'n_subjects': rec['n_subjects'],
                'n_studies': rec['n_studies'],
                'avg_dqi_score': rec['avg_dqi'],
                'high_risk_rate': rec['key_metrics']['high_risk_rate'],
                'high_risk_sites': rec['key_metrics']['high_risk_sites'],
                'pending_sae': rec['key_metrics']['pending_sae'],
                'priority': rec['priority'],
                'top_recommendation': rec['recommendations'][0] if rec['recommendations'] else ''
            })
        pd.DataFrame(country_csv_data).to_csv(OUTPUT_DIR / "recommendations_by_country.csv", index=False)
        print(f"  Saved: outputs/recommendations_by_country.csv")

    # 6. Action Items JSON (Updated)
    action_items = {
        'generated_at': datetime.now().isoformat(),
        'ai_model': llm_model,
        'summary': {
            'total_subjects': len(data['subjects']),
            'total_sites': len(data['sites']),
            'total_regions': len(region_recs) if region_recs else 0,
            'total_countries_flagged': len(country_recs) if country_recs else 0,
            'critical_items': sum(1 for r in site_recs if r['priority'] == 'CRITICAL'),
            'high_priority_items': sum(1 for r in site_recs if r['priority'] == 'HIGH')
        },
        'site_recommendations': site_recs[:20],
        'study_recommendations': study_recs,
        'region_recommendations': region_recs if region_recs else [],
        'country_recommendations': country_recs if country_recs else []
    }
    with open(OUTPUT_DIR / "action_items.json", 'w', encoding='utf-8') as f:
        json.dump(action_items, f, indent=2, default=str)
    print(f"  Saved: outputs/action_items.json")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def run_recommendations_engine(model: str = DEFAULT_MODEL):
    """Main function to run the recommendations engine."""

    print("=" * 70)
    print("JAVELIN.AI - GEN AI RECOMMENDATIONS ENGINE")
    print("=" * 70)

    # Step 1: Initialize LLM
    print("\n[1/8] Initializing LLM...")
    llm = OllamaLLM(model=model)
    if llm.available:
        print(f"  LLM Ready: {llm.model}")
    else:
        print("  LLM not available - continuing without AI insights")
        print("  To enable: Install Ollama, run 'ollama pull mistral', then 'ollama serve'")

    # Step 2: Load Data
    print("\n[2/8] Loading data...")
    data = load_data()

    # Step 3: Generate Subject Recommendations
    print("\n[3/8] Analyzing subject-level risks...")
    subject_recs = generate_subject_recommendations(data['subjects'])
    print(f"  Generated {len(subject_recs)} subject recommendations")
    print(f"  Critical: {sum(1 for r in subject_recs if r['priority'] == 'CRITICAL')}")
    print(f"  High: {sum(1 for r in subject_recs if r['priority'] == 'HIGH')}")

    # Step 4: Generate Site Recommendations
    print("\n[4/8] Analyzing site-level patterns...")
    if llm.available:
        print("  Generating AI insights for top sites...")
    site_recs = generate_site_recommendations(data['sites'], llm if llm.available else None)
    print(f"  Generated {len(site_recs)} site recommendations")
    if llm.available:
        ai_count = sum(1 for r in site_recs if r.get('ai_insight'))
        print(f"  AI insights: {ai_count}")

    # Step 5: Generate Study Recommendations
    print("\n[5/8] Generating study-level insights...")
    study_recs = generate_study_recommendations(data['sites'], llm if llm.available else None)
    print(f"  Analyzed {len(study_recs)} studies")

    # Step 6: Generate Region Recommendations (NEW - addresses Issue 2)
    print("\n[6/8] Generating region-level insights...")
    region_recs = generate_region_recommendations(data['sites'], llm if llm.available else None)
    print(f"  Analyzed {len(region_recs)} regions")
    for rec in region_recs:
        print(f"    {rec['region']}: {rec['n_sites']} sites, DQI={rec['avg_dqi']:.3f}, Priority={rec['priority']}")

    # Step 7: Generate Country Recommendations (NEW - addresses Issue 2)
    print("\n[7/8] Generating country-level insights...")
    country_recs = generate_country_recommendations(data['sites'], llm if llm.available else None)
    print(f"  Flagged {len(country_recs)} countries for attention")

    # Step 8: Generate Reports
    print("\n[8/8] Generating reports...")
    executive_summary = generate_executive_summary(
        subject_recs, site_recs, study_recs, data,
        llm if llm.available else None,
        region_recs=region_recs,
        country_recs=country_recs
    )
    site_report = generate_site_action_report(site_recs)

    save_outputs(
        subject_recs, site_recs, study_recs,
        executive_summary, site_report, data,
        llm.model if llm.available else None,
        region_recs=region_recs,
        country_recs=country_recs
    )

    # Print Summary
    print("\n" + "=" * 70)
    print("EXECUTIVE SUMMARY")
    print("=" * 70)
    print(executive_summary)

    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)
    if llm.available:
        print(f"\nAI Model: {llm.model}")
    print("""
Outputs:
  1. outputs/executive_summary.txt
  2. outputs/recommendations_report.md
  3. outputs/recommendations_by_site.csv
  4. outputs/recommendations_by_region.csv   [NEW - Regional Analysis]
  5. outputs/recommendations_by_country.csv  [NEW - Country Analysis]
  6. outputs/action_items.json
""")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    model = DEFAULT_MODEL

    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx + 1]

    run_recommendations_engine(model=model)
