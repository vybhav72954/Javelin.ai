"""
Javelin.AI - Phase 04: Build Knowledge Graph
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

Usage:
    python src/phases/04_knowledge_graph.py
    python src/phases/04_knowledge_graph.py --subgraphs all
    python src/phases/04_knowledge_graph.py --high-risk-only
"""

import sys
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
# PATH SETUP
# ============================================================================

_SCRIPT_DIR = Path(__file__).parent.resolve()
_SRC_DIR = _SCRIPT_DIR.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# ============================================================================
# CONFIGURATION
# ============================================================================

try:
    from config import PROJECT_ROOT, OUTPUT_DIR
    _USING_CONFIG = True
except ImportError:
    _USING_CONFIG = False
    PROJECT_ROOT = _SRC_DIR.parent
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
    """Knowledge graph for clinical trial data quality intelligence."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_counts = defaultdict(int)
        self.edge_counts = defaultdict(int)
        self.statistics = {}

    def add_node(self, node_id, node_type, **properties):
        self.graph.add_node(node_id, node_type=node_type, **properties)
        self.node_counts[node_type] += 1

    def add_edge(self, source, target, edge_type, **properties):
        self.graph.add_edge(source, target, edge_type=edge_type, **properties)
        self.edge_counts[edge_type] += 1

    def build_from_data(self, subject_df, site_df, study_df=None, region_df=None, country_df=None):
        """Build the knowledge graph from dataframes."""
        print("\nBuilding knowledge graph...")

        # Step 1: Add Region nodes
        print("  Adding Region nodes...")
        if region_df is not None:
            for _, row in region_df.iterrows():
                self.add_node(
                    f"region:{row['region']}", node_type="Region", name=row['region'],
                    site_count=int(row['site_count']), subject_count=int(row['subject_count']),
                    study_count=int(row['study_count']), country_count=int(row['country_count']),
                    avg_dqi_score=round(float(row['avg_dqi_score']), 4),
                    max_dqi_score=round(float(row['max_dqi_score']), 4),
                    high_risk_subjects=int(row['high_risk_subjects']),
                    high_risk_rate=round(float(row['high_risk_rate']), 4),
                    region_risk_category=row['region_risk_category']
                )
        else:
            for region in subject_df['region'].unique():
                self.add_node(f"region:{region}", node_type="Region", name=region)

        # Step 2: Add Country nodes
        print("  Adding Country nodes...")
        if country_df is not None:
            for _, row in country_df.iterrows():
                country_id = f"country:{row['country']}"
                self.add_node(
                    country_id, node_type="Country", name=row['country'], region=row['region'],
                    site_count=int(row['site_count']), subject_count=int(row['subject_count']),
                    study_count=int(row['study_count']),
                    avg_dqi_score=round(float(row['avg_dqi_score']), 4),
                    max_dqi_score=round(float(row['max_dqi_score']), 4),
                    high_risk_subjects=int(row['high_risk_subjects']),
                    high_risk_rate=round(float(row['high_risk_rate']), 4),
                    country_risk_category=row['country_risk_category']
                )
                self.add_edge(country_id, f"region:{row['region']}", edge_type="IN_REGION")
        else:
            country_region = subject_df[['country', 'region']].drop_duplicates()
            for _, row in country_region.iterrows():
                country_id = f"country:{row['country']}"
                self.add_node(country_id, node_type="Country", name=row['country'], region=row['region'])
                self.add_edge(country_id, f"region:{row['region']}", edge_type="IN_REGION")

        # Step 3: Add Study nodes
        print("  Adding Study nodes...")
        if study_df is not None:
            for _, row in study_df.iterrows():
                self.add_node(
                    f"study:{row['study']}", node_type="Study", name=row['study'],
                    subject_count=int(row['subject_count']), site_count=int(row['site_count']),
                    avg_dqi_score=round(float(row['avg_dqi_score']), 4),
                    max_site_dqi_score=round(float(row['max_site_dqi_score']), 4),
                    high_risk_subjects=int(row['high_risk_subjects']),
                    high_risk_rate=round(float(row['high_risk_rate']), 4),
                    high_risk_sites=int(row['high_risk_sites']),
                    subjects_with_issues=int(row['subjects_with_issues']),
                    study_risk_category=row['study_risk_category']
                )
        else:
            study_metrics = subject_df.groupby('study').agg({
                'subject_id': 'count', 'dqi_score': ['mean', 'max'],
                'risk_category': lambda x: (x == 'High').sum(), 'has_issues': 'sum'
            }).reset_index()
            study_metrics.columns = ['study', 'subject_count', 'avg_dqi', 'max_dqi', 'high_risk_count', 'subjects_with_issues']
            site_counts = site_df.groupby('study').size().reset_index(name='site_count')
            study_metrics = study_metrics.merge(site_counts, on='study', how='left')
            for _, row in study_metrics.iterrows():
                self.add_node(
                    f"study:{row['study']}", node_type="Study", name=row['study'],
                    subject_count=int(row['subject_count']), site_count=int(row['site_count']),
                    avg_dqi_score=round(float(row['avg_dqi']), 4),
                    max_dqi_score=round(float(row['max_dqi']), 4),
                    high_risk_count=int(row['high_risk_count']),
                    subjects_with_issues=int(row['subjects_with_issues'])
                )

        # Step 4: Add Site nodes
        print("  Adding Site nodes...")
        for _, row in site_df.iterrows():
            site_id = f"site:{row['study']}:{row['site_id']}"
            self.add_node(
                site_id, node_type="Site", name=row['site_id'], study=row['study'],
                country=row['country'], region=row['region'],
                subject_count=int(row['subject_count']),
                avg_dqi_score=round(float(row['avg_dqi_score']), 4),
                max_dqi_score=round(float(row['max_dqi_score']), 4),
                high_risk_count=int(row['high_risk_count']),
                medium_risk_count=int(row['medium_risk_count']),
                site_risk_category=row['site_risk_category'],
                subjects_with_issues=int(row['subjects_with_issues'])
            )
            self.add_edge(site_id, f"study:{row['study']}", edge_type="PARTICIPATES_IN")
            self.add_edge(site_id, f"country:{row['country']}", edge_type="LOCATED_IN")

        # Step 5: Add Subject nodes
        print("  Adding Subject nodes...")
        subject_cols = ['subject_id', 'study', 'site_id', 'country', 'region', 'subject_status',
                        'dqi_score', 'risk_category', 'n_issue_types', 'has_issues',
                        'sae_pending_count', 'missing_visit_count', 'missing_pages_count', 'lab_issues_count']
        for _, row in subject_df[subject_cols].iterrows():
            subject_node_id = f"subject:{row['study']}:{row['subject_id']}"
            site_node_id = f"site:{row['study']}:{row['site_id']}"
            self.add_node(
                subject_node_id, node_type="Subject", name=row['subject_id'],
                study=row['study'], site_id=row['site_id'], status=row['subject_status'],
                dqi_score=round(float(row['dqi_score']), 4), risk_category=row['risk_category'],
                n_issue_types=int(row['n_issue_types']), has_issues=int(row['has_issues']),
                sae_pending=int(row['sae_pending_count']), missing_visits=int(row['missing_visit_count']),
                missing_pages=int(row['missing_pages_count']), lab_issues=int(row['lab_issues_count'])
            )
            self.add_edge(subject_node_id, site_node_id, edge_type="ENROLLED_AT")

        # Calculate statistics
        self.statistics = {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'node_counts': dict(self.node_counts),
            'edge_counts': dict(self.edge_counts),
            'studies': len(study_df) if study_df is not None else subject_df['study'].nunique(),
            'sites': len(site_df),
            'subjects': len(subject_df),
            'countries': len(country_df) if country_df is not None else subject_df['country'].nunique(),
            'regions': len(region_df) if region_df is not None else subject_df['region'].nunique()
        }
        print(f"  Total nodes: {self.statistics['total_nodes']:,}")
        print(f"  Total edges: {self.statistics['total_edges']:,}")

    def get_high_risk_subgraph(self):
        """Extract subgraph containing only high-risk entities."""
        high_risk_nodes = [n for n, d in self.graph.nodes(data=True)
                          if d.get('risk_category') == 'High' or d.get('site_risk_category') == 'High']
        extended_nodes = set(high_risk_nodes)
        for node in high_risk_nodes:
            extended_nodes.update(self.graph.successors(node))
            extended_nodes.update(self.graph.predecessors(node))
        return self.graph.subgraph(extended_nodes).copy()

    def get_top_studies_subgraph(self, top_n=5):
        """Extract subgraph for top N studies by subject count."""
        study_nodes = [(n, d) for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'Study']
        top_studies = sorted(study_nodes, key=lambda x: x[1].get('subject_count', 0), reverse=True)[:top_n]
        top_study_ids = {node[0] for node in top_studies}
        included_nodes = set(top_study_ids)
        for study_node in top_study_ids:
            included_nodes.update(self.graph.predecessors(study_node))
            for site_node in self.graph.predecessors(study_node):
                included_nodes.update(self.graph.predecessors(site_node))
                included_nodes.update(self.graph.successors(site_node))
        return self.graph.subgraph(included_nodes).copy()

    def get_sample_subgraph(self, sample_size=1000):
        """Extract random sample subgraph."""
        subject_nodes = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'Subject']
        sample_subjects = np.random.choice(subject_nodes, min(sample_size, len(subject_nodes)), replace=False)
        included_nodes = set(sample_subjects)
        for subject_node in sample_subjects:
            included_nodes.update(self.graph.successors(subject_node))
            for connected_node in self.graph.successors(subject_node):
                included_nodes.update(self.graph.successors(connected_node))
        return self.graph.subgraph(included_nodes).copy()

    def export_graphml(self, filepath):
        """Export graph to GraphML format."""
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
        nodes_data = [{'node_id': node_id, **data} for node_id, data in self.graph.nodes(data=True)]
        pd.DataFrame(nodes_data).to_csv(nodes_path, index=False)
        edges_data = [{'source': s, 'target': t, **data} for s, t, data in self.graph.edges(data=True)]
        pd.DataFrame(edges_data).to_csv(edges_path, index=False)

    def export_summary_json(self, filepath):
        """Export summary statistics to JSON."""
        summary = {'statistics': self.statistics, 'risk_by_country': self.get_risk_distribution_by_country()}
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
    if _USING_CONFIG:
        print("(Using centralized config)")

    if not SUBJECT_PATH.exists():
        print(f"\n[ERROR] {SUBJECT_PATH} not found!")
        print("Please run 03_calculate_dqi.py first.")
        return False

    if not SITE_PATH.exists():
        print(f"\n[ERROR] {SITE_PATH} not found!")
        print("Please run 03_calculate_dqi.py first.")
        return False

    print(f"\nLoading data...")
    subject_df = pd.read_csv(SUBJECT_PATH)
    site_df = pd.read_csv(SITE_PATH)

    study_df = pd.read_csv(STUDY_PATH) if STUDY_PATH.exists() else None
    region_df = pd.read_csv(REGION_PATH) if REGION_PATH.exists() else None
    country_df = pd.read_csv(COUNTRY_PATH) if COUNTRY_PATH.exists() else None

    print(f"  Subjects: {len(subject_df):,}")
    print(f"  Sites: {len(site_df):,}")
    if study_df is not None:
        print(f"  Studies: {len(study_df)}")
    if region_df is not None:
        print(f"  Regions: {len(region_df)}")
    if country_df is not None:
        print(f"  Countries: {len(country_df)}")

    # Build Knowledge Graph
    print("\n" + "=" * 70)
    print("STEP 1: BUILD KNOWLEDGE GRAPH")
    print("=" * 70)
    kg = ClinicalTrialKnowledgeGraph()
    kg.build_from_data(subject_df, site_df, study_df, region_df, country_df)

    # Graph Statistics
    print("\n" + "=" * 70)
    print("STEP 2: GRAPH STATISTICS")
    print("=" * 70)
    print(f"\nNode counts by type:")
    for node_type, count in sorted(kg.node_counts.items()):
        print(f"  {node_type}: {count:,}")
    print(f"\nEdge counts by type:")
    for edge_type, count in sorted(kg.edge_counts.items()):
        print(f"  {edge_type}: {count:,}")

    # Sample Queries
    print("\n" + "=" * 70)
    print("STEP 3: SAMPLE QUERIES")
    print("=" * 70)
    print("\nHigh-risk subjects by study:")
    if study_df is not None:
        top_studies = study_df.nlargest(5, 'high_risk_subjects')[['study', 'high_risk_subjects', 'study_risk_category']]
        for _, row in top_studies.iterrows():
            print(f"  {row['study']}: {int(row['high_risk_subjects']):,} high-risk [{row['study_risk_category']}]")

    print("\nRisk summary by region:")
    if region_df is not None:
        for _, row in region_df.iterrows():
            print(f"  {row['region']}: {int(row['site_count'])} sites, DQI={row['avg_dqi_score']:.4f}, "
                  f"High-risk={row['high_risk_rate']*100:.1f}% [{row['region_risk_category']}]")

    # Export Full Graph
    if not args.high_risk_only:
        print("\n" + "=" * 70)
        print("STEP 4: EXPORT FULL KNOWLEDGE GRAPH")
        print("=" * 70)

        graphml_path = OUTPUT_DIR / "knowledge_graph.graphml"
        print(f"\nExporting GraphML...")
        kg.export_graphml(graphml_path)
        print(f"  [OK] Saved: {graphml_path}")

        nodes_path = OUTPUT_DIR / "knowledge_graph_nodes.csv"
        edges_path = OUTPUT_DIR / "knowledge_graph_edges.csv"
        print(f"\nExporting Neo4j CSVs...")
        kg.export_neo4j_csv(nodes_path, edges_path)
        print(f"  [OK] Saved: {nodes_path}")
        print(f"  [OK] Saved: {edges_path}")

        summary_path = OUTPUT_DIR / "knowledge_graph_summary.json"
        print(f"\nExporting summary JSON...")
        kg.export_summary_json(summary_path)
        print(f"  [OK] Saved: {summary_path}")

    # Export Subgraphs
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
                print(f"  [OK] Saved: {filepath}")
                print(f"  Nodes: {subgraph.number_of_nodes():,}, Edges: {subgraph.number_of_edges():,}")
            elif subgraph_type == 'top_studies':
                print(f"\nCreating top-5 studies subgraph...")
                subgraph = kg.get_top_studies_subgraph(top_n=5)
                filepath = OUTPUT_DIR / "subgraph_top_studies.graphml"
                kg.export_subgraph_graphml(subgraph, filepath)
                print(f"  [OK] Saved: {filepath}")
                print(f"  Nodes: {subgraph.number_of_nodes():,}, Edges: {subgraph.number_of_edges():,}")
            elif subgraph_type == 'sample':
                print(f"\nCreating random sample subgraph (1000 subjects)...")
                subgraph = kg.get_sample_subgraph(sample_size=1000)
                filepath = OUTPUT_DIR / "subgraph_sample.graphml"
                kg.export_subgraph_graphml(subgraph, filepath)
                print(f"  [OK] Saved: {filepath}")
                print(f"  Nodes: {subgraph.number_of_nodes():,}, Edges: {subgraph.number_of_edges():,}")

    # Generate Report
    if not args.high_risk_only:
        print("\n" + "=" * 70)
        print("STEP 6: GENERATE REPORT")
        print("=" * 70)
        report_path = OUTPUT_DIR / "knowledge_graph_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("JAVELIN.AI - KNOWLEDGE GRAPH REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write("GRAPH STRUCTURE\n" + "-" * 40 + "\n")
            f.write(f"Total Nodes: {kg.statistics['total_nodes']:,}\n")
            f.write(f"Total Edges: {kg.statistics['total_edges']:,}\n\n")
            f.write("NODE TYPES\n" + "-" * 40 + "\n")
            for node_type, count in sorted(kg.node_counts.items()):
                f.write(f"  {node_type}: {count:,}\n")
            f.write("\nEDGE TYPES\n" + "-" * 40 + "\n")
            for edge_type, count in sorted(kg.edge_counts.items()):
                f.write(f"  {edge_type}: {count:,}\n")
            f.write("\nHIERARCHY\n" + "-" * 40 + "\n")
            f.write(f"Region ({kg.node_counts.get('Region', 0)})\n")
            f.write(f"  -> Country ({kg.node_counts.get('Country', 0)})\n")
            f.write(f"       -> Site ({kg.node_counts.get('Site', 0):,})\n")
            f.write(f"            -> Subject ({kg.node_counts.get('Subject', 0):,})\n")
            f.write(f"Study ({kg.node_counts.get('Study', 0)})\n")
            f.write(f"  -> Site ({kg.node_counts.get('Site', 0):,})\n")
            f.write(f"       -> Subject ({kg.node_counts.get('Subject', 0):,})\n\n")
            if region_df is not None:
                f.write("RISK DISTRIBUTION BY REGION\n" + "-" * 40 + "\n")
                for _, row in region_df.iterrows():
                    f.write(f"{row['region']}: {int(row['high_risk_subjects']):,} high-risk / "
                            f"{int(row['subject_count']):,} total ({row['high_risk_rate']*100:.1f}%) [{row['region_risk_category']}]\n")
        print(f"  [OK] Saved: {report_path}")

    # Summary
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
""")
    else:
        print("\nHigh-risk subgraph created successfully!")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Visualize: Open .graphml files in Gephi or yEd
2. Import to Neo4j: Use nodes.csv and edges.csv
3. Next script: python src/phases/05_recommendations_engine.py
""")
    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build clinical trial knowledge graph')
    parser.add_argument('--subgraphs', type=str, help='Comma-separated: high_risk, top_studies, sample, or "all"')
    parser.add_argument('--high-risk-only', action='store_true', help='Create ONLY the high-risk subgraph')
    args = parser.parse_args()

    success = build_knowledge_graph(args)
    if not success:
        exit(1)
