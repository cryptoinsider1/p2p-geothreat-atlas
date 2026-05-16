"""
run_multi_seed.py — множественные прогоны для оценки устойчивости результатов.

Примеры:
    python src/run_multi_seed.py --runs 10 --coord plane
    python src/run_multi_seed.py --runs 10 --coord geo
    python src/run_multi_seed.py --runs 10 --coord plane --graphs radius knn
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd

from metrics import compute_metrics
from run_experiment import (
    COORD_TYPES,
    GRAPH_TYPES,
    SCENARIOS,
    apply_scenario,
    get_build_graph_fn,
    generate_nodes_by_coord,
    load_config,
    output_root_for_coord,
    parse_bbox,
)


STABILITY_METRICS_TO_PLOT = [
    "density",
    "avg_degree",
    "num_components",
    "largest_component_size",
    "isolated_nodes",
]


def run_multiple(
    graph_type: str,
    coord_type: str,
    scenario_name: str,
    n_runs: int,
    base_seed: int,
    config: dict,
    n_nodes_override: Optional[int] = None,
    radius_override: Optional[float] = None,
    bbox_override: Optional[Tuple[float, float, float, float]] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Выполняет серию прогонов для одной пары graph/scenario."""
    records = []
    k = int(config["model"].get("k_knn", 5))
    build_graph = get_build_graph_fn(graph_type, coord_type, k=k)

    for i in range(n_runs):
        seed = base_seed + i
        nodes = generate_nodes_by_coord(
            coord_type,
            config,
            seed=seed,
            n_nodes_override=n_nodes_override,
            radius_override=radius_override,
            bbox_override=bbox_override,
        )
        G_base = build_graph(nodes)
        G_base.graph["graph_type"] = graph_type
        G_base.graph["coord_type"] = coord_type
        G_mod = apply_scenario(scenario_name, G_base, config, coord_type, seed)
        G_mod.graph["graph_type"] = graph_type
        G_mod.graph["coord_type"] = coord_type

        record = compute_metrics(G_mod)
        record["seed"] = seed
        record["scenario"] = scenario_name
        record["graph_type"] = graph_type
        record["coord_type"] = coord_type
        records.append(record)

    df = pd.DataFrame(records)
    numeric_cols = [col for col in df.columns if col not in {"seed", "scenario", "graph_type", "coord_type"}]
    summary = pd.DataFrame({"mean": df[numeric_cols].mean(numeric_only=True), "std": df[numeric_cols].std(numeric_only=True)})
    return df, summary


def save_stability_boxplots(all_runs: pd.DataFrame, save_path: Path) -> None:
    """Сохраняет боксплоты устойчивости по ключевым метрикам."""
    save_path.parent.mkdir(parents=True, exist_ok=True)

    grouped = list(all_runs.groupby(["graph_type", "scenario"], sort=False))
    if not grouped:
        return

    n_cols = len(SCENARIOS)
    n_rows = max(1, len(sorted(all_runs["graph_type"].unique())))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(3.2 * n_cols, 4.0 * n_rows), squeeze=False)

    graph_order = [g for g in GRAPH_TYPES if g in set(all_runs["graph_type"])]
    for r, graph_type in enumerate(graph_order):
        for c, scenario_name in enumerate(SCENARIOS):
            ax = axes[r][c]
            subset = all_runs[(all_runs["graph_type"] == graph_type) & (all_runs["scenario"] == scenario_name)]
            if subset.empty:
                ax.axis("off")
                continue
            subset[STABILITY_METRICS_TO_PLOT].boxplot(ax=ax)
            ax.set_title(f"{graph_type} / {scenario_name}")
            ax.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close(fig)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run multi-seed stability experiments")
    parser.add_argument("--runs", "-r", type=int, default=10, help="Number of runs per scenario")
    parser.add_argument("--coord", choices=COORD_TYPES, default="plane", help="Coordinate system")
    parser.add_argument("--graphs", nargs="+", choices=GRAPH_TYPES, default=GRAPH_TYPES, help="Graph types")
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=SCENARIOS, help="Scenarios")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--seed", type=int, default=None, help="Base seed override")
    parser.add_argument("--n-nodes", type=int, default=None, help="Override number of nodes")
    parser.add_argument("--radius", type=float, default=None, help="Override radius")
    parser.add_argument("--bbox", default=None, help="Geo bbox: min_lon,min_lat,max_lon,max_lat")
    parser.add_argument("--output", default=None, help="Override output base directory")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.runs <= 0:
        raise ValueError("--runs must be positive")

    config = load_config(args.config)
    base_seed = int(args.seed if args.seed is not None else config["experiment"].get("seed", 42))
    output_base_dir = args.output or config.get("output", {}).get("base_dir", "outputs")
    try:
        bbox = parse_bbox(args.bbox, config["model"].get("bbox_moscow", [37.58, 55.72, 37.68, 55.78]))
    except ValueError as exc:
        parser.error(str(exc))

    rows = []
    run_frames = []
    for graph_type in args.graphs:
        for scenario_name in args.scenarios:
            print(f"Running stability: coord={args.coord}, graph={graph_type}, scenario={scenario_name}")
            df, summary = run_multiple(
                graph_type=graph_type,
                coord_type=args.coord,
                scenario_name=scenario_name,
                n_runs=args.runs,
                base_seed=base_seed,
                config=config,
                n_nodes_override=args.n_nodes,
                radius_override=args.radius,
                bbox_override=bbox if args.coord == "geo" else None,
            )
            run_frames.append(df)

            row = {"scenario": scenario_name, "graph_type": graph_type, "coord_type": args.coord}
            for metric in summary.index:
                row[f"{metric}_mean"] = summary.loc[metric, "mean"]
                row[f"{metric}_std"] = summary.loc[metric, "std"]
            rows.append(row)

    root = output_root_for_coord(output_base_dir, args.coord)
    tables_dir = root / "tables"
    figures_dir = root / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    final_df = pd.DataFrame(rows)
    final_df.to_csv(tables_dir / "stability_metrics.csv", index=False)

    all_runs = pd.concat(run_frames, ignore_index=True) if run_frames else pd.DataFrame()
    all_runs.to_csv(tables_dir / "stability_runs_raw.csv", index=False)
    save_stability_boxplots(all_runs, figures_dir / "stability_boxplots.png")

    print(f"Stability metrics saved to {tables_dir / 'stability_metrics.csv'}")
    print(f"Raw stability runs saved to {tables_dir / 'stability_runs_raw.csv'}")
    print(f"Boxplots saved to {figures_dir / 'stability_boxplots.png'}")


if __name__ == "__main__":
    main()
