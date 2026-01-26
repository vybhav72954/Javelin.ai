"""
Javelin.AI - Step 4: Build Knowledge Graph
============================================

Creates a knowledge graph representing the clinical trial data structure
with DQI scores and risk categories.

GRAPH STRUCTURE:
----------------
Nodes:
  - Study: Clinical trial studies
  - Site: Trial sites/locations
  - Subject: Trial participants
  - Country: Geographic countries
  - Region: Geographic regions

Relationships:
  - Subject -[ENROLLED_AT]-> Site
  - Site -[PARTICIPATES_IN]-> Study
  - Site -[LOCATED_IN]-> Country
  - Country -[IN_REGION]-> Region

Properties:
  - DQI scores, risk categories, issue counts at each level

OUTPUTS:
--------
  - outputs/knowledge_graph.graphml (for Gephi, yEd, etc.)
  - outputs/knowledge_graph_nodes.csv (for Neo4j import)
  - outputs/knowledge_graph_edges.csv (for Neo4j import)
  - outputs/knowledge_graph_summary.json (statistics)
  - outputs/knowledge_graph_report.txt (human-readable report)

SUBGRAPHS (optional):
---------------------
  - outputs/subgraph_high_risk.graphml (high-risk entities only)
  - outputs/subgraph_top_studies.graphml (top 5 studies by size)
  - outputs/subgraph_sample.graphml (random sample of subjects)

Usage:
    python src/04_knowledge_graph.py
    python src/04_knowledge_graph.py --subgraphs all
    python src/04_knowledge_graph.py --subgraphs high_risk,top_studies
    python src/04_knowledge_graph.py --high-risk-only
"""

import pandas as pd
import numpy as np
import networkx as nx
import json
import argparse
from pathlib import Path
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SUBJECT_PATH = OUTPUT_DIR / "master_subject_with_dqi.csv"
SITE_PATH = OUTPUT_DIR / "master_site_with_dqi.csv"
STUDY_PATH = OUTPUT_DIR / "master_study_with_dqi.csv"
REGION_PATH = OUTPUT_DIR / "master_region_with_dqi.csv"
COUNTRY_PATH = OUTPUT_DIR / "master_country_with_dqi.csv"


# ============================================================================
# KNOWLEDGE GRAPH BUILDER
# ============================================================================

