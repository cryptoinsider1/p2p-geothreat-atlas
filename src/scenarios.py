"""
scenarios.py — сценарии угроз и аномального поведения.

Все функции принимают граф NetworkX и возвращают изменённую копию графа.
Исходный граф не мутируется.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

import networkx as nx
import numpy as np


DistanceFn = Callable[[float, float, float, float], float]


def _euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return float(np.hypot(x2 - x1, y2 - y1))


def _sorted_nodes(G: nx.Graph) -> list[str]:
    """Детерминированный порядок узлов для воспроизводимости."""
    return sorted(str(n) for n in G.nodes)


def apply_baseline(G: nx.Graph) -> nx.Graph:
    """Возвращает копию графа без изменений."""
    return G.copy()


def apply_rogue_node(
    G: nx.Graph,
    n_malicious: int = 1,
    extra_radius_mult: float = 2.0,
    seed: Optional[int] = None,
    distance_fn: Optional[DistanceFn] = None,
) -> nx.Graph:
    """
    Делает выбранные узлы вредоносными и добавляет им дополнительные связи.

    Для плоскости используется евклидово расстояние, для geo-режима можно
    передать ``haversine`` через ``distance_fn``.
    """
    G_mod = G.copy()
    nodes = _sorted_nodes(G_mod)
    if not nodes or n_malicious <= 0:
        return G_mod

    rng = np.random.default_rng(seed)
    targets = rng.choice(nodes, size=min(n_malicious, len(nodes)), replace=False)
    dist = distance_fn or _euclidean_distance

    for node in targets:
        G_mod.nodes[node]["state"] = "malicious"
        G_mod.nodes[node]["behavior"] = "rogue"
        base_r = float(G_mod.nodes[node].get("radius", 10.0) or 10.0)
        big_r = base_r * float(extra_radius_mult)
        x1 = float(G_mod.nodes[node].get("x", 0.0))
        y1 = float(G_mod.nodes[node].get("y", 0.0))

        for other in nodes:
            if other == node:
                continue
            x2 = float(G_mod.nodes[other].get("x", 0.0))
            y2 = float(G_mod.nodes[other].get("y", 0.0))
            d = dist(x1, y1, x2, y2)
            if d <= big_r:
                G_mod.add_edge(node, other, weight=float(d))

    return G_mod


def apply_flooding(
    G: nx.Graph,
    n_flooders: int = 1,
    load_mult: float = 10.0,
    seed: Optional[int] = None,
) -> nx.Graph:
    """Назначает части узлов аномально высокую нагрузку без изменения топологии."""
    G_mod = G.copy()
    nodes = _sorted_nodes(G_mod)
    if not nodes or n_flooders <= 0:
        return G_mod

    rng = np.random.default_rng(seed)
    flooders = rng.choice(nodes, size=min(n_flooders, len(nodes)), replace=False)
    for node in flooders:
        G_mod.nodes[node]["behavior"] = "flooder"
        G_mod.nodes[node]["state"] = "suspicious"
        G_mod.nodes[node]["load"] = float(G_mod.nodes[node].get("load", 0.0) or 0.0) + float(load_mult)

    return G_mod


def apply_isolation(
    G: nx.Graph,
    n_isolate: int = 3,
    method: str = "random",
    seed: Optional[int] = None,
) -> nx.Graph:
    """
    Изолирует узлы, удаляя все их инцидентные рёбра.

    method:
    - ``random`` — случайный выбор;
    - ``high_betweenness`` — выбор узлов с максимальной betweenness centrality.
    """
    G_mod = G.copy()
    nodes = _sorted_nodes(G_mod)
    if not nodes or n_isolate <= 0:
        return G_mod

    n_targets = min(n_isolate, len(nodes))
    if method == "high_betweenness":
        bc = nx.betweenness_centrality(G_mod, weight=None)
        targets = [node for node, _ in sorted(bc.items(), key=lambda item: item[1], reverse=True)[:n_targets]]
    else:
        rng = np.random.default_rng(seed)
        targets = rng.choice(nodes, size=n_targets, replace=False)

    for node in targets:
        for neighbor in list(G_mod.neighbors(node)):
            G_mod.remove_edge(node, neighbor)
        G_mod.nodes[node]["state"] = "isolated"
        G_mod.nodes[node]["behavior"] = "isolated"
        G_mod.nodes[node]["trust"] = 0.0

    return G_mod


def apply_spoofing(
    G: nx.Graph,
    n_spoof: int = 1,
    extra_edges: int = 5,
    seed: Optional[int] = None,
) -> nx.Graph:
    """
    Добавляет один или несколько spoof-узлов с ложными связями.

    Воспроизводимость обеспечивается сортированным порядком существующих узлов
    и единым RNG, управляемым через ``seed``.
    """
    G_mod = G.copy()
    if n_spoof <= 0:
        return G_mod

    rng = np.random.default_rng(seed)
    existing_initial = _sorted_nodes(G_mod)
    if not existing_initial:
        return G_mod

    # Аккуратно извлекаем числовую часть n_XXX. Если формат иной — начинаем после размера графа.
    numeric_ids = []
    for node in existing_initial:
        try:
            numeric_ids.append(int(str(node).split("_")[-1]))
        except ValueError:
            pass
    next_idx = (max(numeric_ids) + 1) if numeric_ids else len(existing_initial)

    xs = np.array([float(G_mod.nodes[n].get("x", 0.0)) for n in existing_initial], dtype=float)
    ys = np.array([float(G_mod.nodes[n].get("y", 0.0)) for n in existing_initial], dtype=float)
    radii = np.array([float(G_mod.nodes[n].get("radius", 0.0) or 0.0) for n in existing_initial], dtype=float)
    radius_default = float(np.median(radii)) if len(radii) else 15.0
    coord_type = G_mod.graph.get("coord_type", G_mod.nodes[existing_initial[0]].get("coord_type", "plane"))

    for idx in range(n_spoof):
        new_id = f"n_{next_idx + idx:03d}"
        x = float(rng.uniform(xs.min(), xs.max()))
        y = float(rng.uniform(ys.min(), ys.max()))
        G_mod.add_node(
            new_id,
            x=x,
            y=y,
            radius=radius_default,
            state="malicious",
            trust=0.0,
            load=0.0,
            behavior="spoofer",
            coord_type=coord_type,
        )

        candidates = _sorted_nodes(G_mod)
        candidates = [node for node in candidates if node != new_id]
        if candidates and extra_edges > 0:
            targets = rng.choice(candidates, size=min(extra_edges, len(candidates)), replace=False)
            for target in targets:
                G_mod.add_edge(new_id, str(target), weight=0.0)

    return G_mod
