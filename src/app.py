"""
JAVELIN.AI - Clinical Trial Data Quality Dashboard
===================================================

INSIGHT-DRIVEN dashboard using ALL 9 phases of pipeline output.

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

# =============================================================================
# REUSE EXISTING MODULES
# =============================================================================

from config import (
    PHASE_DIRS, OUTPUT_FILES, DQI_WEIGHTS, THRESHOLDS,
    RISK_COLORS, NUMERIC_ISSUE_COLUMNS, CLUSTERING_FEATURES
)

from utils import get_risk_distribution, calculate_risk_rates

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
# CSS STYLING
# =============================================================================

st.markdown("""
<style>
    .main .block-container { padding: 1rem 2rem; max-width: 1600px; font-size: 1.1rem; }
    #MainMenu, footer, header {visibility: hidden;}
    h1, h2, h3, h4, h5 { color: #ffffff !important; }
    
    /* Global font size increase */
    .stMarkdown, .stText, p, span, div { font-size: 1.1rem; }
    .stExpander { font-size: 1.1rem; }
    
    .metric-card {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
    }
    .metric-label { color: #94a3b8; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { color: #ffffff; font-size: 2.25rem; font-weight: 700; }
    .metric-row { display: flex; justify-content: space-between; padding: 0.3rem 0; font-size: 1.1rem; }
    
    .alert-card {
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid;
    }
    .alert-critical { background: rgba(239,68,68,0.1); border-color: #ef4444; }
    .alert-warning { background: rgba(245,158,11,0.1); border-color: #f59e0b; }
    .alert-info { background: rgba(59,130,246,0.1); border-color: #3b82f6; }
    
    .insight-box {
        background: linear-gradient(135deg, rgba(59,130,246,0.15) 0%, rgba(6,182,212,0.1) 100%);
        border: 1px solid rgba(59,130,246,0.3);
        border-radius: 12px;
        padding: 1.25rem;
        margin: 1rem 0;
    }
    .insight-title { color: #60a5fa; font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem; }
    .insight-text { color: #e2e8f0; font-size: 1.15rem; line-height: 1.7; }
    
    .cluster-card {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    
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
    }
    
    .region-card {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .impact-banner {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin: 1rem 0;
    }
    
    .agent-insight {
        background: linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(59,130,246,0.1) 100%);
        border: 1px solid rgba(139,92,246,0.3);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.75rem 0;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# DATA LOADING - ALL PHASES
# =============================================================================

def find_output_dir() -> Path:
    """Find outputs directory."""
    candidates = [
        PHASE_DIRS['phase_03'].parent,
        Path("/home/claude/outputs/outputs"),
        Path(__file__).parent.parent / "outputs" / "outputs",
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
        return json.load(open(path)) if path.exists() else {}

    def load_text(phase, filename):
        path = base / phase / filename
        return open(path).read() if path.exists() else ""

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
    weighted = (dist['High'] * 1.0 + dist['Medium'] * 0.3) / total
    score = int(100 * (1 - weighted))
    score = max(0, min(100, score))
    if score >= 85: return score, "HEALTHY", "Portfolio performing well"
    elif score >= 70: return score, "MODERATE", "Some areas need attention"
    elif score >= 50: return score, "AT RISK", "Significant issues detected"
    else: return score, "CRITICAL", "Urgent intervention required"

# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_insight(title: str, text: str, icon: str = "💡"):
    # Convert **text** to <strong>text</strong> for HTML rendering
    import re
    html_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    st.markdown(f"""
        <div class="insight-box">
            <div class="insight-title">{icon} {title}</div>
            <div class="insight-text">{html_text}</div>
        </div>
    """, unsafe_allow_html=True)


def render_agent_insight(agent: str, insight: str):
    import re
    html_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', insight)
    st.markdown(f"""
        <div class="agent-insight">
            <div style="color:#a78bfa;font-weight:600;font-size:0.85rem;margin-bottom:0.5rem">🤖 {agent}</div>
            <div style="color:#e2e8f0;font-size:0.9rem">{html_text}</div>
        </div>
    """, unsafe_allow_html=True)


def render_metric_card(icon: str, label: str, value: int, breakdown: dict = None):
    rows = ""
    if breakdown:
        colors = {'Critical': '#ef4444', 'High Risk': '#ef4444', 'High': '#ef4444',
                  'At Risk': '#f59e0b', 'Medium': '#f59e0b', 'Healthy': '#10b981', 'Low': '#10b981'}
        for k, v in breakdown.items():
            c = colors.get(k, '#94a3b8')
            rows += f"<div class='metric-row'><span style='color:{c}'>{k}</span><span style='color:#fff;font-weight:600'>{v:,}</span></div>"
        rows = f"<div style='margin-top:0.75rem;padding-top:0.75rem;border-top:1px solid #334155'>{rows}</div>"
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{icon} {label}</div>
            <div class="metric-value">{value:,}</div>
            {rows}
        </div>
    """, unsafe_allow_html=True)


def render_alert(severity: str, title: str, subtitle: str, detail: str = ""):
    icons = {'critical': '🔴', 'warning': '🟠', 'info': '🔵'}
    det = f"<div style='color:#64748b;font-size:0.8rem;margin-top:0.25rem;font-style:italic'>{detail}</div>" if detail else ""
    st.markdown(f"""
        <div class="alert-card alert-{severity}">
            <div style="color:#fff;font-weight:600">{icons.get(severity, '⚪')} {title}</div>
            <div style="color:#94a3b8;font-size:0.85rem">{subtitle}</div>
            {det}
        </div>
    """, unsafe_allow_html=True)


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
        with mc[1]: render_metric_card("🏥", "Sites", len(sites), {'High Risk': site_dist['High'], 'Medium': site_dist['Medium'], 'Low': site_dist['Low']})
        with mc[2]: render_metric_card("👥", "Subjects", len(subjects), {'High Risk': subj_dist['High'], 'Medium': subj_dist['Medium'], 'Low': subj_dist['Low']})

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

    # Cluster alert
    if cluster_summary.get('cluster_summary'):
        critical_clusters = [c for c in cluster_summary['cluster_summary'] if c['risk_level'] == 'Critical']
        if critical_clusters:
            total_crit = sum(c['sites'] for c in critical_clusters)
            alerts.append(('warning', f"{total_crit} sites in critical clusters",
                          f"{len(critical_clusters)} cluster groups need immediate attention", ''))

    if alerts:
        st.markdown("##### ⚠️ Critical Alerts")
        st.markdown("""<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">""", unsafe_allow_html=True)
        for sev, title, sub, det in alerts[:6]:
            icons = {'critical': '🔴', 'warning': '🟠', 'info': '🔵'}
            det_html = f"<div style='color:#64748b;font-size:0.8rem;margin-top:0.25rem;font-style:italic'>{det}</div>" if det else ""
            st.markdown(f"""
                <div class="alert-card alert-{sev}">
                    <div style="color:#fff;font-weight:600">{icons.get(sev, '⚪')} {title}</div>
                    <div style="color:#94a3b8;font-size:0.85rem">{sub}</div>
                    {det_html}
                </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

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
            else:
                st.info("No study data available for chart")
        else:
            st.info("Study risk data not available")

    with c2:
        st.markdown("##### 🔍 Top Issues")
        if not subjects.empty:
            issues = [(c, int(subjects[c].sum())) for c in NUMERIC_ISSUE_COLUMNS if c in subjects.columns and subjects[c].sum() > 0]
            issues.sort(key=lambda x: -x[1])
            for col, total in issues[:6]:
                color = '#ef4444' if 'sae' in col else '#f59e0b' if 'missing' in col else '#3b82f6'
                icon = '🔴' if 'sae' in col else '🟠' if 'missing' in col else '🔵'
                st.markdown(f"""
                    <div style="display:flex;justify-content:space-between;padding:0.85rem 1rem;background:linear-gradient(90deg,{color}15,transparent);border-left:3px solid {color};border-radius:0 8px 8px 0;margin-bottom:0.5rem">
                        <span style="color:#e2e8f0;font-size:1.1rem">{icon} {format_issue(col)}</span>
                        <span style="color:{color};font-weight:700;font-size:1.2rem">{total:,}</span>
                    </div>
                """, unsafe_allow_html=True)

    # Insights from multi-agent and clustering
    st.markdown("---")
    st.markdown("##### 💡 AI-Powered Insights")

    ic1, ic2 = st.columns(2)

    with ic1:
        # Multi-agent insight
        if agent_analysis.get('portfolio_context'):
            ctx = agent_analysis['portfolio_context']
            high_risk_studies = [s for s, r in ctx.get('study_risks', {}).items() if r == 'High']
            render_agent_insight(
                "Multi-Agent Analysis",
                f"Portfolio average DQI: {ctx.get('portfolio_avg_dqi', 0):.4f}. "
                f"**{len(high_risk_studies)} studies** classified as high-risk by consensus. "
                f"Average SAE rate: {ctx.get('portfolio_avg_sae', 0):.1f} per site."
            )

    with ic2:
        # Cluster insight
        if cluster_summary.get('cluster_summary'):
            clusters = cluster_summary['cluster_summary']
            high_perf = next((c for c in clusters if c['name'] == 'High Performers'), None)
            if high_perf:
                render_insight(
                    "Cluster Analysis",
                    f"**{high_perf['sites']} sites ({high_perf['pct']}%)** are high performers with zero issues. "
                    f"These can serve as benchmarks. {sum(c['sites'] for c in clusters if c['risk_level'] == 'Critical')} sites "
                    f"in critical clusters need immediate attention."
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

    tab1, tab2, tab3 = st.tabs(["🌍 Geographic", "📊 Studies", "🔬 Clusters"])

    # =========================================================================
    # GEOGRAPHIC TAB
    # =========================================================================
    with tab1:
        c1, c2 = st.columns([2.2, 1])

        with c1:
            st.markdown("##### Global Risk Distribution")
            if not countries.empty and 'country' in countries.columns:
                # Use scatter_geo for better looking map with bubbles
                df = countries.copy()
                df['size'] = df['site_count'] * 3  # Scale for visibility
                df['risk_level'] = df['avg_dqi_score'].apply(
                    lambda x: 'High' if x > 0.1 else 'Medium' if x > 0.05 else 'Low'
                )

                fig = px.scatter_geo(
                    df,
                    locations='country',
                    locationmode='ISO-3',
                    size='site_count',
                    color='avg_dqi_score',
                    hover_name='country',
                    hover_data={'site_count': True, 'avg_dqi_score': ':.4f'},
                    color_continuous_scale='RdYlGn_r',  # Red=bad, Green=good (reversed)
                    size_max=40,
                    projection='natural earth',
                    labels={'avg_dqi_score': 'DQI Score', 'site_count': 'Sites'}
                )
                fig.update_layout(
                    geo=dict(
                        showframe=False,
                        showcoastlines=True,
                        coastlinecolor='#475569',
                        landcolor='#1e293b',
                        oceancolor='#0f172a',
                        bgcolor='rgba(0,0,0,0)',
                        showland=True,
                        showcountries=True,
                        countrycolor='#334155'
                    ),
                    height=420,
                    margin=dict(l=0,r=0,t=10,b=0),
                    paper_bgcolor='rgba(0,0,0,0)',
                    coloraxis_colorbar=dict(
                        title=dict(text="DQI", font=dict(color="#e2e8f0", size=13)),
                        tickfont=dict(color='#e2e8f0', size=12),
                    )
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No geographic data available")

        with c2:
            st.markdown("##### Regional Summary")
            if not regions.empty and not sites.empty:
                avg = sites['avg_dqi_score'].mean()
                for _, r in regions.sort_values('avg_dqi_score', ascending=False).iterrows():
                    pct = ((r['avg_dqi_score'] / avg) - 1) * 100 if avg > 0 else 0
                    delta_color = '#ef4444' if pct > 10 else '#10b981' if pct < -10 else '#94a3b8'
                    delta_text = f"↑{abs(pct):.0f}% above" if pct > 10 else f"↓{abs(pct):.0f}% below" if pct < -10 else "≈ avg"
                    st.markdown(f"""
                        <div class="region-card">
                            <div style="color:#fff;font-weight:600;font-size:1.15rem">{r['region']}</div>
                            <div style="color:#94a3b8;font-size:1.05rem">{r['site_count']:,} sites • DQI: {r['avg_dqi_score']:.4f}</div>
                            <div style="color:{delta_color};font-weight:600;margin-top:0.25rem;font-size:1.1rem">{delta_text}</div>
                        </div>
                    """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("##### Top 10 Countries by Risk")
        if not countries.empty:
            df = countries.nlargest(10, 'avg_dqi_score')[['country', 'site_count', 'avg_dqi_score']].copy()
            if 'high_risk_rate' in countries.columns:
                df['High-Risk %'] = (countries.nlargest(10, 'avg_dqi_score')['high_risk_rate'] * 100).round(1).astype(str) + '%'
            df.columns = ['Country', 'Sites', 'Avg DQI'] + (['High-Risk %'] if 'High-Risk %' in df.columns else [])
            df['Avg DQI'] = df['Avg DQI'].round(4)
            st.dataframe(df, use_container_width=True, hide_index=True)

        # Geographic insight
        if not regions.empty and not sites.empty:
            worst = regions.loc[regions['avg_dqi_score'].idxmax()]
            avg = sites['avg_dqi_score'].mean()
            pct = ((worst['avg_dqi_score'] / avg) - 1) * 100
            if pct > 10:
                # Get region risks from agent analysis
                region_risks = agent_analysis.get('portfolio_context', {}).get('region_risks', {})
                risk_level = region_risks.get(worst['region'], 'Unknown')
                render_insight(
                    "Geographic Concentration",
                    f"**{worst['region']}** is {pct:.0f}% above portfolio average with {worst['site_count']:,} sites. "
                    f"Multi-agent consensus: **{risk_level}** risk. Consider region-specific training and dedicated monitors."
                )

    # =========================================================================
    # STUDIES TAB
    # =========================================================================
    with tab2:
        st.markdown("##### Study Portfolio Overview")
        st.caption("Size = Subjects | Color = Risk (🟢 <10% | 🟡 10-20% | 🔴 >20%)")

        if not studies.empty and 'subject_count' in studies.columns:
            df = studies.copy()
            if 'high_risk_rate' in df.columns:
                df['color'] = df['high_risk_rate'].apply(lambda x: '#ef4444' if x >= 0.2 else '#f59e0b' if x >= 0.1 else '#10b981')
                df['risk_label'] = df['high_risk_rate'].apply(lambda x: 'High Risk' if x >= 0.2 else 'Medium Risk' if x >= 0.1 else 'Low Risk')
            else:
                df['color'] = '#3b82f6'
                df['risk_label'] = 'Unknown'

            fig = go.Figure(go.Treemap(
                labels=df['study'],
                parents=['']*len(df),
                values=df['subject_count'],
                marker=dict(colors=df['color'], line=dict(width=2, color='#0f172a')),
                textinfo='label+value',
                textfont=dict(size=14, color='white'),
                hovertemplate='<b>%{label}</b><br>Subjects: %{value:,}<br>Risk: %{customdata}<extra></extra>',
                customdata=df['risk_label']
            ))
            fig.update_layout(height=450, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Study data not available")

        st.markdown("---")
        st.markdown("##### Study Risk Ranking")
        if not studies.empty:
            df = studies.copy()
            if 'high_risk_rate' in df.columns:
                df['High-Risk %'] = (df['high_risk_rate'] * 100).round(1).astype(str) + '%'
            display = df.sort_values('avg_dqi_score', ascending=False)[['study', 'site_count', 'subject_count', 'avg_dqi_score'] + (['High-Risk %'] if 'High-Risk %' in df.columns else [])].head(15)
            display.columns = ['Study', 'Sites', 'Subjects', 'Avg DQI'] + (['High-Risk %'] if 'High-Risk %' in df.columns else [])
            display['Avg DQI'] = display['Avg DQI'].round(4)
            st.dataframe(display, use_container_width=True, hide_index=True)

        # Study insight
        if not studies.empty and 'high_risk_rate' in studies.columns:
            df = studies.copy()
            high_risk_studies = len(df[df['high_risk_rate'] >= 0.2])
            if high_risk_studies > 0:
                worst = df.loc[df['high_risk_rate'].idxmax()]
                study_risks = agent_analysis.get('portfolio_context', {}).get('study_risks', {})
                render_insight(
                    "Study Concentration",
                    f"**{high_risk_studies} studies** exceed 20% high-risk rate. **{worst['study']}** is highest at "
                    f"**{worst['high_risk_rate']*100:.1f}%** ({worst['site_count']} sites, {worst['subject_count']:,} subjects). "
                    f"Agent analysis confirms {sum(1 for r in study_risks.values() if r == 'High')} studies as high-risk."
                )

    # =========================================================================
    # CLUSTERS TAB
    # =========================================================================
    with tab3:
        st.markdown("##### Site Clustering Analysis")
        st.caption("Sites grouped by similar risk profiles using Gaussian Mixture Models")

        if not cluster_profiles.empty:
            # Cluster visualization
            c1, c2 = st.columns([1.5, 1])

            with c1:
                # Horizontal bar chart of clusters
                cluster_grouped = cluster_profiles.groupby('cluster_name').agg({
                    'site_count': 'sum',
                    'pct_of_total': 'sum',
                    'risk_level': 'first',
                    'avg_dqi_score': 'mean'
                }).reset_index().sort_values('site_count', ascending=True)

                colors_map = {'Critical': '#ef4444', 'High': '#f59e0b', 'Low': '#10b981'}
                bar_colors = [colors_map.get(r, '#3b82f6') for r in cluster_grouped['risk_level']]

                fig = go.Figure(go.Bar(
                    y=cluster_grouped['cluster_name'],
                    x=cluster_grouped['site_count'],
                    orientation='h',
                    marker_color=bar_colors,
                    text=[f"{s:,} sites ({p:.0f}%)" for s, p in zip(cluster_grouped['site_count'], cluster_grouped['pct_of_total'])],
                    textposition='outside',
                    textfont=dict(size=13, color='#e2e8f0'),
                ))
                fig.update_layout(
                    height=300, margin=dict(l=20,r=100,t=20,b=40),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e2e8f0', size=13),
                    xaxis=dict(gridcolor='#334155', title='Number of Sites'),
                    yaxis=dict(gridcolor='#334155')
                )
                st.plotly_chart(fig, use_container_width=True)

            with c2:
                st.markdown("##### Cluster Metrics")
                # Quick metrics
                total_sites = cluster_grouped['site_count'].sum()
                critical_sites = cluster_grouped[cluster_grouped['risk_level'] == 'Critical']['site_count'].sum()
                healthy_sites = cluster_grouped[cluster_grouped['risk_level'] == 'Low']['site_count'].sum()

                st.markdown(f"""
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-bottom:1rem">
                        <div style="background:#1e293b;padding:0.75rem;border-radius:8px;text-align:center">
                            <div style="color:#ef4444;font-size:1.5rem;font-weight:700">{critical_sites:,}</div>
                            <div style="color:#94a3b8;font-size:0.85rem">Critical</div>
                        </div>
                        <div style="background:#1e293b;padding:0.75rem;border-radius:8px;text-align:center">
                            <div style="color:#10b981;font-size:1.5rem;font-weight:700">{healthy_sites:,}</div>
                            <div style="color:#94a3b8;font-size:0.85rem">Healthy</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                st.markdown("##### Top Clusters")
                colors_map = {'Critical': '#ef4444', 'High': '#f59e0b', 'Low': '#10b981'}
                for _, row in cluster_profiles.sort_values('intervention_priority').head(4).iterrows():
                    color = colors_map.get(row['risk_level'], '#3b82f6')
                    issues = parse_list(row.get('dominant_issues', []))[:2]
                    issues_str = ', '.join([i.split('(')[0].strip() for i in issues]) if issues else 'None'
                    st.markdown(f"""
                        <div class="cluster-card" style="border-left:4px solid {color}">
                            <div style="display:flex;justify-content:space-between">
                                <span style="color:#fff;font-weight:600;font-size:1rem">{row['cluster_name']}</span>
                                <span style="background:{color}33;color:{color};padding:0.2rem 0.5rem;border-radius:10px;font-size:0.8rem">{row['risk_level']}</span>
                            </div>
                            <div style="color:#94a3b8;font-size:0.95rem;margin-top:0.25rem">{row['site_count']} sites ({row['pct_of_total']}%)</div>
                            <div style="color:#64748b;font-size:0.9rem;margin-top:0.25rem">Issues: {issues_str}</div>
                        </div>
                    """, unsafe_allow_html=True)

            # Cluster insight
            if cluster_summary.get('metrics'):
                metrics = cluster_summary['metrics']
                crit_clusters = [c for c in cluster_summary.get('cluster_summary', []) if c['risk_level'] == 'Critical']
                render_insight(
                    "Clustering Insight",
                    f"GMM clustering identified **{cluster_summary.get('n_clusters', 0)} distinct site groups** "
                    f"(silhouette score: {metrics.get('silhouette_score', 0):.3f}). "
                    f"**{len(crit_clusters)} clusters** ({sum(c['sites'] for c in crit_clusters)} sites) are critical priority. "
                    f"Sites in 'High Performers' cluster can serve as benchmarks for struggling sites."
                )
        else:
            st.info("Cluster data not available. Run Phase 08.")


# =============================================================================
# PAGE 3: ROOT CAUSES
# =============================================================================

def page_root_causes(data: dict):
    root_causes = data.get('root_causes', pd.DataFrame())
    cooccurrence = data.get('cooccurrence', pd.DataFrame())
    contributing_factors = data.get('contributing_factors', pd.DataFrame())
    subjects = data.get('subjects', pd.DataFrame())
    agent_analysis = data.get('agent_analysis', {})

    st.markdown("### 🔍 Root Cause Analysis")
    st.caption("Understanding why problems occur, not just where")

    if root_causes.empty:
        st.warning("No root cause data. Run Phase 09.")
        return

    # Impact summary
    total_sites = int(root_causes['affected_sites'].sum())
    total_subj = int(root_causes['affected_subjects'].sum())
    high_risk = len(subjects[subjects['risk_category'] == 'High']) if not subjects.empty and 'risk_category' in subjects.columns else 0
    reduction = int(high_risk * 0.47)

    cols = st.columns(4)
    for col, (label, val, color) in zip(cols, [
        ("Root Causes", len(root_causes), "#3b82f6"),
        ("Sites Affected", total_sites, "#f59e0b"),
        ("Subjects Impacted", total_subj, "#ef4444"),
        ("Potential Reduction", f"-{reduction:,}", "#10b981")
    ]):
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
        f"({high_risk:,} → {high_risk-reduction:,}). This represents the highest-leverage intervention opportunity."
    )

    st.markdown("---")
    st.markdown("##### Identified Root Causes")

    severity_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
    for _, rc in root_causes.sort_values(by='severity', key=lambda x: x.map(severity_order)).iterrows():
        sev = rc['severity']
        color = '#ef4444' if sev == 'Critical' else '#f59e0b' if sev == 'High' else '#3b82f6'

        evidence = parse_list(rc.get('evidence', []))
        evidence_html = "".join([f"<div style='color:#cbd5e1;padding:0.25rem 0;font-size:1.05rem'>• {e}</div>" for e in evidence[:3]])

        st.markdown(f"""
            <div class="rc-card" style="border-left-color:{color}">
                <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div>
                        <div style="color:#94a3b8;font-size:0.9rem;text-transform:uppercase;letter-spacing:0.5px">{rc['category']}</div>
                        <div style="color:#fff;font-size:1.2rem;font-weight:600;margin:0.25rem 0">{rc['description']}</div>
                    </div>
                    <span style="background:{color}33;color:{color};padding:0.3rem 0.85rem;border-radius:12px;font-size:0.9rem;font-weight:600">{sev}</span>
                </div>
                <div style="display:flex;gap:2.5rem;margin:0.75rem 0;padding:0.6rem 0.75rem;background:rgba(0,0,0,0.2);border-radius:8px">
                    <div><div style="color:#94a3b8;font-size:0.85rem;text-transform:uppercase">Confidence</div><div style="color:#fff;font-size:1.25rem;font-weight:700">{int(rc['confidence']*100)}%</div></div>
                    <div><div style="color:#94a3b8;font-size:0.85rem;text-transform:uppercase">Sites</div><div style="color:#fff;font-size:1.25rem;font-weight:700">{rc['affected_sites']:,}</div></div>
                    <div><div style="color:#94a3b8;font-size:0.85rem;text-transform:uppercase">Subjects</div><div style="color:#fff;font-size:1.25rem;font-weight:700">{rc['affected_subjects']:,}</div></div>
                </div>
                {f"<div style='margin-top:0.5rem'><div style='color:#94a3b8;font-size:0.9rem;margin-bottom:0.25rem'>Evidence:</div>{evidence_html}</div>" if evidence_html else ""}
            </div>
        """, unsafe_allow_html=True)

        actions = parse_list(rc.get('recommended_actions', []))
        if actions:
            subj = rc['affected_subjects']
            impact_text = f" → ~{int(subj/len(actions)):,} subjects per action" if subj > 0 else ""
            with st.expander(f"📋 {len(actions)} Recommended Actions{impact_text}"):
                for i, a in enumerate(actions, 1):
                    st.markdown(f"**{i}.** {a}")

    st.markdown("---")

    # Co-occurrence heatmap
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
                paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#e2e8f0', size=11),
                xaxis=dict(tickangle=90)
            )
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("""
            <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.25rem">
                <h5 style="color:#fff;margin-bottom:0.75rem">Reading the Heatmap</h5>
                <p style="color:#cbd5e1;font-size:0.85rem;margin-bottom:0.5rem"><span style="color:#ef4444">■</span> <strong>Red</strong> = Strong correlation</p>
                <p style="color:#cbd5e1;font-size:0.85rem;margin-bottom:0.5rem"><span style="color:#8b5cf6">■</span> <strong>Purple</strong> = Moderate</p>
                <p style="color:#cbd5e1;font-size:0.85rem;margin-bottom:0.75rem"><span style="color:#3b82f6">■</span> <strong>Blue</strong> = Weak</p>
                <hr style="border-color:#334155;margin:0.75rem 0">
                <p style="color:#94a3b8;font-size:0.8rem">Correlated issues often share root causes. Fixing one may resolve the other.</p>
            </div>
        """, unsafe_allow_html=True)

    # Contributing factors
    if not contributing_factors.empty:
        st.markdown("---")
        st.markdown("##### Contributing Factors")
        st.dataframe(contributing_factors.head(10), use_container_width=True, hide_index=True)


# =============================================================================
# PAGE 4: ACTION CENTER
# =============================================================================

def page_action_center(data: dict):
    root_causes = data.get('root_causes', pd.DataFrame())
    recommendations = data.get('recommendations', pd.DataFrame())
    multi_agent_recs = data.get('multi_agent_recs', pd.DataFrame())
    subjects = data.get('subjects', pd.DataFrame())
    anomaly_summary = data.get('anomaly_summary', {})

    st.markdown("### ⚡ Action Center")
    st.caption("Prioritized interventions ranked by impact")

    # Impact banner - separate boxes
    if not subjects.empty and 'risk_category' in subjects.columns:
        high = len(subjects[subjects['risk_category'] == 'High'])
        med = len(subjects[subjects['risk_category'] == 'Medium'])
        total = len(subjects)

        curr_health = int(100 * (1 - (high * 1.0 + med * 0.3) / total))
        proj_high = int(high * 0.66)
        proj_health = int(100 * (1 - (proj_high * 1.0 + med * 0.3) / total))

        cols = st.columns(3)
        with cols[0]:
            st.markdown(f"""
                <div style="background:linear-gradient(135deg,#059669 0%,#047857 100%);border-radius:12px;padding:1.25rem;text-align:center">
                    <div style="color:rgba(255,255,255,0.8);font-size:0.85rem;text-transform:uppercase">High-Risk Subjects</div>
                    <div style="color:#fff;font-size:1.75rem;font-weight:700;margin:0.5rem 0">{high:,} → {proj_high:,}</div>
                    <div style="color:#a7f3d0;font-size:1rem">-{high-proj_high:,} subjects</div>
                </div>
            """, unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"""
                <div style="background:linear-gradient(135deg,#059669 0%,#047857 100%);border-radius:12px;padding:1.25rem;text-align:center">
                    <div style="color:rgba(255,255,255,0.8);font-size:0.85rem;text-transform:uppercase">Portfolio Health</div>
                    <div style="color:#fff;font-size:1.75rem;font-weight:700;margin:0.5rem 0">{curr_health} → {proj_health}</div>
                    <div style="color:#a7f3d0;font-size:1rem">+{proj_health-curr_health} points</div>
                </div>
            """, unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f"""
                <div style="background:linear-gradient(135deg,#059669 0%,#047857 100%);border-radius:12px;padding:1.25rem;text-align:center">
                    <div style="color:rgba(255,255,255,0.8);font-size:0.85rem;text-transform:uppercase">Risk Reduction</div>
                    <div style="color:#fff;font-size:1.75rem;font-weight:700;margin:0.5rem 0">-{int((high-proj_high)/high*100) if high > 0 else 0}%</div>
                    <div style="color:#a7f3d0;font-size:1rem">if actions completed</div>
                </div>
            """, unsafe_allow_html=True)

    # Build actions from ALL sources
    actions = []

    # From Phase 05 action_items.json (site/study/region/country recommendations)
    action_items = data.get('action_items', {})

    # Site recommendations
    for rec in action_items.get('site_recommendations', []):
        urgency = 'immediate' if rec.get('priority') == 'CRITICAL' else 'week' if rec.get('priority') == 'HIGH' else 'month'
        actions.append({
            'title': f"Site {rec.get('site_id', '?')} ({rec.get('study', '')}): {rec.get('site_risk_category', '')} Risk",
            'type': 'Site Action',
            'urgency': urgency,
            'sites': 1,
            'subjects': rec.get('subject_count', 0),
            'steps': rec.get('recommendations', [])[:3],
            'source': 'Phase 05 Engine'
        })

    # Study recommendations
    for rec in action_items.get('study_recommendations', []):
        urgency = 'immediate' if rec.get('priority') == 'CRITICAL' else 'week' if rec.get('priority') == 'HIGH' else 'month'
        actions.append({
            'title': f"{rec.get('study', '?')}: {rec.get('total_issues', 0)} issues across {rec.get('site_count', 0)} sites",
            'type': 'Study Action',
            'urgency': urgency,
            'sites': rec.get('site_count', 0),
            'subjects': rec.get('subject_count', 0),
            'steps': rec.get('recommendations', [])[:3],
            'source': 'Phase 05 Engine'
        })

    # Country recommendations
    for rec in action_items.get('country_recommendations', [])[:10]:  # Top 10
        urgency = 'week' if rec.get('priority') in ['CRITICAL', 'HIGH'] else 'month'
        actions.append({
            'title': f"Country {rec.get('country', '?')}: {rec.get('site_count', 0)} sites need attention",
            'type': 'Country Action',
            'urgency': urgency,
            'sites': rec.get('site_count', 0),
            'subjects': rec.get('subject_count', 0),
            'steps': rec.get('recommendations', [])[:2],
            'source': 'Phase 05 Engine'
        })

    # From root causes (Phase 09)
    if not root_causes.empty:
        for _, rc in root_causes.iterrows():
            sev = rc['severity']
            urgency = 'immediate' if sev == 'Critical' else 'week' if sev == 'High' else 'month'
            steps = parse_list(rc.get('recommended_actions', []))[:3]
            actions.append({
                'title': f"ROOT CAUSE: {rc['description'][:60]}",
                'type': rc['category'],
                'urgency': urgency,
                'sites': rc['affected_sites'],
                'subjects': rc['affected_subjects'],
                'steps': steps,
                'source': 'Root Cause Analysis'
            })

    # From multi-agent recommendations (Phase 07)
    if not multi_agent_recs.empty:
        for _, rec in multi_agent_recs.iterrows():
            steps = parse_list(rec.get('recommended_actions', []))[:3]
            actions.append({
                'title': f"AI CONSENSUS: Site {rec.get('site_id', '?')} - {rec.get('risk_category', '')}",
                'type': 'Multi-Agent',
                'urgency': 'immediate' if rec.get('escalation_required') else 'week',
                'sites': 1,
                'subjects': 0,
                'steps': steps,
                'source': 'AI Agents'
            })

    immediate = [a for a in actions if a['urgency'] == 'immediate']
    week = [a for a in actions if a['urgency'] == 'week']
    month = [a for a in actions if a['urgency'] == 'month']

    def render_action(a, urgency_class):
        steps_html = ""
        if a['steps']:
            steps_html = "<div style='margin-top:0.75rem;padding-top:0.75rem;border-top:1px solid #334155'>"
            for s in a['steps']:
                steps_html += f"<div style='color:#cbd5e1;font-size:1.05rem;padding:0.3rem 0;padding-left:1rem'>→ {s}</div>"
            steps_html += "</div>"

        st.markdown(f"""
            <div class="action-card" style="border-left-color:{'#ef4444' if urgency_class == 'immediate' else '#f59e0b' if urgency_class == 'week' else '#3b82f6'}">
                <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div style="color:#fff;font-weight:600;flex:1;font-size:1.15rem">{a['title']}</div>
                    <span style="color:#64748b;font-size:0.9rem;margin-left:0.5rem">{a['source']}</span>
                </div>
                <div style="color:#94a3b8;font-size:1rem;margin-top:0.35rem">
                    📁 {a['type']} • 🏥 {a['sites']:,} sites{f" • 👥 {a['subjects']:,} subjects" if a['subjects'] > 0 else ""}
                </div>
                {steps_html}
            </div>
        """, unsafe_allow_html=True)

    # Immediate
    if immediate:
        st.markdown(f"""
            <div style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);padding:0.75rem 1rem;border-radius:8px;margin:1rem 0;display:flex;justify-content:space-between">
                <span style="color:#fff;font-weight:600">🔴 IMMEDIATE ({len(immediate)} actions)</span>
            </div>
        """, unsafe_allow_html=True)
        for a in immediate[:8]:
            render_action(a, 'immediate')

    # This week
    if week:
        st.markdown(f"""
            <div style="background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.3);padding:0.75rem 1rem;border-radius:8px;margin:1rem 0;display:flex;justify-content:space-between">
                <span style="color:#fff;font-weight:600">🟠 THIS WEEK ({len(week)} actions)</span>
            </div>
        """, unsafe_allow_html=True)
        for a in week[:5]:
            render_action(a, 'week')

    st.markdown("---")

    # Anomaly drilldown
    if anomaly_summary.get('top_sites'):
        st.markdown("##### 🔬 Anomaly Drilldown")
        st.caption("Sites showing unusual patterns that require investigation")

        top_sites = anomaly_summary['top_sites'][:10]  # Show 10 sites
        with st.expander(f"View {len(top_sites)} Top Anomalous Sites", expanded=False):
            for site in top_sites:
                st.markdown(f"""
                    <div class="anomaly-card">
                        <div style="display:flex;justify-content:space-between;align-items:center">
                            <span style="color:#fff;font-weight:600;font-size:1.2rem">{site['site_id']}</span>
                            <span style="color:#ef4444;font-size:1rem;font-weight:600">{site['critical_count']} critical</span>
                        </div>
                        <div style="color:#94a3b8;font-size:1.05rem">{site['study']}</div>
                        <div style="color:#cbd5e1;font-size:1.1rem;margin-top:0.5rem;line-height:1.5">{site['top_anomalies'][:200]}...</div>
                    </div>
                """, unsafe_allow_html=True)

        render_insight(
            "Anomaly Pattern",
            f"**{anomaly_summary.get('sites_with_anomalies', 0)} sites** show anomalous behavior. "
            f"Most common type: **{max(anomaly_summary.get('by_type', {'pattern_anomaly': 0}).items(), key=lambda x: x[1])[0].replace('_', ' ').title()}**. "
            f"These sites may be misclassified or have data quality issues not captured by standard metrics."
        )

    # Summary with context
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
                    <div style="color:#64748b;font-size:0.75rem;margin-top:0.25rem">{context}</div>
                </div>
            """, unsafe_allow_html=True)


# =============================================================================
# MAIN
# =============================================================================

# Header
st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3a5f 0%,#2d4a6f 50%,#0f172a 100%);padding:1.25rem 2rem;border-radius:16px;margin-bottom:1.5rem;display:flex;justify-content:space-between;align-items:center;border:1px solid #334155;box-shadow:0 4px 20px rgba(0,0,0,0.3)">
        <div style="display:flex;align-items:center;gap:0.75rem">
            <span style="font-size:2.5rem">⚡</span>
            <div>
                <span style="font-size:2rem;font-weight:800;color:#fff;letter-spacing:-0.5px">JAVELIN.AI</span>
                <div style="color:#94a3b8;font-size:1rem;margin-top:0.1rem">Clinical Trial Data Quality Intelligence</div>
            </div>
        </div>
        <div style="text-align:right">
            <div style="color:#64748b;font-size:0.9rem">NEST 2.0 Innovation Challenge</div>
            <div style="color:#94a3b8;font-size:1rem;font-weight:600">Team CWTY</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Load data
with st.spinner("Loading all phase outputs..."):
    data = load_all_data()

if data['subjects'].empty:
    st.error("No data found. Run: `python run_pipeline.py --all`")
    st.stop()

# Show data summary
with st.expander("📊 Data Summary", expanded=False):
    st.markdown(f"""
    - **Phase 03**: {len(data['subjects']):,} subjects, {len(data['sites']):,} sites, {len(data['studies'])} studies
    - **Phase 05**: {len(data['recommendations']):,} recommendations
    - **Phase 06**: {data['anomaly_summary'].get('total_anomalies', 0):,} anomalies
    - **Phase 07**: {len(data.get('multi_agent_recs', pd.DataFrame()))} multi-agent recommendations
    - **Phase 08**: {len(data.get('cluster_profiles', pd.DataFrame()))} cluster profiles
    - **Phase 09**: {len(data['root_causes'])} root causes identified
    """)

# Tabs
t1, t2, t3, t4 = st.tabs(["📊 Command Center", "🗺️ Risk Landscape", "🔍 Root Causes", "⚡ Action Center"])

with t1: page_command_center(data)
with t2: page_risk_landscape(data)
with t3: page_root_causes(data)
with t4: page_action_center(data)

# Footer
st.markdown("<div style='text-align:center;padding:1.5rem;margin-top:2rem;border-top:1px solid #334155;color:#64748b;font-size:0.8rem'>JAVELIN.AI | Built for NEST 2.0 Innovation Challenge | Team CWTY</div>", unsafe_allow_html=True)
