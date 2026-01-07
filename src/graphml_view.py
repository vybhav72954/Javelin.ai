import networkx as nx
import matplotlib.pyplot as plt

# Load the graph from file
G = nx.read_graphml("../outputs/knowledge_graph.graphml")

# Draw the graph
nx.draw(G, with_labels=True)
plt.show()