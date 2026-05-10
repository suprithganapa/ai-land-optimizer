import networkx as nx
from shapely.geometry import Point, LineString
import math


def validate_connectivity(plots: list, roads: list, entrance: list) -> dict:
    """
    Build road graph and check every plot is connected to entrance.
    Run Dijkstra for utility routing.
    """
    G = nx.Graph()

    # Add entrance node
    entrance_node = tuple(entrance)
    G.add_node(entrance_node, type="entrance")

    # Add road intersection nodes
    road_nodes = [entrance_node]
    for i, road in enumerate(roads):
        coords = road.get("coordinates", [[]])[0]
        if coords:
            cx = sum(c[0] for c in coords) / len(coords)
            cy = sum(c[1] for c in coords) / len(coords)
            node = (round(cx, 2), round(cy, 2))
            G.add_node(node, type="road")
            road_nodes.append(node)

    # Connect road nodes
    for i in range(len(road_nodes) - 1):
        n1, n2 = road_nodes[i], road_nodes[i + 1]
        dist = math.dist(n1, n2)
        G.add_edge(n1, n2, weight=dist)

    # Add plot nodes + connect to nearest road node
    plot_nodes      = []
    isolated_plots  = []

    for plot in plots:
        coords = plot.get("coordinates", [[]])[0]
        if not coords:
            continue
        cx = sum(c[0] for c in coords) / len(coords)
        cy = sum(c[1] for c in coords) / len(coords)
        pnode = (round(cx, 2), round(cy, 2))
        G.add_node(pnode, type="plot", plot_id=plot["id"])

        # Connect to nearest road node
        nearest = min(road_nodes, key=lambda r: math.dist(r, pnode))
        dist = math.dist(nearest, pnode)
        G.add_edge(pnode, nearest, weight=dist)
        plot_nodes.append(pnode)

        # Check connectivity
        if not nx.has_path(G, pnode, entrance_node):
            isolated_plots.append(plot["id"])

    # Dijkstra — shortest utility path from entrance to all plots
    try:
        lengths = nx.single_source_dijkstra_path_length(G, entrance_node)
        total_utility_length = sum(
            lengths.get(pn, 0) for pn in plot_nodes
        )
    except Exception:
        total_utility_length = 0

    # Connectivity score
    connected_plots = len(plot_nodes) - len(isolated_plots)
    connectivity_pct = round(
        connected_plots / max(1, len(plot_nodes)) * 100, 1
    )

    return {
        "total_plots":        len(plot_nodes),
        "connected_plots":    connected_plots,
        "isolated_plots":     isolated_plots,
        "connectivity_pct":   connectivity_pct,
        "is_fully_connected": len(isolated_plots) == 0,
        "utility_route_length_m": round(total_utility_length, 2),
        "graph_nodes":        G.number_of_nodes(),
        "graph_edges":        G.number_of_edges(),
    }