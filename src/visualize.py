"""
visualize.py — статическая и интерактивная визуализация графов.
"""

from __future__ import annotations

import os
from pathlib import Path

import folium
import matplotlib.pyplot as plt
import networkx as nx


STATE_COLORS = {
    "normal": "limegreen",
    "suspicious": "orange",
    "malicious": "red",
    "isolated": "gray",
}


def _ensure_parent(path: str | os.PathLike) -> None:
    parent = Path(path).parent
    if str(parent):
        parent.mkdir(parents=True, exist_ok=True)


def draw_graph(G: nx.Graph, save_path: str, title: str = "Network Topology") -> None:
    """Рисует граф с учётом координат узлов и сохраняет PNG."""
    _ensure_parent(save_path)

    plt.figure(figsize=(10, 8))
    pos = {node: (G.nodes[node].get("x", 0.0), G.nodes[node].get("y", 0.0)) for node in G.nodes}
    colors = [STATE_COLORS.get(G.nodes[node].get("state", "normal"), "blue") for node in G.nodes]
    loads = [float(G.nodes[node].get("load", 0.0) or 0.0) for node in G.nodes]
    sizes = [70 + min(load * 12, 180) for load in loads]

    nx.draw_networkx(
        G,
        pos,
        node_color=colors,
        node_size=sizes,
        edge_color="lightgray",
        with_labels=False,
        alpha=0.85,
        linewidths=0.5,
    )
    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def draw_geo_map(G: nx.Graph, save_path: str = "outputs/maps/geo_map.html") -> folium.Map:
    """
    Создаёт интерактивную карту Folium.

    Ожидаемое соглашение координат: ``x = lon``, ``y = lat``. Для plane-режима
    карта является условной визуализацией; для geo-режима — реальной привязкой.
    """
    _ensure_parent(save_path)

    if G.number_of_nodes() == 0:
        m = folium.Map(location=[0, 0], zoom_start=2)
        m.save(save_path)
        return m

    lats = [float(G.nodes[node].get("y", 0.0)) for node in G.nodes]
    lons = [float(G.nodes[node].get("x", 0.0)) for node in G.nodes]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)]
    zoom = 13 if G.graph.get("coord_type") == "geo" else 4
    m = folium.Map(location=center, zoom_start=zoom)

    for u, v in G.edges():
        u_lat = float(G.nodes[u].get("y", 0.0))
        u_lon = float(G.nodes[u].get("x", 0.0))
        v_lat = float(G.nodes[v].get("y", 0.0))
        v_lon = float(G.nodes[v].get("x", 0.0))
        folium.PolyLine(
            locations=[[u_lat, u_lon], [v_lat, v_lon]],
            color="lightblue",
            weight=1,
            opacity=0.45,
        ).add_to(m)

    for node in G.nodes:
        lat = float(G.nodes[node].get("y", 0.0))
        lon = float(G.nodes[node].get("x", 0.0))
        state = G.nodes[node].get("state", "normal")
        color = STATE_COLORS.get(state, "blue")
        load = float(G.nodes[node].get("load", 0.0) or 0.0)
        folium.CircleMarker(
            location=[lat, lon],
            radius=5 + min(load, 12) * 0.3,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            tooltip=f"{node} | state={state} | load={load:.2f}",
        ).add_to(m)

    m.save(save_path)
    return m


def plot_metric_comparison(
    baseline_metrics: dict,
    scenario_metrics: dict,
    save_path: str,
    title: str = "Metric Comparison",
) -> None:
    """Строит столбчатую диаграмму сравнения ключевых метрик."""
    _ensure_parent(save_path)

    metric_names = [
        "density",
        "avg_degree",
        "num_components",
        "largest_component_size",
        "isolated_nodes",
    ]
    labels = ["Density", "Avg Degree", "Components", "LCC", "Isolated"]
    baseline_vals = [baseline_metrics.get(metric, 0.0) for metric in metric_names]
    scenario_vals = [scenario_metrics.get(metric, 0.0) for metric in metric_names]

    x = range(len(labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar([i - width / 2 for i in x], baseline_vals, width, label="Baseline")
    ax.bar([i + width / 2 for i in x], scenario_vals, width, label="After Threat")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=20)
    ax.legend()
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close(fig)
