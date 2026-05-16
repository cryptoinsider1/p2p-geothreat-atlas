"""
metrics.py — расчёт графовых, нагрузочных и сравнительных метрик.
"""

from __future__ import annotations

from typing import Dict, Iterable, Tuple

import networkx as nx
import numpy as np
import pandas as pd


LOAD_ANOMALY_THRESHOLD = 5.0


def _safe_float(value: float) -> float:
    """Преобразует numpy-числа в обычный float для стабильной сериализации CSV/JSON."""
    if value is None:
        return 0.0
    try:
        if np.isnan(value):
            return 0.0
    except TypeError:
        pass
    return float(value)


def compute_metrics(G: nx.Graph, load_threshold: float = LOAD_ANOMALY_THRESHOLD) -> Dict[str, float]:
    """
    Возвращает словарь основных структурных и нагрузочных метрик графа.

    Метрики делятся на два слоя:
    1. топологические: связность, плотность, центральности, кластеризация;
    2. нагрузочные: суммарная/средняя/максимальная нагрузка и число аномалий.
    """
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    if n_nodes == 0:
        return {
            "nodes": 0,
            "edges": 0,
            "density": 0.0,
            "avg_degree": 0.0,
            "num_components": 0,
            "largest_component_size": 0,
            "isolated_nodes": 0,
            "avg_clustering": 0.0,
            "max_degree_centrality": 0.0,
            "max_betweenness_centrality": 0.0,
            "degree_centrality_std": 0.0,
            "total_load": 0.0,
            "max_load": 0.0,
            "avg_load": 0.0,
            "load_std": 0.0,
            "load_anomaly_count": 0,
        }

    comps = list(nx.connected_components(G))
    lcc = max((len(c) for c in comps), default=0)
    isolated = sum(1 for v in G.nodes if G.degree(v) == 0)

    degree_centrality = nx.degree_centrality(G)
    betweenness_centrality = nx.betweenness_centrality(G, weight=None)

    loads = np.array([float(G.nodes[v].get("load", 0.0) or 0.0) for v in G.nodes], dtype=float)

    metrics = {
        "nodes": int(n_nodes),
        "edges": int(n_edges),
        "density": _safe_float(nx.density(G)),
        "avg_degree": _safe_float((2 * n_edges / n_nodes) if n_nodes else 0.0),
        "num_components": int(len(comps)),
        "largest_component_size": int(lcc),
        "isolated_nodes": int(isolated),
        "avg_clustering": _safe_float(nx.average_clustering(G) if n_nodes else 0.0),
        "max_degree_centrality": _safe_float(max(degree_centrality.values()) if degree_centrality else 0.0),
        "max_betweenness_centrality": _safe_float(
            max(betweenness_centrality.values()) if betweenness_centrality else 0.0
        ),
        "degree_centrality_std": _safe_float(
            np.std(list(degree_centrality.values())) if degree_centrality else 0.0
        ),
        "total_load": _safe_float(loads.sum()),
        "max_load": _safe_float(loads.max() if len(loads) else 0.0),
        "avg_load": _safe_float(loads.mean() if len(loads) else 0.0),
        "load_std": _safe_float(loads.std(ddof=0) if len(loads) else 0.0),
        "load_anomaly_count": int(np.sum(loads >= load_threshold)),
    }
    return metrics


def compare_scenarios(baseline_metrics: Dict[str, float], scenario_metrics: Dict[str, float]) -> pd.DataFrame:
    """
    Создаёт DataFrame сравнения baseline и одного сценария.
    """
    df = pd.DataFrame([baseline_metrics, scenario_metrics], index=["Baseline", "After Threat"]).T
    df["Change"] = df["After Threat"] - df["Baseline"]
    return df


def compute_centrality_stats(G: nx.Graph, top_n: int = 3) -> Tuple[list, list]:
    """
    Возвращает топ узлов по degree centrality и betweenness centrality.
    """
    if G.number_of_nodes() == 0:
        return [], []

    deg = nx.degree_centrality(G)
    bet = nx.betweenness_centrality(G, weight=None)
    top_deg = sorted(deg.items(), key=lambda item: item[1], reverse=True)[:top_n]
    top_bet = sorted(bet.items(), key=lambda item: item[1], reverse=True)[:top_n]
    return top_deg, top_bet
