"""
run_experiment.py — единая точка запуска экспериментов ВКР.

Примеры:
    python src/run_experiment.py
    python src/run_experiment.py rogue -g radius --coord plane
    python src/run_experiment.py -g knn --coord geo
    python src/run_experiment.py --all-graphs --coord geo

Выходные данные:
    plane: outputs/figures/<graph_type>/..., outputs/maps/<graph_type>/..., outputs/tables/<graph_type>/...
    geo:   outputs/geo/figures/<graph_type>/..., outputs/geo/maps/<graph_type>/..., outputs/geo/tables/<graph_type>/...
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

import pandas as pd
import yaml

from metrics import compare_scenarios, compute_metrics
from model import build_knn_graph, build_radius_graph, euclidean_distance, generate_nodes
from model_geo import build_knn_graph_geo, build_radius_graph_geo, generate_nodes_geo, haversine
from scenarios import (
    apply_baseline,
    apply_flooding,
    apply_isolation,
    apply_rogue_node,
    apply_spoofing,
)
from visualize import draw_geo_map, draw_graph, plot_metric_comparison


SCENARIOS = ["baseline", "rogue", "flooding", "isolation", "spoofing"]
GRAPH_TYPES = ["radius", "knn"]
COORD_TYPES = ["plane", "geo"]

SCENARIO_LABELS = {
    "baseline": "Baseline",
    "rogue": "Rogue",
    "flooding": "Flooding",
    "isolation": "Isolation",
    "spoofing": "Spoofing",
}

DEFAULT_CONFIG = {
    "model": {
        "n_nodes": 50,
        "x_range": [0.0, 100.0],
        "y_range": [0.0, 100.0],
        "radius": 15.0,
        "radius_m": 500.0,
        "k_knn": 5,
        "bbox_moscow": [37.58, 55.72, 37.68, 55.78],
    },
    "scenarios": {
        "rogue": {"n_malicious": 2, "extra_radius_mult": 2.0},
        "flooding": {"n_flooders": 2, "load_mult": 10.0},
        "isolation": {"n_isolate": 3, "method": "random"},
        "spoofing": {"n_spoof": 1, "extra_edges": 5},
    },
    "experiment": {"seed": 42, "graph_types": ["radius", "knn"]},
    "output": {"base_dir": "outputs"},
}


BuildGraphFn = Callable[[pd.DataFrame], object]


def deep_update(base: dict, overrides: dict) -> dict:
    """Рекурсивно объединяет словари конфигурации."""
    result = dict(base)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_update(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | os.PathLike = "config.yaml") -> dict:
    """Загружает config.yaml, если файл существует, иначе возвращает DEFAULT_CONFIG."""
    path_obj = Path(path)
    if not path_obj.exists():
        return DEFAULT_CONFIG

    with path_obj.open("r", encoding="utf-8") as fh:
        user_config = yaml.safe_load(fh) or {}
    return deep_update(DEFAULT_CONFIG, user_config)


def parse_bbox(value: Optional[str], default_bbox: Iterable[float]) -> Tuple[float, float, float, float]:
    """
    Парсит и валидирует bbox формата ``min_lon,min_lat,max_lon,max_lat``.

    Возвращает понятные сообщения об ошибках для CLI-режима:
    - должно быть ровно 4 числа;
    - ``min_lon < max_lon``;
    - ``min_lat < max_lat``.
    """
    raw = list(default_bbox) if value is None else [part.strip() for part in value.split(",")]
    if len(raw) != 4:
        raise ValueError(
            "Некорректный bbox: ожидается 4 значения в формате "
            "min_lon,min_lat,max_lon,max_lat, например 37.58,55.72,37.68,55.78"
        )

    try:
        min_lon, min_lat, max_lon, max_lat = map(float, raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Некорректный bbox: все 4 значения должны быть числами. "
            "Пример: 37.58,55.72,37.68,55.78"
        ) from exc

    if min_lon >= max_lon:
        raise ValueError(
            f"Некорректный bbox: min_lon должен быть меньше max_lon "
            f"(получено min_lon={min_lon}, max_lon={max_lon})."
        )
    if min_lat >= max_lat:
        raise ValueError(
            f"Некорректный bbox: min_lat должен быть меньше max_lat "
            f"(получено min_lat={min_lat}, max_lat={max_lat})."
        )

    return min_lon, min_lat, max_lon, max_lat


def output_root_for_coord(base_dir: str | os.PathLike, coord_type: str) -> Path:
    """
    Возвращает корневую папку вывода.

    Для ``plane`` сохраняется обратная совместимость с существующим ноутбуком:
    ``outputs/tables/radius/...``. Для ``geo`` используется отдельный уровень:
    ``outputs/geo/tables/radius/...``.
    """
    base = Path(base_dir)
    return base if coord_type == "plane" else base / coord_type


def output_dirs(base_dir: str | os.PathLike, coord_type: str, graph_type: str) -> dict[str, Path]:
    root = output_root_for_coord(base_dir, coord_type)
    dirs = {
        "figures": root / "figures" / graph_type,
        "maps": root / "maps" / graph_type,
        "tables": root / "tables" / graph_type,
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def generate_nodes_by_coord(
    coord_type: str,
    config: dict,
    seed: int,
    n_nodes_override: Optional[int] = None,
    radius_override: Optional[float] = None,
    bbox_override: Optional[Tuple[float, float, float, float]] = None,
) -> pd.DataFrame:
    """Генерирует узлы для plane- или geo-режима."""
    model_cfg = config["model"]
    n_nodes = int(n_nodes_override if n_nodes_override is not None else model_cfg["n_nodes"])

    if coord_type == "geo":
        radius_m = float(radius_override if radius_override is not None else model_cfg.get("radius_m", 500.0))
        bbox = bbox_override or tuple(map(float, model_cfg.get("bbox_moscow", [37.58, 55.72, 37.68, 55.78])))
        return generate_nodes_geo(bbox=bbox, n=n_nodes, radius_m=radius_m, seed=seed)

    radius = float(radius_override if radius_override is not None else model_cfg["radius"])
    return generate_nodes(
        n=n_nodes,
        x_range=tuple(model_cfg.get("x_range", [0.0, 100.0])),
        y_range=tuple(model_cfg.get("y_range", [0.0, 100.0])),
        radius=radius,
        seed=seed,
    )


def get_build_graph_fn(graph_type: str, coord_type: str, k: int) -> BuildGraphFn:
    """Возвращает функцию построения графа под выбранный graph/coord режим."""
    if graph_type == "radius" and coord_type == "geo":
        return build_radius_graph_geo
    if graph_type == "radius" and coord_type == "plane":
        return build_radius_graph
    if graph_type == "knn" and coord_type == "geo":
        return lambda nodes: build_knn_graph_geo(nodes, k=k)
    if graph_type == "knn" and coord_type == "plane":
        return lambda nodes: build_knn_graph(nodes, k=k)
    raise ValueError(f"Unsupported graph/coord combination: {graph_type}/{coord_type}")


def apply_scenario(
    scenario_name: str,
    G_base,
    config: dict,
    coord_type: str,
    seed: int,
):
    """Применяет выбранный сценарий к baseline-графу."""
    scen_cfg = config.get("scenarios", {})

    if scenario_name == "baseline":
        return apply_baseline(G_base)
    if scenario_name == "rogue":
        params = scen_cfg.get("rogue", {})
        return apply_rogue_node(
            G_base,
            n_malicious=int(params.get("n_malicious", 2)),
            extra_radius_mult=float(params.get("extra_radius_mult", 2.0)),
            seed=seed,
            distance_fn=haversine if coord_type == "geo" else euclidean_distance,
        )
    if scenario_name == "flooding":
        params = scen_cfg.get("flooding", {})
        return apply_flooding(
            G_base,
            n_flooders=int(params.get("n_flooders", 2)),
            load_mult=float(params.get("load_mult", 10.0)),
            seed=seed,
        )
    if scenario_name == "isolation":
        params = scen_cfg.get("isolation", {})
        return apply_isolation(
            G_base,
            n_isolate=int(params.get("n_isolate", 3)),
            method=str(params.get("method", "random")),
            seed=seed,
        )
    if scenario_name == "spoofing":
        params = scen_cfg.get("spoofing", {})
        return apply_spoofing(
            G_base,
            n_spoof=int(params.get("n_spoof", 1)),
            extra_edges=int(params.get("extra_edges", 5)),
            seed=seed,
        )

    raise ValueError(f"Unknown scenario: {scenario_name}")


def run_scenario(
    scenario_name: str,
    nodes: pd.DataFrame,
    build_graph: BuildGraphFn,
    graph_type: str = "radius",
    coord_type: str = "plane",
    seed: int = 42,
    config: Optional[dict] = None,
    output_base_dir: str | os.PathLike = "outputs",
    write_artifacts: bool = True,
):
    """
    Выполняет один сценарий и возвращает ``(baseline_metrics, modified_metrics, comparison)``.
    """
    if scenario_name not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_name}. Expected one of {SCENARIOS}")

    cfg = config or DEFAULT_CONFIG
    G_base = build_graph(nodes)
    G_base.graph["graph_type"] = graph_type
    G_base.graph["coord_type"] = coord_type

    G_mod = apply_scenario(scenario_name, G_base, cfg, coord_type, seed)
    G_mod.graph["graph_type"] = graph_type
    G_mod.graph["coord_type"] = coord_type

    metrics_base = compute_metrics(G_base)
    metrics_mod = compute_metrics(G_mod)
    comparison = compare_scenarios(metrics_base, metrics_mod)

    if write_artifacts:
        dirs = output_dirs(output_base_dir, coord_type, graph_type)
        draw_graph(
            G_base,
            str(dirs["figures"] / f"{scenario_name}_baseline.png"),
            title=f"{coord_type}/{graph_type}/{scenario_name}: baseline",
        )
        draw_graph(
            G_mod,
            str(dirs["figures"] / f"{scenario_name}_after.png"),
            title=f"{coord_type}/{graph_type}/{scenario_name}: after threat",
        )
        draw_geo_map(G_mod, str(dirs["maps"] / f"{scenario_name}_map.html"))
        comparison.to_csv(dirs["tables"] / f"{scenario_name}_metrics.csv")
        plot_metric_comparison(
            metrics_base,
            metrics_mod,
            str(dirs["figures"] / f"{scenario_name}_metrics.png"),
            title=f"{coord_type}/{graph_type}/{scenario_name}: metric comparison",
        )

    print(f"\n=== {coord_type.upper()} / {graph_type.upper()} / {scenario_name.upper()} ===")
    print(comparison.to_string())
    return metrics_base, metrics_mod, comparison


def build_summary(
    scenario_comparisons: dict[str, pd.DataFrame],
    baseline_metrics: dict,
) -> pd.DataFrame:
    """Собирает сводную таблицу без дублирующего baseline-сценария."""
    summary_data = {"Baseline": pd.Series(baseline_metrics)}
    for scenario_name in SCENARIOS:
        if scenario_name == "baseline":
            continue
        if scenario_name in scenario_comparisons:
            summary_data[SCENARIO_LABELS[scenario_name]] = scenario_comparisons[scenario_name]["After Threat"]
    return pd.DataFrame(summary_data)


def run_experiment(
    graph_type: str,
    coord_type: str,
    scenarios_to_run: Iterable[str],
    config: dict,
    seed: int,
    output_base_dir: str | os.PathLike,
    n_nodes_override: Optional[int] = None,
    radius_override: Optional[float] = None,
    bbox_override: Optional[Tuple[float, float, float, float]] = None,
) -> pd.DataFrame:
    """Запускает набор сценариев для одной пары ``graph_type/coord_type``."""
    k = int(config["model"].get("k_knn", 5))
    nodes = generate_nodes_by_coord(
        coord_type,
        config,
        seed=seed,
        n_nodes_override=n_nodes_override,
        radius_override=radius_override,
        bbox_override=bbox_override,
    )
    build_graph = get_build_graph_fn(graph_type, coord_type, k=k)
    baseline_graph = build_graph(nodes)
    baseline_graph.graph["graph_type"] = graph_type
    baseline_graph.graph["coord_type"] = coord_type
    baseline_metrics = compute_metrics(baseline_graph)

    comparisons: dict[str, pd.DataFrame] = {}
    for scenario_name in scenarios_to_run:
        _, _, comparison = run_scenario(
            scenario_name,
            nodes,
            build_graph,
            graph_type=graph_type,
            coord_type=coord_type,
            seed=seed,
            config=config,
            output_base_dir=output_base_dir,
            write_artifacts=True,
        )
        comparisons[scenario_name] = comparison

    summary = build_summary(comparisons, baseline_metrics)
    dirs = output_dirs(output_base_dir, coord_type, graph_type)
    summary.to_csv(dirs["tables"] / "summary_metrics.csv")

    print(f"\n=== SUMMARY: {coord_type.upper()} / {graph_type.upper()} ===")
    print(summary.to_string())
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run VKR P2P GeoThreats experiments")
    parser.add_argument(
        "scenario",
        nargs="?",
        choices=SCENARIOS,
        help="Scenario to run. If omitted, all scenarios are executed.",
    )
    parser.add_argument("-g", "--graph", choices=GRAPH_TYPES, default="radius", help="Graph type")
    parser.add_argument(
        "--all-graphs",
        action="store_true",
        help="Run both radius and k-NN graph types regardless of --graph.",
    )
    parser.add_argument(
        "--coord",
        choices=COORD_TYPES,
        default="plane",
        help="Coordinate system: plane or geo.",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--seed", type=int, default=None, help="Override seed from config")
    parser.add_argument("--n-nodes", type=int, default=None, help="Override number of generated nodes")
    parser.add_argument(
        "--radius",
        type=float,
        default=None,
        help="Override radius: plane units for --coord plane, meters for --coord geo.",
    )
    parser.add_argument(
        "--bbox",
        default=None,
        help="Geo bbox as min_lon,min_lat,max_lon,max_lat. Used only with --coord geo.",
    )
    parser.add_argument("--output", default=None, help="Override output base directory")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    seed = int(args.seed if args.seed is not None else config["experiment"].get("seed", 42))
    output_base_dir = args.output or config.get("output", {}).get("base_dir", "outputs")
    scenarios_to_run = [args.scenario] if args.scenario else SCENARIOS
    graph_types = GRAPH_TYPES if args.all_graphs else [args.graph]
    try:
        bbox = parse_bbox(args.bbox, config["model"].get("bbox_moscow", [37.58, 55.72, 37.68, 55.78]))
    except ValueError as exc:
        parser.error(str(exc))

    for graph_type in graph_types:
        run_experiment(
            graph_type=graph_type,
            coord_type=args.coord,
            scenarios_to_run=scenarios_to_run,
            config=config,
            seed=seed,
            output_base_dir=output_base_dir,
            n_nodes_override=args.n_nodes,
            radius_override=args.radius,
            bbox_override=bbox if args.coord == "geo" else None,
        )


if __name__ == "__main__":
    main()
