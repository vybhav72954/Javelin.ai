# JAVELIN.AI Dashboard Guide

## Charts, Insights & How to Read Them

> ⚠️ **IMPORTANT: This dashboard is designed for Dark Mode.** Enable dark mode in your Streamlit settings or system preferences for optimal visibility.

---

## Table of Contents

1. [Command Center](#1-command-center)
2. [Risk Landscape](#2-risk-landscape)
3. [Patterns & Signals](#3-patterns--signals)
4. [Root Causes](#4-root-causes)
5. [Action Center](#5-action-center)
6. [Deep Dive](#6-deep-dive)
7. [Understanding DQI Scores](#understanding-dqi-scores)
8. [Color Coding Reference](#color-coding-reference)

---

## 1. Command Center

*Question it answers: "Is my portfolio healthy? What needs my attention?"*

### Portfolio Health Score (Gauge)

A 0-100 score representing overall portfolio health.

**How it's calculated:**
```
Weighted Score = (High-Risk Subjects × 1.0 + Medium-Risk Subjects × 0.3) / Total Subjects
Health Score = 100 × (1 - Weighted Score)
```

**How to read it:**
| Score | Status | Meaning |
|-------|--------|---------|
| 85-100 | HEALTHY | Portfolio performing well |
| 70-84 | MODERATE | Some areas need attention |
| 50-69 | AT RISK | Significant issues detected |
| 0-49 | CRITICAL | Urgent intervention required |

### Metric Cards (Studies / Sites / Subjects)

Three cards showing portfolio composition with risk breakdowns.

**Studies breakdown:**
- **Critical** (red): Studies with ≥20% high-risk subjects
- **At Risk** (orange): Studies with 10-19% high-risk subjects  
- **Healthy** (green): Studies with <10% high-risk subjects

**Sites/Subjects breakdown:**
- **High Risk** (red): Classified as high-risk by DQI scoring
- **Medium** (orange): Moderate data quality issues
- **Low** (green): Within acceptable thresholds

### Critical Alerts

Automatically generated alerts from multiple pipeline phases:
- **SAE Pending** (from Phase 03): Serious Adverse Events awaiting review
- **Root Cause Alerts** (from Phase 09): Critical systemic issues
- **Anomaly Alerts** (from Phase 06): Unusual patterns detected
- **Cluster Alerts** (from Phase 08): Sites in critical behavioral clusters

### Studies by Risk (Horizontal Bar Chart)

Top 10 studies ranked by percentage of high-risk subjects.

**How to read:**
- **Red bars**: Studies exceeding 25% high-risk threshold
- **Orange bars**: Studies between 15-25% high-risk
- **Green bars**: Studies below 15% high-risk
- Bar length = percentage of subjects classified as high-risk

### Top Issues (Issue List)

Aggregated issue counts across all subjects, ranked by volume.

**Color coding:**
- 🔴 Red: Safety-related (SAE pending)
- 🟠 Orange: Completeness issues (missing visits, pages)
- 🔵 Blue: Other data quality issues

### AI-Powered Insights

Two insight boxes powered by different AI analysis:
- **Multi-Agent Analysis**: Consensus from Safety, Data Quality, and Performance AI agents
- **Cluster Analysis**: Pattern-based insights from GMM clustering

---

## 2. Risk Landscape

*Question it answers: "Where are the problems concentrated?"*

### Geographic Tab

#### Global Risk Distribution (World Map)

Interactive scatter-geo visualization showing site distribution worldwide.

**How to read:**
- **Bubble size**: Number of sites in that country
- **Bubble color**: Average DQI score (red = higher risk, green = lower)
- Hover for exact values

#### Regional Summary (Cards)

Four region cards showing relative performance.

**Indicators:**
- **↑X% above**: Region is X% worse than portfolio average (concern)
- **↓X% below**: Region is X% better than portfolio average (good)
- **≈ avg**: Region is near portfolio average

#### Top 10 Countries by Risk (Table)

Countries ranked by average DQI score (highest = worst).

**Columns:**
- **Country**: ISO-3 country code
- **Sites**: Number of sites in that country
- **Avg DQI**: Average Data Quality Index (higher = more issues)

#### Geographic Concentration Insight

Appears when a region is >10% above portfolio average. Suggests region-specific interventions.

### Studies Tab

#### Study Portfolio Overview (Treemap)

Visual representation of all studies sized by subject count.

**How to read:**
- **Block size**: Proportional to number of subjects
- **Color**: Risk category
  - 🔴 Red: High-risk (≥20% high-risk subjects)
  - 🟠 Orange: Medium-risk (10-19%)
  - 🟢 Green: Low-risk (<10%)

#### Study Risk Ranking (Table)

Top 15 studies ranked by average DQI score.

#### Study Concentration Insight

Highlights studies exceeding 20% high-risk threshold with multi-agent consensus.

---

## 3. Patterns & Signals

*Question it answers: "What unusual behaviors are occurring?"*

### Summary Metrics (4 Cards)

| Metric | Source | Meaning |
|--------|--------|---------|
| Total Anomalies | Phase 06 | Count of detected anomalous patterns |
| Sites Affected | Phase 06 | Unique sites with anomalies |
| Clusters | Phase 08 | Number of behavioral site groups |
| Critical Clusters | Phase 08 | Groups needing immediate attention |

### Anomaly Detection Tab

#### Anomaly Score Distribution (Scatter Plot)

X-axis: Average DQI Score | Y-axis: Anomaly Score

**How to read:**
- **Upper-right quadrant**: Highest priority - high DQI AND high anomaly score
- **Red dashed line**: 90th percentile threshold for anomaly scores
- Points above the line are statistically unusual
- Hover for site details

#### Anomaly Types (Progress Bars)

Breakdown of anomaly categories with counts:
- **Pattern Anomaly**: Unusual behavioral patterns
- **Statistical Outlier**: Values beyond expected ranges
- **Cross Study Anomaly**: Issues spanning multiple studies
- **Velocity Anomaly**: Unusual data entry speeds
- **Regional Anomaly**: Geographic clustering of issues

#### Severity Breakdown

Distribution of anomalies by severity level (Critical, High, Medium, Low).

#### Top Anomalous Sites (Cards)

8 sites with highest anomaly scores showing:
- Site ID and study
- Number of critical anomalies
- Brief description of detected issues

### Site Clustering Tab

#### Site Cluster Distribution (Horizontal Bar Chart)

Shows how sites group into behavioral clusters.

**How to read:**
- Bar length = number of sites in cluster
- **Red**: Critical priority clusters
- **Orange**: High priority clusters
- **Green**: Low priority (benchmark) clusters

#### Cluster Profiles (Cards)

Top 5 clusters by intervention priority showing:
- Cluster name and risk level
- Site count and average DQI
- Dominant issues in that cluster

#### Clustering Insight

Explains clustering methodology and identifies benchmark clusters.

---

## 4. Root Causes

*Question it answers: "Why are problems occurring?"*

### Impact Metrics (4 Cards)

| Metric | Meaning |
|--------|---------|
| Root Causes | Number of identified systemic issues |
| Sites Affected | Total sites impacted by root causes |
| Subjects Impacted | Total subjects affected |
| Potential Reduction | Projected high-risk reduction if addressed |

### Projected Impact Insight

Shows potential 47% reduction in high-risk subjects if all root causes are addressed.

### Root Cause Cards

Each card contains:
- **Category**: Type of root cause (Safety, Operational, etc.)
- **Description**: What the root cause is
- **Severity badge**: Critical (red), High (orange), Medium (blue)
- **Confidence**: Statistical confidence in the finding
- **Sites/Subjects**: Scope of impact
- **Evidence**: Supporting data points
- **Recommended Actions**: Expandable list with impact estimates

### Issue Co-occurrence Patterns (Heatmap)

Matrix showing how often different issues appear together.

**How to read:**
- 🔴 **Red cells**: Strong correlation (>0.6) - issues often appear together
- 🟣 **Purple cells**: Moderate correlation (0.3-0.6)
- 🔵 **Blue cells**: Weak correlation (<0.3)
- **Diagonal**: Always shows self-correlation (ignore)

**Interpretation:**
Strongly correlated issues likely share a root cause. Fixing one may resolve the other.

### Co-occurrence Pattern Insight

Identifies the strongest issue pair correlation and suggests shared root cause investigation.

---

## 5. Action Center

*Question it answers: "What should I do next?"*

### Impact Projection (3 Green Cards)

Shows projected improvements if actions are completed:
- **High-Risk Subjects**: Current → Projected count
- **Portfolio Health**: Current → Projected score
- **Risk Reduction**: Percentage decrease expected

### Action Lists

Actions are prioritized into three urgency levels:

#### 🔴 IMMEDIATE
Actions requiring same-day attention. Sources:
- Critical site recommendations (Phase 05)
- Critical root causes (Phase 09)
- Escalation-required multi-agent recommendations (Phase 07)

#### 🟠 THIS WEEK
Actions for the current week. Sources:
- High-priority site recommendations
- High-severity root causes
- Non-escalation multi-agent recommendations
- Country-level recommendations

#### 🟢 THIS MONTH
Lower priority actions. Sources:
- Medium-priority recommendations
- Medium-severity root causes

### Action Cards

Each action shows:
- **Title**: Site/Study/Country and risk level
- **Source**: Which pipeline phase generated it
- **Type**: Site Action, Study Action, Country Action, Multi-Agent, or Root Cause Analysis
- **Scope**: Number of sites and subjects affected
- **Steps**: Expandable recommended actions

### Action Summary (4 Cards)

| Metric | Meaning |
|--------|---------|
| Total Actions | All identified interventions (should be 59) |
| Immediate | Actions for today |
| This Week | Actions for this week |
| This Month | Lower priority actions |

Context text shows sites affected per category.

---

## 6. Deep Dive

*Question it answers: "Let me explore specific studies/sites/subjects."*

### Selection Controls

Three filters for drill-down:
- **Select Study**: Filter to specific study or "All Studies"
- **Select Site**: Filter to specific site (cascades from study selection)
- **Risk Category**: Multi-select for High/Medium/Low

### Study Overview (When Study Selected)

5 metric cards showing study-level stats:
- Sites count
- Subject count
- Average DQI
- High-Risk percentage
- Risk Level badge

**Study Analysis Insight**: Appears when high-risk rate >15%

### Site Profile (When Site Selected)

Detailed site card showing:
- Site ID, study, country, region
- Subject count, average DQI, high-risk count, SAE pending
- Site recommendations (expandable)

**Site Analysis Insight**: Appears for high-risk sites or DQI >0.1

### Subject Data (Table)

Paginated table showing first 100 subjects with columns:
- subject_id, site_id, study, country
- risk_category, dqi_score
- sae_pending_count, missing_visit_count, lab_issues_count

**Export CSV**: Downloads all filtered subjects

### Visualization Row 1

#### Risk Distribution (Donut Chart)
Breakdown of High/Medium/Low risk subjects in current selection.

#### DQI Score Distribution (Histogram)
Distribution of DQI scores across selected subjects.

### Visualization Row 2

#### Top Issues Breakdown (Horizontal Bar)
Issue types ranked by count for current selection.
- Red bars: SAE-related
- Orange bars: Missing data
- Blue bars: Other issues

#### DQI vs SAE Scatter
Scatter plot showing relationship between DQI score and SAE pending count.
- Color = Risk category
- Helps identify subjects with both high DQI and SAE backlog

### Selection Insights (2 Cards)

#### Risk Analysis
Summary of current selection:
- Subject count and high-risk percentage
- Average DQI score
- Whether intervention is recommended

#### Safety Signal / Data Quality
Context-specific insight:
- **Safety Signal**: Appears when SAE backlog exists
- **Data Quality**: Appears when no SAE issues, focuses on other metrics

---

## Understanding DQI Scores

The **Data Quality Index (DQI)** is a weighted composite score where **higher = worse**.

### DQI Score Ranges

| Range | Interpretation |
|-------|----------------|
| 0.00 - 0.05 | Excellent data quality |
| 0.05 - 0.10 | Good data quality |
| 0.10 - 0.20 | Moderate issues |
| 0.20 - 0.30 | Significant issues |
| 0.30+ | Critical data quality problems |

### DQI Weight Categories

| Category | Weight | Components |
|----------|--------|------------|
| Safety | 35% | SAE pending, adverse events |
| Completeness | 32% | Missing visits, missing pages |
| Timeliness | 14% | Days outstanding, delays |
| Coding | 11% | Uncoded MedDRA, WHO Drug |
| Administrative | 8% | Inactivated forms, open queries |

---

## Color Coding Reference

### Risk Levels
| Color | Hex | Meaning |
|-------|-----|---------|
| 🔴 Red | #ef4444 | High / Critical |
| 🟠 Orange | #f59e0b | Medium / At Risk |
| 🟢 Green | #10b981 | Low / Healthy |
| 🔵 Blue | #3b82f6 | Info / Neutral |

### Alert Types
| Border Color | Type |
|--------------|------|
| Red | Critical - Immediate action |
| Orange | Warning - Monitor closely |
| Blue | Info - Awareness |
| Green | Success - Positive trend |

### Chart Conventions
- **Bar charts**: Sorted by value (highest concern first)
- **Scatter plots**: Upper-right = highest priority
- **Heatmaps**: Red = strong correlation
- **Gauges**: Green zone = healthy

---

## Data Freshness

The dashboard loads data from pipeline outputs at startup. To refresh:
1. Re-run the pipeline: `python src/run_pipeline.py --all`
2. Refresh the browser or restart Streamlit

Data is cached for 5 minutes (300 seconds) to improve performance.

---

## Export Capabilities

CSV export buttons are available on:
- Top 10 Countries by Risk
- Study Risk Ranking
- Top Anomalous Sites
- Cluster Comparison
- Identified Root Causes
- Subject Data (Deep Dive)

Click **📥 Export CSV** to download filtered data.

---

*JAVELIN.AI | Built for NEST 2.0 Innovation Challenge | Team CWTY*
