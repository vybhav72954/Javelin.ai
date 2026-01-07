import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime
import os

st.set_page_config(
    page_title="JAVELIN.AI - Data Quality Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem;
    }
    .site-card {
        padding: 0.75rem;
        border-radius: 0.3rem;
        margin-bottom: 0.75rem;
    }
    .site-card h4 {
        margin: 0 0 0.5rem 0;
        font-size: 1.1rem;
    }
    .site-card p {
        margin: 0.25rem 0;
        color: #333;
        font-size: 0.9rem;
    }
    .critical-card {
        background-color: #ffebee;
        padding: 0.75rem;
        border-radius: 0.3rem;
        border-left: 3px solid #d32f2f;
        margin-bottom: 0.75rem;
    }
    .critical-card h4 {
        margin: 0 0 0.5rem 0;
        color: #d32f2f;
        font-size: 1.1rem;
    }
    .critical-card p {
        margin: 0.25rem 0;
        color: #333;
        font-size: 0.9rem;
    }
    .action-list {
        margin: 0.5rem 0 0 1rem;
        color: #333;
    }
    .action-list li {
        margin: 0.25rem 0;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

if os.path.exists('../outputs'):
    OUTPUT_DIR = '../outputs'
    DATA_DIR = '../data'
else:
    OUTPUT_DIR = 'outputs'
    DATA_DIR = 'data'

@st.cache_data
def load_data():
    try:
        recommendations = pd.read_csv(f'{OUTPUT_DIR}/recommendations_by_site.csv')

        if os.path.exists(f'{OUTPUT_DIR}/master_study.csv'):
            study_data = pd.read_csv(f'{OUTPUT_DIR}/master_study.csv')
        else:
            study_data = pd.read_csv(f'{DATA_DIR}/master_study.csv')

        with open(f'{OUTPUT_DIR}/action_items.json', 'r') as f:
            action_items = json.load(f)

        with open(f'{OUTPUT_DIR}/executive_summary.txt', 'r') as f:
            exec_summary = f.read()

        return recommendations, study_data, action_items, exec_summary
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.info(f"Make sure files exist in: {OUTPUT_DIR}")
        return None, None, None, None

recommendations_df, study_df, action_items, exec_summary = load_data()

if recommendations_df is None:
    st.stop()

st.markdown('<div class="main-header">JAVELIN.AI - Clinical Trial Data Quality Dashboard</div>', unsafe_allow_html=True)
st.markdown(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("---")

with st.sidebar:
    st.header("Filters & Navigation")

    page = st.radio(
        "Select View:",
        ["Executive Overview", "Site Analysis", "Study Analysis", "Critical Actions", "Detailed Reports"]
    )

    st.markdown("---")

    st.subheader("Filters")
    selected_studies = st.multiselect(
        "Select Studies:",
        options=sorted(recommendations_df['study'].unique()),
        default=None
    )

    selected_priority = st.multiselect(
        "Priority Level:",
        options=sorted(recommendations_df['priority'].unique()),
        default=None
    )

    selected_regions = st.multiselect(
        "Regions:",
        options=sorted(recommendations_df['region'].unique()),
        default=None
    )

filtered_df = recommendations_df.copy()
if selected_studies:
    filtered_df = filtered_df[filtered_df['study'].isin(selected_studies)]
if selected_priority:
    filtered_df = filtered_df[filtered_df['priority'].isin(selected_priority)]
if selected_regions:
    filtered_df = filtered_df[filtered_df['region'].isin(selected_regions)]

if page == "Executive Overview":
    st.header("Executive Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Studies", len(study_df))

    with col2:
        total_subjects = study_df['subject_count'].sum()
        st.metric("Total Subjects", f"{total_subjects:,}")

    with col3:
        total_sites = study_df['site_count'].sum()
        st.metric("Total Sites", f"{total_sites:,}")

    with col4:
        critical_sites = len(filtered_df[filtered_df['priority'] == 'CRITICAL'])
        st.metric("Critical Sites", critical_sites)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sites by Priority Level")
        priority_counts = filtered_df['priority'].value_counts()
        fig_priority = px.pie(
            values=priority_counts.values,
            names=priority_counts.index,
            color=priority_counts.index,
            color_discrete_map={
                'CRITICAL': '#d32f2f',
                'HIGH': '#f57c00',
                'MEDIUM': '#fbc02d',
                'LOW': '#388e3c'
            },
            hole=0.4
        )
        fig_priority.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_priority, use_container_width=True)

    with col2:
        st.subheader("Sites by Region")
        region_counts = filtered_df['region'].value_counts()
        fig_region = px.bar(
            x=region_counts.index,
            y=region_counts.values,
            labels={'x': 'Region', 'y': 'Number of Sites'},
            color=region_counts.values,
            color_continuous_scale='Blues'
        )
        fig_region.update_layout(showlegend=False)
        st.plotly_chart(fig_region, use_container_width=True)

    st.markdown("---")

    st.subheader("Top Issue Categories Across Portfolio")
    issue_data = {
        'Category': ['Max Days Outstanding', 'Lab Issues', 'SAE Pending', 'Missing Pages', 'Inactivated Forms',
                     'Missing Visits', 'EDRR Issues', 'Uncoded WHODD', 'Uncoded MedDRA'],
        'Count': [29694, 7427, 5407, 2569, 4558, 867, 475, 418, 303],
        'Priority': ['MEDIUM', 'MEDIUM', 'CRITICAL', 'MEDIUM', 'LOW', 'HIGH', 'LOW', 'LOW', 'HIGH']
    }
    issue_df = pd.DataFrame(issue_data)

    fig_issues = px.bar(
        issue_df,
        x='Category',
        y='Count',
        color='Priority',
        color_discrete_map={
            'CRITICAL': '#d32f2f',
            'HIGH': '#f57c00',
            'MEDIUM': '#fbc02d',
            'LOW': '#388e3c'
        },
        text='Count'
    )
    fig_issues.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    fig_issues.update_layout(xaxis_tickangle=-45, height=500)
    st.plotly_chart(fig_issues, use_container_width=True)

    st.markdown("---")

    st.subheader("AI-Generated Executive Insight")
    if "AI-GENERATED INSIGHT" in exec_summary:
        insight_section = exec_summary.split("AI-GENERATED INSIGHT")[1].split("CRITICAL ITEMS")[0]
        st.info(insight_section.strip())

elif page == "Site Analysis":
    st.header("Site-Level Analysis")

    st.subheader("Top 20 Critical Sites")
    top_critical = filtered_df[filtered_df['priority'].isin(['CRITICAL', 'HIGH'])].nlargest(20, 'avg_dqi_score')

    for idx, row in top_critical.iterrows():
        priority_color = "#d32f2f" if row['priority'] == 'CRITICAL' else "#f57c00"
        bg_color = "#ffebee" if row['priority'] == 'CRITICAL' else "#fff3e0"

        st.markdown(f"""
        <div class="site-card" style="background-color: {bg_color}; border-left: 3px solid {priority_color};">
            <h4 style="color: {priority_color};">[{row['priority']}] {row['study']} - {row['site_id']} ({row['country']})</h4>
            <p><strong>DQI:</strong> {row['avg_dqi_score']:.3f} | 
               <strong>High-Risk:</strong> {row['high_risk_count']}/{row['subject_count']} | 
               <strong>Issue:</strong> {row['top_issue']}</p>
            <p><strong>Action:</strong> {row['top_recommendation']}</p>
        </div>
        """, unsafe_allow_html=True)

        if pd.notna(row['ai_insight']) and len(str(row['ai_insight'])) > 50:
            with st.expander("View AI Insight"):
                st.write(row['ai_insight'])

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("DQI Score Distribution")
        fig_dqi = px.histogram(
            filtered_df,
            x='avg_dqi_score',
            nbins=30,
            labels={'avg_dqi_score': 'DQI Score'},
            color_discrete_sequence=['#1f77b4']
        )
        fig_dqi.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_dqi, use_container_width=True)

    with col2:
        st.subheader("High-Risk Subjects by Priority")
        priority_risk = filtered_df.groupby('priority')['high_risk_count'].sum().reset_index()
        fig_risk_bar = px.bar(
            priority_risk,
            x='priority',
            y='high_risk_count',
            color='priority',
            color_discrete_map={
                'CRITICAL': '#d32f2f',
                'HIGH': '#f57c00',
                'MEDIUM': '#fbc02d',
                'LOW': '#388e3c'
            },
            labels={'high_risk_count': 'High-Risk Subjects', 'priority': 'Priority Level'}
        )
        fig_risk_bar.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_risk_bar, use_container_width=True)