class ClinicalTrialKnowledgeGraph:
    """
    Knowledge graph for clinical trial data quality intelligence.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_counts = defaultdict(int)
        self.edge_counts = defaultdict(int)
        self.statistics = {}

    def add_node(self, node_id, node_type, **properties):
        """Add a node with type and properties."""
        self.graph.add_node(
            node_id,
            node_type=node_type,
            **properties
        )
        self.node_counts[node_type] += 1

    def add_edge(self, source, target, edge_type, **properties):
        """Add an edge with type and properties."""
        self.graph.add_edge(
            source,
            target,
            edge_type=edge_type,
            **properties
        )
        self.edge_counts[edge_type] += 1

    def build_from_data(self, subject_df, site_df, study_df=None, region_df=None, country_df=None):
        """
        Build the knowledge graph from subject, site, and optionally
        pre-computed study/region/country dataframes.

        Args:
            subject_df: Subject-level data with DQI scores
            site_df: Site-level aggregated data
            study_df: Pre-computed study-level data (optional, computed if None)
            region_df: Pre-computed region-level data (optional, computed if None)
            country_df: Pre-computed country-level data (optional, computed if None)
        """
        print("\nBuilding knowledge graph...")

        # =====================================================================
        # Step 1: Add Region nodes (use pre-computed if available)
        # =====================================================================
        print("  Adding Region nodes...")
        if region_df is not None:
            for _, row in region_df.iterrows():
                self.add_node(
                    f"region:{row['region']}",
                    node_type="Region",
                    name=row['region'],
                    site_count=int(row['site_count']),
                    subject_count=int(row['subject_count']),
                    study_count=int(row['study_count']),
                    country_count=int(row['country_count']),
                    avg_dqi_score=round(float(row['avg_dqi_score']), 4),
                    max_dqi_score=round(float(row['max_dqi_score']), 4),
                    high_risk_subjects=int(row['high_risk_subjects']),
                    high_risk_rate=round(float(row['high_risk_rate']), 4),
                    region_risk_category=row['region_risk_category']
                )
        else:
            # Fallback: compute from subject_df
            regions = subject_df['region'].unique()
            for region in regions:
                self.add_node(
                    f"region:{region}",
                    node_type="Region",
                    name=region
                )

        # =====================================================================
        # Step 2: Add Country nodes and Region relationships
        # =====================================================================
        print("  Adding Country nodes...")
        if country_df is not None:
            for _, row in country_df.iterrows():
                country_id = f"country:{row['country']}"
                self.add_node(
                    country_id,
                    node_type="Country",
                    name=row['country'],
                    region=row['region'],
                    site_count=int(row['site_count']),
                    subject_count=int(row['subject_count']),
                    study_count=int(row['study_count']),
                    avg_dqi_score=round(float(row['avg_dqi_score']), 4),
                    max_dqi_score=round(float(row['max_dqi_score']), 4),
                    high_risk_subjects=int(row['high_risk_subjects']),
                    high_risk_rate=round(float(row['high_risk_rate']), 4),
                    country_risk_category=row['country_risk_category']
                )
                # Country -> Region relationship
                self.add_edge(
                    country_id,
                    f"region:{row['region']}",
                    edge_type="IN_REGION"
                )
        else:
            # Fallback: compute from subject_df
            country_region = subject_df[['country', 'region']].drop_duplicates()
            for _, row in country_region.iterrows():
                country_id = f"country:{row['country']}"
                self.add_node(
                    country_id,
                    node_type="Country",
                    name=row['country'],
                    region=row['region']
                )
                self.add_edge(
                    country_id,
                    f"region:{row['region']}",
                    edge_type="IN_REGION"
                )

        # =====================================================================
        # Step 3: Add Study nodes with aggregated metrics
        # =====================================================================
        print("  Adding Study nodes...")
        if study_df is not None:
            for _, row in study_df.iterrows():
                self.add_node(
                    f"study:{row['study']}",
                    node_type="Study",
                    name=row['study'],
                    subject_count=int(row['subject_count']),
                    site_count=int(row['site_count']),
                    avg_dqi_score=round(float(row['avg_dqi_score']), 4),
                    max_site_dqi_score=round(float(row['max_site_dqi_score']), 4),
                    high_risk_subjects=int(row['high_risk_subjects']),
                    high_risk_rate=round(float(row['high_risk_rate']), 4),
                    high_risk_sites=int(row['high_risk_sites']),
                    subjects_with_issues=int(row['subjects_with_issues']),
                    study_risk_category=row['study_risk_category']
                )
        else:
            # Fallback: compute from subject_df
            study_metrics = subject_df.groupby('study').agg({
                'subject_id':'count',
                'dqi_score':['mean', 'max'],
                'risk_category':lambda x:(x=='High').sum(),
                'has_issues':'sum'
            }).reset_index()
            study_metrics.columns = ['study', 'subject_count', 'avg_dqi', 'max_dqi',
                                     'high_risk_count', 'subjects_with_issues']
            site_counts = site_df.groupby('study').size().reset_index(name='site_count')
            study_metrics = study_metrics.merge(site_counts, on='study', how='left')

            for _, row in study_metrics.iterrows():
                self.add_node(
                    f"study:{row['study']}",
                    node_type="Study",
                    name=row['study'],
                    subject_count=int(row['subject_count']),
                    site_count=int(row['site_count']),
                    avg_dqi_score=round(float(row['avg_dqi']), 4),
                    max_dqi_score=round(float(row['max_dqi']), 4),
                    high_risk_count=int(row['high_risk_count']),
                    subjects_with_issues=int(row['subjects_with_issues'])
                )

        # =====================================================================
        # Step 4: Add Site nodes with relationships
        # =====================================================================
        print("  Adding Site nodes...")
        for _, row in site_df.iterrows():
            site_id = f"site:{row['study']}:{row['site_id']}"

            self.add_node(
                site_id,
                node_type="Site",
                name=row['site_id'],
                study=row['study'],
                country=row['country'],
                region=row['region'],
                subject_count=int(row['subject_count']),
                avg_dqi_score=round(float(row['avg_dqi_score']), 4),
                max_dqi_score=round(float(row['max_dqi_score']), 4),
                high_risk_count=int(row['high_risk_count']),
                medium_risk_count=int(row['medium_risk_count']),
                site_risk_category=row['site_risk_category'],
                subjects_with_issues=int(row['subjects_with_issues'])
            )

            # Site -> Study relationship
            self.add_edge(
                site_id,
                f"study:{row['study']}",
                edge_type="PARTICIPATES_IN"
            )

            # Site -> Country relationship
            self.add_edge(
                site_id,
                f"country:{row['country']}",
                edge_type="LOCATED_IN"
            )

        # =====================================================================
        # Step 5: Add Subject nodes with relationships
        # =====================================================================
        print("  Adding Subject nodes...")
        subject_cols = ['subject_id', 'study', 'site_id', 'country', 'region',
                        'subject_status', 'dqi_score', 'risk_category',
                        'n_issue_types', 'has_issues',
                        'sae_pending_count', 'missing_visit_count',
                        'missing_pages_count', 'lab_issues_count']

        for _, row in subject_df[subject_cols].iterrows():
            subject_node_id = f"subject:{row['study']}:{row['subject_id']}"
            site_node_id = f"site:{row['study']}:{row['site_id']}"

            self.add_node(
                subject_node_id,
                node_type="Subject",
                name=row['subject_id'],
                study=row['study'],
                site_id=row['site_id'],
                status=row['subject_status'],
                dqi_score=round(float(row['dqi_score']), 4),
                risk_category=row['risk_category'],
                n_issue_types=int(row['n_issue_types']),
                has_issues=int(row['has_issues']),
                sae_pending=int(row['sae_pending_count']),
                missing_visits=int(row['missing_visit_count']),
                missing_pages=int(row['missing_pages_count']),
                lab_issues=int(row['lab_issues_count'])
            )

            # Subject -> Site relationship
            self.add_edge(
                subject_node_id,
                site_node_id,
                edge_type="ENROLLED_AT"
            )

        # =====================================================================
        # Calculate statistics
        # =====================================================================
        # Count from the actual data passed in or computed
        num_studies = len(study_df) if study_df is not None else subject_df['study'].nunique()
        num_sites = len(site_df)
        num_subjects = len(subject_df)
        num_countries = len(country_df) if country_df is not None else subject_df['country'].nunique()
        num_regions = len(region_df) if region_df is not None else subject_df['region'].nunique()

        self.statistics = {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'node_counts': dict(self.node_counts),
            'edge_counts': dict(self.edge_counts),
            'studies': num_studies,
            'sites': num_sites,
            'subjects': num_subjects,
            'countries': num_countries,
            'regions': num_regions
        }

        print(f"  Total nodes: {self.statistics['total_nodes']:,}")
        print(f"  Total edges: {self.statistics['total_edges']:,}")

    def get_high_risk_subgraph(self):
        """Extract subgraph containing only high-risk subjects and their connections."""
        high_risk_nodes = [
            n for n, d in self.graph.nodes(data=True)
            if d.get('risk_category') == 'High' or d.get('site_risk_category') == 'High'
        ]

        # Also include connected sites, studies, countries, regions
        extended_nodes = set(high_risk_nodes)
        for node in high_risk_nodes:
            extended_nodes.update(self.graph.successors(node))
            extended_nodes.update(self.graph.predecessors(node))

        return self.graph.subgraph(extended_nodes).copy()

    def get_top_studies_subgraph(self, top_n=5):
        """Extract subgraph for top N studies by subject count."""
        # Find top studies
        study_nodes = [(n, d) for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'Study']
        top_studies = sorted(study_nodes, key=lambda x: x[1].get('subject_count', 0), reverse=True)[:top_n]
        top_study_ids = {node[0] for node in top_studies}

        # Collect all nodes connected to these studies
        included_nodes = set(top_study_ids)
        for study_node in top_study_ids:
            # Get all predecessors (sites connecting to study)
            included_nodes.update(self.graph.predecessors(study_node))
            # For each site, get subjects
            for site_node in self.graph.predecessors(study_node):
                included_nodes.update(self.graph.predecessors(site_node))
                # Get country and region for site
                included_nodes.update(self.graph.successors(site_node))

        return self.graph.subgraph(included_nodes).copy()

    def get_sample_subgraph(self, sample_size=1000):
        """Extract random sample subgraph."""
        # Get random sample of subjects
        subject_nodes = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'Subject']
        sample_subjects = np.random.choice(subject_nodes, min(sample_size, len(subject_nodes)), replace=False)

        # Include all connected nodes
        included_nodes = set(sample_subjects)
        for subject_node in sample_subjects:
            included_nodes.update(self.graph.successors(subject_node))
            for connected_node in self.graph.successors(subject_node):
                included_nodes.update(self.graph.successors(connected_node))

        return self.graph.subgraph(included_nodes).copy()

    def get_region_subgraph(self, region_name):
        """Extract subgraph for a specific region."""
        # Find all nodes in this region
        region_nodes = [n for n, d in self.graph.nodes(data=True)
                       if d.get('region') == region_name or d.get('name') == region_name]

        included_nodes = set(region_nodes)
        for node in region_nodes:
            # Add predecessors (subjects/sites in this region)
            included_nodes.update(self.graph.predecessors(node))
            # Add successors (countries, studies)
            included_nodes.update(self.graph.successors(node))

        return self.graph.subgraph(included_nodes).copy()

    def export_graphml(self, filepath):
        """Export graph to GraphML format."""
        # Convert all attributes to strings for GraphML compatibility
        G = self.graph.copy()
        for node in G.nodes():
            for key, value in G.nodes[node].items():
                G.nodes[node][key] = str(value)
        for u, v in G.edges():
            for key, value in G.edges[u, v].items():
                G.edges[u, v][key] = str(value)

        nx.write_graphml(G, filepath)

    def export_subgraph_graphml(self, subgraph, filepath):
        """Export a subgraph to GraphML format."""
        G = subgraph.copy()
        for node in G.nodes():
            for key, value in G.nodes[node].items():
                G.nodes[node][key] = str(value)
        for u, v in G.edges():
            for key, value in G.edges[u, v].items():
                G.edges[u, v][key] = str(value)

        nx.write_graphml(G, filepath)

    def export_neo4j_csv(self, nodes_path, edges_path):
        """Export to CSV format for Neo4j import."""
        # Nodes
        nodes_data = []
        for node_id, data in self.graph.nodes(data=True):
            node_row = {'node_id': node_id}
            node_row.update(data)
            nodes_data.append(node_row)

        nodes_df = pd.DataFrame(nodes_data)
        nodes_df.to_csv(nodes_path, index=False)

        # Edges
        edges_data = []
        for source, target, data in self.graph.edges(data=True):
            edge_row = {
                'source': source,
                'target': target
            }
            edge_row.update(data)
            edges_data.append(edge_row)

        edges_df = pd.DataFrame(edges_data)
        edges_df.to_csv(edges_path, index=False)

    def export_summary_json(self, filepath):
        """Export summary statistics to JSON."""
        summary = {
            'statistics': self.statistics,
            'risk_by_country': self.get_risk_distribution_by_country()
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)

    def get_risk_distribution_by_country(self):
        """Get risk distribution grouped by country."""
        distribution = defaultdict(lambda: {'High': 0, 'Medium': 0, 'Low': 0, 'total': 0})

        for node, data in self.graph.nodes(data=True):
            if data.get('node_type') == 'Subject':
                country = data.get('country', 'Unknown')
                risk = data.get('risk_category', 'Unknown')
                if risk in distribution[country]:
                    distribution[country][risk] += 1
                distribution[country]['total'] += 1

        return dict(distribution)


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def build_knowledge_graph(args):
    """Main function to build and export the knowledge graph."""

    print("=" * 70)
    print("JAVELIN.AI - KNOWLEDGE GRAPH BUILDER")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Load Data
    # -------------------------------------------------------------------------
    if not SUBJECT_PATH.exists():
        print(f"\nERROR: {SUBJECT_PATH} not found!")
        print("Please run 03_calculate_dqi.py first.")
        return False

    if not SITE_PATH.exists():
        print(f"\nERROR: {SITE_PATH} not found!")
        print("Please run 03_calculate_dqi.py first.")
        return False

    print(f"\nLoading data...")
    subject_df = pd.read_csv(SUBJECT_PATH)
    site_df = pd.read_csv(SITE_PATH)

    # Load pre-computed aggregated data (optional - has fallback)
    study_df = None
    region_df = None
    country_df = None

    if STUDY_PATH.exists():
        study_df = pd.read_csv(STUDY_PATH)
        print(f"  Studies: {len(study_df)} (from pre-computed file)")
    else:
        print(f"  Studies: {subject_df['study'].nunique()} (will compute)")

    if REGION_PATH.exists():
        region_df = pd.read_csv(REGION_PATH)
        print(f"  Regions: {len(region_df)} (from pre-computed file)")

    if COUNTRY_PATH.exists():
        country_df = pd.read_csv(COUNTRY_PATH)
        print(f"  Countries: {len(country_df)} (from pre-computed file)")

    print(f"  Subjects: {len(subject_df):,}")
    print(f"  Sites: {len(site_df):,}")

    # -------------------------------------------------------------------------
    # Build Knowledge Graph
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 1: BUILD KNOWLEDGE GRAPH")
    print("=" * 70)

    kg = ClinicalTrialKnowledgeGraph()
    kg.build_from_data(subject_df, site_df, study_df, region_df, country_df)

    # -------------------------------------------------------------------------
    # Graph Statistics
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 2: GRAPH STATISTICS")
    print("=" * 70)

    print(f"\nNode counts by type:")
    for node_type, count in sorted(kg.node_counts.items()):
        print(f"  {node_type}: {count:,}")

    print(f"\nEdge counts by type:")
    for edge_type, count in sorted(kg.edge_counts.items()):
        print(f"  {edge_type}: {count:,}")

    # -------------------------------------------------------------------------
    # Sample Queries
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 3: SAMPLE QUERIES")
    print("=" * 70)

    # Query 1: High-risk subject count by study
    print("\nHigh-risk subjects by study:")
    if study_df is not None:
        top_studies = study_df.nlargest(5, 'high_risk_subjects')[['study', 'high_risk_subjects', 'study_risk_category']]
        for _, row in top_studies.iterrows():
            print(f"  {row['study']}: {int(row['high_risk_subjects']):,} high-risk subjects [{row['study_risk_category']}]")
    else:
        study_risk = subject_df.groupby('study')['risk_category'].apply(
            lambda x: (x == 'High').sum()
        ).sort_values(ascending=False).head(5)
        for study, count in study_risk.items():
            print(f"  {study}: {count:,} high-risk subjects")

    # Query 2: Top countries by average DQI
    print("\nTop 5 countries by average DQI score:")
    if country_df is not None:
        top_countries = country_df.nlargest(5, 'avg_dqi_score')[['country', 'region', 'avg_dqi_score', 'country_risk_category']]
        for _, row in top_countries.iterrows():
            print(f"  {row['country']} ({row['region']}): {row['avg_dqi_score']:.4f} [{row['country_risk_category']}]")
    else:
        country_dqi = subject_df.groupby('country')['dqi_score'].mean().sort_values(ascending=False).head(5)
        for country, dqi in country_dqi.items():
            print(f"  {country}: {dqi:.4f}")

    # Query 3: Risk distribution by region
    print("\nRisk summary by region:")
    if region_df is not None:
        for _, row in region_df.iterrows():
            print(f"  {row['region']}: {int(row['site_count'])} sites, {int(row['subject_count']):,} subjects, "
                  f"DQI={row['avg_dqi_score']:.4f}, High-risk rate={row['high_risk_rate'] * 100:.1f}% [{row['region_risk_category']}]")
    else:
        region_risk = subject_df.groupby(['region', 'risk_category']).size().unstack(fill_value=0)
        print(region_risk.to_string())

    # -------------------------------------------------------------------------
    # Export Full Graph
    # -------------------------------------------------------------------------
    if not args.high_risk_only:
        print("\n" + "=" * 70)
        print("STEP 4: EXPORT FULL KNOWLEDGE GRAPH")
        print("=" * 70)

        # GraphML export
        graphml_path = OUTPUT_DIR / "knowledge_graph.graphml"
        print(f"\nExporting GraphML...")
        kg.export_graphml(graphml_path)
        print(f"  Saved: {graphml_path}")

        # Neo4j CSV export
        nodes_path = OUTPUT_DIR / "knowledge_graph_nodes.csv"
        edges_path = OUTPUT_DIR / "knowledge_graph_edges.csv"
        print(f"\nExporting Neo4j CSVs...")
        kg.export_neo4j_csv(nodes_path, edges_path)
        print(f"  Saved: {nodes_path}")
        print(f"  Saved: {edges_path}")

        # Summary JSON
        summary_path = OUTPUT_DIR / "knowledge_graph_summary.json"
        print(f"\nExporting summary JSON...")
        kg.export_summary_json(summary_path)
        print(f"  Saved: {summary_path}")

    # -------------------------------------------------------------------------
    # Export Subgraphs
    # -------------------------------------------------------------------------
    if args.subgraphs or args.high_risk_only:
        print("\n" + "=" * 70)
        print("STEP 5: EXPORT SUBGRAPHS")
        print("=" * 70)

        subgraphs_to_export = args.subgraphs.split(',') if args.subgraphs else []
        if args.high_risk_only:
            subgraphs_to_export = ['high_risk']
        if 'all' in subgraphs_to_export:
            subgraphs_to_export = ['high_risk', 'top_studies', 'sample']

        for subgraph_type in subgraphs_to_export:
            subgraph_type = subgraph_type.strip()

            if subgraph_type == 'high_risk':
                print(f"\nCreating high-risk subgraph...")
                subgraph = kg.get_high_risk_subgraph()
                filepath = OUTPUT_DIR / "subgraph_high_risk.graphml"
                kg.export_subgraph_graphml(subgraph, filepath)
                print(f"  Saved: {filepath}")
                print(f"  Nodes: {subgraph.number_of_nodes():,}, Edges: {subgraph.number_of_edges():,}")

            elif subgraph_type == 'top_studies':
                print(f"\nCreating top-5 studies subgraph...")
                subgraph = kg.get_top_studies_subgraph(top_n=5)
                filepath = OUTPUT_DIR / "subgraph_top_studies.graphml"
                kg.export_subgraph_graphml(subgraph, filepath)
                print(f"  Saved: {filepath}")
                print(f"  Nodes: {subgraph.number_of_nodes():,}, Edges: {subgraph.number_of_edges():,}")

            elif subgraph_type == 'sample':
                print(f"\nCreating random sample subgraph (1000 subjects)...")
                subgraph = kg.get_sample_subgraph(sample_size=1000)
                filepath = OUTPUT_DIR / "subgraph_sample.graphml"
                kg.export_subgraph_graphml(subgraph, filepath)
                print(f"  Saved: {filepath}")
                print(f"  Nodes: {subgraph.number_of_nodes():,}, Edges: {subgraph.number_of_edges():,}")

    # -------------------------------------------------------------------------
    # Generate Report
    # -------------------------------------------------------------------------
    if not args.high_risk_only:
        print("\n" + "=" * 70)
        print("STEP 6: GENERATE REPORT")
        print("=" * 70)

        report_path = OUTPUT_DIR / "knowledge_graph_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("JAVELIN.AI - KNOWLEDGE GRAPH REPORT\n")
            f.write("=" * 60 + "\n\n")

            f.write("GRAPH STRUCTURE\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Nodes: {kg.statistics['total_nodes']:,}\n")
            f.write(f"Total Edges: {kg.statistics['total_edges']:,}\n\n")

            f.write("NODE TYPES\n")
            f.write("-" * 40 + "\n")
            for node_type, count in sorted(kg.node_counts.items()):
                f.write(f"  {node_type}: {count:,}\n")
            f.write("\n")

            f.write("EDGE TYPES\n")
            f.write("-" * 40 + "\n")
            for edge_type, count in sorted(kg.edge_counts.items()):
                f.write(f"  {edge_type}: {count:,}\n")
            f.write("\n")

            f.write("HIERARCHY\n")
            f.write("-" * 40 + "\n")
            f.write(f"Region ({kg.node_counts.get('Region', 0)})\n")
            f.write(f"  └── Country ({kg.node_counts.get('Country', 0)})\n")
            f.write(f"        └── Site ({kg.node_counts.get('Site', 0):,})\n")
            f.write(f"              └── Subject ({kg.node_counts.get('Subject', 0):,})\n")
            f.write(f"Study ({kg.node_counts.get('Study', 0)})\n")
            f.write(f"  └── Site ({kg.node_counts.get('Site', 0):,})\n")
            f.write(f"        └── Subject ({kg.node_counts.get('Subject', 0):,})\n\n")

            # Risk distribution - use pre-computed data if available
            f.write("RISK DISTRIBUTION BY REGION\n")
            f.write("-" * 40 + "\n")
            if region_df is not None:
                for _, row in region_df.iterrows():
                    f.write(f"{row['region']}: {int(row['high_risk_subjects']):,} high-risk / "
                            f"{int(row['subject_count']):,} total "
                            f"({row['high_risk_rate'] * 100:.1f}%) [{row['region_risk_category']}]\n")
            else:
                # Compute on the fly
                region_risk = subject_df.groupby(['region', 'risk_category']).size().unstack(fill_value=0)
                f.write(region_risk.to_string())
            f.write("\n\n")

            f.write("USE CASES\n")
            f.write("-" * 40 + "\n")
            f.write("1. Drill-down: Study -> Site -> Subject\n")
            f.write("2. Geographic analysis: Region -> Country -> Site\n")
            f.write("3. Risk hotspots: Filter by risk_category\n")
            f.write("4. Site comparison: Compare sites within a study\n")
            f.write("5. Trend analysis: Track DQI over time (with timestamps)\n")
            f.write("\n")

            f.write("EXPORT FORMATS\n")
            f.write("-" * 40 + "\n")
            f.write("1. GraphML: For Gephi, yEd, Cytoscape visualization\n")
            f.write("2. CSV (nodes/edges): For Neo4j import\n")
            f.write("3. JSON: For web applications\n")

        print(f"  Saved: {report_path}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if not args.high_risk_only:
        print(f"""
