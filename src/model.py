"""
model.py — плоскостная модель мобильной P2P-сети.

Модуль отвечает за:
1. генерацию синтетических узлов на условной двумерной плоскости;
2. построение radius graph по евклидовому расстоянию;
3. построение k-NN graph по евклидовому расстоянию.

Координаты x/y в этом модуле не являются широтой и долготой. Для реальных
географических координат используется отдельный модуль ``model_geo.py``.
"""

from __future__ import annotations

import math
from typing import Tuple

import networkx as nx
import numpy as np
import pandas as pd


DEFAULT_NODE_COLUMNS = [
    "id",
    "x",
    "y",
    "radius",
    "state",
    "trust",
    "load",
    "behavior",
    "coord_type",
]


def generate_nodes(
    n: int = 50,
    x_range: Tuple[float, float] = (0.0, 100.0),
    y_range: Tuple[float, float] = (0.0, 100.0),
    radius: float = 15.0,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Генерирует таблицу узлов на условной координатной плоскости.

    Parameters
    ----------
    n:
        Количество узлов.
    x_range, y_range:
        Диапазоны синтетических координат.
    radius:
        Радиус уверенной связи в условных единицах.
    seed:
        Seed генератора случайных чисел для воспроизводимости.

    Returns
    -------
    pandas.DataFrame
        Таблица с колонками ``id, x, y, radius, state, trust, load, behavior``.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if radius < 0:
        raise ValueError("radius must be non-negative")

    rng = np.random.default_rng(seed)
    xs = rng.uniform(x_range[0], x_range[1], n)
    ys = rng.uniform(y_range[0], y_range[1], n)

    return pd.DataFrame(
        {
            "id": [f"n_{i:03d}" for i in range(n)],
            "x": xs,
            "y": ys,
            "radius": float(radius),
            "state": "normal",
            "trust": 1.0,
            "load": 0.0,
            "behavior": "normal",
            "coord_type": "plane",
        },
        columns=DEFAULT_NODE_COLUMNS,
    )


def _add_nodes_from_dataframe(G: nx.Graph, nodes: pd.DataFrame) -> None:
    """Добавляет в граф узлы со всеми атрибутами из DataFrame."""
    required = {"id", "x", "y"}
    missing = required - set(nodes.columns)
    if missing:
        raise ValueError(f"nodes DataFrame is missing required columns: {sorted(missing)}")

    for _, row in nodes.iterrows():
        G.add_node(str(row["id"]), **row.to_dict())


def euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Евклидово расстояние между двумя точками на плоскости."""
    return math.hypot(x2 - x1, y2 - y1)


def build_radius_graph(
    nodes: pd.DataFrame,
    radius_col: str = "radius",
    x_col: str = "x",
    y_col: str = "y",
) -> nx.Graph:
    """
    Строит неориентированный радиусный граф сетевой близости.

    Ребро ``(i, j)`` создаётся, если расстояние между узлами не превосходит
    индивидуальный радиус каждого из них:

    ``d(i, j) <= min(r_i, r_j)``.
    """
    if radius_col not in nodes.columns:
        raise ValueError(f"nodes DataFrame is missing radius column: {radius_col}")

    G = nx.Graph(graph_type="radius", coord_type="plane")
    _add_nodes_from_dataframe(G, nodes)

    coords = nodes[[x_col, y_col]].to_numpy(dtype=float)
    ids = nodes["id"].astype(str).to_list()
    radii = nodes[radius_col].to_numpy(dtype=float)

    n = len(nodes)
    for i in range(n):
        for j in range(i + 1, n):
            dist = euclidean_distance(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
            if dist <= radii[i] and dist <= radii[j]:
                G.add_edge(ids[i], ids[j], weight=float(dist))

    return G


def build_knn_graph(
    nodes: pd.DataFrame,
    k: int = 5,
    x_col: str = "x",
    y_col: str = "y",
) -> nx.Graph:
    """
    Строит симметризованный граф k ближайших соседей на плоскости.

    Для каждого узла выбираются ``k`` ближайших соседей по евклидовому
    расстоянию. Граф неориентированный: если ``B`` выбран соседом для ``A``,
    ребро ``A--B`` добавляется независимо от обратного выбора.
    """
    if k <= 0:
        raise ValueError("k must be a positive integer")

    G = nx.Graph(graph_type="knn", coord_type="plane", k=int(k))
    _add_nodes_from_dataframe(G, nodes)

    coords = nodes[[x_col, y_col]].to_numpy(dtype=float)
    ids = nodes["id"].astype(str).to_list()
    n = len(nodes)
    if n <= 1:
        return G

    k_eff = min(int(k), n - 1)
    for i in range(n):
        dists = []
        for j in range(n):
            if i == j:
                continue
            dist = euclidean_distance(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
            dists.append((j, float(dist)))

        dists.sort(key=lambda item: item[1])
        for j, dist in dists[:k_eff]:
            if not G.has_edge(ids[i], ids[j]):
                G.add_edge(ids[i], ids[j], weight=dist)

    return G