elif page == "Study Analysis":
    st.header("Study-Level Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Studies by Subject Count")
        top_studies = study_df.nlargest(10, 'subject_count')
        fig_subjects = px.bar(
            top_studies,
            x='study',
            y='subject_count',
            color='subject_count',
            color_continuous_scale='Blues',
            labels={'subject_count': 'Number of Subjects'}
        )
        fig_subjects.update_layout(xaxis_tickangle=-45, showlegend=False, height=400)
        st.plotly_chart(fig_subjects, use_container_width=True)

    with col2:
        st.subheader("Top Studies by Site Count")
        top_sites_study = study_df.nlargest(10, 'site_count')
        fig_sites = px.bar(
            top_sites_study,
            x='study',
            y='site_count',
            color='site_count',
            color_continuous_scale='Greens',
            labels={'site_count': 'Number of Sites'}
        )
        fig_sites.update_layout(xaxis_tickangle=-45, showlegend=False, height=400)
        st.plotly_chart(fig_sites, use_container_width=True)

    st.markdown("---")

    st.subheader("Critical Metrics by Study")

    study_metrics = study_df[['study', 'sae_pending_count', 'missing_visit_count',
                               'lab_issues_count', 'missing_pages_count']].set_index('study')

    study_metrics_sorted = study_metrics.sort_values('sae_pending_count', ascending=False).head(15)

    fig_heatmap = px.imshow(
        study_metrics_sorted.T,
        labels=dict(x="Study", y="Metric", color="Count"),
        color_continuous_scale='Reds',
        aspect='auto',
        text_auto=True
    )
    fig_heatmap.update_layout(height=400)
    fig_heatmap.update_xaxes(tickangle=-45)
    st.plotly_chart(fig_heatmap, use_container_width=True)

