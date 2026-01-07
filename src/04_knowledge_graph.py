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

Usage:
    python src/04_build_knowledge_graph.py
"""

import pandas as pd
import numpy as np
import networkx as nx
import json
from pathlib import Path
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

OUTPUT_DIR = Path("outputs")
SUBJECT_PATH = OUTPUT_DIR / "master_subject_with_dqi.csv"
SITE_PATH = OUTPUT_DIR / "master_site_with_dqi.csv"


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

    def build_from_data(self, subject_df, site_df):
        """
        Build the knowledge graph from subject and site dataframes.
        """
        print("\nBuilding knowledge graph...")

        # =====================================================================
        # Step 1: Add Region nodes
        # =====================================================================
        print("  Adding Region nodes...")
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
        country_region = subject_df[['country', 'region']].drop_duplicates()
        for _, row in country_region.iterrows():
            country_id = f"country:{row['country']}"
            self.add_node(
                country_id,
                node_type="Country",
                name=row['country'],
                region=row['region']
            )
            # Country -> Region relationship
            self.add_edge(
                country_id,
                f"region:{row['region']}",
                edge_type="IN_REGION"
            )

        # =====================================================================
        # Step 3: Add Study nodes with aggregated metrics
        # =====================================================================
        print("  Adding Study nodes...")
        study_metrics = subject_df.groupby('study').agg({
            'subject_id':'count',
            'dqi_score':['mean', 'max'],
            'risk_category':lambda x:(x=='High').sum(),
            'has_issues':'sum'
        }).reset_index()
        study_metrics.columns = ['study', 'subject_count', 'avg_dqi', 'max_dqi',
                                 'high_risk_count', 'subjects_with_issues']

        # Get site counts per study
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
        self.statistics = {
            'total_nodes':self.graph.number_of_nodes(),
            'total_edges':self.graph.number_of_edges(),
            'node_counts':dict(self.node_counts),
            'edge_counts':dict(self.edge_counts),
            'studies':len(study_metrics),
            'sites':len(site_df),
            'subjects':len(subject_df),
            'countries':len(country_region),
            'regions':len(regions)
        }

        print(f"  Total nodes: {self.statistics['total_nodes']:,}")
        print(f"  Total edges: {self.statistics['total_edges']:,}")

    def get_high_risk_subgraph(self):
        """Extract subgraph containing only high-risk subjects and their connections."""
        high_risk_nodes = [
            n for n, d in self.graph.nodes(data=True)
            if d.get('risk_category')=='High' or d.get('site_risk_category')=='High'
        ]

        # Also include connected sites and studies
        extended_nodes = set(high_risk_nodes)
        for node in high_risk_nodes:
            extended_nodes.update(self.graph.successors(node))
            extended_nodes.update(self.graph.predecessors(node))

        return self.graph.subgraph(extended_nodes)

    def query_site_subjects(self, study, site_id):
        """Get all subjects at a specific site."""
        site_node = f"site:{study}:{site_id}"
        if site_node not in self.graph:
            return []

        subjects = []
        for pred in self.graph.predecessors(site_node):
            if self.graph.nodes[pred].get('node_type')=='Subject':
                subjects.append(self.graph.nodes[pred])
        return subjects

    def query_study_metrics(self, study):
        """Get aggregated metrics for a study."""
        study_node = f"study:{study}"
        if study_node not in self.graph:
            return None
        return dict(self.graph.nodes[study_node])

    def get_risk_distribution_by_country(self):
        """Get risk distribution grouped by country."""
        distribution = defaultdict(lambda:{'High':0, 'Medium':0, 'Low':0, 'total':0})

        for node, data in self.graph.nodes(data=True):
            if data.get('node_type')=='Subject':
                country = data.get('country', 'Unknown')
                risk = data.get('risk_category', 'Unknown')
                if risk in distribution[country]:
                    distribution[country][risk] += 1
                distribution[country]['total'] += 1

        return dict(distribution)

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

    def export_neo4j_csv(self, nodes_path, edges_path):
        """Export to CSV format for Neo4j import."""
        # Nodes
        nodes_data = []
        for node_id, data in self.graph.nodes(data=True):
            node_row = {'node_id':node_id}
            node_row.update(data)
            nodes_data.append(node_row)

        nodes_df = pd.DataFrame(nodes_data)
        nodes_df.to_csv(nodes_path, index=False)

        # Edges
        edges_data = []
        for source, target, data in self.graph.edges(data=True):
            edge_row = {
                'source':source,
                'target':target
            }
            edge_row.update(data)
            edges_data.append(edge_row)

        edges_df = pd.DataFrame(edges_data)
        edges_df.to_csv(edges_path, index=False)

    def export_summary_json(self, filepath):
        """Export summary statistics to JSON."""
        summary = {
            'statistics':self.statistics,
            'risk_by_country':self.get_risk_distribution_by_country()
        }

        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def build_knowledge_graph():
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

    print(f"  Subjects: {len(subject_df):,}")
    print(f"  Sites: {len(site_df):,}")
    print(f"  Studies: {subject_df['study'].nunique()}")

    # -------------------------------------------------------------------------
    # Build Knowledge Graph
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 1: BUILD KNOWLEDGE GRAPH")
    print("=" * 70)

    kg = ClinicalTrialKnowledgeGraph()
    kg.build_from_data(subject_df, site_df)

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
    study_risk = subject_df.groupby('study')['risk_category'].apply(
        lambda x:(x=='High').sum()
    ).sort_values(ascending=False).head(5)
    for study, count in study_risk.items():
        print(f"  {study}: {count:,} high-risk subjects")

    # Query 2: Top countries by average DQI
    print("\nTop 5 countries by average DQI score:")
    country_dqi = subject_df.groupby('country')['dqi_score'].mean().sort_values(ascending=False).head(5)
    for country, dqi in country_dqi.items():
        print(f"  {country}: {dqi:.4f}")

    # Query 3: Risk distribution by region
    print("\nRisk distribution by region:")
    region_risk = subject_df.groupby(['region', 'risk_category']).size().unstack(fill_value=0)
    print(region_risk.to_string())

    # -------------------------------------------------------------------------
    # Export Graph
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 4: EXPORT KNOWLEDGE GRAPH")
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
    # Generate Report
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 5: GENERATE REPORT")
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
        f.write("Region (3)\n")
        f.write("  └── Country (71)\n")
        f.write("        └── Site (3,399)\n")
        f.write("              └── Subject (57,997)\n")
        f.write("Study (23)\n")
        f.write("  └── Site (3,399)\n")
        f.write("        └── Subject (57,997)\n\n")

        f.write("RISK DISTRIBUTION BY REGION\n")
        f.write("-" * 40 + "\n")
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

    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Visualize: Open knowledge_graph.graphml in Gephi or yEd
2. Import to Neo4j: Use nodes.csv and edges.csv
3. Query: Use the ClinicalTrialKnowledgeGraph class for programmatic access
4. Next script: python src/05_generate_insights.py (or build dashboard)
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__=="__main__":
    success = build_knowledge_graph()
    if not success:
        exit(1)