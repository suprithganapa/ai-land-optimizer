import math
import networkx as nx


def validate_connectivity(plots: list, roads: list, entrance: list) -> dict:
    G              = nx.Graph()
    entrance_node  = (round(entrance[0], 2), round(entrance[1], 2))
    G.add_node(entrance_node, type="entrance")

    road_nodes = [entrance_node]
    for road in roads:
        coords = road.get("coordinates", [[]])[0]
        if coords:
            cx = sum(c[0] for c in coords) / len(coords)
            cy = sum(c[1] for c in coords) / len(coords)
            n  = (round(cx, 2), round(cy, 2))
            G.add_node(n, type="road")
            road_nodes.append(n)

    for i in range(len(road_nodes) - 1):
        n1, n2 = road_nodes[i], road_nodes[i + 1]
        G.add_edge(n1, n2, weight=math.dist(n1, n2))

    plot_nodes     = []
    isolated_plots = []

    for plot in plots:
        coords = plot.get("coordinates", [[]])[0]
        if not coords:
            continue
        cx = sum(c[0] for c in coords) / len(coords)
        cy = sum(c[1] for c in coords) / len(coords)
        pn = (round(cx, 2), round(cy, 2))
        G.add_node(pn, type="plot", plot_id=plot["id"])

        nearest = min(road_nodes, key=lambda r: math.dist(r, pn))
        G.add_edge(pn, nearest, weight=math.dist(nearest, pn))
        plot_nodes.append(pn)

        if not nx.has_path(G, pn, entrance_node):
            isolated_plots.append(plot["id"])

    try:
        lengths              = nx.single_source_dijkstra_path_length(G, entrance_node)
        utility_route_length = sum(lengths.get(pn, 0) for pn in plot_nodes)
    except Exception:
        utility_route_length = 0.0

    connected    = len(plot_nodes) - len(isolated_plots)
    connectivity = round(connected / max(1, len(plot_nodes)) * 100, 1)

    print(f"  🔍 NetworkX: {connected}/{len(plot_nodes)} plots connected "
          f"({connectivity}%), utility route={round(utility_route_length, 1)}m")

    return {
        "total_plots":            len(plot_nodes),
        "connected_plots":        connected,
        "isolated_plots":         isolated_plots,
        "connectivity_pct":       connectivity,
        "is_fully_connected":     len(isolated_plots) == 0,
        "utility_route_length_m": round(utility_route_length, 2),
        "graph_nodes":            G.number_of_nodes(),
        "graph_edges":            G.number_of_edges(),
    }