elif page == "Critical Actions":
    st.header("Critical Actions Required")

    if isinstance(action_items, dict):
        study_actions = action_items.get('study_recommendations', [])
    else:
        study_actions = []

    critical_studies = [s for s in study_actions if s.get('priority') == 'CRITICAL']

    if critical_studies:
        for study in critical_studies[:10]:
            actions_html = ""
            if study.get('recommendations'):
                actions_html = "<ul class='action-list'>"
                for rec in study['recommendations']:
                    actions_html += f"<li>{rec}</li>"
                actions_html += "</ul>"

            st.markdown(f"""
            <div class="critical-card">
                <h4>{study.get('study', 'N/A')}</h4>
                <p><strong>Sites:</strong> {study.get('n_sites', 0)} | 
                   <strong>Subjects:</strong> {study.get('n_subjects', 0)} | 
                   <strong>High-Risk:</strong> {study.get('total_high_risk', 0)} | 
                   <strong>Avg DQI:</strong> {study.get('avg_dqi', 0):.3f}</p>
                {actions_html}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No critical study actions found.")

    st.markdown("---")

    st.subheader("Pending SAE Reviews")
    total_pending_sae = study_df['sae_pending_count'].sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Pending SAEs", f"{total_pending_sae:,}")
    with col2:
        studies_with_sae = len(study_df[study_df['sae_pending_count'] > 0])
        st.metric("Studies Affected", studies_with_sae)
    with col3:
        critical_sae = len(study_df[study_df['sae_pending_count'] > 100])
        st.metric("Critical SAE Studies", critical_sae)

    sae_studies = study_df[study_df['sae_pending_count'] > 0].nlargest(10, 'sae_pending_count')
    fig_sae = px.bar(
        sae_studies,
        x='study',
        y='sae_pending_count',
        color='sae_pending_count',
        color_continuous_scale='Reds',
        labels={'sae_pending_count': 'Pending SAE Count'},
        text='sae_pending_count'
    )
    fig_sae.update_traces(texttemplate='%{text}', textposition='outside')
    fig_sae.update_layout(xaxis_tickangle=-45, showlegend=False, height=400)
    st.plotly_chart(fig_sae, use_container_width=True)

elif page == "Detailed Reports":
    st.header("Detailed Reports")

    st.subheader("Site Recommendations")

    display_cols = ['study', 'site_id', 'country', 'region', 'priority',
                    'subject_count', 'high_risk_count', 'avg_dqi_score', 'top_issue']

    st.dataframe(
        filtered_df[display_cols].sort_values(['priority', 'avg_dqi_score'], ascending=[True, False]),
        use_container_width=True,
        height=400
    )

    st.markdown("---")

    st.subheader("Download Reports")

    col1, col2, col3 = st.columns(3)

    with col1:
        csv_recommendations = filtered_df.to_csv(index=False)
        st.download_button(
            label="Download Site Recommendations (CSV)",
            data=csv_recommendations,
            file_name="site_recommendations.csv",
            mime="text/csv"
        )

    with col2:
        st.download_button(
            label="Download Executive Summary (TXT)",
            data=exec_summary,
            file_name="executive_summary.txt",
            mime="text/plain"
        )

    with col3:
        json_actions = json.dumps(action_items, indent=2)
        st.download_button(
            label="Download Action Items (JSON)",
            data=json_actions,
            file_name="action_items.json",
            mime="application/json"
        )

    st.markdown("---")

    st.subheader("Executive Summary Preview")

    if "OVERVIEW" in exec_summary and "CRITICAL ITEMS" in exec_summary:
        overview = exec_summary.split("OVERVIEW")[1].split("AI-GENERATED INSIGHT")[0]
        st.text(overview.strip())

        with st.expander("View Full Executive Summary"):
            st.text(exec_summary)
    else:
        with st.expander("View Executive Summary"):
            st.text(exec_summary)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    <p><strong>JAVELIN.AI - Clinical Trial Data Quality Engine</strong></p>
    <p>Powered by Ollama (Mistral) | Generated with Streamlit</p>
</div>
""", unsafe_allow_html=True)
