"""
Smoke-тесты для VKR P2P GeoThreats v0.4.

Назначение: быстро проверить, что основной CLI создаёт ожидаемые артефакты
и что ключевые сценарии дают базовые ожидаемые изменения.

Запуск из корня репозитория:
    python tests/smoke_test.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_cmd(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    """Запускает команду и падает с подробным выводом при ошибке."""
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(
            "Command failed:\n"
            f"  {' '.join(args)}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )
    return result


def read_summary(output_dir: Path, coord: str, graph: str) -> pd.DataFrame:
    """Читает summary_metrics.csv для plane/geo и заданного графа."""
    if coord == "geo":
        path = output_dir / "geo" / "tables" / graph / "summary_metrics.csv"
    else:
        path = output_dir / "tables" / graph / "summary_metrics.csv"
    assert path.exists(), f"Missing summary table: {path}"
    return pd.read_csv(path, index_col=0)


def assert_core_scenario_effects(summary: pd.DataFrame) -> None:
    """Проверяет минимальные семантические эффекты сценариев."""
    required_columns = {"Baseline", "Rogue", "Flooding", "Isolation", "Spoofing"}
    missing_columns = required_columns - set(summary.columns)
    assert not missing_columns, f"Missing scenario columns: {missing_columns}"

    required_metrics = {"nodes", "edges", "load_anomaly_count", "isolated_nodes", "largest_component_size"}
    missing_metrics = required_metrics - set(summary.index)
    assert not missing_metrics, f"Missing metrics: {missing_metrics}"

    baseline_nodes = float(summary.loc["nodes", "Baseline"])
    spoofing_nodes = float(summary.loc["nodes", "Spoofing"])
    assert spoofing_nodes > baseline_nodes, "Spoofing must increase the number of nodes"

    flooding_anomalies = float(summary.loc["load_anomaly_count", "Flooding"])
    assert flooding_anomalies > 0, "Flooding must produce at least one load anomaly"

    isolation_lcc = float(summary.loc["largest_component_size", "Isolation"])
    baseline_lcc = float(summary.loc["largest_component_size", "Baseline"])
    assert isolation_lcc <= baseline_lcc, "Isolation must not increase largest component size"


def test_plane_and_geo_experiments() -> None:
    """Проверяет запуск plane и geo экспериментов для radius/knn."""
    with tempfile.TemporaryDirectory(prefix="vkr_smoke_") as tmp:
        output_dir = Path(tmp)

        run_cmd([
            PYTHON,
            "src/run_experiment.py",
            "--all-graphs",
            "--coord",
            "plane",
            "--n-nodes",
            "20",
            "--output",
            str(output_dir),
        ])
        run_cmd([
            PYTHON,
            "src/run_experiment.py",
            "--all-graphs",
            "--coord",
            "geo",
            "--n-nodes",
            "20",
            "--output",
            str(output_dir),
        ])

        for coord in ("plane", "geo"):
            for graph in ("radius", "knn"):
                summary = read_summary(output_dir, coord, graph)
                assert_core_scenario_effects(summary)


def test_multi_seed_outputs() -> None:
    """Проверяет, что multi-seed режим формирует summary и raw таблицы."""
    with tempfile.TemporaryDirectory(prefix="vkr_smoke_multi_") as tmp:
        output_dir = Path(tmp)
        run_cmd([
            PYTHON,
            "src/run_multi_seed.py",
            "--runs",
            "2",
            "--coord",
            "plane",
            "--graphs",
            "radius",
            "knn",
            "--n-nodes",
            "16",
            "--output",
            str(output_dir),
        ])

        stability_path = output_dir / "tables" / "stability_metrics.csv"
        raw_path = output_dir / "tables" / "stability_runs_raw.csv"
        fig_path = output_dir / "figures" / "stability_boxplots.png"
        assert stability_path.exists(), f"Missing {stability_path}"
        assert raw_path.exists(), f"Missing {raw_path}"
        assert fig_path.exists(), f"Missing {fig_path}"

        stability = pd.read_csv(stability_path)
        assert {"scenario", "graph_type", "coord_type"}.issubset(stability.columns)
        assert set(stability["graph_type"]) == {"radius", "knn"}


def test_invalid_bbox_error_is_readable() -> None:
    """Проверяет, что некорректный bbox даёт понятную CLI-ошибку."""
    result = subprocess.run(
        [
            PYTHON,
            "src/run_experiment.py",
            "-g",
            "radius",
            "--coord",
            "geo",
            "--bbox",
            "37.70,55.72,37.60,55.78",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0, "Invalid bbox must fail"
    assert "min_lon" in result.stderr and "max_lon" in result.stderr, result.stderr


if __name__ == "__main__":
    test_plane_and_geo_experiments()
    test_multi_seed_outputs()
    test_invalid_bbox_error_is_readable()
    print("Smoke tests passed.")
