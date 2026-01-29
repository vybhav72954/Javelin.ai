"""
JAVELIN.AI - Clinical Trial Data Quality Dashboard
==============================================================

INSIGHT-DRIVEN dashboard using ALL 9 phases of pipeline output.

SCREENS:
    1. Command Center - Portfolio health overview
    2. Risk Landscape - Geographic and study analysis
    3. Patterns & Signals - Anomaly detection and clustering
    4. Root Causes - Why problems occur
    5. Action Center - Prioritized interventions
    6. Deep Dive - Study → Site → Subject drill-down

Reuses:
    - config.py: Paths, weights, thresholds
    - utils/: get_risk_distribution, calculate_risk_rates

Run:
    cd src
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import json
import ast
from typing import Dict, List, Tuple, Any
from datetime import datetime
import io
import textwrap

# =============================================================================
# REUSE EXISTING MODULES
# =============================================================================

try:
    from config import (
        PHASE_DIRS, OUTPUT_FILES, DQI_WEIGHTS, THRESHOLDS,
        RISK_COLORS, NUMERIC_ISSUE_COLUMNS, CLUSTERING_FEATURES
    )
    from utils import get_risk_distribution, calculate_risk_rates
except ImportError:
    # Fallback for standalone testing
    PHASE_DIRS = {'phase_03': Path('outputs/phase03')}
    DQI_WEIGHTS = {}
    THRESHOLDS = type('obj', (object,), {'HIGH_RISK_PERCENTILE': 0.9})()
    RISK_COLORS = {'High': '#ef4444', 'Medium': '#f59e0b', 'Low': '#10b981'}
    NUMERIC_ISSUE_COLUMNS = ['sae_pending_count', 'missing_visit_count', 'lab_issues_count']
    CLUSTERING_FEATURES = []
    def get_risk_distribution(df, col):
        if df.empty or col not in df.columns:
            return {'High': 0, 'Medium': 0, 'Low': 0}
        return df[col].value_counts().to_dict()
    def calculate_risk_rates(df, col):
        return {}

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="JAVELIN.AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =============================================================================
# ENHANCED CSS STYLING
# =============================================================================

st.markdown("""
<style>
    /* Base Layout */
    .main .block-container { padding: 1rem 2rem; max-width: 1800px; }
    #MainMenu, footer, header { visibility: hidden; }
    h1, h2, h3, h4, h5 { color: #ffffff !important; }
    
    /* Typography */
    .stMarkdown, .stText, p, span, div { font-size: 1.05rem; }
    
    /* Metric Cards - Enhanced */
    .metric-card {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    .metric-label { color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { color: #ffffff; font-size: 2.25rem; font-weight: 700; }
    .metric-delta { font-size: 0.85rem; margin-top: 0.25rem; }
    .metric-row { display: flex; justify-content: space-between; padding: 0.3rem 0; }
    .metric-context { color: #64748b; font-size: 0.8rem; margin-top: 0.35rem; }
    
    /* Alert Cards */
    .alert-card {
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid;
        transition: transform 0.15s ease;
    }
    .alert-card:hover { transform: translateX(4px); }
    .alert-critical { background: rgba(239,68,68,0.1); border-color: #ef4444; }
    .alert-warning { background: rgba(245,158,11,0.1); border-color: #f59e0b; }
    .alert-info { background: rgba(59,130,246,0.1); border-color: #3b82f6; }
    .alert-success { background: rgba(16,185,129,0.1); border-color: #10b981; }
    
    /* Insight Boxes */
    .insight-box {
        background: linear-gradient(135deg, rgba(59,130,246,0.15) 0%, rgba(6,182,212,0.1) 100%);
        border: 1px solid rgba(59,130,246,0.3);
        border-radius: 12px;
        padding: 1.25rem;
        margin: 1rem 0;
    }
    .insight-title { color: #60a5fa; font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem; }
    .insight-text { color: #e2e8f0; font-size: 1.05rem; line-height: 1.6; }
    
    /* Cards */
    .cluster-card, .site-card, .region-card {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        transition: all 0.2s ease;
    }
    .cluster-card:hover, .site-card:hover { border-color: #475569; }
    
    .anomaly-card {
        background: rgba(239,68,68,0.08);
        border: 1px solid rgba(239,68,68,0.3);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
    }
    
    .rc-card {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid;
    }
    
    .action-card {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid;
        transition: all 0.2s ease;
    }
    .action-card:hover { border-color: #475569; transform: translateX(2px); }
    
    /* Agent Insights */
    .agent-insight {
        background: linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(59,130,246,0.1) 100%);
        border: 1px solid rgba(139,92,246,0.3);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.75rem 0;
    }
    
    /* Deep Dive Cards */
    .profile-card {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .profile-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #334155;
    }
    .profile-title { color: #fff; font-size: 1.5rem; font-weight: 700; }
    .profile-subtitle { color: #94a3b8; font-size: 0.95rem; margin-top: 0.25rem; }
    
    /* Status Badges */
    .badge {
        padding: 0.35rem 0.85rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-critical { background: rgba(239,68,68,0.2); color: #ef4444; }
    .badge-high { background: rgba(249,115,22,0.2); color: #f97316; }
    .badge-medium { background: rgba(245,158,11,0.2); color: #f59e0b; }
    .badge-low { background: rgba(16,185,129,0.2); color: #10b981; }
    
    /* Navigation Enhancement */
    .nav-indicator {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }
    .nav-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #334155;
    }
    .nav-dot.active { background: #3b82f6; }
    
    /* Export Button */
    .export-btn {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        border: none;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .export-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(59,130,246,0.4); }
    
    /* Comparison View */
    .comparison-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1.5rem;
    }
    
    /* Stat Grid */
    .stat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 1rem;
    }
    .stat-item {
        background: rgba(0,0,0,0.2);
        padding: 0.75rem;
        border-radius: 8px;
        text-align: center;
    }
    .stat-value { color: #fff; font-size: 1.5rem; font-weight: 700; }
    .stat-label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }
    
    /* Progress Bar */
    .progress-bar {
        background: #1e293b;
        border-radius: 4px;
        height: 8px;
        overflow: hidden;
    }
    .progress-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.5s ease;
    }
    
    /* Align Download Button to the right */
    [data-testid="stDownloadButton"] {
        width: 100%;
    }
    [data-testid="stDownloadButton"] button {
        width: 100%;
        display: block;
        margin-left: auto;
    }
    
    /* Ensure the header aligns vertically with the button */
    .export-header {
        margin-bottom: 0 !important;
        display: flex;
        align-items: center;
        height: 100%;
    }
    
    /* Tabs Enhancement */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #1e293b;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        color: #94a3b8;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# DATA LOADING
# =============================================================================

def find_output_dir() -> Path:
    """Find outputs directory."""
    candidates = [
        PHASE_DIRS.get('phase_03', Path('outputs/phase03')).parent,
        Path("outputs"),
        Path(__file__).parent.parent / "outputs",
    ]
    for p in candidates:
        if (p / "phase03" / "master_subject_with_dqi.csv").exists():
            return p
    return candidates[0]


@st.cache_data(ttl=300)
def load_all_data() -> dict:
    """Load ALL phase outputs."""
    base = find_output_dir()
    data = {}

    def load_csv(phase, filename):
        path = base / phase / filename
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    def load_json(phase, filename):
        path = base / phase / filename
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}

    def load_text(phase, filename):
        path = base / phase / filename
        if path.exists():
            with open(path) as f:
                return f.read()
        return ""

    # Phase 03: Core DQI
    data['subjects'] = load_csv('phase03', 'master_subject_with_dqi.csv')
    data['sites'] = load_csv('phase03', 'master_site_with_dqi.csv')
    data['studies'] = load_csv('phase03', 'master_study_with_dqi.csv')
    data['countries'] = load_csv('phase03', 'master_country_with_dqi.csv')
    data['regions'] = load_csv('phase03', 'master_region_with_dqi.csv')

    # Phase 05: Recommendations
    data['recommendations'] = load_csv('phase05', 'recommendations_by_site.csv')
    data['action_items'] = load_json('phase05', 'action_items.json')
    data['executive_summary'] = load_text('phase05', 'executive_summary.txt')

    # Phase 06: Anomalies
    data['anomalies'] = load_csv('phase06', 'anomalies_detected.csv')
    data['anomaly_scores'] = load_csv('phase06', 'site_anomaly_scores.csv')
    data['anomaly_summary'] = load_json('phase06', 'anomaly_summary.json')

    # Phase 07: Multi-Agent
    data['agent_analysis'] = load_json('phase07', 'agent_analysis.json')
    data['multi_agent_recs'] = load_csv('phase07', 'multi_agent_recommendations.csv')

    # Phase 08: Clustering
    data['clusters'] = load_csv('phase08', 'site_clusters.csv')
    data['cluster_profiles'] = load_csv('phase08', 'cluster_profiles.csv')
    data['cluster_summary'] = load_json('phase08', 'cluster_summary.json')

    # Phase 09: Root Cause
    data['root_causes'] = load_csv('phase09', 'root_cause_analysis.csv')
    data['cooccurrence'] = load_csv('phase09', 'issue_cooccurrence.csv')
    data['contributing_factors'] = load_csv('phase09', 'contributing_factors.csv')
    data['geographic_patterns'] = load_csv('phase09', 'geographic_patterns.csv')
    data['root_cause_summary'] = load_json('phase09', 'root_cause_summary.json')

    return data

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_list(val) -> list:
    if isinstance(val, list): return val
    if pd.isna(val): return []
    try: return ast.literal_eval(str(val))
    except: return [str(val)] if val else []

def format_issue(col: str) -> str:
    return col.replace('_count', '').replace('_sum', '').replace('_', ' ').title()

def calc_health(subjects: pd.DataFrame) -> Tuple[int, str, str]:
    if subjects.empty: return 0, "UNKNOWN", "No data"
    dist = get_risk_distribution(subjects, 'risk_category')
    total = len(subjects)
    high = dist.get('High', 0)
    medium = dist.get('Medium', 0)
    weighted = (high * 1.0 + medium * 0.3) / total if total > 0 else 0
    score = int(100 * (1 - weighted))
    score = max(0, min(100, score))
    if score >= 85: return score, "HEALTHY", "Portfolio performing well"
    elif score >= 70: return score, "MODERATE", "Some areas need attention"
    elif score >= 50: return score, "AT RISK", "Significant issues detected"
    else: return score, "CRITICAL", "Urgent intervention required"

def get_risk_color(risk: str) -> str:
    colors = {'High': '#ef4444', 'Critical': '#ef4444', 'Medium': '#f59e0b', 'Low': '#10b981'}
    return colors.get(risk, '#6b7280')

def export_to_csv(df: pd.DataFrame, filename: str):
    """Create downloadable CSV."""
    return df.to_csv(index=False).encode('utf-8')


def render_export_header(title: str, df: pd.DataFrame, filename: str, key: str):
    """Renders a header and a download button side-by-side, perfectly aligned."""
    c1, c2 = st.columns([8, 1])
    with c1:
        st.markdown(f'<h5 class="export-header">{title}</h5>', unsafe_allow_html=True)
    with c2:
        if not df.empty:
            csv = export_to_csv(df, filename)
            st.download_button(
                label="📥 Export CSV",
                data=csv,
                file_name=filename,
                mime="text/csv",
                key=key
            )

# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_insight(title: str, text: str, icon: str = "💡"):
    import re
    html_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    html_code = (
        f'<div class="insight-box">'
        f'<div class="insight-title">{icon} {title}</div>'
        f'<div class="insight-text">{html_text}</div>'
        f'</div>'
    )
    st.markdown(html_code, unsafe_allow_html=True)


def render_agent_insight(agent: str, insight: str):
    import re
    html_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', insight)
    st.markdown(f"""
        <div class="agent-insight">
            <div style="color:#a78bfa;font-weight:600;font-size:0.9rem;margin-bottom:0.5rem">🤖 {agent}</div>
            <div style="color:#e2e8f0;font-size:0.95rem">{html_text}</div>
        </div>
    """, unsafe_allow_html=True)


def render_metric_card(icon: str, label: str, value, breakdown: dict = None, delta: str = None, context: str = None):
    """Render a metric card with optional breakdown, delta, and context."""
    rows_html = ""
    if breakdown:
        row_items = []
        colors = {'Critical':'#ef4444', 'High Risk':'#ef4444', 'High':'#ef4444',
                  'At Risk':'#f59e0b', 'Medium':'#f59e0b', 'Healthy':'#10b981', 'Low':'#10b981'}
        for k, v in breakdown.items():
            c = colors.get(k, '#94a3b8')
            row_items.append(
                f"<div class='metric-row'><span style='color:{c}'>{k}</span><span style='color:#fff;font-weight:600'>{v:,}</span></div>")
        rows_inner = "".join(row_items)
        rows_html = f"<div style='margin-top:0.75rem;padding-top:0.75rem;border-top:1px solid #334155'>{rows_inner}</div>"

    delta_html = ""
    if delta:
        delta_color = '#10b981' if delta.startswith('+') or delta.startswith('↑') else '#ef4444' if delta.startswith('-') or delta.startswith('↓') else '#94a3b8'
        delta_html = f"<div class='metric-delta' style='color:{delta_color}'>{delta}</div>"

    context_html = ""
    if context:
        context_html = f"<div class='metric-context'>{context}</div>"

    val_str = f"{value:,}" if isinstance(value, (int, float)) else str(value)

    html_code = (
        f'<div class="metric-card">'
        f'<div class="metric-label">{icon} {label}</div>'
        f'<div class="metric-value">{val_str}</div>'
        f'{delta_html}'
        f'{context_html}'
        f'{rows_html}'
        f'</div>'
    )
    st.markdown(html_code, unsafe_allow_html=True)


def render_gauge(score: int, status: str):
    colors = {'HEALTHY': '#10b981', 'MODERATE': '#f59e0b', 'AT RISK': '#f97316', 'CRITICAL': '#ef4444', 'UNKNOWN': '#6b7280'}
    color = colors.get(status, '#6b7280')
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={'font': {'size': 56, 'color': color, 'family': 'Arial Black'}},
        gauge={
            'axis': {'range': [0, 100], 'tickcolor': '#475569'},
            'bar': {'color': color, 'thickness': 0.8},
            'bgcolor': '#1e293b',
            'borderwidth': 2,
            'bordercolor': '#334155',
            'steps': [
                {'range': [0, 50], 'color': 'rgba(239,68,68,0.15)'},
                {'range': [50, 70], 'color': 'rgba(249,115,22,0.15)'},
                {'range': [70, 85], 'color': 'rgba(245,158,11,0.15)'},
                {'range': [85, 100], 'color': 'rgba(16,185,129,0.15)'}
            ],
        }
    ))
    fig.update_layout(height=240, margin=dict(l=20,r=20,t=40,b=20), paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#fff'))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(f"<div style='text-align:center;margin-top:-15px'><span style='background:{color}33;color:{color};padding:0.4rem 1.25rem;border-radius:20px;font-weight:700;font-size:0.9rem'>{status}</span></div>", unsafe_allow_html=True)


def render_site_profile_card(site_data: dict, show_actions: bool = True):
    risk = site_data.get('site_risk_category', site_data.get('risk_category', 'Unknown'))
    color = get_risk_color(risk)
    badge_type = 'critical' if risk=='High' else 'medium' if risk=='Medium' else 'low'

    html_code = (
        f'<div class="profile-card" style="border-left: 4px solid {color}">'
        f'<div class="profile-header">'
        f'<div>'
        f'<div class="profile-title">Site {site_data.get("site_id", "Unknown")}</div>'
        f'<div class="profile-subtitle">{site_data.get("study", "")} • {site_data.get("country", "")} ({site_data.get("region", "")})</div>'
        f'</div>'
        f'<span class="badge badge-{badge_type}">{risk} Risk</span>'
        f'</div>'
        f'<div class="stat-grid">'
        f'<div class="stat-item"><div class="stat-value">{site_data.get("subject_count", 0):,}</div><div class="stat-label">Subjects</div></div>'
        f'<div class="stat-item"><div class="stat-value">{site_data.get("avg_dqi_score", 0):.4f}</div><div class="stat-label">Avg DQI</div></div>'
        f'<div class="stat-item"><div class="stat-value">{site_data.get("high_risk_count", 0):,}</div><div class="stat-label">High Risk</div></div>'
        f'<div class="stat-item"><div class="stat-value">{int(site_data.get("sae_pending_count_sum", site_data.get("sae_pending_count", 0))):,}</div><div class="stat-label">SAE Pending</div></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html_code, unsafe_allow_html=True)


# =============================================================================
# PAGE 1: COMMAND CENTER
# =============================================================================

def page_command_center(data: dict):
    subjects, sites, studies = data['subjects'], data['sites'], data['studies']
    cluster_summary = data.get('cluster_summary', {})
    anomaly_summary = data.get('anomaly_summary', {})
    agent_analysis = data.get('agent_analysis', {})

    st.markdown("### 📊 Command Center")
    st.caption("Is my portfolio healthy? What needs my attention?")

    # Row 1: Gauge + Metrics
    c1, c2 = st.columns([1, 2])

    with c1:
        st.markdown("##### Portfolio Health Score")
        score, status, desc = calc_health(subjects)
        render_gauge(score, status)
        st.caption(f"_{desc}_")

    with c2:
        subj_dist = get_risk_distribution(subjects, 'risk_category') if not subjects.empty else {'High':0,'Medium':0,'Low':0}
        site_dist = get_risk_distribution(sites, 'site_risk_category') if not sites.empty and 'site_risk_category' in sites.columns else {'High':0,'Medium':0,'Low':0}

        study_dist = {'Critical': 0, 'At Risk': 0, 'Healthy': 0}
        if not studies.empty and 'high_risk_rate' in studies.columns:
            s = studies.copy()
            study_dist['Critical'] = len(s[s['high_risk_rate'] >= 0.20])
            study_dist['At Risk'] = len(s[(s['high_risk_rate'] >= 0.10) & (s['high_risk_rate'] < 0.20)])
            study_dist['Healthy'] = len(s[s['high_risk_rate'] < 0.10])

        mc = st.columns(3)
        with mc[0]: render_metric_card("📋", "Studies", len(studies), study_dist)
        with mc[1]: render_metric_card("🏥", "Sites", len(sites), {'High Risk': site_dist.get('High', 0), 'Medium': site_dist.get('Medium', 0), 'Low': site_dist.get('Low', 0)})
        with mc[2]: render_metric_card("👥", "Subjects", len(subjects), {'High Risk': subj_dist.get('High', 0), 'Medium': subj_dist.get('Medium', 0), 'Low': subj_dist.get('Low', 0)})

    st.markdown("---")

    # Alerts
    alerts = []
    if not subjects.empty and 'sae_pending_count' in subjects.columns:
        sae = int(subjects['sae_pending_count'].sum())
        if sae > 0:
            top = ', '.join(subjects.groupby('study')['sae_pending_count'].sum().nlargest(3).index.tolist()) if 'study' in subjects.columns else ""
            alerts.append(('critical', f'{sae:,} SAEs pending review', 'Regulatory compliance risk', f'Top studies: {top}' if top else ''))

    if not data['root_causes'].empty:
        for _, rc in data['root_causes'][data['root_causes']['severity'] == 'Critical'].head(2).iterrows():
            alerts.append(('critical', f"{rc['affected_sites']:,} sites: {rc['description'][:50]}...", f"Root cause: {rc['category']}", ''))

    if anomaly_summary.get('total_anomalies', 0) > 0:
        by_sev = anomaly_summary.get('by_severity', {})
        alerts.append(('warning', f"{anomaly_summary['total_anomalies']:,} anomalies detected",
                      f"{by_sev.get('critical', 0)} critical, {by_sev.get('high', 0)} high severity",
                      f"{anomaly_summary.get('sites_with_anomalies', 0)} sites affected"))

    if cluster_summary.get('cluster_summary'):
        critical_clusters = [c for c in cluster_summary['cluster_summary'] if c.get('risk_level') == 'Critical']
        if critical_clusters:
            total_crit = sum(c.get('sites', 0) for c in critical_clusters)
            alerts.append(('warning', f"{total_crit} sites in critical clusters",
                          f"{len(critical_clusters)} cluster groups need immediate attention", ''))

    if alerts:
        st.markdown("##### ⚠️ Critical Alerts")
        cols = st.columns(2)
        for i, (sev, title, sub, det) in enumerate(alerts[:6]):
            with cols[i % 2]:
                icons = {'critical': '🔴', 'warning': '🟠', 'info': '🔵'}
                det_html = f"<div style='color:#64748b;font-size:0.8rem;margin-top:0.25rem;font-style:italic'>{det}</div>" if det else ""
                alert_html = (
                    f'<div class="alert-card alert-{sev}">'
                    f'<div style="color:#fff;font-weight:600">{icons.get(sev, "⚪")} {title}</div>'
                    f'<div style="color:#94a3b8;font-size:0.85rem">{sub}</div>'
                    f'{det_html}'
                    f'</div>'
                )
                st.markdown(alert_html, unsafe_allow_html=True)

    st.markdown("---")

    # Chart + Issues
    c1, c2 = st.columns([1.5, 1])

    with c1:
        st.markdown("##### 📈 Studies by Risk")
        if not studies.empty and 'high_risk_rate' in studies.columns:
            df = studies.copy()
            df['hr_pct'] = df['high_risk_rate'] * 100
            df = df.nlargest(10, 'hr_pct').sort_values('hr_pct')

            if len(df) > 0:
                colors_list = ['#10b981' if x < 15 else '#f59e0b' if x < 25 else '#ef4444' for x in df['hr_pct']]
                fig = go.Figure(go.Bar(
                    y=df['study'], x=df['hr_pct'], orientation='h',
                    marker_color=colors_list,
                    text=[f"{v:.1f}%" for v in df['hr_pct']],
                    textposition='outside',
                    textfont=dict(color='#e2e8f0')
                ))
                fig.update_layout(
                    height=350, margin=dict(l=20,r=80,t=20,b=40),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e2e8f0'),
                    xaxis=dict(gridcolor='#334155', title='High-Risk Subjects (%)'),
                    yaxis=dict(gridcolor='#334155')
                )
                st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("##### 🔍 Top Issues")
        if not subjects.empty:
            issues = [(c, int(subjects[c].sum())) for c in NUMERIC_ISSUE_COLUMNS if c in subjects.columns and subjects[c].sum() > 0]
            issues.sort(key=lambda x: -x[1])
            for col, total in issues[:6]:
                color = '#ef4444' if 'sae' in col else '#f59e0b' if 'missing' in col else '#3b82f6'
                icon = '🔴' if 'sae' in col else '🟠' if 'missing' in col else '🔵'
                st.markdown(f"""
                    <div style="display:flex;justify-content:space-between;padding:0.75rem 1rem;background:linear-gradient(90deg,{color}15,transparent);border-left:3px solid {color};border-radius:0 8px 8px 0;margin-bottom:0.5rem">
                        <span style="color:#e2e8f0">{icon} {format_issue(col)}</span>
                        <span style="color:{color};font-weight:700">{total:,}</span>
                    </div>
                """, unsafe_allow_html=True)

    # AI Insights
    st.markdown("---")
    st.markdown("##### 💡 AI-Powered Insights")
    ic1, ic2 = st.columns(2)

    with ic1:
        if agent_analysis.get('portfolio_context'):
            ctx = agent_analysis['portfolio_context']
            high_risk_studies = [s for s, r in ctx.get('study_risks', {}).items() if r == 'High']
            render_agent_insight(
                "Multi-Agent Analysis",
                f"Portfolio average DQI: {ctx.get('portfolio_avg_dqi', 0):.4f}. "
                f"**{len(high_risk_studies)} studies** classified as high-risk by consensus."
            )

    with ic2:
        if cluster_summary.get('cluster_summary'):
            clusters = cluster_summary['cluster_summary']
            high_perf = next((c for c in clusters if c.get('name') == 'High Performers'), None)
            if high_perf:
                render_insight(
                    "Cluster Analysis",
                    f"**{high_perf.get('sites', 0)} sites ({high_perf.get('pct', 0)}%)** are high performers. "
                    f"These can serve as benchmarks for improvement."
                )


# =============================================================================
# PAGE 2: RISK LANDSCAPE
# =============================================================================

def page_risk_landscape(data: dict):
    countries, regions, studies, sites = data['countries'], data['regions'], data['studies'], data['sites']
    cluster_profiles = data.get('cluster_profiles', pd.DataFrame())
    cluster_summary = data.get('cluster_summary', {})
    agent_analysis = data.get('agent_analysis', {})

    st.markdown("### 🗺️ Risk Landscape")
    st.caption("Where are the problems concentrated?")

    tab1, tab2 = st.tabs(["🌍 Geographic", "📊 Studies"])

    # --- TAB 1: GEOGRAPHIC ---
    with tab1:
        c1, c2 = st.columns([2.2, 1])

        with c1:
            st.markdown("##### Global Risk Distribution")
            if not countries.empty and 'country' in countries.columns:
                df = countries.copy()
                fig = px.scatter_geo(
                    df, locations='country', locationmode='ISO-3',
                    size='site_count', color='avg_dqi_score',
                    hover_name='country',
                    hover_data={'site_count': True, 'avg_dqi_score': ':.4f'},
                    color_continuous_scale='RdYlGn_r',
                    size_max=40, projection='natural earth'
                )
                fig.update_layout(
                    geo=dict(showframe=False, showcoastlines=True, coastlinecolor='#475569',
                            landcolor='#1e293b', oceancolor='#0f172a', bgcolor='rgba(0,0,0,0)',
                            showland=True, showcountries=True, countrycolor='#334155'),
                    height=420, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)',
                    coloraxis_colorbar=dict(title=dict(text="DQI", font=dict(color="#e2e8f0")))
                )
                st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("##### Regional Summary")
            if not regions.empty and not sites.empty:
                avg = sites['avg_dqi_score'].mean() if 'avg_dqi_score' in sites.columns else 0
                for _, r in regions.sort_values('avg_dqi_score', ascending=False).iterrows():
                    pct = ((r['avg_dqi_score'] / avg) - 1) * 100 if avg > 0 else 0
                    delta_color = '#ef4444' if pct > 10 else '#10b981' if pct < -10 else '#94a3b8'
                    delta_text = f"↑{abs(pct):.0f}% above" if pct > 10 else f"↓{abs(pct):.0f}% below" if pct < -10 else "≈ avg"
                    st.markdown(f"""
                        <div class="region-card">
                            <div style="color:#fff;font-weight:600">{r['region']}</div>
                            <div style="color:#94a3b8;font-size:0.9rem">{r['site_count']:,} sites • DQI: {r['avg_dqi_score']:.4f}</div>
                            <div style="color:{delta_color};font-weight:600;margin-top:0.25rem">{delta_text}</div>
                        </div>
                    """, unsafe_allow_html=True)

        # Top countries table with export
        st.markdown("---")
        render_export_header("Top 10 Countries by Risk", countries, 'countries_risk.csv', 'dl_countries')

        if not countries.empty:
            df = countries.nlargest(10, 'avg_dqi_score')[['country', 'site_count', 'avg_dqi_score']].copy()
            df.columns = ['Country', 'Sites', 'Avg DQI']
            df['Avg DQI'] = df['Avg DQI'].round(4)
            st.dataframe(df, use_container_width=True, hide_index=True)

        # Geographic insight
        if not regions.empty and not sites.empty:
            worst = regions.loc[regions['avg_dqi_score'].idxmax()]
            avg = sites['avg_dqi_score'].mean() if 'avg_dqi_score' in sites.columns else 0
            pct = ((worst['avg_dqi_score'] / avg) - 1) * 100 if avg > 0 else 0
            if pct > 10:
                region_risks = agent_analysis.get('portfolio_context', {}).get('region_risks', {})
                risk_level = region_risks.get(worst['region'], 'Elevated')
                render_insight(
                    "Geographic Concentration",
                    f"**{worst['region']}** is {pct:.0f}% above portfolio average with {worst['site_count']:,} sites. "
                    f"Multi-agent consensus: **{risk_level}** risk. Consider region-specific training and dedicated monitors."
                )

    # --- TAB 2: STUDIES ---
    with tab2:
        st.markdown("##### Study Portfolio Overview")
        if not studies.empty and 'subject_count' in studies.columns:
            df = studies.copy()
            if 'high_risk_rate' in df.columns:
                df['color'] = df['high_risk_rate'].apply(lambda x: '#ef4444' if x >= 0.2 else '#f59e0b' if x >= 0.1 else '#10b981')
                df['risk_label'] = df['high_risk_rate'].apply(lambda x: 'High Risk' if x >= 0.2 else 'Medium Risk' if x >= 0.1 else 'Low Risk')
            else:
                df['color'] = '#3b82f6'
                df['risk_label'] = 'Unknown'

            fig = go.Figure(go.Treemap(
                labels=df['study'], parents=['']*len(df), values=df['subject_count'],
                marker=dict(colors=df['color'], line=dict(width=2, color='#0f172a')),
                textinfo='label+value', textfont=dict(size=14, color='white'),
                hovertemplate='<b>%{label}</b><br>Subjects: %{value:,}<extra></extra>'
            ))
            fig.update_layout(height=450, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

        # Study table with export
        render_export_header("Study Risk Ranking", studies, 'studies_risk.csv', 'dl_studies')

        if not studies.empty:
            df = studies.sort_values('avg_dqi_score', ascending=False)[['study', 'site_count', 'subject_count', 'avg_dqi_score']].head(15)
            df.columns = ['Study', 'Sites', 'Subjects', 'Avg DQI']
            df['Avg DQI'] = df['Avg DQI'].round(4)
            st.dataframe(df, use_container_width=True, hide_index=True)

        # Study insight
        if not studies.empty and 'high_risk_rate' in studies.columns:
            df = studies.copy()
            high_risk_studies = len(df[df['high_risk_rate'] >= 0.2])
            if high_risk_studies > 0:
                worst = df.loc[df['high_risk_rate'].idxmax()]
                study_risks = agent_analysis.get('portfolio_context', {}).get('study_risks', {})
                agent_high_risk_count = sum(1 for r in study_risks.values() if r == 'High')
                render_insight(
                    "Study Concentration",
                    f"**{high_risk_studies} studies** exceed 20% high-risk rate. **{worst['study']}** is highest at "
                    f"**{worst['high_risk_rate']*100:.1f}%** ({worst['site_count']} sites, {worst['subject_count']:,} subjects). "
                    f"Agent analysis confirms **{agent_high_risk_count} studies** as high-risk."
                )


# =============================================================================
# PAGE 3: PATTERNS & SIGNALS
# =============================================================================

def page_patterns_signals(data: dict):
    """Dedicated anomaly detection and pattern analysis page."""
    anomalies = data.get('anomalies', pd.DataFrame())
    anomaly_scores = data.get('anomaly_scores', pd.DataFrame())
    anomaly_summary = data.get('anomaly_summary', {})
    clusters = data.get('clusters', pd.DataFrame())
    cluster_profiles = data.get('cluster_profiles', pd.DataFrame())
    cluster_summary = data.get('cluster_summary', {})
    sites = data.get('sites', pd.DataFrame())

    st.markdown("### 🔬 Patterns & Signals")
    st.caption("Detecting unusual behavior and identifying site patterns")

    # Summary metrics
    cols = st.columns(4)
    with cols[0]:
        render_metric_card("🎯", "Total Anomalies", anomaly_summary.get('total_anomalies', 0))
    with cols[1]:
        render_metric_card("🏥", "Sites Affected", anomaly_summary.get('sites_with_anomalies', 0))
    with cols[2]:
        n_clusters = cluster_summary.get('n_clusters', len(cluster_profiles)) if cluster_profiles is not None else 0
        render_metric_card("📊", "Clusters", n_clusters)
    with cols[3]:
        crit = sum(1 for c in cluster_summary.get('cluster_summary', []) if c.get('risk_level')=='Critical')
        render_metric_card("⚠️", "Critical Clusters", crit)

    st.markdown("---")

    tab1, tab2 = st.tabs(["🎯 Anomaly Detection", "📊 Site Clustering"])

    # =========================================================================
    # TAB 1: ANOMALY DETECTION
    # =========================================================================
    with tab1:
        c1, c2 = st.columns([2, 1])

        with c1:
            st.markdown("##### Anomaly Score Distribution")
            df = anomaly_scores.copy()
            if not df.empty and 'avg_dqi_score' not in df.columns:
                if not sites.empty and 'site_id' in sites.columns:
                    site_metrics = sites[['site_id', 'avg_dqi_score']].drop_duplicates()
                    df = pd.merge(df, site_metrics, on='site_id', how='left')

            if not df.empty and 'avg_dqi_score' in df.columns and 'anomaly_score' in df.columns:
                fig = px.scatter(
                    df, x='avg_dqi_score', y='anomaly_score',
                    color='anomaly_score',
                    size='subject_count' if 'subject_count' in df.columns else None,
                    color_continuous_scale='Reds',
                    hover_data=['site_id', 'study'] if 'study' in df.columns else ['site_id'],
                    labels={'avg_dqi_score':'Average DQI Score', 'anomaly_score':'Anomaly Score'}
                )
                fig.update_layout(
                    height=400, margin=dict(l=40, r=20, t=20, b=40),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e2e8f0'),
                    xaxis=dict(gridcolor='#334155'), yaxis=dict(gridcolor='#334155')
                )
                threshold = df['anomaly_score'].quantile(0.9)
                fig.add_hline(y=threshold, line_dash="dash", line_color="#ef4444",
                              annotation_text="90th percentile", annotation_position="top right")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Anomaly vs DQI data not available (requires both scores).")

        with c2:
            st.markdown("##### Anomaly Types")
            by_type = anomaly_summary.get('by_type', {})
            if by_type:
                for atype, count in sorted(by_type.items(), key=lambda x:-x[1]):
                    pct = count / anomaly_summary.get('total_anomalies', 1) * 100
                    color = '#ef4444' if 'critical' in atype.lower() else '#f59e0b' if 'high' in atype.lower() else '#3b82f6'
                    st.markdown(f"""
                        <div style="margin-bottom:0.75rem">
                            <div style="display:flex;justify-content:space-between;margin-bottom:0.25rem">
                                <span style="color:#e2e8f0">{atype.replace('_', ' ').title()}</span>
                                <span style="color:{color};font-weight:600">{count:,}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width:{pct}%;background:{color}"></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("##### Severity Breakdown")
            by_sev = anomaly_summary.get('by_severity', {})
            if by_sev:
                for sev, count in sorted(by_sev.items(), key=lambda x:-x[1]):
                    color = '#ef4444' if sev=='critical' else '#f59e0b' if sev=='high' else '#3b82f6'
                    st.markdown(f"""
                        <div style="display:flex;justify-content:space-between;padding:0.5rem;background:{color}15;border-radius:8px;margin-bottom:0.5rem">
                            <span style="color:#e2e8f0">{sev.title()}</span>
                            <span style="color:#e2e8f0;font-weight:700">{count:,}</span>
                        </div>
                    """, unsafe_allow_html=True)

        # Top anomalous sites export
        st.markdown("---")
        render_export_header("Top Anomalous Sites", anomaly_scores, 'anomaly_scores.csv', 'dl_anomalies')

        if anomaly_summary.get('top_sites'):
            top_sites = anomaly_summary['top_sites'][:8]
            cols = st.columns(2)
            for i, site in enumerate(top_sites):
                with cols[i % 2]:
                    st.markdown(f"""
                        <div class="anomaly-card">
                            <div style="display:flex;justify-content:space-between;align-items:center">
                                <span style="color:#fff;font-weight:600">{site.get('site_id', 'Unknown')}</span>
                                <span style="color:#ef4444;font-weight:600">{site.get('critical_count', 0)} critical</span>
                            </div>
                            <div style="color:#94a3b8;font-size:0.9rem">{site.get('study', '')}</div>
                            <div style="color:#cbd5e1;font-size:0.85rem;margin-top:0.5rem">{str(site.get('top_anomalies', ''))[:150]}...</div>
                        </div>
                    """, unsafe_allow_html=True)

        # Insight
        if anomaly_summary.get('total_anomalies', 0) > 0:
            render_insight(
                "Anomaly Pattern Analysis",
                f"**{anomaly_summary.get('sites_with_anomalies', 0)} sites** exhibit anomalous behavior patterns. "
                f"Sites in the upper-right quadrant of the scatter plot have both high DQI scores AND unusual patterns - "
                f"these are the highest priority for investigation."
            )

    # =========================================================================
    # TAB 2: SITE CLUSTERING
    # =========================================================================
    with tab2:
        if cluster_profiles.empty:
            st.warning("Cluster data not available. Run Phase 08 (Site Clustering).")
            return

        c1, c2 = st.columns([1.5, 1])

        with c1:
            st.markdown("##### Site Cluster Distribution")
            if 'cluster_name' in cluster_profiles.columns:
                cluster_grouped = cluster_profiles.groupby('cluster_name').agg({
                    'site_count':'sum',
                    'pct_of_total':'sum',
                    'risk_level':'first',
                    'avg_dqi_score':'mean'
                }).reset_index().sort_values('site_count', ascending=True)

                colors_map = {'Critical':'#ef4444', 'High':'#f59e0b', 'Low':'#10b981'}
                bar_colors = [colors_map.get(r, '#3b82f6') for r in cluster_grouped['risk_level']]

                fig = go.Figure(go.Bar(
                    y=cluster_grouped['cluster_name'], x=cluster_grouped['site_count'], orientation='h',
                    marker_color=bar_colors,
                    text=[f"{s:,} ({p:.0f}%)" for s, p in
                          zip(cluster_grouped['site_count'], cluster_grouped['pct_of_total'])],
                    textposition='outside', textfont=dict(color='#e2e8f0')
                ))
                fig.update_layout(
                    height=350, margin=dict(l=20, r=100, t=20, b=40),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e2e8f0'),
                    xaxis=dict(gridcolor='#334155', title='Number of Sites'),
                    yaxis=dict(gridcolor='#334155')
                )
                st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("##### Cluster Profiles")
            colors_map = {'Critical':'#ef4444', 'High':'#f59e0b', 'Low':'#10b981'}
            for _, row in cluster_profiles.sort_values(
                    'intervention_priority' if 'intervention_priority' in cluster_profiles.columns else 'avg_dqi_score',
                    ascending=True).head(5).iterrows():
                color = colors_map.get(row.get('risk_level', ''), '#3b82f6')
                issues = parse_list(row.get('dominant_issues', []))[:2]
                issues_str = ', '.join([str(i).split('(')[0].strip() for i in issues]) if issues else 'None'
                st.markdown(f"""
                    <div class="cluster-card" style="border-left:4px solid {color}">
                        <div style="display:flex;justify-content:space-between">
                            <span style="color:#fff;font-weight:600">{row.get('cluster_name', 'Unknown')}</span>
                            <span style="background:{color}33;color:{color};padding:0.2rem 0.5rem;border-radius:10px;font-size:0.8rem">{row.get('risk_level', '')}</span>
                        </div>
                        <div style="color:#94a3b8;font-size:0.85rem;margin-top:0.25rem">{row.get('site_count', 0)} sites • DQI: {row.get('avg_dqi_score', 0):.4f}</div>
                        <div style="color:#64748b;font-size:0.8rem;margin-top:0.25rem">Issues: {issues_str}</div>
                    </div>
                """, unsafe_allow_html=True)

        # Cluster comparison
        st.markdown("---")
        render_export_header("Cluster Comparison", cluster_profiles, 'cluster_profiles.csv', 'dl_clusters')

        if not cluster_profiles.empty:
            display_cols = ['cluster_name', 'site_count', 'pct_of_total', 'avg_dqi_score', 'risk_level']
            display_cols = [c for c in display_cols if c in cluster_profiles.columns]
            df = cluster_profiles[display_cols].copy()
            if 'avg_dqi_score' in df.columns:
                df['avg_dqi_score'] = df['avg_dqi_score'].round(4)
            st.dataframe(df, use_container_width=True, hide_index=True)

        # Insight
        if cluster_summary.get('metrics'):
            metrics = cluster_summary['metrics']
            crit_clusters = [c for c in cluster_summary.get('cluster_summary', []) if c.get('risk_level') == 'Critical']
            render_insight(
                "Clustering Insight",
                f"GMM clustering identified **{cluster_summary.get('n_clusters', 0)} distinct site groups** "
                f"(silhouette score: {metrics.get('silhouette_score', 0):.3f}). "
                f"**{len(crit_clusters)} clusters** ({sum(c.get('sites', 0) for c in crit_clusters)} sites) are critical priority. "
                f"Sites in 'High Performers' cluster can serve as benchmarks for struggling sites."
            )


# =============================================================================
# PAGE 4: ROOT CAUSES
# =============================================================================

def page_root_causes(data: dict):
    root_causes = data.get('root_causes', pd.DataFrame())
    cooccurrence = data.get('cooccurrence', pd.DataFrame())
    contributing_factors = data.get('contributing_factors', pd.DataFrame())
    subjects = data.get('subjects', pd.DataFrame())

    st.markdown("### 🔍 Root Cause Analysis")
    st.caption("Understanding why problems occur, not just where")

    if root_causes.empty:
        st.warning("No root cause data. Run Phase 09.")
        return

    # Impact metrics
    total_sites = int(root_causes['affected_sites'].sum())
    total_subj = int(root_causes['affected_subjects'].sum())
    high_risk = len(subjects[subjects['risk_category'] == 'High']) if not subjects.empty and 'risk_category' in subjects.columns else 0
    reduction = int(high_risk * 0.47)

    cols = st.columns(4)
    metrics_data = [
        ("Root Causes", len(root_causes), "#3b82f6"),
        ("Sites Affected", total_sites, "#f59e0b"),
        ("Subjects Impacted", total_subj, "#ef4444"),
        ("Potential Reduction", f"-{reduction:,}", "#10b981")
    ]
    for col, (label, val, color) in zip(cols, metrics_data):
        with col:
            st.markdown(f"""
                <div class="metric-card" style="text-align:center">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value" style="color:{color}">{val if isinstance(val, str) else f'{val:,}'}</div>
                </div>
            """, unsafe_allow_html=True)

    render_insight(
        "Projected Impact",
        f"Addressing all {len(root_causes)} root causes could reduce high-risk subjects by ~**47%** "
        f"({high_risk:,} → {high_risk-reduction:,})."
    )

    st.markdown("---")
    render_export_header("Identified Root Causes", root_causes, 'root_causes.csv', 'dl_root_causes')

    severity_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
    for _, rc in root_causes.sort_values(by='severity', key=lambda x: x.map(severity_order)).iterrows():
        sev = rc['severity']
        color = '#ef4444' if sev == 'Critical' else '#f59e0b' if sev == 'High' else '#3b82f6'

        evidence = parse_list(rc.get('evidence', []))
        evidence_html = "".join([f"<div style='color:#cbd5e1;padding:0.2rem 0'>• {e}</div>" for e in evidence[:3]])

        st.markdown(f"""
            <div class="rc-card" style="border-left-color:{color}">
                <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div>
                        <div style="color:#94a3b8;font-size:0.85rem;text-transform:uppercase">{rc['category']}</div>
                        <div style="color:#fff;font-size:1.1rem;font-weight:600;margin:0.25rem 0">{rc['description']}</div>
                    </div>
                    <span style="background:{color}33;color:{color};padding:0.3rem 0.75rem;border-radius:12px;font-size:0.85rem;font-weight:600">{sev}</span>
                </div>
                <div style="display:flex;gap:2rem;margin:0.75rem 0;padding:0.5rem;background:rgba(0,0,0,0.2);border-radius:8px">
                    <div><div style="color:#94a3b8;font-size:0.8rem">Confidence</div><div style="color:#fff;font-size:1.1rem;font-weight:700">{int(rc['confidence']*100)}%</div></div>
                    <div><div style="color:#94a3b8;font-size:0.8rem">Sites</div><div style="color:#fff;font-size:1.1rem;font-weight:700">{rc['affected_sites']:,}</div></div>
                    <div><div style="color:#94a3b8;font-size:0.8rem">Subjects</div><div style="color:#fff;font-size:1.1rem;font-weight:700">{rc['affected_subjects']:,}</div></div>
                </div>
                {f"<div style='margin-top:0.5rem'><div style='color:#94a3b8;font-size:0.85rem;margin-bottom:0.25rem'>Evidence:</div>{evidence_html}</div>" if evidence_html else ""}
            </div>
        """, unsafe_allow_html=True)

        # Recommended actions with impact numbers
        actions = parse_list(rc.get('recommended_actions', []))
        if actions:
            subj = rc['affected_subjects']
            impact_text = f" → ~{int(subj/len(actions)):,} subjects per action" if subj > 0 and len(actions) > 0 else ""
            with st.expander(f"📋 {len(actions)} Recommended Actions{impact_text}"):
                for i, a in enumerate(actions, 1):
                    st.markdown(f"**{i}.** {a}")

    # Co-occurrence heatmap
    st.markdown("---")
    st.markdown("##### Issue Co-occurrence Patterns")
    c1, c2 = st.columns([1.5, 1])

    with c1:
        if not cooccurrence.empty:
            df = cooccurrence.copy()
            first_col = df.columns[0]
            if df[first_col].dtype == 'object':
                labels = [format_issue(str(l)) for l in df[first_col].tolist()]
                matrix = df.iloc[:, 1:].values.astype(float)
            else:
                labels = [format_issue(str(c)) for c in df.columns]
                matrix = df.values.astype(float)

            n = min(len(labels), matrix.shape[0], matrix.shape[1] if len(matrix.shape) > 1 else 10)
            labels, matrix = labels[:n], matrix[:n, :n]

            fig = go.Figure(go.Heatmap(
                z=matrix, x=labels, y=labels,
                colorscale=[[0,'#0f172a'],[0.3,'#3b82f6'],[0.6,'#8b5cf6'],[1,'#ef4444']],
                hovertemplate='%{y} + %{x}<br>Correlation: %{z:.2f}<extra></extra>'
            ))
            fig.update_layout(
                height=400, margin=dict(l=120,r=20,t=20,b=150),
                paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#e2e8f0', size=10),
                xaxis=dict(tickangle=90)
            )
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("""
            <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1rem">
                <h5 style="color:#fff;margin-bottom:0.5rem">Reading the Heatmap</h5>
                <p style="color:#cbd5e1;font-size:0.85rem;margin-bottom:0.4rem"><span style="color:#ef4444">■</span> Red = Strong correlation</p>
                <p style="color:#cbd5e1;font-size:0.85rem;margin-bottom:0.4rem"><span style="color:#8b5cf6">■</span> Purple = Moderate</p>
                <p style="color:#cbd5e1;font-size:0.85rem"><span style="color:#3b82f6">■</span> Blue = Weak</p>
                <hr style="border-color:#334155;margin:0.75rem 0">
                <p style="color:#94a3b8;font-size:0.8rem">Correlated issues often share root causes. Fixing one may resolve the other.</p>
            </div>
        """, unsafe_allow_html=True)

    # Co-occurrence insight
    if not cooccurrence.empty:
        df = cooccurrence.copy()
        first_col = df.columns[0]
        if df[first_col].dtype == 'object':
            labels = df[first_col].tolist()
            matrix = df.iloc[:, 1:].values.astype(float)
        else:
            labels = list(df.columns)
            matrix = df.values.astype(float)

        # Find max off-diagonal correlation
        np.fill_diagonal(matrix, 0)
        if matrix.size > 0:
            max_idx = np.unravel_index(np.argmax(matrix), matrix.shape)
            max_corr = matrix[max_idx]
            if max_corr > 0.3 and max_idx[0] < len(labels) and max_idx[1] < len(labels):
                issue1 = format_issue(str(labels[max_idx[0]]))
                issue2 = format_issue(str(labels[max_idx[1]]))
                render_insight(
                    "Co-occurrence Pattern",
                    f"**{issue1}** and **{issue2}** have the strongest correlation ({max_corr:.2f}). "
                    f"Sites with one issue are likely to have the other. Addressing the shared root cause "
                    f"could resolve both problems simultaneously."
                )


# =============================================================================
# PAGE 5: ACTION CENTER
# =============================================================================

def page_action_center(data: dict):
    root_causes = data.get('root_causes', pd.DataFrame())
    recommendations = data.get('recommendations', pd.DataFrame())
    multi_agent_recs = data.get('multi_agent_recs', pd.DataFrame())
    subjects = data.get('subjects', pd.DataFrame())
    anomaly_summary = data.get('anomaly_summary', {})

    st.markdown("### ⚡ Action Center")
    st.caption("Prioritized interventions ranked by impact")

    # Impact projection
    if not subjects.empty and 'risk_category' in subjects.columns:
        high = len(subjects[subjects['risk_category'] == 'High'])
        med = len(subjects[subjects['risk_category'] == 'Medium'])
        total = len(subjects)

        curr_health = int(100 * (1 - (high * 1.0 + med * 0.3) / total)) if total > 0 else 0
        proj_high = int(high * 0.66)
        proj_health = int(100 * (1 - (proj_high * 1.0 + med * 0.3) / total)) if total > 0 else 0

        cols = st.columns(3)
        impact_data = [
            ("High-Risk Subjects", f"{high:,} → {proj_high:,}", f"-{high-proj_high:,} subjects"),
            ("Portfolio Health", f"{curr_health} → {proj_health}", f"+{proj_health-curr_health} points"),
            ("Risk Reduction", f"-{int((high-proj_high)/high*100) if high > 0 else 0}%", "if actions completed")
        ]
        for col, (label, main, sub) in zip(cols, impact_data):
            with col:
                st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#059669 0%,#047857 100%);border-radius:12px;padding:1.25rem;text-align:center">
                        <div style="color:rgba(255,255,255,0.8);font-size:0.85rem;text-transform:uppercase">{label}</div>
                        <div style="color:#fff;font-size:1.5rem;font-weight:700;margin:0.5rem 0">{main}</div>
                        <div style="color:#a7f3d0;font-size:0.9rem">{sub}</div>
                    </div>
                """, unsafe_allow_html=True)

    # =========================================================================
    # BUILD ACTIONS FROM ALL SOURCES (FIXED - matching original 59)
    # =========================================================================
    actions = []
    action_items = data.get('action_items', {})

    # From site recommendations (ALL)
    for rec in action_items.get('site_recommendations', []):
        urgency = 'immediate' if rec.get('priority') == 'CRITICAL' else 'week' if rec.get('priority') == 'HIGH' else 'month'
        actions.append({
            'title': f"Site {rec.get('site_id', '?')} ({rec.get('study', '')}): {rec.get('site_risk_category', '')} Risk",
            'type': 'Site Action', 'urgency': urgency, 'sites': 1,
            'subjects': rec.get('subject_count', 0),
            'steps': rec.get('recommendations', [])[:3], 'source': 'Phase 05 Engine'
        })

    # From study recommendations (ALL)
    for rec in action_items.get('study_recommendations', []):
        urgency = 'immediate' if rec.get('priority') == 'CRITICAL' else 'week' if rec.get('priority') == 'HIGH' else 'month'
        actions.append({
            'title': f"{rec.get('study', '?')}: {rec.get('total_issues', 0)} issues across {rec.get('site_count', 0)} sites",
            'type': 'Study Action', 'urgency': urgency,
            'sites': rec.get('site_count', 0), 'subjects': rec.get('subject_count', 0),
            'steps': rec.get('recommendations', [])[:3], 'source': 'Phase 05 Engine'
        })

    # From country recommendations (top 10)
    for rec in action_items.get('country_recommendations', [])[:10]:
        urgency = 'week' if rec.get('priority') in ['CRITICAL', 'HIGH'] else 'month'
        actions.append({
            'title': f"Country {rec.get('country', '?')}: {rec.get('site_count', 0)} sites need attention",
            'type': 'Country Action', 'urgency': urgency,
            'sites': rec.get('site_count', 0), 'subjects': rec.get('subject_count', 0),
            'steps': rec.get('recommendations', [])[:2], 'source': 'Phase 05 Engine'
        })

    # From root causes (Phase 09)
    if not root_causes.empty:
        for _, rc in root_causes.iterrows():
            sev = rc['severity']
            urgency = 'immediate' if sev == 'Critical' else 'week' if sev == 'High' else 'month'
            actions.append({
                'title': f"ROOT CAUSE: {rc['description'][:60]}",
                'type': rc['category'], 'urgency': urgency,
                'sites': rc['affected_sites'], 'subjects': rc['affected_subjects'],
                'steps': parse_list(rc.get('recommended_actions', []))[:3],
                'source': 'Root Cause Analysis'
            })

    # From multi-agent recommendations (Phase 07)
    if not multi_agent_recs.empty:
        for _, rec in multi_agent_recs.iterrows():
            steps = parse_list(rec.get('recommended_actions', []))[:3]
            actions.append({
                'title': f"AI CONSENSUS: Site {rec.get('site_id', '?')} - {rec.get('risk_category', '')}",
                'type': 'Multi-Agent', 'urgency': 'immediate' if rec.get('escalation_required') else 'week',
                'sites': 1, 'subjects': 0,
                'steps': steps, 'source': 'AI Agents'
            })

    immediate = [a for a in actions if a['urgency'] == 'immediate']
    week = [a for a in actions if a['urgency'] == 'week']
    month = [a for a in actions if a['urgency'] == 'month']

    def render_action(a, urgency_class):
        steps_html = ""
        if a['steps']:
            steps_html = "<div style='margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid #334155'>"
            for s in a['steps'][:3]:
                steps_html += f"<div style='color:#cbd5e1;font-size:0.9rem;padding:0.2rem 0;padding-left:1rem'>→ {s}</div>"
            steps_html += "</div>"

        color = '#ef4444' if urgency_class == 'immediate' else '#f59e0b' if urgency_class == 'week' else '#3b82f6'
        st.markdown(f"""
            <div class="action-card" style="border-left-color:{color}">
                <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div style="color:#fff;font-weight:600;flex:1">{a['title']}</div>
                    <span style="color:#64748b;font-size:0.8rem;margin-left:0.5rem">{a['source']}</span>
                </div>
                <div style="color:#94a3b8;font-size:0.9rem;margin-top:0.25rem">
                    📁 {a['type']} • 🏥 {a['sites']:,} sites{f" • 👥 {a['subjects']:,} subjects" if a['subjects'] > 0 else ""}
                </div>
                {steps_html}
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Immediate actions
    if immediate:
        st.markdown(f"""
            <div style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);padding:0.75rem 1rem;border-radius:8px;margin-bottom:0.75rem">
                <span style="color:#fff;font-weight:600">🔴 IMMEDIATE ({len(immediate)} actions)</span>
            </div>
        """, unsafe_allow_html=True)
        for a in immediate[:6]:
            render_action(a, 'immediate')

    # This week
    if week:
        st.markdown(f"""
            <div style="background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.3);padding:0.75rem 1rem;border-radius:8px;margin:1rem 0 0.75rem 0">
                <span style="color:#fff;font-weight:600">🟠 THIS WEEK ({len(week)} actions)</span>
            </div>
        """, unsafe_allow_html=True)
        for a in week[:4]:
            render_action(a, 'week')

    # Action Summary with context verbiage
    st.markdown("---")
    st.markdown("##### 📋 Action Summary")

    total_sites_affected = sum(a['sites'] for a in actions)
    total_subjects_affected = sum(a['subjects'] for a in actions)

    cols = st.columns(4)
    summaries = [
        ("Total Actions", len(actions), "#3b82f6", f"Across {total_sites_affected:,} sites"),
        ("Immediate", len(immediate), "#ef4444", "Do today" if immediate else "None pending"),
        ("This Week", len(week), "#f59e0b", f"{sum(a['sites'] for a in week):,} sites" if week else "None pending"),
        ("This Month", len(month), "#10b981", "Lower priority" if month else "None scheduled")
    ]
    for col, (label, val, color, context) in zip(cols, summaries):
        with col:
            st.markdown(f"""
                <div class="metric-card" style="text-align:center">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value" style="color:{color}">{val}</div>
                    <div class="metric-context">{context}</div>
                </div>
            """, unsafe_allow_html=True)


# =============================================================================
# PAGE 6: DEEP DIVE (ENHANCED)
# =============================================================================

def page_deep_dive(data: dict):
    """Study → Site → Subject drill-down page."""
    subjects = data.get('subjects', pd.DataFrame())
    sites = data.get('sites', pd.DataFrame())
    studies = data.get('studies', pd.DataFrame())
    recommendations = data.get('recommendations', pd.DataFrame())
    clusters = data.get('clusters', pd.DataFrame())
    agent_analysis = data.get('agent_analysis', {})

    st.markdown("### 🔎 Deep Dive")
    st.caption("Study → Site → Subject exploration")

    if subjects.empty:
        st.warning("No data available for deep dive.")
        return

    # Selection controls
    col1, col2, col3 = st.columns(3)

    with col1:
        study_list = ['All Studies'] + sorted(subjects['study'].unique().tolist()) if 'study' in subjects.columns else ['All Studies']
        selected_study = st.selectbox("Select Study", study_list, key="dd_study")

    # Filter sites based on study
    filtered_sites = sites.copy()
    filtered_subjects = subjects.copy()
    if selected_study != 'All Studies':
        if 'study' in sites.columns:
            filtered_sites = sites[sites['study'] == selected_study]
        if 'study' in subjects.columns:
            filtered_subjects = subjects[subjects['study'] == selected_study]

    with col2:
        site_list = ['All Sites'] + sorted(filtered_sites['site_id'].unique().tolist()) if 'site_id' in filtered_sites.columns and not filtered_sites.empty else ['All Sites']
        selected_site = st.selectbox("Select Site", site_list, key="dd_site")

    with col3:
        risk_filter = st.multiselect("Risk Category", ['High', 'Medium', 'Low'], default=['High', 'Medium', 'Low'], key="dd_risk")

    # Apply filters
    if selected_site != 'All Sites' and 'site_id' in filtered_subjects.columns:
        filtered_subjects = filtered_subjects[filtered_subjects['site_id'] == selected_site]
    if risk_filter and 'risk_category' in filtered_subjects.columns:
        filtered_subjects = filtered_subjects[filtered_subjects['risk_category'].isin(risk_filter)]

    st.markdown("---")

    # Study Overview (if specific study selected)
    if selected_study != 'All Studies' and not studies.empty:
        study_data = studies[studies['study'] == selected_study].iloc[0] if len(studies[studies['study'] == selected_study]) > 0 else None
        if study_data is not None:
            st.markdown("##### 📋 Study Overview")
            cols = st.columns(5)
            with cols[0]:
                render_metric_card("🏥", "Sites", int(study_data.get('site_count', 0)))
            with cols[1]:
                render_metric_card("👥", "Subjects", int(study_data.get('subject_count', 0)))
            with cols[2]:
                render_metric_card("📊", "Avg DQI", f"{study_data.get('avg_dqi_score', 0):.4f}")
            with cols[3]:
                hr_rate = study_data.get('high_risk_rate', 0) * 100
                render_metric_card("⚠️", "High-Risk %", f"{hr_rate:.1f}%")
            with cols[4]:
                risk = study_data.get('study_risk_category', 'Unknown')
                color = get_risk_color(risk)
                st.markdown(f"""
                    <div class="metric-card" style="text-align:center">
                        <div class="metric-label">Risk Level</div>
                        <div class="metric-value" style="color:{color};font-size:1.5rem">{risk}</div>
                    </div>
                """, unsafe_allow_html=True)

            # Study-specific insight
            study_risks = agent_analysis.get('portfolio_context', {}).get('study_risks', {})
            agent_risk = study_risks.get(selected_study, 'Unknown')
            if hr_rate > 15:
                render_insight(
                    "Study Analysis",
                    f"**{selected_study}** has a **{hr_rate:.1f}%** high-risk rate across {int(study_data.get('site_count', 0))} sites. "
                    f"Multi-agent consensus: **{agent_risk}** risk. Focus on sites with highest DQI scores for maximum impact."
                )
            st.markdown("---")

    # Site Profile (if specific site selected)
    if selected_site != 'All Sites' and not sites.empty:
        site_data = filtered_sites[filtered_sites['site_id'] == selected_site]
        if not site_data.empty:
            site_row = site_data.iloc[0].to_dict()
            st.markdown("##### 🏥 Site Profile")
            render_site_profile_card(site_row)

            # Site-specific insight
            risk = site_row.get('site_risk_category', site_row.get('risk_category', 'Unknown'))
            dqi = site_row.get('avg_dqi_score', 0)
            subj_count = site_row.get('subject_count', 0)
            high_risk_count = site_row.get('high_risk_count', 0)

            if risk == 'High' or dqi > 0.1:
                render_insight(
                    "Site Analysis",
                    f"**Site {selected_site}** is classified as **{risk}** risk with DQI score {dqi:.4f}. "
                    f"**{high_risk_count}** of {subj_count} subjects ({int(high_risk_count/subj_count*100) if subj_count > 0 else 0}%) are high-risk. "
                    f"Review pending SAEs and missing visits as priority actions."
                )

            # Site recommendations
            if not recommendations.empty and 'site_id' in recommendations.columns:
                site_recs = recommendations[recommendations['site_id'] == selected_site]
                if not site_recs.empty:
                    with st.expander("📋 Site Recommendations", expanded=True):
                        for _, rec in site_recs.iterrows():
                            recs = parse_list(rec.get('recommendations', []))
                            for r in recs[:5]:
                                st.markdown(f"• {r}")

            st.markdown("---")

    # Subject Data Table
    st.markdown("##### 👥 Subject Data")
    render_export_header(f"Subject Data ({len(filtered_subjects):,} subjects)", filtered_subjects,
                         'subjects_export.csv', 'dl_subjects')

    # Display columns
    display_cols = ['subject_id', 'site_id', 'study', 'country', 'risk_category', 'dqi_score',
                   'sae_pending_count', 'missing_visit_count', 'lab_issues_count']
    display_cols = [c for c in display_cols if c in filtered_subjects.columns]

    if not filtered_subjects.empty:
        df_display = filtered_subjects[display_cols].copy()
        if 'dqi_score' in df_display.columns:
            df_display['dqi_score'] = df_display['dqi_score'].round(4)

        st.dataframe(
            df_display.head(100),
            use_container_width=True,
            hide_index=True,
            column_config={
                "risk_category": st.column_config.TextColumn("Risk", width="small"),
                "dqi_score": st.column_config.NumberColumn("DQI Score", format="%.4f"),
            }
        )

        if len(filtered_subjects) > 100:
            st.caption(f"Showing first 100 of {len(filtered_subjects):,} subjects. Export for full data.")

    # =========================================================================
    # ENHANCED VISUALIZATIONS (NEW)
    # =========================================================================
    if not filtered_subjects.empty and 'risk_category' in filtered_subjects.columns:
        st.markdown("---")
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("##### Risk Distribution")
            risk_counts = filtered_subjects['risk_category'].value_counts()
            fig = go.Figure(go.Pie(
                labels=risk_counts.index,
                values=risk_counts.values,
                marker_colors=[get_risk_color(r) for r in risk_counts.index],
                hole=0.4
            ))
            fig.update_layout(
                height=300, margin=dict(l=20,r=20,t=20,b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#e2e8f0'),
                showlegend=True,
                legend=dict(orientation='h', y=-0.1)
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("##### DQI Score Distribution")
            if 'dqi_score' in filtered_subjects.columns:
                fig = go.Figure(go.Histogram(
                    x=filtered_subjects['dqi_score'],
                    nbinsx=30,
                    marker_color='#3b82f6'
                ))
                fig.update_layout(
                    height=300, margin=dict(l=40,r=20,t=20,b=40),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e2e8f0'),
                    xaxis=dict(gridcolor='#334155', title='DQI Score'),
                    yaxis=dict(gridcolor='#334155', title='Count')
                )
                st.plotly_chart(fig, use_container_width=True)

        # Additional visualizations row
        st.markdown("---")
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("##### Top Issues Breakdown")
            issue_cols = ['sae_pending_count', 'missing_visit_count', 'lab_issues_count',
                         'missing_pages_count', 'uncoded_meddra_count', 'edrr_open_issues']
            issue_cols = [c for c in issue_cols if c in filtered_subjects.columns]
            if issue_cols:
                issue_totals = {format_issue(c): int(filtered_subjects[c].sum()) for c in issue_cols}
                issue_totals = {k: v for k, v in sorted(issue_totals.items(), key=lambda x: -x[1]) if v > 0}
                if issue_totals:
                    fig = go.Figure(go.Bar(
                        x=list(issue_totals.values())[:8],
                        y=list(issue_totals.keys())[:8],
                        orientation='h',
                        marker_color=['#ef4444' if 'Sae' in k else '#f59e0b' if 'Missing' in k else '#3b82f6'
                                     for k in list(issue_totals.keys())[:8]],
                        text=[f"{v:,}" for v in list(issue_totals.values())[:8]],
                        textposition='outside',
                        textfont=dict(color='#e2e8f0')
                    ))
                    fig.update_layout(
                        height=300, margin=dict(l=20,r=60,t=20,b=40),
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#e2e8f0'),
                        xaxis=dict(gridcolor='#334155', title='Count'),
                        yaxis=dict(gridcolor='#334155')
                    )
                    st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("##### DQI vs SAE Scatter")
            if 'dqi_score' in filtered_subjects.columns and 'sae_pending_count' in filtered_subjects.columns and len(filtered_subjects) > 0:
                # Sample for performance if too many points
                sample_df = filtered_subjects.sample(min(500, len(filtered_subjects))) if len(filtered_subjects) > 500 else filtered_subjects
                fig = px.scatter(
                    sample_df, x='dqi_score', y='sae_pending_count',
                    color='risk_category' if 'risk_category' in sample_df.columns else None,
                    color_discrete_map={'High': '#ef4444', 'Medium': '#f59e0b', 'Low': '#10b981'},
                    labels={'dqi_score': 'DQI Score', 'sae_pending_count': 'SAE Pending Count'},
                    hover_data=['subject_id', 'site_id'] if 'subject_id' in sample_df.columns else None
                )
                fig.update_layout(
                    height=300, margin=dict(l=40,r=20,t=20,b=40),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e2e8f0'),
                    xaxis=dict(gridcolor='#334155'), yaxis=dict(gridcolor='#334155'),
                    legend=dict(orientation='h', y=-0.2)
                )
                st.plotly_chart(fig, use_container_width=True)

        # Selection Insights
        st.markdown("---")
        st.markdown("##### 💡 Selection Insights")

        # Calculate insights
        high_risk_count = len(filtered_subjects[filtered_subjects['risk_category'] == 'High']) if 'risk_category' in filtered_subjects.columns else 0
        high_risk_pct = high_risk_count / len(filtered_subjects) * 100 if len(filtered_subjects) > 0 else 0
        avg_dqi = filtered_subjects['dqi_score'].mean() if 'dqi_score' in filtered_subjects.columns else 0
        total_sae = int(filtered_subjects['sae_pending_count'].sum()) if 'sae_pending_count' in filtered_subjects.columns else 0

        # Context string
        if selected_study != 'All Studies' and selected_site != 'All Sites':
            context_str = f"Site **{selected_site}** in study **{selected_study}**"
        elif selected_study != 'All Studies':
            context_str = f"Study **{selected_study}**"
        elif selected_site != 'All Sites':
            context_str = f"Site **{selected_site}**"
        else:
            context_str = "The **entire portfolio**"

        ic1, ic2 = st.columns(2)
        with ic1:
            render_insight("Risk Analysis",
                f"{context_str} has **{len(filtered_subjects):,} subjects** with **{high_risk_pct:.1f}%** classified as high-risk. "
                f"Average DQI score is **{avg_dqi:.4f}**. "
                f"{'This is above the portfolio average - prioritize for intervention.' if high_risk_pct > 15 else 'Risk levels are within acceptable range.'}")

        with ic2:
            if total_sae > 0:
                render_insight("Safety Signal",
                    f"**{total_sae:,} pending SAE reviews** detected in this selection. "
                    f"SAE backlog is a critical compliance risk that requires immediate attention. "
                    f"Consider prioritizing safety data processing for this {'site' if selected_site != 'All Sites' else 'study' if selected_study != 'All Studies' else 'portfolio segment'}.",
                    icon="⚠️")
            else:
                missing_visits = int(filtered_subjects['missing_visit_count'].sum()) if 'missing_visit_count' in filtered_subjects.columns else 0
                lab_issues = int(filtered_subjects['lab_issues_count'].sum()) if 'lab_issues_count' in filtered_subjects.columns else 0
                render_insight("Data Quality",
                    f"No pending SAE reviews in this selection. "
                    f"Focus on other data quality metrics like missing visits (**{missing_visits:,}**) "
                    f"and lab issues (**{lab_issues:,}**).")


# =============================================================================
# MAIN
# =============================================================================

# Header
st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3a5f 0%,#2d4a6f 50%,#0f172a 100%);padding:1.25rem 2rem;border-radius:16px;margin-bottom:1.5rem;display:flex;justify-content:space-between;align-items:center;border:1px solid #334155;box-shadow:0 4px 20px rgba(0,0,0,0.3)">
        <div style="display:flex;align-items:center;gap:0.75rem">
            <span style="font-size:2.5rem">⚡</span>
            <div>
                <span style="font-size:1.75rem;font-weight:800;color:#fff;letter-spacing:-0.5px">JAVELIN.AI</span>
                <div style="color:#94a3b8;font-size:0.9rem;margin-top:0.1rem">Clinical Trial Data Quality Intelligence</div>
            </div>
        </div>
        <div style="text-align:right">
            <div style="color:#64748b;font-size:0.85rem">NEST 2.0 Innovation Challenge</div>
            <div style="color:#94a3b8;font-size:0.95rem;font-weight:600">Team CWTY</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Load data
with st.spinner("Loading pipeline outputs..."):
    data = load_all_data()

if data['subjects'].empty:
    st.error("No data found. Run: `python src/run_pipeline.py --all`")
    st.stop()

# Data summary (collapsed)
with st.expander("📊 Data Summary", expanded=False):
    cols = st.columns(6)
    summaries = [
        ("Subjects", len(data['subjects'])),
        ("Sites", len(data['sites'])),
        ("Studies", len(data['studies'])),
        ("Anomalies", data['anomaly_summary'].get('total_anomalies', 0)),
        ("Clusters", len(data.get('cluster_profiles', pd.DataFrame()))),
        ("Root Causes", len(data['root_causes']))
    ]
    for col, (label, val) in zip(cols, summaries):
        with col:
            st.metric(label, f"{val:,}")

# Navigation Tabs
tabs = st.tabs([
    "📊 Command Center",
    "🗺️ Risk Landscape",
    "🔬 Patterns & Signals",
    "🔍 Root Causes",
    "⚡ Action Center",
    "🔎 Deep Dive"
])

with tabs[0]: page_command_center(data)
with tabs[1]: page_risk_landscape(data)
with tabs[2]: page_patterns_signals(data)
with tabs[3]: page_root_causes(data)
with tabs[4]: page_action_center(data)
with tabs[5]: page_deep_dive(data)

# Footer
st.markdown("""
    <div style='text-align:center;padding:1.5rem;margin-top:2rem;border-top:1px solid #334155;color:#64748b;font-size:0.8rem'>
        JAVELIN.AI | Built for NEST 2.0 Innovation Challenge | Team CWTY<br>
        <span style='font-size:0.75rem'>57,997 subjects • 3,424 sites • 23 studies • 9-phase intelligence pipeline</span>
    </div>
""", unsafe_allow_html=True)
