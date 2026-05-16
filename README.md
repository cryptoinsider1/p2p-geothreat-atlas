# P2P-GeoThreatAtlas

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-v0.5%20analytical-orange)](https://github.com/cryptoinsider1/p2p-geothreat-atlas)

**P2P-GeoThreatAtlas** — исследовательский Python-прототип для моделирования и визуализации угроз в мобильных P2P-сетях на базе геоданных.

Репозиторий: <https://github.com/cryptoinsider1/p2p-geothreat-atlas>

Проект разработан в рамках выпускной квалификационной работы:

> **«Моделирование и визуализация угроз в мобильных P2P-сетях на базе геоданных»**

---

## 1. Назначение

Проект моделирует мобильную P2P-сеть как граф сетевой близости, применяет сценарии аномального поведения и рассчитывает структурные, нагрузочные и устойчивостные метрики до и после воздействия угроз.

Главная задача прототипа — дать воспроизводимый экспериментальный контур для анализа того, как разные типы топологии реагируют на угрозы:

- **radius graph** — радиусная модель сетевой доступности;
- **k-NN graph** — модель `k` ближайших соседей;
- **plane mode** — условная двумерная плоскость;
- **geo mode** — реальные координаты `lon/lat`, bbox и haversine-метрика.

---

## 2. Текущее состояние

Актуальная версия: **v0.5 analytical**.

В версии v0.5 синхронизированы код, структура репозитория, README, smoke-тесты и аналитический ноутбук.

Реализовано:

- два типа графа: `radius` и `knn`;
- два режима координат: `plane` и `geo`;
- географический модуль `src/model_geo.py` с haversine-расстоянием;
- сценарии угроз: `baseline`, `rogue`, `flooding`, `isolation`, `spoofing`;
- структурные и нагрузочные метрики;
- multi-seed проверка устойчивости;
- smoke-тесты для быстрой проверки воспроизводимости;
- аналитический ноутбук с дельтами, сравнением графов, диагностическими признаками и интерпретационными карточками.

---

## 3. Структура проекта

```text
p2p-geothreat-atlas/
├── README.md
├── README_RU.md
├── LICENSE
├── requirements.txt
├── requirements-dev.txt
├── config.yaml
├── src/
│   ├── model.py                 # plane-модель: генерация узлов, radius graph, k-NN graph
│   ├── model_geo.py             # geo-модель: bbox, haversine, radius graph, k-NN graph
│   ├── scenarios.py             # baseline, rogue, flooding, isolation, spoofing
│   ├── metrics.py               # структурные и нагрузочные метрики
│   ├── visualize.py             # PNG-графы и Folium-карты
│   ├── run_experiment.py        # основной запуск экспериментов
│   └── run_multi_seed.py        # серия прогонов по нескольким seed
├── notebooks/
│   ├── final_report.ipynb
│   └── final_report_analytical_v0_5.ipynb
├── tests/
│   └── smoke_test.py
└── outputs/                     # генерируемые результаты, обычно не коммитятся
    ├── figures/
    ├── maps/
    ├── tables/
    └── geo/
```

---

## 4. Установка

Рекомендуемая версия Python: **3.11+**.

```bash
git clone https://github.com/cryptoinsider1/p2p-geothreat-atlas.git
cd p2p-geothreat-atlas

python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

pip install --upgrade pip
pip install -r requirements.txt
```

Для работы с Jupyter-ноутбуками:

```bash
pip install -r requirements-dev.txt
python -m ipykernel install --user --name=vkr_venv --display-name "Python (vkr)"
```

---

## 5. Быстрый запуск

### 5.1 Plane mode

```bash
python src/run_experiment.py --all-graphs --coord plane
python src/run_multi_seed.py --runs 10 --coord plane
```

### 5.2 Geo mode

```bash
python src/run_experiment.py --all-graphs --coord geo
python src/run_multi_seed.py --runs 10 --coord geo
```

### 5.3 Один сценарий

```bash
python src/run_experiment.py rogue -g radius --coord plane
python src/run_experiment.py flooding -g knn --coord geo
python src/run_experiment.py isolation -g radius --coord geo
```

---

## 6. Режимы координат

### 6.1 `--coord plane`

Используется условная двумерная координатная плоскость:

```text
x ∈ [0, 100]
y ∈ [0, 100]
radius = 15.0 условных единиц
```

Этот режим нужен для воспроизводимого анализа топологии без привязки к конкретному району.

### 6.2 `--coord geo`

Используются реальные географические координаты внутри bbox:

```text
bbox_moscow = [37.58, 55.72, 37.68, 55.78]
radius_m = 500.0 метров
```

Соглашение:

```text
x = longitude / долгота
y = latitude / широта
radius = радиус связи в метрах
```

Расстояния считаются через haversine-метрику. Пользовательский bbox можно передать из командной строки:

```bash
python src/run_experiment.py -g radius --coord geo --bbox 37.55,55.70,37.75,55.82
```

---

## 7. Построение графов

### 7.1 Radius graph

Ребро между двумя узлами создаётся, если расстояние между ними не превышает радиус связи каждого из узлов:

```text
(i, j) ∈ E, если d(i, j) <= min(r_i, r_j)
```

В `plane`-режиме используется евклидово расстояние, в `geo`-режиме — haversine-расстояние в метрах.

### 7.2 k-NN graph

Для каждого узла выбираются `k` ближайших соседей. Граф симметризуется: если узел `B` выбран соседом для `A`, ребро `A--B` добавляется независимо от обратного выбора.

```text
k_knn = 5
```

---

## 8. Сценарии угроз

| Сценарий | Смысл | Ожидаемый эффект |
|---|---|---|
| `baseline` | контрольная сеть без угроз | базовая точка сравнения |
| `rogue` | вредоносные узлы с расширенным радиусом влияния | рост связей, плотности, центральности, ложная связность |
| `flooding` | аномальная нагрузка на отдельных узлах | структурные метрики могут не меняться, нагрузочные — растут |
| `isolation` | удаление связей у выбранных узлов | рост компонент, падение largest component size |
| `spoofing` | добавление подставных узлов | рост числа узлов, ложные связи, локальное искажение структуры |

---

## 9. Метрики

### 9.1 Структурные метрики

| Метрика | Интерпретация |
|---|---|
| `nodes` | количество узлов |
| `edges` | количество рёбер |
| `density` | плотность графа |
| `avg_degree` | средняя степень вершины |
| `num_components` | число компонент связности |
| `largest_component_size` | размер крупнейшей компоненты |
| `isolated_nodes` | число изолированных узлов |
| `avg_clustering` | средний коэффициент кластеризации |
| `max_degree_centrality` | максимальная degree centrality |
| `max_betweenness_centrality` | максимальная betweenness centrality |
| `degree_centrality_std` | разброс degree centrality |

### 9.2 Нагрузочные метрики

| Метрика | Интерпретация |
|---|---|
| `total_load` | суммарная нагрузка по сети |
| `max_load` | максимальная нагрузка на одном узле |
| `avg_load` | средняя нагрузка |
| `load_std` | стандартное отклонение нагрузки |
| `load_anomaly_count` | число узлов, превысивших порог аномальной нагрузки |

---

## 10. Выходные файлы

### 10.1 Plane mode

```text
outputs/figures/radius/*.png
outputs/figures/knn/*.png
outputs/maps/radius/*.html
outputs/maps/knn/*.html
outputs/tables/radius/*.csv
outputs/tables/knn/*.csv
outputs/tables/stability_metrics.csv
outputs/tables/stability_runs_raw.csv
```

### 10.2 Geo mode

```text
outputs/geo/figures/radius/*.png
outputs/geo/figures/knn/*.png
outputs/geo/maps/radius/*.html
outputs/geo/maps/knn/*.html
outputs/geo/tables/radius/*.csv
outputs/geo/tables/knn/*.csv
outputs/geo/tables/stability_metrics.csv
outputs/geo/tables/stability_runs_raw.csv
```

---

## 11. Аналитический ноутбук

Основной расширенный ноутбук:

```text
notebooks/final_report_analytical_v0_5.ipynb
```

Он не только выводит таблицы и изображения, но и формирует аналитический слой:

- абсолютные дельты от baseline;
- процентные дельты от baseline;
- сравнение реакции `radius` и `k-NN`;
- проверку ожидаемых эффектов сценариев;
- диагностический светофор;
- интерпретационные карточки;
- экспорт аналитических таблиц и `REPORT_INTERPRETATION.md`.

Смысловая логика ноутбука:

```text
baseline-норма → дельты → проверка ожидаемых эффектов → диагностика → интерпретация
```

---

## 12. Быстрая проверка перед коммитом

```bash
python tests/smoke_test.py
```

Smoke-тест проверяет:

| Проверка | Что подтверждает |
|---|---|
| `run_experiment.py --all-graphs --coord plane` | плоскостная модель создаёт результаты для `radius` и `knn` |
| `run_experiment.py --all-graphs --coord geo` | географическая модель создаёт результаты для `radius` и `knn` |
| `spoofing` | количество узлов увеличивается |
| `flooding` | появляется нагрузочная аномалия |
| `isolation` | крупнейшая компонента не увеличивается |
| `run_multi_seed.py` | создаются таблицы устойчивости и боксплоты |
| некорректный `--bbox` | CLI выдаёт понятную ошибку без Python traceback |

---

## 13. Воспроизводимость

Для воспроизводимости используется фиксированный seed:

```text
seed = 42
```

Сценарий `spoofing` реализован детерминированно: существующие узлы сортируются перед выбором связей, а количество создаваемых spoof-узлов задаётся параметром `n_spoof`.

---

## 14. Ограничения модели

- модель является симуляционной;
- не учитываются реальные радиопомехи, коллизии и физический уровень радиосети;
- не моделируются реальные протоколы маршрутизации;
- мобильность узлов во времени пока не моделируется;
- `plane`-режим использует условную координатную плоскость;
- `geo`-режим учитывает bbox и haversine-расстояния, но не учитывает препятствия, плотность застройки и направленность антенн;
- `flooding` моделируется как нагрузочная аномалия, а не как полный сетевой стек DoS/DDoS.

---

## 15. Соответствие версии кода и текста ВКР

| Блок текста ВКР | Реализация в репозитории | Что подтверждает |
|---|---|---|
| Постановка модели мобильной P2P-сети | `src/model.py`, `src/model_geo.py` | генерация узлов, координаты, радиусы связи |
| Условная плоскостная модель | `generate_nodes`, `build_radius_graph`, `build_knn_graph` | базовый воспроизводимый топологический эксперимент |
| Географическая привязка | `generate_nodes_geo`, `haversine`, `build_radius_graph_geo`, `build_knn_graph_geo` | bbox, реальные `lon/lat`, расстояния в метрах |
| Сценарии угроз | `src/scenarios.py` | `baseline`, `rogue`, `flooding`, `isolation`, `spoofing` |
| Метрики анализа | `src/metrics.py` | связность, центральности, кластеризация, нагрузочные аномалии |
| Визуализация результатов | `src/visualize.py` | PNG-графы и интерактивные Folium-карты |
| Основные эксперименты | `src/run_experiment.py` | запуск по `--graph`, `--coord`, `--scenario` |
| Проверка устойчивости | `src/run_multi_seed.py` | серия прогонов по нескольким seed, `mean/std`, боксплоты |
| Итоговый отчёт | `notebooks/final_report_analytical_v0_5.ipynb` | таблицы, дельты, сравнение, интерпретационные карточки |
| Воспроизводимость окружения | `requirements.txt`, `requirements-dev.txt`, `config.yaml`, `.gitignore`, `tests/` | зависимости, параметры, чистота репозитория, smoke-контроль |

---

## 16. История версий

| Версия | Содержание |
|---|---|
| `v0.2` | базовый `radius graph`, сценарии угроз, CSV/PNG/HTML-вывод |
| `v0.3` | добавлен `k-NN graph`, нагрузочные метрики, multi-seed устойчивость |
| `v0.4` | добавлен `--coord plane/geo`, `model_geo.py`, haversine, `outputs/geo` |
| `v0.4.1` | repo-ready: `.gitignore`, smoke-тесты, понятная ошибка bbox |
| `v0.5` | аналитический ноутбук: дельты, диагностика, интерпретационные карточки |

---

## 17. Лицензия

Лицензия проекта: **MIT License**.

---

## 18. Цитирование

Если проект используется как часть учебной, исследовательской или демонстрационной работы, рекомендуется ссылаться на репозиторий:

```text
P2P-GeoThreatAtlas: Modeling and visualization toolkit for geospatial threat scenarios in mobile P2P networks.
GitHub: https://github.com/cryptoinsider1/p2p-geothreat-atlas
```
