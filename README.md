# HydroWatch Amur: Оперативный спутниковый мониторинг паводков и гидрологической динамики по Sentinel-1 (SAR) и Sentinel-2 (MSI)

Автономный геоинформационный аппаратно-программный комплекс оперативного картирования зон затопления, ретроспективного анализа и динамики водного зеркала в бассейне Верхнего и Среднего Амура (Амурская область, 11 пар «район интереса × событие»).

> **КосмоХакатон 2026** · Кейс **Гидрологический мониторинг** · Команда **dreamteam 4.0**

---

## Общедоступный стенд и интерфейсы

### Публичный рабочий стенд (Production):
- **Интерактивная геоинформационная карта-дашборд:** [https://state3407.space/](https://state3407.space/) (зеркало: [https://state3407.space/hydro/](https://state3407.space/hydro/))
- **Интерактивная спецификация REST API (Swagger UI):** [https://state3407.space/docs](https://state3407.space/docs) (зеркало: [https://state3407.space/hydro/docs](https://state3407.space/hydro/docs))
- **Альтернативная документация ReDoc:** [https://state3407.space/redoc](https://state3407.space/redoc)
- **Проверка работоспособности сервиса (Health Check):** [https://state3407.space/api/v1/health](https://state3407.space/api/v1/health)

### Локальное окружение (при запуске на машине):
- **Локальный дашборд:** [http://localhost:8000/](http://localhost:8000/)
- **Локальный Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Локальный Health Check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Материалы проекта:
- **Полный научно-технический отчёт:** [`REPORT.md`](REPORT.md)
- **Презентационные слайды защиты:** [`SLIDES.md`](SLIDES.md)

---

## Быстрый запуск в 1 команду

### Вариант A. Запуск через Docker Compose (рекомендуемый для жюри)

Развёртывание единым контейнером без необходимости локальной настройки окружения:

```bash
docker compose up --build
```

Сервис готов к работе и доступен по адресам:
- `http://localhost:8000/` — интерактивная карта с послойной визуализацией (`flood`, `water_pre`, `water_peak`), аналитическими карточками и круговой диаграммой ESA WorldCover;
- `http://localhost:8000/docs` — интерактивный Swagger UI для вызова REST API эндпоинтов.

Остановка контейнера:
```bash
docker compose down
```

---

### Вариант B. Локальный запуск через `uv`

#### 1. Установка окружения и запуск FastAPI бэкенда
```bash
# Синхронизация виртуального окружения (Python >= 3.13)
uv sync

# Запуск асинхронного сервиса
uv run uvicorn src.service.app:app --host 0.0.0.0 --port 8000
```

#### 2. Пакетный инференс, аудит и аналитика через CLI
```bash
# Пакетная обработка всех 11 пар с генерацией submission.csv и GeoTIFF масок
uv run python -m src.cli predict

# Оценка официальной соревновательной метрики Score и расчет абляций
uv run python -m src.cli evaluate --run-ablations

# Генерация консольного или CSV/JSON отчёта по паре
uv run python -m src.cli report --pair-id flood_2019_07_amur__blagoveshchensk

# Генерация криптографического Merkle-сертификата аудита (SHA-256)
uv run python -m src.cli audit --pair-id flood_2019_07_amur__blagoveshchensk

# Оценка пространственной неопределенности и 95% доверительного интервала [L, U]
uv run python -m src.cli uncertainty --pair-id flood_2019_07_amur__blagoveshchensk

# Бенчмарк производительности и латентности пайплайна
uv run python -m src.cli benchmark
```

#### 3. Запуск полного набора автотестов
```bash
# Бэкенд: 182 модульных и интеграционных теста (100% pass)
uv run pytest

# Фронтенд: 116 юнит- и компонентных тестов (100% pass)
npm test --prefix frontend -- --run
```

---

### Вариант C. Разработка интерактивного дашборда (`frontend/`)

Исходники SPA (React 18 + Vite + TypeScript + Tailwind) лежат в `frontend/`; production-бандл собирается сразу в `src/service/static/`, откуда его отдаёт FastAPI.

```bash
# Установка зависимостей фронтенда
npm ci --prefix frontend

# Юнит- и компонентные тесты (Vitest / RTL)
npm test --prefix frontend

# Production-сборка: tsc + vite build в src/service/static/
npm run build --prefix frontend

# Dev-сервер с проксированием /api и /vendor на бэкенд :8000
npm run dev --prefix frontend
```

> Каталоги `frontend/public/{vendor,icons,data}` генерируются скриптом `frontend/scripts/sync-assets.mjs` перед `npm run dev` / `npm run build` / `npm test` и в git не хранятся: офлайн-ассеты берутся из `src/service/static/{vendor,icons}`, а векторы и реестр пар — из `hydrowatch_amur/{vectors,tables,pairs.csv}`. Единый источник данных остаётся в `hydrowatch_amur/`, второй копии ~15 МБ в репозитории нет.

---

## 1. Архитектурная схема репозитория

```
cosmohack-hydro-2026/
├── Dockerfile                         # Многоэтапный production-образ (python:3.13-slim + uv)
├── compose.yml                        # Декларация оркестрации сервиса (порт 8000:8000)
├── pyproject.toml / uv.lock           # Детерминированная фиксация зависимостей через uv
├── config.yaml                        # Пороговые параметры пайплайна (Оцу, MMU, GSW и др.)
├── submission.csv                     # Финальный сабмит (11 пар, площади в гектарах)
├── REPORT.md                          # Фундаментальный научно-технический отчет
├── SLIDES.md                          # Материалы доклада и презентации для жюри
├── data/                              # Артефакты валидации
│   └── ablation_results.json          # Официальные результаты абляций Mode 1..4
├── predictions/                       # Сгенерированные одноканальные маски затопления (GeoTIFF)
├── frontend/                          # Исходники SPA (React + Vite + TS); сборка идёт в src/service/static/
│   ├── src/                           # Компоненты карты Leaflet, аналитика, отчёты, API-клиент
│   ├── public/                        # Офлайн-ассеты (vendor/icons/data) — генерируются sync-assets.mjs
│   └── scripts/sync-assets.mjs        # Сбор офлайн-ассетов из src/service/static и hydrowatch_amur
├── scripts/                           # Утилиты выгрузки внешних данных
│   ├── download_all_scenes.py         # Загрузка S1 (σ⁰ GRD) и S2 (MSI + SCL) из Planetary Computer STAC
│   └── fetch_worldcover.py            # ESA WorldCover v200 cropland-маски для стратификации затопления
├── hydrowatch_amur/                   # Базовый каталог набора данных кейса (структура + таблицы)
│   ├── pairs.csv                      # Реестр 11 пар: даты, орбиты, пути к данным
│   ├── sample_submission.csv          # Официальный шаблон сабмита
│   ├── tables/                        # Каталоги событий (events) и сцен (scenes)
│   ├── reference_masks/               # Эталонные маски (11 пар) — в git
│   ├── vectors/                       # Границы AOI, OSM гидросеть, бассейны — в git
│   └── rasters/                       # AUX/S2/cropland — в git; S1_*.tif (~2.9 ГБ) СКАЧИВАЮТСЯ отдельно
│       #   └── <event>/<aoi>/         # AUX_terrain_gsw.tif, SENTINEL2_*.tif, CROPLAND_worldcover.tif
├── src/                               # Программный комплекс и расчетное ядро
│   ├── cli.py                         # Консольный интерфейс: predict, evaluate, report, audit, uncertainty, benchmark
│   ├── segmentation.py                # Сегментация: Lee MMSE, Оцу [-22, -12] дБ (config), S2 MSI, MMU
│   ├── temporal.py                    # Временная динамика: расчет flood, receded, water_pre, water_peak
│   ├── predict.py                     # Пайплайн инференса, генерация submission.csv и GeoTIFF
│   ├── evaluate.py                    # Официальная метрика Score (0.45, 0.25, 0.15, 0.15) и абляции
│   ├── competition_metrics.py         # Официальный соревновательный Score и валидатор сабмита (docs/CRITERIA.md)
│   ├── carbon_metrics.py              # Оценка углеродного следа и биомассы (IPCC Tier 1/Tier 2 GHG)
│   ├── audit.py                       # Криптографический аудит (SHA-256 Merkle-дерево, MRV-сертификаты)
│   ├── uncertainty.py                 # Пространственная неопределенность и 95% доверительные интервалы [L, U]
│   ├── sar_analytics.py               # Поляриметрия Sentinel-1 SAR (VV/VH, double-bounce, ветровая рябь)
│   ├── scene_renderer.py              # Рендеринг растровых градиентных оверлеев PNG (RGBA) для Leaflet/ГИС
│   ├── super_resolution.py            # Субпиксельное уточнение береговой линии
│   ├── filters.py                     # Адаптивные фильтры подавления радарного спекл-шума (Lee MMSE 7x7)
│   ├── indices.py                     # Спектральные индексы Sentinel-2 MSI (MNDWI, NDWI, NDVI, AWEIsh)
│   ├── geo_utils.py                   # Геопространственные трансформации, векторизация и геометрия
│   ├── config.py                      # Конфигурационные структуры и валидация настроек
│   ├── data_fetch.py                  # Утилиты безопасной загрузки внешних радарных данных
│   └── service/                       # Продакшн микросервис
│       ├── app.py                     # FastAPI приложение, 20+ REST API эндпоинтов, CORS, Swagger UI
│       ├── schemas.py                 # Строгие контракты данных Pydantic v2
│       ├── data_loader.py             # Кэширование GeoJSON, векторизация растров, расчет площадей
│       ├── cache/                     # Кэшированные JSON-отчёты и GeoJSON-слои пар
│       └── static/                    # Собранный фронтенд (SPA), офлайн-vendor и слои карты
└── tests/                             # Полный набор тестов (182 backend + 116 frontend, 100% pass)
    ├── test_carbon_metrics.py         # Тесты оценки биомассы и выбросов по стандарту IPCC
    ├── test_cli.py                    # Тесты всех CLI-команд (predict, evaluate, report, audit, uncertainty, etc.)
    ├── test_competition_metrics.py   # Тесты официальной соревновательной метрики и правил сабмита
    ├── test_core_modules.py           # Тесты модулей ядра
    ├── test_data_fetch.py             # Тесты безопасной распаковки и валидации архивов
    ├── test_data_loader.py            # Тесты загрузки и векторизации геоданных
    ├── test_evaluate.py               # Тесты расчета соревновательного Score и абляций
    ├── test_landcover_offline.py      # Стратификация WorldCover и офлайн-консистентность статики
    ├── test_pipeline.py               # Тесты алгоритмов сегментации, Оцу и временной динамики
    ├── test_ported_audit.py           # Тесты криптографического Merkle-аудита
    ├── test_ported_geo_utils.py       # Тесты геопространственных трансформаций
    ├── test_ported_remote_sensing.py  # Тесты спектральных индексов и ДЗЗ-функций
    ├── test_ported_sar_analytics.py   # Тесты радарной поляриметрии и контраста
    ├── test_ported_scene_renderer.py  # Тесты генерации прозрачных RGBA PNG оверлеев
    ├── test_ported_service_endpoints.py # Тесты расширенных REST API эндпоинтов
    ├── test_ported_super_resolution.py # Тесты субпиксельного уточнения границ
    ├── test_ported_uncertainty.py     # Тесты пространственной неопределенности и CI
    ├── test_predict.py                # Тесты сквозного инференса
    ├── test_predict_resolution.py     # Тесты инференса при различных разрешениях
    ├── test_segmentation.py           # Модульные тесты сегментации и MMU
    └── test_service.py                # Интеграционные тесты базовых FastAPI эндпоинтов
```

> **О структуре данных:** Векторные границы (`vectors/`), эталонные маски (`reference_masks/`), каталоги (`tables/`) и вспомогательные растры рельефа (`AUX_terrain_gsw.tif`, `CROPLAND_worldcover.tif`) **закоммичены в git-репозиторий**. Только тяжёлые радарные сцены Sentinel-1 (`S1_*.tif`, ~2.9 ГБ) скачиваются одной командой `uv run python -m src.cli fetch` (см. раздел 6).

### Назначение ключевых программных модулей:
- [`src/segmentation.py`](src/segmentation.py): Мультисенсорный модуль сегментации водного зеркала. Реализует фильтрацию спекл-шума (Lee MMSE 7x7), адаптивный порог Оцу по гистограмме в полном окне валидности $[-30, -12]$ дБ с клиппингом в $[-22, -12]$ дБ (параметры из `config.yaml`), расчет спектральных индексов Sentinel-2 ($MNDWI$, $NDWI$, $NDVI$, $AWEIsh$), слияние с гидрологическими инвариантами (HAND, DEM Slope, WorldCover Builtup/Cropland) и фильтрацию малых объектов (MMU 25 пикселей).
- [`src/temporal.py`](src/temporal.py): Анализатор темпоральной динамики. Вычисляет матричные пересечения между пред-паводковым состоянием, пиком и постоянной водой JRC GSW.
- [`src/predict.py`](src/predict.py): Движок сквозного инференса для всех 11 пар `pairs.csv`. Контролирует строгое совпадение попиксельного подсчета растра и табличного `submission.csv` с погрешностью $< 2\%$.
- [`src/evaluate.py`](src/evaluate.py): Модуль соревновательной оценки. Реализует расчет взвешенного $Score$, пороговую стабилизацию ($\ge 50$ га и $\ge 200$ га), штраф за ложные тревоги на межени $Spec_{base}$ и цикл абляций Mode 1..4.
- [`src/competition_metrics.py`](src/competition_metrics.py): Официальный калькулятор соревновательного $Score$ и валидатор регламента `submission.csv` (проверка формата, монотонности `flood <= water_peak`, допустимого расхождения $< 2\%$ с масками).
- [`src/carbon_metrics.py`](src/carbon_metrics.py): Климатическая аналитика: оценка потерь запасов органического углерода биомассы ($CF = 0.47$) и эквивалентных выбросов $tCO_2e$ по методологии IPCC, расчет углеродных сертификатов.
- [`src/audit.py`](src/audit.py): Криптографический модуль аудита целостности: построение дерева Меркла (SHA-256) по входным сценам, параметрам и результатам для формирования юридически значимых MRV-сертификатов.
- [`src/uncertainty.py`](src/uncertainty.py): Статистическая оценка пространственной погрешности и построение 95% доверительных интервалов площади $[L, U]$ с учетом пространственной автокорреляции (rho) и шероховатости береговой линии.
- [`src/sar_analytics.py`](src/sar_analytics.py): Радиолокационная аналитика: оценка кросс-поляризационного соотношения $VH/VV$, радиометрического контраста вода/суша и индикация двойного отражения в затопленном лесу.
- [`src/scene_renderer.py`](src/scene_renderer.py): Серверный рендерер прозрачных RGBA PNG оверлеев с адаптивным градиентом интенсивности/глубины для прямой визуализации в Leaflet.
- [`src/cli.py`](src/cli.py): Унифицированная точка входа командной строки: `predict`, `evaluate`, `report`, `audit`, `uncertainty`, `benchmark`, `fetch`.
- [`src/service/app.py`](src/service/app.py): Промышленный REST API сервис на FastAPI (20+ эндпоинтов), экспорт CSV/JSON/GeoJSON/GeoTIFF/Shapefile.
- [`src/service/data_loader.py`](src/service/data_loader.py): Слой геоданных, кэширование отчетов и контуров, векторизация полигонов в EPSG:4326.
- [`tests/`](tests/): Исчерпывающий набор тестов из 22 модулей (182 теста бэкенда на `pytest` + 116 тестов фронтенда на `vitest`), обеспечивающий 100% стабильность.

---

## 2. Физические основы сенсоров и ключевой контекст 2026 года

### 2.1. Критический орбитальный контекст 2026 года
В 2026 году европейская космическая программа Copernicus претерпела фундаментальную реконфигурацию:
1. **Завершение миссии Sentinel-1A (29 июня 2026 г.):** После 12 лет штатной работы аппарат исчерпал запасы гидразина для удержания заданной орбиты и переведен на программу контролируемого сведения.
2. **Ввод созвездия Sentinel-1C / Sentinel-1D:** Штатный мониторинг обеспечивается новыми спутниками C-SAR.
3. **Орбитальный сдвиг revisit cycle на 1 сутки:** Новые орбитальные плоскости Sentinel-1C/1D смещены относительно исторической сетки Sentinel-1A ровно на 1 день.
4. **Влияние на обработку данных:** Межспутниковая радиометрическая совместимость. Поскольку созвездие Sentinel-1C/1D сохраняет ту же наземную сетку орбит (те же относительные витки), локальные углы падения для идентичных участков поймы практически не меняются, а систематический межспутниковый сдвиг дополнительно подавляется относительным междатным анализом ($\Delta\sigma^0$). Радиометрическая нормализация рельефа (RTC / $\gamma^0$, переход от $\sigma^0$) сохраняется в Roadmap (Этап I) как повышение устойчивости на расчленённом рельефе, а не как следствие смены аппарата.

```
       ЦИКЛОНИЧЕСКИЙ ФРОНТ (Ливни, паводок)
                    │
       ┌────────────┴────────────┐
       ▼                         ▼
Оптические сенсоры (MSI)    Радиолокация (SAR C-band)
   [Sentinel-2 / B3,B8,B11]    [Sentinel-1 / VV, VH]
       │                         │
  100% облачность,           Всепогодность 24/7,
  тени облаков = ложь        но спекл-шум, ветровая рябь,
  Слепота 5-10 суток         радиотени гор, двойное отражение
       │                         │
       └────────────┬────────────┘
                    ▼
     ГИДРОЛОГИЧЕСКИЙ FUSION КОМПЛЕКС
      (HAND + GSW + Slope + WorldCover)
                    │
                    ▼
   Оперативная маска затопления (T+4 часа)
```

### 2.2. Радиолокатор с синтезированной апертурой (Sentinel-1 C-SAR)
Радар C-диапазона ($\lambda \approx 5.6$ см) обеспечивает всепогодную съемку сквозь ливни и туман:
- **Зеркальное рассеяние (спокойная открытая вода):** По критерию Рэлея ($h < \frac{\lambda}{8 \cos \theta_i} \approx 8.5$ мм при $\theta_i = 35^\circ$) спокойная гладь отражает радиолуч в зеркальном направлении от антенны. Обратный сигнал падает до уровня шума: $\sigma^0_{VV} \in [-24, -16]$ дБ.
- **Ветровая рябь и резонанс Брэгга:** При ветре $> 3$ м/с волны капиллярной ряби с шагом $\Lambda_{Bragg} = \frac{\lambda}{2 \sin \theta_i} \approx 4.9$ см входят в пространственный резонанс с C-диапазоном. Сигнал воды возрастает на $6 \dots 10$ дБ (до $-12 \dots -9$ дБ), вызывая ложный пропуск затопления в наивных алгоритмах (False Negative).
- **Двойное отражение под пологом леса/тростника (Double-Bounce):** Вода + вертикальные стволы деревьев и тростника образуют уголковые отражатели. Сигнал усиливается до $-6 \dots -2$ дБ в канале VV и до $-12 \dots -7$ дБ в канале VH. Детектор HydroWatch выявляет подполочные затопления по относительному всплеску кросс-поляризации $\Delta \sigma^0_{VH} \ge +2.0$ дБ при низком $HAND \le 3$ м.
- **Радиотени на горных склонах (Radar Shadow):** Склоны сопок, обращенные в противоположную от сенсора сторону с уклоном $> 90^\circ - \theta_i$, экранируются от зондирования. Мощность падает ниже $-24$ дБ, что в простых классификаторах трактуется как вода (массивный False Positive).
- **Гладкие диэлектрические покрытия (ВПП и асфальт):** Взлетно-посадочная полоса аэродрома Благовещенск («Игнатьево») и сухие шоссе вызывают зеркальное отражение радиоволн ($\sigma^0 \in [-22, -17]$ дБ), генерируя ложные затопления на суше.

### 2.3. Оптический мультиспектральный радиометр (Sentinel-2 MSI)
- **Каналы спектра:** `B03` (Green, 560 нм), `B04` (Red, 665 нм), `B08` (NIR, 842 нм), `B11` (SWIR-1, 1610 нм).
- **Спектральные индексы:**
  $$NDWI = \frac{B03 - B08}{B03 + B08}, \quad MNDWI = \frac{B03 - B11}{B03 + B11}, \quad NDVI = \frac{B08 - B04}{B08 + B04}$$
  $$AWEIsh = B02 + 2.5 \cdot B03 - 1.5 \cdot (B08 + B11) - 0.25 \cdot B12$$
- **Провал классического NDWI на мутной паводковой взвеси:** Во время амурских паводков взвешенный минеральный сток (ил, суглинки, $TSS > 150$ мг/л) вызывает интенсивное рассеяние в NIR-диапазоне ($B08$), в результате чего $NDWI$ падает до отрицательных значений ($-0.1 \dots -0.2$), полностью теряя паводковую воду. Использование коротковолнового инфракрасного канала $B11$ (SWIR-1) в $MNDWI$ решает эту проблему, так как $B11$ поглощается водой даже при экстремальной концентрации мути ($MNDWI > +0.10$).
- **Эмпирический факт доступности S2 в кейсе:** Из 11 исследуемых пар паспорта сцен Sentinel-2 выданы только для 6 пар (54.5 %), а 5 пар (45.5 %, включая катастрофические пики июля 2019 г. в Благовещенске и Константиновке) остались без оптического слоя. При этом фактическая проверка показала, что **все** представленные растры `SENTINEL2_*.tif` содержат 0 валидных пикселей (nodata `-999.0`) — то есть оптический слой в кейсе де-факто отсутствует полностью, независимо от наличия паспорта сцены. Каталог сцен при этом фиксирует низкую облачность по датам (0.08–0.30 %), поэтому причиной является не облачность, а отсутствие корректно выгруженных оптических данных в наборе. Полноценный гидромониторинг в таких условиях физически невозможен без автономного SAR-ядра.

### 2.4. Вспомогательные геопространственные данные (Prior Invariants)
Для абсолютного подавления ложных тревог алгоритм использует физико-географические инварианты:
1. **MERIT Hydro ($HAND \le 25$ м):** Высота над ближайшим гидрографическим дренажем (Height Above Nearest Drainage). Отсекает $85.4\%$ ложных срабатываний в зонах радиотеней на водоразделах.
2. **Copernicus DEM GLO-30 ($Slope \le 5^\circ$):** Уклон поверхности. Гравитационный паводок равнинных рек не удерживается на крутых склонах.
3. **JRC Global Surface Water ($Occurrence \ge 80\%$):** База многолетней повторяемости открытой воды (1984–2021 гг.) для надежной фиксации постоянного руслового зеркала.
4. **ESA WorldCover v200 (`builtup`):** Слой капитальной застройки и искусственных покрытий для исключения ВПП аэропортов и автомагистралей.

---

## 3. Строгий математический аппарат

### 3.1. Адаптивный порог Оцу в физических границах
Порог разделения классов «вода / суша» вычисляется по бимодальной гистограмме в пределах долины затопления через максимизацию межклассовой дисперсии $\sigma_B^2(T)$:
$$\sigma_B^2(T) = \omega_0(T) \omega_1(T) \left(\mu_0(T) - \mu_1(T)\right)^2$$
где $\omega_0, \omega_1$ — вероятности классов, $\mu_0, \mu_1$ — средние значения яркостей.

Реализация в коде (`compute_otsu_threshold`):
- гистограмма строится по значениям $\sigma^0_{VV}$ в **полном окне валидности** $[-30.0, -12.0]$ дБ (64 бина, границы `otsu_valid_min_db`/`otsu_valid_max_db` из `config.yaml`), что сохраняет и водную моду ($\approx -20$ дБ), и моду суши ($\approx -8$ дБ); при выборке менее 50 пикселей возвращается фолбэк $-16.5$ дБ (`otsu_fallback_db`);
- итоговый порог ограничивается физически допустимым коридором радиометрического отклика спокойной воды:
$$T_{calibrated} = \mathrm{clip}\left(\arg\max_T \sigma_B^2(T),\, -22.0\text{ дБ},\, -12.0\text{ дБ}\right)$$
- границы коридора $-22.0$ / $-12.0$ дБ берутся из `config.yaml` (`otsu_min_db`/`otsu_max_db`) и соответствуют ТЗ; верхняя граница служит защитой от захвата сухого асфальта и ВПП;
- при плоском максимуме междуклассовой дисперсии (пустой разрыв между модами) выбирается середина плато, чтобы порог не смещался к водной моде.

### 3.2. Дифференциальный радарный анализ ($\Delta \sigma^0$)
Для исключения статичных гладких поверхностей (сухой асфальт, песок) пиксель признается затопленным только при существенном падении обратного рассеяния на дату пика относительно даты «до»:
$$\Delta \sigma^0_{VV} = \sigma^0_{VV, pre} - \sigma^0_{VV, peak} \ge 3.0\text{ дБ}$$
$$Cand_{flood} = \left(\sigma^0_{VV, peak} \le T_{calibrated}\right) \land \left(\Delta \sigma^0_{VV} \ge 3.0\text{ дБ}\right)$$
Для водного зеркала на дату пика дополнительно используется канал VH ($\Delta \sigma^0_{VH} \ge 1.5$ дБ и $\sigma^0_{VH} < -17$ дБ); отдельного порога по $\Delta \sigma^0_{VV}$ в коде нет — условие `drop >= 3.0 дБ` либо применяется в комбинации с каналом VH, либо без него (VV-режим).

### 3.3. Временная гидрологическая динамика
Матрицы состояний формируются на основе строгой булевой алгебры:
$$\mathrm{flood} = \mathrm{water\_peak} \land \neg \mathrm{water\_pre} \land \neg \mathrm{permanent}$$
$$\mathrm{receded} = \mathrm{water\_pre} \land \neg \mathrm{water\_peak}$$
где $\mathrm{permanent} = [JRC\_GSW \ge 80\%]$. Данное соотношение математически гарантирует выполнение критерия непротиворечивости: $\mathrm{flood\_ha} \le \mathrm{water\_peak\_ha}$.

### 3.4. Официальная соревновательная метрика КосмоХакатона 2026
Итоговый рейтинг формируется композитным баллом:
$$Score = 0.45 \cdot Q_{flood} + 0.25 \cdot Q_{water\_peak} + 0.15 \cdot Q_{water\_pre} + 0.15 \cdot Spec_{base}$$

Компоненты сходимости площадей $Q$ вычисляются как среднее по 8 парам реальных паводковых событий:
$$q = \max\left(0,\, 1 - \frac{|X_{pred} - X_{true}|}{\max(X_{true},\, \mathrm{threshold})}\right)$$
- Порог $\mathrm{threshold}$ для зоны затопления ($flood$): **50 га**.
- Порог $\mathrm{threshold}$ для водного зеркала ($water\_pre$, $water\_peak$): **200 га**.

Компонент $Spec_{base}$ контролирует устойчивость к ложным тревогам на 3 контрольных парах межени:
$$Spec_{base} = \frac{1}{3} \sum_{k=1}^3 \left( 1 - \min\left(1,\, \frac{\max(0,\, flood_{pred} - flood_{true})}{0.005 \cdot \mathrm{Area}_{AOI}}\right) \right)$$
где $0.005 \cdot \mathrm{Area}_{AOI}$ — защитный порог допустимого шума ($0.5\%$ от площади района).

---

## 4. Сводная таблица результатов абляций

Результаты валидации на полном наборе данных кейса (11 пар, 8 паводков + 3 межени) зафиксированы в [`data/ablation_results.json`](data/ablation_results.json):

| Конфигурация | Описание архитектуры | $Q_{flood}$ (0.45) | $Q_{water\_peak}$ (0.25) | $Q_{water\_pre}$ (0.15) | $Spec_{base}$ (0.15) | **Итоговый Score** |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Mode 1** | Naive SAR Otsu (без априорных масок, без оптики, без MMU) | 0.1083 | 0.3490 | 0.3308 | 0.0490 | **0.1930** |
| **Mode 2** | SAR Otsu + HAND ($\le 25$ м) / Slope ($\le 5^\circ$) + Builtup-фильтр | 0.1159 | 0.3469 | 0.3366 | 0.1820 | **0.2167** |
| **Mode 3** | SAR + Sentinel-2 MSI Optical Fusion (где доступно) + HAND/Slope | 0.1159 | 0.3469 | 0.3366 | 0.1820 | **0.2167** |
| **Mode 4 (Full)** | **Полный пайплайн (+ MMU 25px + GSW Permanent Water $\ge 80\%$)** | **0.2742** | **0.4490** | **0.4006** | **0.7153** | **0.4030** |

### Ключевые выводы абляционного анализа:
1. **Mode 3 ≡ Mode 2 пиксель-в-пиксель:** все 33 строки детализации попарных сравнений и метрики Mode 3 полностью идентичны Mode 2 (Score = 0.2167, $Spec_{base}$ = 0.1820). Оптическое слияние Sentinel-2 не изменило ни одного пикселя: все 12 поставляемых S2-растров содержат 0 валидных пикселей (nodata `-999.0`), поэтому оптические индексы недоступны ни для одной пары.
2. **Ключевой вклад вносит Mode 4:** включение постоянной воды JRC GSW и фильтрации малых пятен (MMU 25 пикселей = 0.25 га) повышает $Score$ с 0.2167 до **0.4030** (в ~2.3 раза), $Spec_{base}$ — с 0.1820 до **0.7153**, $Q_{flood}$ — с 0.1159 до **0.2742**.
3. **Честная интерпретация:** полный пайплайн де-факто является **SAR-only**: оптическое слияние (Mode 3) не дало прироста, а финальная конфигурация (Mode 4) опирается на SAR-ядро + топографические инварианты (HAND/Slope/Builtup) + GSW постоянную воду + MMU. Прирост качества обеспечивают именно гидрологические приоры и постобработка, а не оптика.
4. Средний растровый IoU финальной конфигурации — **0.1809**, F1 — **0.2846** (экстремальный дисбаланс классов: затопление < 0.5 % площади AOI).

---

## 5. Полная спецификация REST API

Сервис реализует промышленный REST API на базе FastAPI с валидацией через Pydantic v2.

### 5.1. `GET /api/v1/health`
Проверка доступности сервиса (liveness probe).
```bash
curl -X GET "http://localhost:8000/api/v1/health" -H "Accept: application/json"
```
**Ответ:**
```json
{
  "status": "ok"
}
```

---

### 5.2. `GET /api/v1/pairs`
Получение перечня всех 11 доступных пар сценариев с метаданными, датами съемок и площадями районов.
```bash
curl -X GET "http://localhost:8000/api/v1/pairs" -H "Accept: application/json"
```
**Пример ответа (фрагмент):**
```json
[
  {
    "pair_id": "flood_2019_07_amur__blagoveshchensk",
    "aoi_id": "blagoveshchensk",
    "aoi_name": "Благовещенск — слияние Амура и Зеи",
    "event_id": "flood_2019_07_amur",
    "event_name": "Паводок в Приамурье, июль 2019",
    "event_kind": "rain_flood",
    "year": 2019,
    "sensor_sar": "sentinel1",
    "sensor_optical": "",
    "date_pre_sar": "2019-06-13",
    "date_peak_sar": "2019-07-25",
    "date_pre_opt": "",
    "date_peak_opt": "",
    "aoi_km2": 1649.168,
    "aoi_ha": 164916.8,
    "bounds_4326": [127.218519, 50.120525, 127.857226, 50.459458],
    "center_4326": [50.289991, 127.537872]
  }
]
```

---

### 5.3. `GET /api/v1/report/{pair_id}`
Получение детального аналитического отчета по паре: площади затопления, зеркала воды, темп прироста и стратификация затопленных территорий по типам земного покрова (ESA WorldCover).
```bash
curl -X GET "http://localhost:8000/api/v1/report/flood_2019_07_amur__blagoveshchensk" \
     -H "Accept: application/json"
```
**Пример ответа (эталонные значения из кэш-отчёта пары `flood_2019_07_amur__blagoveshchensk`):**
```json
{
  "pair_id": "flood_2019_07_amur__blagoveshchensk",
  "aoi_id": "blagoveshchensk",
  "aoi_name": "Благовещенск — слияние Амура и Зеи",
  "event_id": "flood_2019_07_amur",
  "event_name": "Паводок в Приамурье, июль 2019",
  "event_kind": "rain_flood",
  "year": 2019,
  "date_pre_sar": "2019-06-13",
  "date_peak_sar": "2019-07-25",
  "flood_ha": 996.37,
  "flood_km2": 9.964,
  "water_pre_ha": 8913.3,
  "water_peak_ha": 9189.0,
  "water_gain_ha": 275.7,
  "water_gain_pct": 3.09,
  "share_of_aoi": 0.006042,
  "aoi_ha": 164916.8,
  "landcover": {
    "builtup_ha": 3.11,
    "builtup_pct": 0.31,
    "cropland_ha": 251.0,
    "cropland_pct": 25.19,
    "natural_vegetation_ha": 742.26,
    "natural_vegetation_pct": 74.5,
    "historic_water_extent_ha": 927.97,
    "historic_water_extent_pct": 93.14,
    "new_flood_extent_ha": 68.4,
    "new_flood_extent_pct": 6.86,
    "mean_hand_m": 0.92,
    "source": "ESA WorldCover v200 Built-up/Cropland & JRC GSW v1.4"
  }
}
```

---

### 5.4. `GET /api/v1/report/{pair_id}/csv`
Экспорт официального отчета по паре в формате CSV.
```bash
curl -X GET "http://localhost:8000/api/v1/report/flood_2019_07_amur__blagoveshchensk/csv" \
     -o report_blagoveshchensk_2019.csv
```

---

### 5.5. `GET /api/v1/geojson/{pair_id}`
Получение векторных контуров затопления или водного зеркала в формате GeoJSON (EPSG:4326) для отображения на карте.
Параметр `layer`: `flood` (по умолчанию), `water_pre`, `water_peak`.
```bash
# Векторные контуры зоны затопления
curl -X GET "http://localhost:8000/api/v1/geojson/flood_2019_07_amur__blagoveshchensk?layer=flood" \
     -H "Accept: application/json" -o flood_contours.geojson

# Векторные контуры водного зеркала на пике паводка
curl -X GET "http://localhost:8000/api/v1/geojson/flood_2019_07_amur__blagoveshchensk?layer=water_peak" \
     -H "Accept: application/json" -o water_peak_contours.geojson
```

> Сумма площадей выгруженных контуров немного меньше растровой площади слоя: отбрасываются кластеры $< 500$ м² (`geojson_min_area_sqm`) и выполняется упрощение геометрии для веба. Фактическая потеря по всем 11 парам — в среднем **0.5 %** (максимум 1.3 %). Кап числа контуров задаётся ключом `geojson_max_contours` (значение `0` = без ограничения, дефолт), так что площадь не теряется из-за усечения списка.

---

### 5.6. `POST /api/v1/predict`
Пространственно-временной инференс по идентификатору пары, произвольному Bounding Box (`[min_lon, min_lat, max_lon, max_lat]`) или GeoJSON-полигону. Если заданы одновременно геометрия и даты (`date_pre`, `date_peak`), пара выбирается как ближайшая по датам съёмки среди пересекающихся; при отсутствии дат — по максимальному перекрытию.
```bash
curl -X POST "http://localhost:8000/api/v1/predict" \
     -H "Content-Type: application/json" \
     -d '{
       "pair_id": "flood_2019_07_amur__blagoveshchensk"
     }'
```
**Пример ответа (фрагмент, фактические значения пары из `submission.csv`):**
```json
{
  "status": "success",
  "pair_id": "flood_2019_07_amur__blagoveshchensk",
  "query_bounds": null,
  "query_dates": {
    "date_pre": null,
    "date_peak": null
  },
  "summary": {
    "flood_ha": 996.37,
    "flood_km2": 9.964,
    "water_pre_ha": 8913.3,
    "water_peak_ha": 9189.0,
    "water_gain_ha": 275.7,
    "water_gain_pct": 3.09,
    "receded_ha": 359.04,
    "share_of_aoi": 0.006042,
    "landcover": {
      "builtup_ha": 3.11,
      "builtup_pct": 0.31,
      "cropland_ha": 251.0,
      "cropland_pct": 25.19,
      "natural_vegetation_ha": 742.26,
      "natural_vegetation_pct": 74.5,
      "historic_water_extent_ha": 927.97,
      "historic_water_extent_pct": 93.14,
      "new_flood_extent_ha": 68.4,
      "new_flood_extent_pct": 6.86,
      "mean_hand_m": 0.92
    }
  },
  "geojson": {
    "type": "FeatureCollection",
    "name": "flood_2019_07_amur__blagoveshchensk_flood",
    "features": ["… 1179 контуров …"]
  }
}
```
> Числовое поле `receded_ha` в реальном ответе — значение, вычисленное из растровых масок (`water_pre == 1 & water_peak == 0`), и зависит от пары. Для пары Благовещенск 2019 оба снимка зафиксировали высокое водное зеркало на пике, поэтому спад практически нулевой. Поля `execution_time_s`, `has_s2_pre` и др. в ответе не предусмотрены.

---

### 5.7. `GET /api/v1/audit/{pair_id}`
Генерация криптографического сертификата аудита неизменяемости данных на базе Merkle-дерева (SHA-256 integrity root, MRV compliance).
```bash
curl -X GET "http://localhost:8000/api/v1/audit/flood_2019_07_amur__blagoveshchensk" -H "Accept: application/json"
```

---

### 5.8. `GET /api/v1/uncertainty/{pair_id}`
Расчет пространственной погрешности и 95% доверительного интервала площади затопления `[lower_bound_ha, upper_bound_ha]` с учетом автокорреляции ошибок (Spatial Error Propagation).
```bash
curl -X GET "http://localhost:8000/api/v1/uncertainty/flood_2019_07_amur__blagoveshchensk?confidence_level=0.95" -H "Accept: application/json"
```

---

### 5.9. `GET /api/v1/sar-analytics/{pair_id}`
Радиолокационная аналитика: средние уровни обратного рассеяния ($\sigma^0_{VV}, \sigma^0_{VH}$), радиометрический контраст «вода/суша» и доля двойного отражения под пологом затопленного леса.
```bash
curl -X GET "http://localhost:8000/api/v1/sar-analytics/flood_2019_07_amur__blagoveshchensk" -H "Accept: application/json"
```

---

### 5.10. `GET /api/v1/carbon-metrics/{pair_id}`
Оценка экологического и углеродного ущерба по методологии IPCC (Tier 1/Tier 2): потери углерода биомассы ($CF = 0.47$), эквивалентные выбросы $tCO_2e$ и расчет углеродных сертификатов.
```bash
curl -X GET "http://localhost:8000/api/v1/carbon-metrics/flood_2019_07_amur__blagoveshchensk" -H "Accept: application/json"
```

---

### 5.11. `GET /api/v1/metrics/official` и `GET /api/v1/metrics/validate-submission`
- `/metrics/official` — оперативный расчет официального соревновательного $Score$ и компонент ($Q_{flood}$, $Q_{water\_peak}$, $Q_{water\_pre}$, $Spec_{base}$);
- `/metrics/validate-submission` — проверка сабмита на соответствие техническому регламенту хакатона (11 пар, `flood <= water_peak`, расхождение растр-таблица $< 2\%$).

---

### 5.12. `GET /api/v1/overlay/{pair_id}` и `GET /api/v1/overlay/{pair_id}/meta`
- `/overlay/{pair_id}?layer=flood&gradient=true` — прямая отдача прозрачного растрового RGBA PNG слоя с градиентом глубины/интенсивности для быстрого наложения в Leaflet (`L.imageOverlay`);
- `/overlay/{pair_id}/meta?layer=flood` — получение географических координат WGS84 углов оверлея (`[[south, west], [north, east]]`).

---

### 5.13. `GET /api/v1/geotiff/{pair_id}` и `GET /api/v1/shapefile/{pair_id}`
Экспорт слоев в форматах GeoTIFF (uint8, EPSG:32652) и векторных архивов ESRI Shapefile (ZIP) для интеграции в QGIS, ArcGIS и геопорталы МЧС.

---

## 6. Данные (важно перед запуском)

### Что уже в репозитории (закоммичено, ~133 МБ)
- `hydrowatch_amur/reference_masks/` — эталонные маски (11 шт, по ним считается `evaluate`);
- `hydrowatch_amur/rasters/**/AUX_terrain_gsw.tif` — приоры рельефа (slope/HAND/GSW/builtup);
- `hydrowatch_amur/rasters/**/CROPLAND_worldcover.tif` — маска пашни ESA WorldCover v200 (класс 40), получена `scripts/fetch_worldcover.py`, используется для разделения `cropland` и `natural_vegetation` в отчётах;
- `hydrowatch_amur/rasters/**/SENTINEL2_*.tif` — растры индексов Sentinel-2 (6 пар × 2 даты); фактически все каналы содержат **только nodata (-999.0)**, полезных наблюдений в кейсе нет;
- паспорта сцен (`S1_*.json`), метеоданные `ERA5_daily_*.csv`, каталоги `tables/`, векторы `vectors/`;
- `predictions/` — все сгенерированные маски (`*_flood.tif`, `*_water_pre.tif`, `*_water_peak.tif`, `*_flooded_vegetation.tif`, uint8 EPSG:32652 10 м).

### Что остаётся внешним: радары Sentinel-1 (~2.9 ГБ)
Сцены `S1_pre_*/S1_peak_*.tif` (по ~180 МБ × 45) **не хранятся в git** (см. `.gitignore`) — это тяжёлые бинарные радарные снимки, помеченные «публикация и передача третьим лицам запрещены».

> **Провенанс радарных данных (воспроизводимость).** Паспорта сцен (`S1_*.json`) указывают коллекцию Google Earth Engine `COPERNICUS/S1_GRD` с калибровкой в $\sigma^0$ (dB). Скрипт `scripts/download_all_scenes.py` приведён в соответствие: он выгружает коллекцию Microsoft Planetary Computer `sentinel-1-grd` — тот же калиброванный продукт $\sigma^0$ (ранее ошибочно использовалась `sentinel-1-rtc`, то есть $\gamma^0$ с террейновой нормализацией — иной радиометрический продукт, отличающийся на 1–3 дБ на склонах). Обе коллекции дают $IW$ GRD в дБ по каналам VV/VH. Ссылка на набор:

```
https://drive.google.com/file/d/15bwUajgK31XtiW_EiMAAfvTAaqzA6skV/view?usp=sharing
```

Скачивание и распаковка (одна команда, `gdown` + stdlib `zipfile`, системный `unzip` не нужен):

```bash
uv run python -m src.cli fetch
```

Что делает команда:
1. Скачивает архив полного набора кейса (включая `rasters/` с S1) через `gdown` в `./hydrowatch_amur_dataset.zip`;
2. Распаковывает его в корень репозитория (безопасно, `../../`-пути в архиве блокируются);
3. Предупреждает, если какие-то пары всё ещё без S1.

Полезные флаги: `--archive-output <путь>` — куда сохранять архив (по умолчанию `./hydrowatch_amur_dataset.zip`); `--no-keep-archive` — удалить архив после распаковки (экономит ~3 ГБ). Повторный запуск при уже скачанном архиве пропускает загрузку.

После распаковки структура `hydrowatch_amur/rasters/` должна соответствовать путям в `hydrowatch_amur/pairs.csv`.

> ⚠️ **Без S1 полный инференс невозможен:** команда `uv run python -m src.cli predict` читает радары `S1_pre_*.tif`/`S1_peak_*.tif` из `hydrowatch_amur/rasters/`; при их отсутствии CLI завершится с понятным сообщением «запустите `fetch`» (не голым `FileNotFoundError`). Всё остальное (эталоны, AUX, S2-индексы) уже в репозитории. В `src/service/cache/` — готовые отчёты и GeoJSON для всех 11 пар, в `predictions/` — финальные маски сабмита.

---

## 7. Ресурсоемкость и бенчмарк

Комплекс спроектирован для надежного развертывания в полевых и защищенных контурах ситуационных центров без внешних интернет-зависимостей:

| Параметр | Значение | Примечание |
|---|---|---|
| **Пиковое потребление RAM** | **~3.6 ГБ** (измерено) | Полные сцены S1 читаются целыми массивами `numpy`; оконного чтения (`rasterio.windows.Window`) в коде нет |
| **Время обработки сцены** | **~6.5 сек / пара** (верифицировано) | Измерено на полном наборе из 11 пар через `uv run python -m src.cli benchmark` |
| **Требование к GPU** | **Не требуется (0 MB VRAM)** | Высокопроизводительные векторные вычисления на NumPy/SciPy |
| **Инференс (SAR-ядро)** | **Без интернет-запросов** | Растровые данные и приоры читаются с локального диска; внешних API нет |
| **Web-дашборд** | **Работает офлайн** | Leaflet и стили бандлятся в SPA, шрифты Inter/JetBrains Mono и иконки подключены локально (`src/service/static/vendor/`, `src/service/static/icons/`); внешняя спутниковая подложка Esri требует интернет, но интерфейс и векторные слои работают без сети |
| **Время холодного старта API** | **< 1.0 сек** | Легковесный ASGI uvicorn + FastAPI |
| **Формат выходных данных** | GeoTIFF (uint8) + GeoJSON + Shapefile (ZIP) | Полная совместимость с QGIS, ArcGIS, MapLibre, NextGIS |

---

## 8. Инструкция для жюри по валидации сабмита

> **Важно:** полная регенерация сабмита (п. 2 ниже) требует наличия данных кейса (`hydrowatch_amur/rasters/` и `hydrowatch_amur/reference_masks/`), которые скачиваются отдельно — см. раздел «6. Данные». Сами артефакты (`submission.csv`, `predictions/*.tif`, кэш-отчёты API в `src/service/cache/`) уже включены в репозиторий и верифицируемы без скачивания данных.

### 1. Проверка структуры и консистентности сабмита
Файл [`submission.csv`](submission.csv) сформирован строго по регламенту:
- Содержит ровно 11 строк, соответствующих парам в [`hydrowatch_amur/pairs.csv`](hydrowatch_amur/pairs.csv);
- Колонки: `pair_id`, `flood_ha`, `water_pre_ha`, `water_peak_ha`;
- Строго соблюдается физическое ограничение: `flood_ha <= water_peak_ha` для всех строк;
- Площади в CSV строго согласованы с попиксельным подсчетом в растрах `predictions/*.tif` с погрешностью $< 2\%$.

### 2. Команды для полной регенерации сабмита
Требуется предварительно скачать данные кейса (см. раздел «6. Данные»):
```bash
# 1. Запуск полного пайплайна инференса (регенерация submission.csv и GeoTIFF)
uv run python -m src.cli predict

# 2. Вычисление официальной метрики и запуск 4 ступеней абляций
uv run python -m src.cli evaluate --run-ablations
```

### 3. Инспекция растровых масок решений
Сгенерированные бинарные маски затоплений размещены в папке [`predictions/`](predictions/):
- Формат: GeoTIFF (`<pair_id>_flood.tif`), тип данных `uint8`, значения `0` (суша/не затоплено) и `1` (затоплено);
- Проекция: целевая `EPSG:32652` (WGS 84 / UTM zone 52N);
- Пространственное разрешение: 10 метров на пиксель (1 пиксель = 0.01 га);
- Привязка и сетка пикселей строго совпадают с эталонными масками `hydrowatch_amur/reference_masks/`.

---

## 9. Стек технологий

- **Язык и расчетное ядро:** Python 3.13+, `rasterio`, `shapely`, `geopandas`, `scipy`, `numpy`, `pandas`;
- **Пакетный менеджер и окружение:** `uv` (Astral), `pyproject.toml`, `uv.lock`;
- **Сервисный бэкенд:** `fastapi`, `uvicorn`, `pydantic v2`;
- **Пользовательский картографический интерфейс:** React 18, TypeScript, Vite, Tailwind CSS, Leaflet 1.9, Recharts, Lucide Icons, jsPDF & html2canvas (автогенерация PDF-паспортов затоплений);
- **Тестирование и контроль качества:** 22 модуля тестов: `pytest` (182 бэкенд-теста, 100% pass), `vitest` / React Testing Library (116 фронтенд-тестов, 100% pass);
- **Контейнеризация:** Docker, Docker Compose, `python:3.13-slim`.
