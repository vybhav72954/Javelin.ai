# Javelin.AI
## AI-Powered Clinical Trial Data Quality Intelligence Platform

An end-to-end solution for monitoring, analyzing, and improving clinical trial data quality across multi-site global studies. Built for the **NEST 2.0 Innovation Challenge** (Problem Statement 1: Integrated Insight-Driven Data-Flow Model).

---

## 🎯 The Problem

Clinical trials generate massive heterogeneous data from multiple sources — EDC systems, lab reports, site metrics, safety databases — but these remain siloed. This causes:

- Delayed identification of data quality issues
- Inconsistent monitoring across sites and studies
- Manual, reactive processes instead of proactive intervention
- Limited visibility into cross-study patterns

**Javelin.AI** solves this by creating a unified data quality intelligence layer with AI-powered insights.

---

## 💡 Our Solution

### What We Built

| Component | Description |
|-----------|-------------|
| **Unified Data Pipeline** | Ingests and harmonizes 9 different data sources across 23 studies |
| **Data Quality Index (DQI)** | Clinically-weighted scoring system for subject and site-level risk assessment |
| **Knowledge Graph** | Cross-study relationship discovery across regions, countries, sites, and subjects |
| **AI Recommendations Engine** | LLM-powered actionable insights for clinical operations teams |
| **Interactive Dashboard** | Real-time visualization and drill-down for data quality monitoring |

### Key Metrics

| Metric | Value |
|--------|-------|
| Studies Processed | 23 |
| Total Subjects | 57,997 |
| Total Sites | 3,424 |
| Data Sources Integrated | 9 per study |
| Knowledge Graph Nodes | 61,520 |
| Knowledge Graph Edges | 64,867 |

---

## 🔬 Pipeline Overview

### Step 1: Data Discovery & Integration

**Script:** `01_data_discovery.py`

Scans all study folders and automatically classifies files into 9 standardized types:

- EDC Metrics
- Visit Tracker
- Query Aging
- Lab Reconciliation
- Coding Status (MedDRA & WHODrug)
- Site CRA Metrics
- Safety Review Status
- Page Tracker

Handles inconsistent naming conventions across studies and validates column mappings for downstream processing.

---

### Step 2: Master Table Construction

**Script:** `02_build_master_table.py`

Creates a unified subject-level master table by joining all 9 data sources using Subject ID, Site ID, and Study ID as keys. Computes derived metrics including:

- Missing visit counts and percentages
- Open query counts and aging
- Lab reconciliation gaps
- Uncoded adverse event terms
- Pending safety reviews

**Output:** `master_subject.csv` (57,997 rows) and `master_site.csv` (3,424 rows)

---

### Step 3: Data Quality Index (DQI) Calculation

**Script:** `03_calculate_dqi.py`

Implements a clinically-weighted scoring system based on domain knowledge:

| Weight Tier | Weight | Components |
|-------------|--------|------------|
| **Safety** | 35% | Pending SAE reviews, Uncoded MedDRA terms |
| **Completeness** | 32% | Missing visits, Missing pages, Lab issues |
| **Timeliness** | 14% | Days queries outstanding |
| **Coding/Reconciliation** | 11% | Uncoded drugs, EDRR issues |
| **Administrative** | 8% | Inactivated forms, Issue counts |

**Scoring Method:** Binary presence (50%) + Severity weighting (50%)

**Risk Classification:**
- **High Risk:** SAE pending OR top 10% DQI score
- **Medium Risk:** Any issue present, not High
- **Low Risk:** No issues detected

**Validation Results:**
- 100% SAE capture rate (all safety-critical subjects flagged)
- 100% issue capture rate (no subjects with issues missed)
- Proper risk pyramid: Medium (12%) > High (9.1%)

---

### Step 4: Knowledge Graph Construction

**Script:** `04_build_knowledge_graph.py`

Builds a hierarchical knowledge graph connecting:

```
Region → Country → Site → Subject
           ↓
        Study
```

**Graph Structure:**
- 4 Regions (AMERICA, ASIA, EMEA, OTHER)
- 72 Countries
- 23 Studies
- 3,399 Sites
- 57,997 Subjects

