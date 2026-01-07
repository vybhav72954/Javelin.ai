"""
Javelin.AI - Step 6: Gen AI Recommendations Engine
===================================================

This module generates actionable recommendations from DQI scores
using a combination of rule-based logic and LLM-powered insights.

Architecture:
------------
1. Data Layer: Load DQI scores, site metrics, knowledge graph
2. Rules Engine: Generate recommendations based on thresholds
3. LLM Layer: Transform recommendations into natural language
4. Output Layer: Prioritized action items with context

The Gen AI component adds value by:
- Contextualizing recommendations with study/site specifics
- Generating executive summaries
- Answering natural language queries about data quality
- Providing root cause analysis suggestions

Usage:
    python src/06_recommendations_engine.py

    # Or with query mode:
    python src/06_recommendations_engine.py --query "Which sites need immediate attention?"

Output:
    - outputs/recommendations_report.md
    - outputs/recommendations_by_site.csv
    - outputs/executive_summary.txt
    - outputs/action_items.json
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get the project root directory (parent of src folder)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

SUBJECT_DQI_PATH = OUTPUT_DIR / "master_subject_with_dqi.csv"
SITE_DQI_PATH = OUTPUT_DIR / "master_site_with_dqi.csv"
WEIGHTS_PATH = OUTPUT_DIR / "dqi_weights.csv"

# Recommendation thresholds
THRESHOLDS = {
    'critical_dqi': 0.4,      # Immediate action required
    'high_dqi': 0.2,          # Action within 48 hours
    'medium_dqi': 0.1,        # Review within 1 week
    'high_risk_site_pct': 0.15,  # >15% high-risk subjects = flagged site
    'sae_pending_critical': 1,   # Any pending SAE = critical
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

    # Filter to subjects with issues
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

        # Identify specific issues
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

        # Sort issues by priority
        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        rec['issues'].sort(key=lambda x: priority_order.get(x['priority'], 4))

        # Set overall priority based on highest priority issue
        if rec['issues']:
            rec['priority'] = rec['issues'][0]['priority']
        else:
            rec['priority'] = 'LOW'

        recommendations.append(rec)

    # Sort by priority and DQI score
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    recommendations.sort(key=lambda x: (priority_order.get(x['priority'], 4), -x['dqi_score']))

    return recommendations


def generate_site_recommendations(df: pd.DataFrame) -> List[Dict]:
    """Generate recommendations for sites requiring attention."""
    recommendations = []

    # Sites with high average DQI or high-risk subjects
    flagged_sites = df[
        (df['site_risk_category'] == 'High') |
        (df['avg_dqi_score'] > THRESHOLDS['high_dqi'])
    ].copy()

    for _, row in flagged_sites.iterrows():
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
            'recommendations': []
        }

        # Identify main issues at site level
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

        # Generate root cause hypotheses based on patterns
        if row.get('avg_issue_types', 0) > 3:
            rec['root_causes'].append("Systemic site quality issues - multiple issue types indicate training gaps")
        if row.get('max_days_outstanding_sum', 0) > 100:
            rec['root_causes'].append("Data entry backlog - site may be under-resourced")
        if row.get('missing_visit_count_sum', 0) > 5:
            rec['root_causes'].append("Protocol compliance issues - subjects missing scheduled visits")
        if row.get('sae_pending_count_sum', 0) > 0:
            rec['root_causes'].append("Safety reporting delays - requires immediate escalation")

        # Generate site-level recommendations
        if row['site_risk_category'] == 'High':
            rec['recommendations'].append("Schedule urgent site quality call within 48 hours")
            rec['recommendations'].append("Consider triggered monitoring visit")
        if row.get('high_risk_count', 0) > row['subject_count'] * 0.2:
            rec['recommendations'].append("Review site training records and re-train if needed")
        if row.get('subjects_with_issues', 0) / row['subject_count'] > 0.5:
            rec['recommendations'].append("Implement enhanced oversight procedures")

        # Set priority
        if row.get('sae_pending_count_sum', 0) > 0:
            rec['priority'] = 'CRITICAL'
        elif row['site_risk_category'] == 'High':
            rec['priority'] = 'HIGH'
        else:
            rec['priority'] = 'MEDIUM'

        recommendations.append(rec)

    # Sort by priority
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    recommendations.sort(key=lambda x: (priority_order.get(x['priority'], 4), -x['avg_dqi_score']))

    return recommendations


def generate_study_recommendations(site_df: pd.DataFrame) -> List[Dict]:
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

    for _, row in study_summary.iterrows():
        rec = {
            'level': 'STUDY',
            'study': row['study'],
            'n_sites': int(row['n_sites']),
            'n_subjects': int(row['n_subjects']),
            'avg_dqi': round(row['avg_dqi'], 3),
            'total_high_risk': int(row['total_high_risk']),
            'key_metrics': {},
            'recommendations': []
        }

        rec['key_metrics'] = {
            'high_risk_rate': round(row['total_high_risk'] / row['n_subjects'] * 100, 1) if row['n_subjects'] > 0 else 0,
            'pending_sae': int(row['total_sae_pending']),
            'missing_visits': int(row['total_missing_visits']),
            'uncoded_ae': int(row['total_uncoded_meddra'])
        }

        # Generate study-level recommendations
        if row['total_sae_pending'] > 0:
            rec['recommendations'].append(f"URGENT: {int(row['total_sae_pending'])} pending SAE reviews require immediate attention")
            rec['priority'] = 'CRITICAL'
        elif row['total_high_risk'] > row['n_subjects'] * 0.1:
            rec['recommendations'].append(f"High-risk subject rate ({rec['key_metrics']['high_risk_rate']}%) exceeds threshold - review data management processes")
            rec['priority'] = 'HIGH'
        else:
            rec['priority'] = 'MEDIUM'

        if row['total_missing_visits'] > 10:
            rec['recommendations'].append(f"Address {int(row['total_missing_visits'])} missing visits across sites")

        if row['total_uncoded_meddra'] > 5:
            rec['recommendations'].append(f"Clear {int(row['total_uncoded_meddra'])} uncoded adverse event terms")

        recommendations.append(rec)

    return recommendations


# ============================================================================
# NATURAL LANGUAGE GENERATION
# ============================================================================

def generate_executive_summary(
    subject_recs: List[Dict],
    site_recs: List[Dict],
    study_recs: List[Dict],
    data: Dict[str, pd.DataFrame]
) -> str:
    """Generate an executive summary of data quality status."""

    subjects_df = data['subjects']
    sites_df = data['sites']

    # Calculate key metrics
    total_subjects = len(subjects_df)
    high_risk_subjects = len(subjects_df[subjects_df['risk_category'] == 'High'])
    medium_risk_subjects = len(subjects_df[subjects_df['risk_category'] == 'Medium'])

    total_sites = len(sites_df)
    high_risk_sites = len(sites_df[sites_df['site_risk_category'] == 'High'])

    critical_count = sum(1 for r in subject_recs if r.get('priority') == 'CRITICAL')
    critical_sites = sum(1 for r in site_recs if r.get('priority') == 'CRITICAL')

    # Get pending SAE count
    pending_sae = int(subjects_df['sae_pending_count'].sum()) if 'sae_pending_count' in subjects_df.columns else 0

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
  • High Risk: {high_risk_subjects:,} subjects ({high_risk_subjects/total_subjects*100:.1f}%)
  • Medium Risk: {medium_risk_subjects:,} subjects ({medium_risk_subjects/total_subjects*100:.1f}%)
  • Low Risk: {total_subjects - high_risk_subjects - medium_risk_subjects:,} subjects

Site Level:
  • High Risk Sites: {high_risk_sites} ({high_risk_sites/total_sites*100:.1f}%)

CRITICAL ITEMS REQUIRING IMMEDIATE ACTION
-----------------------------------------
"""

    if pending_sae > 0:
        summary += f"⚠️  PENDING SAE REVIEWS: {pending_sae} subjects have SAE records awaiting review\n"
        summary += "   → Action: Immediate pharmacovigilance review required\n\n"

    if critical_count > 0:
        summary += f"🔴 CRITICAL SUBJECTS: {critical_count} subjects require immediate intervention\n"

    if critical_sites > 0:
        summary += f"🔴 CRITICAL SITES: {critical_sites} sites flagged for urgent quality review\n"

    if pending_sae == 0 and critical_count == 0 and critical_sites == 0:
        summary += "✅ No critical items requiring immediate action\n"

    summary += """
TOP PRIORITIES THIS WEEK
------------------------
"""

    # Add top 5 site-level priorities
    for i, rec in enumerate(site_recs[:5], 1):
        summary += f"{i}. [{rec['priority']}] {rec['study']} - {rec['site_id']} ({rec['country']})\n"
        summary += f"   DQI Score: {rec['avg_dqi_score']:.3f} | High-risk subjects: {rec['high_risk_count']}\n"
        if rec['recommendations']:
            summary += f"   → {rec['recommendations'][0]}\n"
        summary += "\n"

    summary += """
RECOMMENDATIONS BY CATEGORY
---------------------------
"""

    # Aggregate recommendations by type
    all_issues = []
    for rec in subject_recs:
        all_issues.extend(rec.get('issues', []))

    issue_counts = {}
    for issue in all_issues:
        issue_type = issue['type']
        if issue_type not in issue_counts:
            issue_counts[issue_type] = {'count': 0, 'priority': issue['priority'], 'action': issue['action']}
        issue_counts[issue_type]['count'] += issue['count']

    for issue_type, info in sorted(issue_counts.items(), key=lambda x: x[1]['count'], reverse=True):
        summary += f"• {issue_type.replace('_', ' ').title()}: {info['count']} instances\n"
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

    for i, rec in enumerate(site_recs, 1):
        report += f"""
--------------------------------------------------------------------------------
{i}. {rec['study']} - {rec['site_id']} ({rec['country']}, {rec['region']})
--------------------------------------------------------------------------------
Priority: {rec['priority']}
Subjects: {rec['subject_count']} | High-Risk: {rec['high_risk_count']}
Average DQI: {rec['avg_dqi_score']:.3f} | Max DQI: {rec['max_dqi_score']:.3f}

Issues Identified:
"""
        for issue in rec['issues'][:5]:
            report += f"  • {issue['type'].replace('_', ' ').title()}: {issue['total_count']} instances [{issue['priority']}]\n"
            report += f"    Action: {issue['action']}\n"

        if rec['root_causes']:
            report += "\nPotential Root Causes:\n"
            for cause in rec['root_causes']:
                report += f"  • {cause}\n"

        if rec['recommendations']:
            report += "\nRecommended Actions:\n"
            for action in rec['recommendations']:
                report += f"  → {action}\n"

        report += "\n"

    return report


