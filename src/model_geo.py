"""
model_geo.py — географическая модель мобильной P2P-сети.

Модуль отвечает за:
1. генерацию узлов в реальных координатах внутри bbox;
2. построение radius graph с использованием haversine-метрики;
3. построение k-NN graph с использованием haversine-метрики.

Соглашение по координатам:
- x = longitude / долгота;
- y = latitude / широта;
- radius = радиус связи в метрах.
"""

from __future__ import annotations

import math
from typing import Tuple

import networkx as nx
import numpy as np
import pandas as pd


EARTH_RADIUS_M = 6_371_000


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Возвращает расстояние между двумя точками в метрах по сферической модели Земли.

    Parameters
    ----------
    lon1, lat1, lon2, lat2:
        Долгота и широта двух точек в градусах.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def generate_nodes_geo(
    bbox: Tuple[float, float, float, float],
    n: int = 50,
    radius_m: float = 500.0,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Генерирует DataFrame узлов внутри географической рамки.

    Parameters
    ----------
    bbox:
        Кортеж ``(min_lon, min_lat, max_lon, max_lat)``.
    n:
        Количество узлов.
    radius_m:
        Радиус уверенной связи в метрах.
    seed:
        Seed генератора случайных чисел.
    """
    if len(bbox) != 4:
        raise ValueError("bbox must contain 4 values: min_lon, min_lat, max_lon, max_lat")
    min_lon, min_lat, max_lon, max_lat = map(float, bbox)
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("bbox must satisfy min_lon < max_lon and min_lat < max_lat")
    if n < 0:
        raise ValueError("n must be non-negative")
    if radius_m < 0:
        raise ValueError("radius_m must be non-negative")

    rng = np.random.default_rng(seed)
    lons = rng.uniform(min_lon, max_lon, n)
    lats = rng.uniform(min_lat, max_lat, n)

    return pd.DataFrame(
        {
            "id": [f"n_{i:03d}" for i in range(n)],
            "x": lons,
            "y": lats,
            "radius": float(radius_m),
            "state": "normal",
            "trust": 1.0,
            "load": 0.0,
            "behavior": "normal",
            "coord_type": "geo",
        }
    )


def _add_nodes_from_dataframe(G: nx.Graph, nodes: pd.DataFrame) -> None:
    """Добавляет в граф узлы со всеми атрибутами из DataFrame."""
    required = {"id", "x", "y"}
    missing = required - set(nodes.columns)
    if missing:
        raise ValueError(f"nodes DataFrame is missing required columns: {sorted(missing)}")

    for _, row in nodes.iterrows():
        G.add_node(str(row["id"]), **row.to_dict())


def build_radius_graph_geo(
    nodes: pd.DataFrame,
    radius_col: str = "radius",
    x_col: str = "x",
    y_col: str = "y",
) -> nx.Graph:
    """
    Строит радиусный граф в географических координатах.

    Ребро создаётся, если haversine-расстояние между узлами не превышает
    радиус связи каждого из двух узлов: ``d <= min(r_i, r_j)``.
    """
    if radius_col not in nodes.columns:
        raise ValueError(f"nodes DataFrame is missing radius column: {radius_col}")

    G = nx.Graph(graph_type="radius", coord_type="geo")
    _add_nodes_from_dataframe(G, nodes)

    coords = nodes[[x_col, y_col]].to_numpy(dtype=float)  # lon, lat
    ids = nodes["id"].astype(str).to_list()
    radii = nodes[radius_col].to_numpy(dtype=float)

    n = len(nodes)
    for i in range(n):
        lon_i, lat_i = coords[i]
        for j in range(i + 1, n):
            lon_j, lat_j = coords[j]
            dist = haversine(lon_i, lat_i, lon_j, lat_j)
            if dist <= radii[i] and dist <= radii[j]:
                G.add_edge(ids[i], ids[j], weight=float(dist))

    return G


def build_knn_graph_geo(
    nodes: pd.DataFrame,
    k: int = 5,
    x_col: str = "x",
    y_col: str = "y",
) -> nx.Graph:
    """
    Строит симметризованный k-NN граф на основе haversine-расстояния.
    """
    if k <= 0:
        raise ValueError("k must be a positive integer")

    G = nx.Graph(graph_type="knn", coord_type="geo", k=int(k))
    _add_nodes_from_dataframe(G, nodes)

    coords = nodes[[x_col, y_col]].to_numpy(dtype=float)
    ids = nodes["id"].astype(str).to_list()
    n = len(nodes)
    if n <= 1:
        return G

    k_eff = min(int(k), n - 1)
    for i in range(n):
        lon_i, lat_i = coords[i]
        dists = []
        for j in range(n):
            if i == j:
                continue
            lon_j, lat_j = coords[j]
            d = haversine(lon_i, lat_i, lon_j, lat_j)
            dists.append((j, float(d)))

        dists.sort(key=lambda item: item[1])
        for j, dist in dists[:k_eff]:
            if not G.has_edge(ids[i], ids[j]):
                G.add_edge(ids[i], ids[j], weight=dist)

    return G