Enables pattern discovery such as:
- Which countries have highest concentration of high-risk sites
- Cross-study site performance comparison
- Regional clustering of data quality issues

**Output:** GraphML and GEXF files for visualization in yEd/Gephi

---

### Step 5: AI-Powered Recommendations Engine

**Script:** `05_recommendations_engine.py`

Uses a local LLM (Mistral via Ollama) to generate actionable recommendations:

**Site-Level:**
- Analyzes DQI scores and issue breakdown
- Generates specific remediation actions
- Prioritizes by criticality (CRITICAL → HIGH → MEDIUM)

**Study-Level:**
- Aggregates site performance
- Identifies systemic issues
- Recommends resource allocation

**Executive Summary:**
- Portfolio-wide health assessment
- Top 3 priority actions for the week
- Risk trend analysis

**Output:** `recommendations_by_site.csv`, `action_items.json`, `executive_summary.txt`

---

### Step 6: Interactive Dashboard

**Script:** `app.py`

Streamlit-based dashboard with 5 views:

1. **Executive Overview** — Portfolio KPIs, priority distribution, issue categories
2. **Site Analysis** — High-priority site cards with AI insights, DQI distribution
3. **Study Analysis** — Cross-study comparison, issue heatmap
4. **Critical Actions** — Pending SAE tracker, critical study recommendations
5. **Detailed Reports** — Filterable data tables, downloadable reports

**Features:**
- Real-time filters by Study, Priority, Region
- Expandable AI analysis for each flagged site
- CSV/JSON/TXT export functionality

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Ollama with Mistral model (for AI recommendations)

### Installation

```bash
# Clone and setup
git clone <repository>
cd Javelin.AI
pip install -r requirements.txt

# Install Ollama and pull Mistral (for AI features)
# See: https://ollama.ai
ollama pull mistral
```

### Run Pipeline

```bash
# Step 1: Discover and classify data files
python src/01_data_discovery.py

# Step 2: Build master tables
python src/02_build_master_table.py

# Step 3: Calculate DQI scores
python src/03_calculate_dqi.py

# Step 4: Build knowledge graph
python src/04_build_knowledge_graph.py

# Step 5: Generate AI recommendations
python src/05_recommendations_engine.py

# Step 6: Launch dashboard
streamlit run src/app.py
```

---

## 📋 Requirements

```
pandas>=2.0.0
numpy>=1.24.0
networkx>=3.0
plotly>=5.18.0
streamlit>=1.29.0
openpyxl>=3.1.0
requests>=2.31.0
```

---

## 🏆 Key Innovations

### 1. Domain-Knowledge DQI
Unlike arbitrary scoring, our DQI weights are based on clinical operations expertise — safety issues are weighted highest because they have regulatory implications, followed by data completeness which affects analysis integrity.

### 2. Unified Multi-Source Integration
Harmonizes 9 disparate data sources per study into a single analytical layer, enabling cross-functional insights that were previously impossible with siloed systems.

### 3. Generative AI for Actionable Insights
Moves beyond dashboards that just show problems — uses LLM to generate specific, contextual recommendations that clinical operations teams can act on immediately.

### 4. Knowledge Graph for Pattern Discovery
Enables discovery of non-obvious patterns like geographic clustering of issues, cross-study site performance, and regional resource allocation needs.

---

## 📊 Sample Results

**Risk Distribution:**
| Category | Subjects | Percentage |
|----------|----------|------------|
| High | 5,264 | 9.1% |
| Medium | 6,949 | 12.0% |
| Low | 45,784 | 78.9% |

**Top Issue Categories:**
| Issue | Count |
|-------|-------|
| Inactivated Forms | 66,829 |
| Lab Issues | 20,669 |
| Missing Pages | 6,116 |
| SAE Pending | 5,407 |

**Flagged Sites:** 387 of 3,424 (11.3%) requiring action

---

## 👥 Team

Built for NEST 2.0 Innovation Challenge — Novartis

---

## 📄 License

This project was developed for the NEST 2.0 hackathon competition.