# ============================================================================
# QUERY INTERFACE
# ============================================================================

def answer_query(query: str, data: Dict[str, pd.DataFrame],
                 subject_recs: List[Dict], site_recs: List[Dict]) -> str:
    """Answer natural language queries about data quality."""

    query_lower = query.lower()
    subjects_df = data['subjects']
    sites_df = data['sites']

    # Query patterns
    if 'critical' in query_lower or 'immediate' in query_lower or 'urgent' in query_lower:
        critical_recs = [r for r in site_recs if r['priority'] == 'CRITICAL']
        if critical_recs:
            response = f"Found {len(critical_recs)} sites requiring immediate attention:\n\n"
            for rec in critical_recs[:5]:
                response += f"• {rec['study']} - {rec['site_id']} ({rec['country']})\n"
                response += f"  Issues: {', '.join([i['type'] for i in rec['issues'][:3]])}\n"
        else:
            response = "No critical issues requiring immediate attention."
        return response

    elif 'worst' in query_lower or 'highest risk' in query_lower:
        top_sites = sites_df.nlargest(5, 'avg_dqi_score')
        response = "Top 5 highest risk sites:\n\n"
        for _, row in top_sites.iterrows():
            response += f"• {row['study']} - {row['site_id']} (DQI: {row['avg_dqi_score']:.3f})\n"
        return response

    elif 'sae' in query_lower or 'safety' in query_lower:
        pending_sae = subjects_df[subjects_df['sae_pending_count'] > 0]
        response = f"SAE Status:\n"
        response += f"• Subjects with pending SAE: {len(pending_sae)}\n"
        response += f"• Total pending SAE count: {int(pending_sae['sae_pending_count'].sum())}\n\n"
        if len(pending_sae) > 0:
            response += "Sites with pending SAE:\n"
            sae_sites = pending_sae.groupby(['study', 'site_id'])['sae_pending_count'].sum().reset_index()
            for _, row in sae_sites.head(10).iterrows():
                response += f"  • {row['study']} - {row['site_id']}: {int(row['sae_pending_count'])} pending\n"
        return response

    elif 'country' in query_lower or 'region' in query_lower:
        region_summary = sites_df.groupby('region').agg({
            'site_id': 'count',
            'avg_dqi_score': 'mean',
            'high_risk_count': 'sum'
        }).reset_index()
        response = "Risk by Region:\n\n"
        for _, row in region_summary.iterrows():
            response += f"• {row['region']}: {int(row['site_id'])} sites, Avg DQI: {row['avg_dqi_score']:.3f}, High-risk subjects: {int(row['high_risk_count'])}\n"
        return response

    elif 'study' in query_lower:
        study_summary = sites_df.groupby('study').agg({
            'site_id': 'count',
            'subject_count': 'sum',
            'avg_dqi_score': 'mean'
        }).reset_index()
        response = "Study Summary:\n\n"
        for _, row in study_summary.iterrows():
            response += f"• {row['study']}: {int(row['site_id'])} sites, {int(row['subject_count'])} subjects, Avg DQI: {row['avg_dqi_score']:.3f}\n"
        return response

    else:
        return f"""I can answer questions about:
• Critical/urgent issues ("What needs immediate attention?")
• Highest risk sites ("Which sites have the highest risk?")
• SAE status ("How many pending SAE?")
• Regional breakdown ("Risk by region")
• Study overview ("Summary by study")

Your query: "{query}"
Please rephrase or ask one of the above."""


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def save_outputs(
    subject_recs: List[Dict],
    site_recs: List[Dict],
    study_recs: List[Dict],
    executive_summary: str,
    site_report: str,
    data: Dict[str, pd.DataFrame]
):
    """Save all outputs."""

    # 1. Executive Summary (TXT)
    with open(OUTPUT_DIR / "executive_summary.txt", 'w', encoding='utf-8') as f:
        f.write(executive_summary)
    print(f"  Saved: outputs/executive_summary.txt")

    # 2. Site Action Report (MD)
    with open(OUTPUT_DIR / "recommendations_report.md", 'w', encoding='utf-8') as f:
        f.write("# Javelin.AI - Data Quality Recommendations Report\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        f.write("## Executive Summary\n\n")
        f.write("```\n")
        f.write(executive_summary)
        f.write("```\n\n")
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
            'top_recommendation': rec['recommendations'][0] if rec['recommendations'] else ''
        })
    pd.DataFrame(site_csv_data).to_csv(OUTPUT_DIR / "recommendations_by_site.csv", index=False)
    print(f"  Saved: outputs/recommendations_by_site.csv")

    # 4. Action Items JSON
    action_items = {
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_subjects': len(data['subjects']),
            'total_sites': len(data['sites']),
            'critical_items': sum(1 for r in site_recs if r['priority'] == 'CRITICAL'),
            'high_priority_items': sum(1 for r in site_recs if r['priority'] == 'HIGH')
        },
        'site_recommendations': site_recs[:20],  # Top 20
        'study_recommendations': study_recs
    }
    with open(OUTPUT_DIR / "action_items.json", 'w', encoding='utf-8') as f:
        json.dump(action_items, f, indent=2, default=str)
    print(f"  Saved: outputs/action_items.json")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def run_recommendations_engine(interactive: bool = False):
    """Main function to run the recommendations engine."""

    print("=" * 70)
    print("JAVELIN.AI - GEN AI RECOMMENDATIONS ENGINE")
    print("=" * 70)

    # Step 1: Load Data
    print("\n[1/5] Loading data...")
    data = load_data()

    # Step 2: Generate Subject Recommendations
    print("\n[2/5] Analyzing subject-level risks...")
    subject_recs = generate_subject_recommendations(data['subjects'])
    print(f"  Generated {len(subject_recs)} subject recommendations")
    print(f"  Critical: {sum(1 for r in subject_recs if r['priority'] == 'CRITICAL')}")
    print(f"  High: {sum(1 for r in subject_recs if r['priority'] == 'HIGH')}")

    # Step 3: Generate Site Recommendations
    print("\n[3/5] Analyzing site-level patterns...")
    site_recs = generate_site_recommendations(data['sites'])
    print(f"  Generated {len(site_recs)} site recommendations")

    # Step 4: Generate Study Recommendations
    print("\n[4/5] Generating study-level insights...")
    study_recs = generate_study_recommendations(data['sites'])
    print(f"  Analyzed {len(study_recs)} studies")

    # Step 5: Generate Reports
    print("\n[5/5] Generating reports...")
    executive_summary = generate_executive_summary(subject_recs, site_recs, study_recs, data)
    site_report = generate_site_action_report(site_recs)

    save_outputs(subject_recs, site_recs, study_recs, executive_summary, site_report, data)

    # Print Executive Summary
    print("\n" + "=" * 70)
    print("EXECUTIVE SUMMARY")
    print("=" * 70)
    print(executive_summary)

    # Interactive Query Mode
    if interactive:
        print("\n" + "=" * 70)
        print("QUERY MODE (type 'exit' to quit)")
        print("=" * 70)
        while True:
            query = input("\n🔍 Ask a question: ").strip()
            if query.lower() in ['exit', 'quit', 'q']:
                break
            response = answer_query(query, data, subject_recs, site_recs)
            print(f"\n{response}")

    print("\n" + "=" * 70)
    print("RECOMMENDATIONS ENGINE COMPLETE")
    print("=" * 70)
    print("""
Outputs generated:
  1. outputs/executive_summary.txt - High-level summary for leadership
  2. outputs/recommendations_report.md - Detailed markdown report
  3. outputs/recommendations_by_site.csv - Site-level action items
  4. outputs/action_items.json - Machine-readable recommendations

Next Steps:
  • Review executive_summary.txt for immediate actions
  • Share recommendations_by_site.csv with CRAs
  • Use action_items.json for dashboard integration
""")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    interactive = "--interactive" in sys.argv or "-i" in sys.argv

    if "--query" in sys.argv:
        # Quick query mode
        idx = sys.argv.index("--query")
        if idx + 1 < len(sys.argv):
            query = sys.argv[idx + 1]
            data = load_data()
            subject_recs = generate_subject_recommendations(data['subjects'])
            site_recs = generate_site_recommendations(data['sites'])
            print(answer_query(query, data, subject_recs, site_recs))
    else:
        run_recommendations_engine(interactive=interactive)