KNOWLEDGE GRAPH BUILT SUCCESSFULLY

Structure:
  - Nodes: {kg.statistics['total_nodes']:,}
  - Edges: {kg.statistics['total_edges']:,}

Node Types:
  - Regions: {kg.node_counts['Region']}
  - Countries: {kg.node_counts['Country']}
  - Studies: {kg.node_counts['Study']}
  - Sites: {kg.node_counts['Site']:,}
  - Subjects: {kg.node_counts['Subject']:,}

Relationships:
  - ENROLLED_AT (Subject -> Site): {kg.edge_counts['ENROLLED_AT']:,}
  - PARTICIPATES_IN (Site -> Study): {kg.edge_counts['PARTICIPATES_IN']:,}
  - LOCATED_IN (Site -> Country): {kg.edge_counts['LOCATED_IN']:,}
  - IN_REGION (Country -> Region): {kg.edge_counts['IN_REGION']}

Outputs:
  - outputs/knowledge_graph.graphml
  - outputs/knowledge_graph_nodes.csv
  - outputs/knowledge_graph_edges.csv
  - outputs/knowledge_graph_summary.json
  - outputs/knowledge_graph_report.txt
""")
    else:
        print("\nHigh-risk subgraph created successfully!")

    if args.subgraphs or args.high_risk_only:
        print("\nSubgraphs created:")
        if 'high_risk' in (args.subgraphs or '').split(',') or args.high_risk_only:
            print("  - subgraph_high_risk.graphml")
        if 'top_studies' in (args.subgraphs or '').split(','):
            print("  - subgraph_top_studies.graphml")
        if 'sample' in (args.subgraphs or '').split(','):
            print("  - subgraph_sample.graphml")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Visualize: Open .graphml files in Gephi or yEd
2. Import to Neo4j: Use nodes.csv and edges.csv
3. Query: Use the ClinicalTrialKnowledgeGraph class for programmatic access
4. Next script: python src/05_recommendations_engine.py
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Build clinical trial knowledge graph',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/04_knowledge_graph.py                          # Full graph
  python src/04_knowledge_graph.py --subgraphs all          # Full + all subgraphs
  python src/04_knowledge_graph.py --subgraphs high_risk    # Full + high-risk only
  python src/04_knowledge_graph.py --high-risk-only         # ONLY high-risk subgraph
        """
    )
    parser.add_argument(
        '--subgraphs',
        type=str,
        help='Comma-separated list of subgraphs to create: high_risk, top_studies, sample, or "all"'
    )
    parser.add_argument(
        '--high-risk-only',
        action='store_true',
        help='Create ONLY the high-risk subgraph (skip full graph)'
    )

    args = parser.parse_args()

    success = build_knowledge_graph(args)
    if not success:
        exit(1)
