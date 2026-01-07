"""
Javelin.AI - Clinical Trial Data Quality Dashboard
==================================================

A comprehensive dashboard for monitoring clinical trial data quality
across studies, sites, and subjects.

Usage:
    streamlit run app.py

Requirements:
    pip install streamlit pandas plotly
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from pathlib import Path
from datetime import datetime

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="JAVELIN.AI - Data Quality Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM STYLING
# ============================================================================

st.markdown("""
<style>
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Headers - works in both light and dark mode */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #63b3ed;
        text-align: center;
        padding: 1rem 0;
        border-bottom: 3px solid #3182ce;
        margin-bottom: 1.5rem;
    }

    .section-header {
        font-size: 1.4rem;
        font-weight: 600;
        color: #63b3ed;
        padding: 0.5rem 0;
        border-left: 4px solid #3182ce;
        padding-left: 1rem;
        margin: 1.5rem 0 1rem 0;
    }

    /* Site cards - dark mode compatible */
    .site-card {
        background-color: rgba(45, 55, 72, 0.6);
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        border-left: 4px solid #718096;
    }

    .site-card-critical {
        background-color: rgba(197, 48, 48, 0.15);
        border-left-color: #fc8181;
    }

    .site-card-high {
        background-color: rgba(221, 107, 32, 0.15);
        border-left-color: #f6ad55;
    }

    .site-card-medium {
        background-color: rgba(214, 158, 46, 0.15);
        border-left-color: #ecc94b;
    }

    .site-card h4 {
        margin: 0 0 0.5rem 0;
        color: #e2e8f0;
        font-size: 1.05rem;
    }

    .site-card p {
        margin: 0.25rem 0;
        color: #cbd5e0;
        font-size: 0.9rem;
    }

    /* Priority badges */
    .priority-critical {
        background-color: #c53030;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .priority-high {
        background-color: #dd6b20;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .priority-medium {
        background-color: #d69e2e;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* AI insight box - dark mode */
    .ai-insight-box {
        background-color: rgba(49, 130, 206, 0.15);
        border: 1px solid #4299e1;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    .ai-insight-box p {
        color: #bee3f8;
        margin: 0;
        font-size: 0.9rem;
        line-height: 1.5;
    }

    /* Footer */
    .footer {
        text-align: center;
        color: #a0aec0;
        padding: 2rem 0 1rem 0;
        border-top: 1px solid #4a5568;
        margin-top: 2rem;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Dataframe styling */
    .dataframe {
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# COLOR SCHEME
# ============================================================================

COLORS = {
    'primary': '#3182ce',
    'secondary': '#805ad5',
    'success': '#38a169',
    'warning': '#d69e2e',
    'danger': '#c53030',
    'info': '#00b5d8',
    'light': '#f7fafc',
    'dark': '#1a202c',

    # Priority colors
    'CRITICAL': '#c53030',
    'HIGH': '#dd6b20',
    'MEDIUM': '#d69e2e',
    'LOW': '#38a169',

    # Chart palette
    'chart_palette': ['#3182ce', '#805ad5', '#38a169', '#d69e2e', '#c53030', '#00b5d8', '#ed64a6']
}

PRIORITY_COLORS = {
    'CRITICAL': '#c53030',
    'HIGH': '#dd6b20',
    'MEDIUM': '#d69e2e',
    'LOW': '#38a169'
}

# ============================================================================
# DATA LOADING
# ============================================================================

@st.cache_data
def get_data_path():
    """Determine the correct data path."""
    possible_paths = [
        Path('outputs'),
        Path('../outputs'),
        Path('src/outputs'),
    ]
    for path in possible_paths:
        if path.exists() and (path / 'recommendations_by_site.csv').exists():
            return path
    return Path('outputs')  # Default


@st.cache_data
def load_all_data():
    """Load all required data files."""
    data_path = get_data_path()

    try:
        # Load recommendations
        recommendations_df = pd.read_csv(data_path / 'recommendations_by_site.csv')

        # Load study data
        study_df = pd.read_csv(data_path / 'master_study.csv')

        # Load site data with DQI
        site_dqi_df = pd.read_csv(data_path / 'master_site_with_dqi.csv')

        # Load action items JSON
        with open(data_path / 'action_items.json', 'r', encoding='utf-8') as f:
            action_items = json.load(f)

        # Load executive summary
        exec_summary = ""
        exec_path = data_path / 'executive_summary.txt'
        if exec_path.exists():
            with open(exec_path, 'r', encoding='utf-8') as f:
                exec_summary = f.read()

        return {
            'recommendations': recommendations_df,
            'studies': study_df,
            'sites': site_dqi_df,
            'action_items': action_items,
            'executive_summary': exec_summary
        }

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.info(f"Looking for data in: {data_path.absolute()}")
        return None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_issue_summary(study_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate issue summary from study data."""
    issue_columns = {
        'sae_pending_count': ('SAE Pending', 'CRITICAL'),
        'missing_visit_count': ('Missing Visits', 'HIGH'),
        'lab_issues_count': ('Lab Issues', 'MEDIUM'),
        'missing_pages_count': ('Missing Pages', 'MEDIUM'),
        'inactivated_forms_count': ('Inactivated Forms', 'LOW'),
        'edrr_open_issues': ('EDRR Issues', 'LOW'),
        'total_uncoded_count': ('Uncoded Terms', 'HIGH'),
    }

    issues = []
    for col, (name, priority) in issue_columns.items():
        if col in study_df.columns:
            total = int(study_df[col].sum())
            if total > 0:
                issues.append({
                    'Category': name,
                    'Count': total,
                    'Priority': priority
                })

    return pd.DataFrame(issues).sort_values('Count', ascending=False)


def format_number(num):
    """Format large numbers with commas."""
    return f"{num:,}"


def get_priority_class(priority: str) -> str:
    """Get CSS class for priority level."""
    return f"priority-{priority.lower()}"


# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def create_priority_donut(df: pd.DataFrame) -> go.Figure:
    """Create a donut chart for priority distribution."""
    priority_counts = df['priority'].value_counts()

    # Ensure consistent order
    priority_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    values = [priority_counts.get(p, 0) for p in priority_order]
    colors = [PRIORITY_COLORS.get(p, '#gray') for p in priority_order]

    fig = go.Figure(data=[go.Pie(
        labels=priority_order,
        values=values,
        hole=0.5,
        marker_colors=colors,
        textinfo='label+percent',
        textposition='outside',
        textfont=dict(size=14, color='#e2e8f0'),
        hovertemplate='<b>%{label}</b><br>Sites: %{value}<br>Percentage: %{percent}<extra></extra>'
    )])

    fig.update_layout(
        showlegend=False,
        margin=dict(t=30, b=30, l=30, r=30),
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        annotations=[dict(
            text=f'<b>{len(df)}</b><br>Sites',
            x=0.5, y=0.5,
            font_size=20,
            font_color='#e2e8f0',
            showarrow=False
        )]
    )

    return fig


def create_region_bar(df: pd.DataFrame) -> go.Figure:
    """Create a bar chart for regional distribution."""
    region_counts = df['region'].value_counts().reset_index()
    region_counts.columns = ['Region', 'Count']

    fig = go.Figure(data=[go.Bar(
        x=region_counts['Region'],
        y=region_counts['Count'],
        marker_color=COLORS['primary'],
        marker_line_color=COLORS['primary'],
        marker_line_width=1,
        text=region_counts['Count'],
        textposition='outside',
        textfont=dict(size=14, color='#e2e8f0'),
        hovertemplate='<b>%{x}</b><br>Sites: %{y}<extra></extra>',
        cliponaxis=False
    )])

    fig.update_layout(
        xaxis_title='',
        yaxis_title='Number of Flagged Sites',
        margin=dict(t=50, b=60, l=80, r=30),
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            tickfont=dict(size=13, color='#cbd5e0'),
            gridcolor='#4a5568',
            title_font=dict(size=14, color='#e2e8f0')
        ),
        yaxis=dict(
            tickfont=dict(size=13, color='#cbd5e0'),
            gridcolor='#4a5568',
            title_font=dict(size=14, color='#e2e8f0'),
            range=[0, region_counts['Count'].max() * 1.15]
        ),
        font=dict(color='#e2e8f0')
    )

    return fig


def create_issue_bar(issue_df: pd.DataFrame) -> go.Figure:
    """Create a horizontal bar chart for issue categories."""
    if issue_df.empty:
        return go.Figure()

    colors = [PRIORITY_COLORS.get(p, '#gray') for p in issue_df['Priority']]

    fig = go.Figure(data=[go.Bar(
        y=issue_df['Category'],
        x=issue_df['Count'],
        orientation='h',
        marker_color=colors,
        text=[format_number(c) for c in issue_df['Count']],
        textposition='outside',
        textfont=dict(size=13, color='#e2e8f0'),
        hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>',
        cliponaxis=False
    )])

    fig.update_layout(
        xaxis_title='Number of Issues',
        yaxis_title='',
        margin=dict(t=30, b=60, l=180, r=120),
        height=450,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            tickfont=dict(size=13, color='#cbd5e0'),
            gridcolor='#4a5568',
            title_font=dict(size=14, color='#e2e8f0'),
            range=[0, issue_df['Count'].max() * 1.12]
        ),
        yaxis=dict(
            tickfont=dict(size=13, color='#cbd5e0'),
            autorange='reversed'
        ),
        font=dict(color='#e2e8f0')
    )

    return fig


def create_dqi_histogram(df: pd.DataFrame) -> go.Figure:
    """Create a histogram of DQI scores."""
    fig = go.Figure(data=[go.Histogram(
        x=df['avg_dqi_score'],
        nbinsx=30,
        marker_color=COLORS['primary'],
        marker_line_color='#4299e1',
        marker_line_width=1,
        opacity=0.85,
        hovertemplate='DQI Range: %{x}<br>Count: %{y}<extra></extra>'
    )])

    fig.update_layout(
        xaxis_title='DQI Score',
        yaxis_title='Number of Sites',
        margin=dict(t=30, b=60, l=80, r=30),
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            tickfont=dict(size=13, color='#cbd5e0'),
            gridcolor='#4a5568',
            title_font=dict(size=14, color='#e2e8f0')
        ),
        yaxis=dict(
            tickfont=dict(size=13, color='#cbd5e0'),
            gridcolor='#4a5568',
            title_font=dict(size=14, color='#e2e8f0')
        ),
        font=dict(color='#e2e8f0'),
        bargap=0.05
    )

    return fig


def create_study_comparison(study_df: pd.DataFrame) -> go.Figure:
    """Create a grouped bar chart comparing studies."""
    top_studies = study_df.nlargest(10, 'subject_count')

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Subjects per Study', 'Sites per Study'),
        horizontal_spacing=0.15
    )

    # Subjects bar
    fig.add_trace(
        go.Bar(
            x=top_studies['study'],
            y=top_studies['subject_count'],
            marker_color=COLORS['primary'],
            name='Subjects',
            text=top_studies['subject_count'],
            textposition='outside',
            textfont=dict(size=11, color='#e2e8f0'),
            hovertemplate='<b>%{x}</b><br>Subjects: %{y:,}<extra></extra>',
            cliponaxis=False
        ),
        row=1, col=1
    )

    # Sites bar
    fig.add_trace(
        go.Bar(
            x=top_studies['study'],
            y=top_studies['site_count'],
            marker_color=COLORS['secondary'],
            name='Sites',
            text=top_studies['site_count'],
            textposition='outside',
            textfont=dict(size=11, color='#e2e8f0'),
            hovertemplate='<b>%{x}</b><br>Sites: %{y:,}<extra></extra>',
            cliponaxis=False
        ),
        row=1, col=2
    )

    fig.update_layout(
        showlegend=False,
        margin=dict(t=70, b=120, l=80, r=30),
        height=500,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e2e8f0')
    )

    fig.update_xaxes(
        tickangle=-45,
        tickfont=dict(size=11, color='#cbd5e0'),
        gridcolor='#4a5568'
    )
    fig.update_yaxes(
        tickfont=dict(size=12, color='#cbd5e0'),
        gridcolor='#4a5568',
        range=[0, top_studies['subject_count'].max() * 1.15], row=1, col=1
    )
    fig.update_yaxes(
        tickfont=dict(size=12, color='#cbd5e0'),
        gridcolor='#4a5568',
        range=[0, top_studies['site_count'].max() * 1.15], row=1, col=2
    )

    # Update subplot titles
    fig.update_annotations(font=dict(size=14, color='#e2e8f0'))

    return fig


def create_sae_chart(study_df: pd.DataFrame) -> go.Figure:
    """Create SAE pending chart by study."""
    sae_data = study_df[study_df['sae_pending_count'] > 0].nlargest(10, 'sae_pending_count')

    if sae_data.empty:
        fig = go.Figure()
        fig.add_annotation(text="No pending SAE records", xref="paper", yref="paper",
                          x=0.5, y=0.5, showarrow=False, font=dict(size=14, color='#a0aec0'))
        return fig

    fig = go.Figure(data=[go.Bar(
        x=sae_data['study'],
        y=sae_data['sae_pending_count'],
        marker_color=COLORS['danger'],
        marker_line_color='#fc8181',
        marker_line_width=1,
        text=sae_data['sae_pending_count'],
        textposition='outside',
        textfont=dict(size=12, color='#e2e8f0'),
        hovertemplate='<b>%{x}</b><br>Pending SAE: %{y}<extra></extra>',
        cliponaxis=False
    )])

    fig.update_layout(
        xaxis_title='',
        yaxis_title='Pending SAE Count',
        margin=dict(t=50, b=100, l=80, r=30),
        height=450,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            tickangle=-45,
            tickfont=dict(size=12, color='#cbd5e0'),
            gridcolor='#4a5568'
        ),
        yaxis=dict(
            tickfont=dict(size=13, color='#cbd5e0'),
            gridcolor='#4a5568',
            title_font=dict(size=14, color='#e2e8f0'),
            range=[0, sae_data['sae_pending_count'].max() * 1.15]
        ),
        font=dict(color='#e2e8f0')
    )

    return fig


def create_heatmap(study_df: pd.DataFrame) -> go.Figure:
    """Create a heatmap of issues by study."""
    metrics = ['sae_pending_count', 'missing_visit_count', 'lab_issues_count',
               'missing_pages_count', 'inactivated_forms_count']

    available_metrics = [m for m in metrics if m in study_df.columns]

    if not available_metrics:
        return go.Figure()

    # Get top studies by total issues
    study_df_copy = study_df.copy()
    study_df_copy['total_issues'] = study_df_copy[available_metrics].sum(axis=1)
    top_studies = study_df_copy.nlargest(12, 'total_issues')

    # Prepare heatmap data
    heatmap_data = top_studies[available_metrics].T
    heatmap_data.columns = top_studies['study']

    # Clean metric names
    metric_labels = [m.replace('_count', '').replace('_', ' ').title() for m in available_metrics]

    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns,
        y=metric_labels,
        colorscale='Reds',
        text=heatmap_data.values,
        texttemplate='%{text:.0f}',
        textfont=dict(size=11, color='#1a202c'),
        hovertemplate='Study: %{x}<br>Metric: %{y}<br>Count: %{z}<extra></extra>'
    ))

    fig.update_layout(
        margin=dict(t=30, b=120, l=150, r=30),
        height=450,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            tickangle=-45,
            tickfont=dict(size=11, color='#cbd5e0')
        ),
        yaxis=dict(
            tickfont=dict(size=12, color='#cbd5e0')
        ),
        font=dict(color='#e2e8f0')
    )

    return fig


# ============================================================================
# PAGE RENDERERS
# ============================================================================

def render_executive_overview(data: dict):
    """Render the Executive Overview page."""
    st.markdown('<div class="section-header">Portfolio Overview</div>', unsafe_allow_html=True)

    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    summary = data['action_items'].get('summary', {})
    study_df = data['studies']
    rec_df = data['recommendations']

    total_subjects = study_df['subject_count'].sum()
    total_sites = study_df['site_count'].sum()
    total_studies = len(study_df)
    critical_sites = len(rec_df[rec_df['priority'] == 'CRITICAL'])
    pending_sae = study_df['sae_pending_count'].sum()

    with col1:
        st.metric("Total Studies", format_number(total_studies))
    with col2:
        st.metric("Total Subjects", format_number(int(total_subjects)))
    with col3:
        st.metric("Total Sites", format_number(int(total_sites)))
    with col4:
        st.metric("Critical Sites", format_number(critical_sites), delta=None)
    with col5:
        st.metric("Pending SAE", format_number(int(pending_sae)), delta=None)

    st.markdown("---")

    # Charts row 1
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-header">Sites by Priority Level</div>', unsafe_allow_html=True)
        fig = create_priority_donut(rec_df)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<div class="section-header">Flagged Sites by Region</div>', unsafe_allow_html=True)
        fig = create_region_bar(rec_df)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Issue summary
    st.markdown('<div class="section-header">Issue Categories Across Portfolio</div>', unsafe_allow_html=True)
    issue_df = calculate_issue_summary(study_df)
    if not issue_df.empty:
        fig = create_issue_bar(issue_df)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # AI Insight
    exec_summary = data['executive_summary']
    if "AI-GENERATED INSIGHT" in exec_summary:
        st.markdown('<div class="section-header">AI-Generated Executive Insight</div>', unsafe_allow_html=True)
        try:
            insight = exec_summary.split("AI-GENERATED INSIGHT")[1].split("CRITICAL ITEMS")[0]
            insight = insight.replace("-" * 20, "").strip()
            st.markdown(f'<div class="ai-insight-box"><p>{insight}</p></div>', unsafe_allow_html=True)
        except:
            pass


def render_site_analysis(data: dict, filtered_df: pd.DataFrame):
    """Render the Site Analysis page."""
    st.markdown('<div class="section-header">High Priority Sites</div>', unsafe_allow_html=True)

    # Top critical sites
    critical_high = filtered_df[filtered_df['priority'].isin(['CRITICAL', 'HIGH'])].nlargest(15, 'avg_dqi_score')

    for _, row in critical_high.iterrows():
        priority = row['priority']
        card_class = f"site-card site-card-{priority.lower()}"

        st.markdown(f"""
        <div class="{card_class}">
            <h4><span class="priority-{priority.lower()}">{priority}</span> {row['study']} - {row['site_id']} ({row['country']})</h4>
            <p><strong>DQI Score:</strong> {row['avg_dqi_score']:.3f} | 
               <strong>High-Risk Subjects:</strong> {row['high_risk_count']}/{row['subject_count']} | 
               <strong>Top Issue:</strong> {str(row['top_issue']).replace('_', ' ').title()}</p>
            <p><strong>Recommended Action:</strong> {row['top_recommendation']}</p>
        </div>
        """, unsafe_allow_html=True)

        # AI insight expander
        if pd.notna(row.get('ai_insight')) and len(str(row.get('ai_insight', ''))) > 20:
            with st.expander("View AI Analysis"):
                st.markdown(f'<div class="ai-insight-box"><p>{row["ai_insight"]}</p></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Distribution charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-header">DQI Score Distribution</div>', unsafe_allow_html=True)
        fig = create_dqi_histogram(filtered_df)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<div class="section-header">High-Risk Subjects by Priority</div>', unsafe_allow_html=True)
        priority_risk = filtered_df.groupby('priority')['high_risk_count'].sum().reset_index()

        # Ensure order
        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        priority_risk['order'] = priority_risk['priority'].map(priority_order)
        priority_risk = priority_risk.sort_values('order')

        colors = [PRIORITY_COLORS.get(p, '#gray') for p in priority_risk['priority']]

        fig = go.Figure(data=[go.Bar(
            x=priority_risk['priority'],
            y=priority_risk['high_risk_count'],
            marker_color=colors,
            text=priority_risk['high_risk_count'],
            textposition='outside',
            textfont=dict(size=13, color='#e2e8f0'),
            cliponaxis=False
        )])

        fig.update_layout(
            xaxis_title='Priority Level',
            yaxis_title='High-Risk Subjects',
            margin=dict(t=50, b=60, l=80, r=30),
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickfont=dict(size=13, color='#cbd5e0'),
                gridcolor='#4a5568',
                title_font=dict(size=14, color='#e2e8f0')
            ),
            yaxis=dict(
                tickfont=dict(size=13, color='#cbd5e0'),
                gridcolor='#4a5568',
                title_font=dict(size=14, color='#e2e8f0'),
                range=[0, priority_risk['high_risk_count'].max() * 1.15]
            ),
            font=dict(color='#e2e8f0')
        )

        st.plotly_chart(fig, use_container_width=True)


def render_study_analysis(data: dict):
    """Render the Study Analysis page."""
    study_df = data['studies']

    st.markdown('<div class="section-header">Study Comparison</div>', unsafe_allow_html=True)
    fig = create_study_comparison(study_df)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    st.markdown('<div class="section-header">Issue Heatmap by Study</div>', unsafe_allow_html=True)
    fig = create_heatmap(study_df)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Study metrics table
    st.markdown('<div class="section-header">Study Metrics Summary</div>', unsafe_allow_html=True)

    display_cols = ['study', 'subject_count', 'site_count', 'sae_pending_count',
                    'missing_visit_count', 'lab_issues_count', 'missing_pages_count']
    available_cols = [c for c in display_cols if c in study_df.columns]

    st.dataframe(
        study_df[available_cols].sort_values('sae_pending_count', ascending=False),
        use_container_width=True,
        height=400
    )


def render_critical_actions(data: dict):
    """Render the Critical Actions page."""
    study_df = data['studies']
    action_items = data['action_items']

    # SAE Summary
    st.markdown('<div class="section-header">Pending SAE Reviews</div>', unsafe_allow_html=True)

    total_sae = study_df['sae_pending_count'].sum()
    studies_with_sae = len(study_df[study_df['sae_pending_count'] > 0])
    critical_sae_studies = len(study_df[study_df['sae_pending_count'] > 50])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Pending SAE", format_number(int(total_sae)))
    with col2:
        st.metric("Studies Affected", format_number(studies_with_sae))
    with col3:
        st.metric("Critical SAE Studies (>50)", format_number(critical_sae_studies))

    fig = create_sae_chart(study_df)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Critical study actions
    st.markdown('<div class="section-header">Critical Study Actions</div>', unsafe_allow_html=True)

    study_recommendations = action_items.get('study_recommendations', [])
    critical_studies = [s for s in study_recommendations if s.get('priority') == 'CRITICAL']

    if critical_studies:
        for study in critical_studies[:10]:
            recommendations = study.get('recommendations', [])
            rec_html = ""
            if recommendations:
                rec_html = "<ul style='margin: 0.5rem 0 0 1.5rem; color: #cbd5e0;'>"
                for rec in recommendations:
                    rec_html += f"<li style='margin: 0.25rem 0; font-size: 0.9rem;'>{rec}</li>"
                rec_html += "</ul>"

            st.markdown(f"""
            <div class="site-card site-card-critical">
                <h4><span class="priority-critical">CRITICAL</span> {study.get('study', 'N/A')}</h4>
                <p><strong>Sites:</strong> {study.get('n_sites', 0)} | 
                   <strong>Subjects:</strong> {study.get('n_subjects', 0)} | 
                   <strong>High-Risk:</strong> {study.get('total_high_risk', 0)} | 
                   <strong>Avg DQI:</strong> {study.get('avg_dqi', 0):.3f}</p>
                {rec_html}
            </div>
            """, unsafe_allow_html=True)

            # AI insight
            if study.get('ai_insight'):
                with st.expander("View AI Analysis"):
                    st.markdown(f'<div class="ai-insight-box"><p>{study["ai_insight"]}</p></div>', unsafe_allow_html=True)
    else:
        st.info("No critical study actions at this time.")


def render_detailed_reports(data: dict, filtered_df: pd.DataFrame):
    """Render the Detailed Reports page."""
    st.markdown('<div class="section-header">Site Recommendations Data</div>', unsafe_allow_html=True)

    display_cols = ['study', 'site_id', 'country', 'region', 'priority',
                    'subject_count', 'high_risk_count', 'avg_dqi_score', 'top_issue']
    available_cols = [c for c in display_cols if c in filtered_df.columns]

    # Sort by priority then DQI
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    sorted_df = filtered_df.copy()
    sorted_df['priority_order'] = sorted_df['priority'].map(priority_order)
    sorted_df = sorted_df.sort_values(['priority_order', 'avg_dqi_score'], ascending=[True, False])

    st.dataframe(
        sorted_df[available_cols],
        use_container_width=True,
        height=450
    )

    st.markdown("---")

    # Downloads
    st.markdown('<div class="section-header">Download Reports</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        csv_data = filtered_df.to_csv(index=False)
        st.download_button(
            label="Download Site Recommendations (CSV)",
            data=csv_data,
            file_name="site_recommendations.csv",
            mime="text/csv"
        )

    with col2:
        st.download_button(
            label="Download Executive Summary (TXT)",
            data=data['executive_summary'],
            file_name="executive_summary.txt",
            mime="text/plain"
        )

    with col3:
        json_data = json.dumps(data['action_items'], indent=2)
        st.download_button(
            label="Download Action Items (JSON)",
            data=json_data,
            file_name="action_items.json",
            mime="application/json"
        )

    st.markdown("---")

    # Executive summary preview
    st.markdown('<div class="section-header">Executive Summary</div>', unsafe_allow_html=True)

    with st.expander("View Full Executive Summary", expanded=False):
        st.text(data['executive_summary'])


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    # Load data
    data = load_all_data()

    if data is None:
        st.stop()

    # Header
    st.markdown('<div class="main-header">JAVELIN.AI - Clinical Trial Data Quality Dashboard</div>', unsafe_allow_html=True)

    gen_time = data['action_items'].get('generated_at', '')
    ai_model = data['action_items'].get('ai_model', '')

    if gen_time:
        st.markdown(f"**Last Updated:** {gen_time[:19].replace('T', ' ')} | **AI Model:** {ai_model or 'N/A'}")

    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.markdown("### Navigation")

        page = st.radio(
            "Select View:",
            ["Executive Overview", "Site Analysis", "Study Analysis", "Critical Actions", "Detailed Reports"],
            label_visibility="collapsed"
        )

        st.markdown("---")
        st.markdown("### Filters")

        rec_df = data['recommendations']

        # Study filter
        selected_studies = st.multiselect(
            "Studies:",
            options=sorted(rec_df['study'].unique()),
            default=None
        )

        # Priority filter
        selected_priority = st.multiselect(
            "Priority:",
            options=['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
            default=None
        )

        # Region filter
        selected_regions = st.multiselect(
            "Regions:",
            options=sorted(rec_df['region'].unique()),
            default=None
        )

        st.markdown("---")
        st.markdown("### Quick Stats")
        st.markdown(f"**Flagged Sites:** {len(rec_df)}")
        st.markdown(f"**Critical:** {len(rec_df[rec_df['priority'] == 'CRITICAL'])}")
        st.markdown(f"**High:** {len(rec_df[rec_df['priority'] == 'HIGH'])}")

    # Apply filters
    filtered_df = rec_df.copy()
    if selected_studies:
        filtered_df = filtered_df[filtered_df['study'].isin(selected_studies)]
    if selected_priority:
        filtered_df = filtered_df[filtered_df['priority'].isin(selected_priority)]
    if selected_regions:
        filtered_df = filtered_df[filtered_df['region'].isin(selected_regions)]

    # Render selected page
    if page == "Executive Overview":
        render_executive_overview(data)
    elif page == "Site Analysis":
        render_site_analysis(data, filtered_df)
    elif page == "Study Analysis":
        render_study_analysis(data)
    elif page == "Critical Actions":
        render_critical_actions(data)
    elif page == "Detailed Reports":
        render_detailed_reports(data, filtered_df)

    # Footer
    st.markdown("""
    <div class="footer">
        <p><strong>JAVELIN.AI</strong> - Clinical Trial Data Quality Intelligence</p>
        <p>Powered by Domain Knowledge + Local LLM (Ollama)</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
