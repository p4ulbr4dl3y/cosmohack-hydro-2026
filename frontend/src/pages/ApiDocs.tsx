import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Send,
  Copy,
  Check,
  ExternalLink,
  Terminal,
  CheckCircle2,
  Menu,
  X,
  BookOpen,
  Map,
} from 'lucide-react';

interface EndpointParam {
  name: string;
  type: string;
  required: boolean;
  description: string;
  default?: string;
  options?: string[];
}

interface ErrorCode {
  code: number;
  description: string;
}

interface EndpointDef {
  id: string;
  method: 'GET' | 'POST';
  path: string;
  title: string;
  description: string;
  category: 'core' | 'analytics' | 'layers' | 'system';
  params?: EndpointParam[];
  requestBody?: string;
  responseExample: string;
  errorCodes: ErrorCode[];
  curlTemplate: (params: Record<string, string>, body?: string) => string;
  buildUrl: (params: Record<string, string>) => string;
}

const PAIR_OPTIONS = [
  'flood_2019_07_amur__blagoveshchensk',
  'baseline_2018_09_low__blagoveshchensk',
  'baseline_2018_09_low__konstantinovka',
  'baseline_2018_09_low__svobodny',
  'flood_2019_07_amur__belogorsk',
  'flood_2019_07_amur__konstantinovka',
  'flood_2019_07_amur__svobodny',
  'flood_2021_06_amur__blagoveshchensk',
  'flood_2021_06_amur__konstantinovka',
  'flood_2021_06_amur__poyarkovo',
  'flood_2021_08_zeya__svobodny',
];

export const ENDPOINTS: EndpointDef[] = [
  {
    id: 'events',
    method: 'GET',
    path: '/api/v1/events',
    title: 'Реестр событий и пар наблюдений',
    description: 'Возвращает массив всех 11 зарегистрированных пар разновременных наблюдений (Sentinel-1 SAR + Sentinel-2 MSI) с датами, типами событий, AOI и площадями.',
    category: 'core',
    responseExample: JSON.stringify(
      [
        {
          pair_id: 'flood_2019_07_amur__blagoveshchensk',
          aoi_id: 'blagoveshchensk',
          aoi_name: 'Благовещенск — слияние Амура и Зеи',
          event_id: 'flood_2019_07_amur',
          event_name: 'Паводок в Приамурье, июль 2019',
          event_kind: 'rain_flood',
          year: 2019,
          sensor_sar: 'sentinel1',
          sensor_optical: '',
          date_pre_sar: '2019-06-13',
          date_peak_sar: '2019-07-25',
          date_pre_opt: '',
          date_peak_opt: '',
          aoi_km2: 1649.168,
          aoi_ha: 164916.8,
        },
      ],
      null,
      2
    ),
    errorCodes: [
      { code: 500, description: 'Внутренняя ошибка загрузчика каталога данных' },
    ],
    buildUrl: () => '/api/v1/events',
    curlTemplate: () => `curl -X GET http://127.0.0.1:8000/api/v1/events`,
  },
  {
    id: 'pairs',
    method: 'GET',
    path: '/api/v1/pairs',
    title: 'Список всех пар наблюдений',
    description: 'Расширенный список 11 пар со всеми гидрологическими характеристиками, сенсорами и статусами контроля.',
    category: 'core',
    responseExample: JSON.stringify(
      [
        {
          pair_id: 'flood_2019_07_amur__blagoveshchensk',
          aoi_id: 'blagoveshchensk',
          aoi_name: 'Благовещенск — слияние Амура и Зеи',
          event_id: 'flood_2019_07_amur',
          event_name: 'Паводок в Приамурье, июль 2019',
          event_kind: 'rain_flood',
          year: 2019,
          sensor_sar: 'sentinel1',
          sensor_optical: '',
          date_pre_sar: '2019-06-13',
          date_peak_sar: '2019-07-25',
          aoi_km2: 1649.168,
          aoi_ha: 164916.8,
        },
      ],
      null,
      2
    ),
    errorCodes: [
      { code: 500, description: 'Ошибка чтения реестра пар' },
    ],
    buildUrl: () => '/api/v1/pairs',
    curlTemplate: () => `curl -X GET http://127.0.0.1:8000/api/v1/pairs`,
  },
  {
    id: 'aoi',
    method: 'GET',
    path: '/api/v1/aoi',
    title: 'Границы районов интереса (AOI)',
    description: 'Возвращает GeoJSON FeatureCollection с векторными полигонами границ всех зон мониторинга в Амурской области (EPSG:4326).',
    category: 'core',
    responseExample: JSON.stringify(
      {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: { aoi_id: 'blagoveshchensk', name_ru: 'Благовещенск', area_km2: 1649.17 },
            geometry: { type: 'Polygon', coordinates: [[[127.21, 50.12], [127.85, 50.12], [127.85, 50.45], [127.21, 50.45], [127.21, 50.12]]] },
          },
        ],
      },
      null,
      2
    ),
    errorCodes: [
      { code: 404, description: 'Файл aoi.geojson не найден' },
      { code: 500, description: 'Ошибка разбора GeoJSON' },
    ],
    buildUrl: () => '/api/v1/aoi',
    curlTemplate: () => `curl -X GET http://127.0.0.1:8000/api/v1/aoi`,
  },
  {
    id: 'analyze',
    method: 'POST',
    path: '/api/v1/analyze',
    title: 'Анализ гидродинамики (Analyze)',
    description: 'Запускает расчёт зоны нового затопления и водного зеркала по идентификатору пары или границам, возвращая площади и распределение по типам покрова.',
    category: 'analytics',
    requestBody: JSON.stringify(
      {
        pair_id: 'flood_2019_07_amur__blagoveshchensk',
      },
      null,
      2
    ),
    responseExample: JSON.stringify(
      {
        status: 'success',
        pair_id: 'flood_2019_07_amur__blagoveshchensk',
        query_bounds: null,
        query_polygon: null,
        query_dates: { date_pre: null, date_peak: null },
        scene_dates: { date_pre: '2019-06-13', date_peak: '2019-07-25' },
        summary: {
          flood_ha: 996.37,
          flood_km2: 9.964,
          water_pre_ha: 8913.3,
          water_peak_ha: 9189.0,
          water_gain_ha: 275.7,
          water_gain_pct: 3.09,
          receded_ha: 820.79,
          share_of_aoi: 0.006042,
          landcover: {
            builtup_ha: 3.11,
            builtup_pct: 0.31,
            cropland_ha: 251.0,
            cropland_pct: 25.19,
            natural_vegetation_ha: 742.26,
            natural_vegetation_pct: 74.5,
            historic_water_extent_ha: 927.97,
            historic_water_extent_pct: 93.14,
            new_flood_extent_ha: 68.4,
            new_flood_extent_pct: 6.86,
            mean_hand_m: 0.92,
          },
        },
        geojson: { name: 'flood_2019_07_amur__blagoveshchensk_flood', features: ['…'] },
      },
      null,
      2
    ),
    errorCodes: [
      { code: 400, description: 'Некорректный запрос или отсутствует pair_id' },
      { code: 404, description: 'Пара наблюдений не найдена' },
      { code: 500, description: 'Внутренняя ошибка ML-консенсуса' },
    ],
    buildUrl: () => '/api/v1/analyze',
    curlTemplate: (_p, body) =>
      `curl -X POST http://127.0.0.1:8000/api/v1/analyze \\\n  -H "Content-Type: application/json" \\\n  -d '${body || '{"pair_id":"flood_2019_07_amur__blagoveshchensk"}'}'`,
  },
  {
    id: 'predict',
    method: 'POST',
    path: '/api/v1/predict',
    title: 'Пространственный расчёт (Inference)',
    description: 'Инференс консенсусной модели детекции затопления по пространственно-временным координатам и датам наблюдений.',
    category: 'analytics',
    requestBody: JSON.stringify(
      {
        pair_id: 'flood_2019_07_amur__blagoveshchensk',
        date_pre: '2019-06-13',
        date_peak: '2019-07-25',
      },
      null,
      2
    ),
    responseExample: JSON.stringify(
      {
        status: 'success',
        pair_id: 'flood_2019_07_amur__blagoveshchensk',
        summary: {
          flood_ha: 996.37,
          flood_km2: 9.964,
          water_pre_ha: 8913.3,
          water_peak_ha: 9189.0,
          water_gain_ha: 275.7,
          water_gain_pct: 3.09,
          receded_ha: 820.79,
        },
      },
      null,
      2
    ),
    errorCodes: [
      { code: 400, description: 'Неверные координаты или формат даты' },
      { code: 500, description: 'Ошибка сегментации SAR/MSI' },
    ],
    buildUrl: () => '/api/v1/predict',
    curlTemplate: (_p, body) =>
      `curl -X POST http://127.0.0.1:8000/api/v1/predict \\\n  -H "Content-Type: application/json" \\\n  -d '${body || '{"pair_id":"flood_2019_07_amur__blagoveshchensk"}'}'`,
  },
  {
    id: 'report',
    method: 'GET',
    path: '/api/v1/report/{pair_id}',
    title: 'Аналитический отчёт по паре',
    description: 'Полный аналитический отчёт с площадями нового затопления, историческими максимумами, балансом воды и разбивкой по типам покрова (Landcover).',
    category: 'analytics',
    params: [
      {
        name: 'pair_id',
        type: 'string',
        required: true,
        description: 'Идентификатор пары наблюдений',
        default: 'flood_2019_07_amur__blagoveshchensk',
        options: PAIR_OPTIONS,
      },
    ],
    responseExample: JSON.stringify(
      {
        pair_id: 'flood_2019_07_amur__blagoveshchensk',
        aoi_id: 'blagoveshchensk',
        aoi_name: 'Благовещенск — слияние Амура и Зеи',
        event_id: 'flood_2019_07_amur',
        event_name: 'Паводок в Приамурье, июль 2019',
        event_kind: 'rain_flood',
        year: 2019,
        sensor_sar: 'sentinel1',
        sensor_optical: '',
        date_pre_sar: '2019-06-13',
        date_peak_sar: '2019-07-25',
        date_pre_opt: '',
        date_peak_opt: '',
        aoi_km2: 1649.168,
        aoi_ha: 164916.8,
        generated_at: '2026-09-21T20:21:00+00:00',
        flood_ha: 996.37,
        flood_km2: 9.964,
        water_pre_ha: 8913.3,
        water_peak_ha: 9189.0,
        permanent_ha: 7338.12,
        receded_ha: 820.79,
        water_gain_ha: 275.7,
        water_gain_pct: 3.09,
        share_of_aoi: 0.006042,
        flood_share_pct: 0.604,
        landcover: {
          builtup_ha: 3.11,
          builtup_pct: 0.31,
          cropland_ha: 251.0,
          cropland_pct: 25.19,
          natural_vegetation_ha: 742.26,
          natural_vegetation_pct: 74.5,
          historic_water_extent_ha: 927.97,
          historic_water_extent_pct: 93.14,
          new_flood_extent_ha: 68.4,
          new_flood_extent_pct: 6.86,
          mean_hand_m: 0.92,
          source: 'ESA WorldCover v200 Built-up/Cropland & JRC GSW v1.4',
        },
      },
      null,
      2
    ),
    errorCodes: [
      { code: 404, description: 'Отчёт для указанной пары не найден' },
    ],
    buildUrl: (p) => `/api/v1/report/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}`,
    curlTemplate: (p) =>
      `curl -X GET http://127.0.0.1:8000/api/v1/report/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}`,
  },
  {
    id: 'comparison',
    method: 'GET',
    path: '/api/v1/comparison/{pair_id}',
    title: 'Сравнение с эталоном (Reference Validation)',
    description: 'Сопоставление расчетных площадей с эталонной верифицированной маской паводка и вычисление процента отклонения.',
    category: 'analytics',
    params: [
      {
        name: 'pair_id',
        type: 'string',
        required: true,
        description: 'Идентификатор пары наблюдений',
        default: 'flood_2019_07_amur__blagoveshchensk',
        options: PAIR_OPTIONS,
      },
    ],
    responseExample: JSON.stringify(
      {
        pair_id: 'flood_2019_07_amur__blagoveshchensk',
        rows: [
          { metric: 'flood_ha', label: 'Новое затопление', pred: 996.37, reference: 386.3, diff_pct: 157.9 },
          {
            metric: 'water_peak_ha',
            label: 'Водное зеркало (пик)',
            pred: 9189.0,
            reference: 8894.42,
            diff_pct: 3.3,
          },
          {
            metric: 'water_pre_ha',
            label: 'Водное зеркало (до)',
            pred: 8913.3,
            reference: 2866.89,
            diff_pct: 210.9,
          },
        ],
      },
      null,
      2
    ),
    errorCodes: [
      { code: 404, description: 'Пара или эталонная маска не найдены' },
    ],
    buildUrl: (p) => `/api/v1/comparison/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}`,
    curlTemplate: (p) =>
      `curl -X GET http://127.0.0.1:8000/api/v1/comparison/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}`,
  },
  {
    id: 'ablation',
    method: 'GET',
    path: '/api/v1/ablation',
    title: 'Результаты абляции ML-моделей',
    description: 'Метрики качества (F1, IoU, Precision, Recall) для различных конфигураций пайплайна: SAR-only, MSI-only, Consensus, с HAND и DEM фильтрацией.',
    category: 'analytics',
    responseExample: JSON.stringify(
      {
        ablation_4: {
          mode: 4,
          description: 'Ablation 4: Full pipeline (+ MMU 25px + GSW permanent)',
          official_metrics: {
            score: 0.403,
            Q_flood: 0.2742,
            Q_water_peak: 0.449,
            Q_water_pre: 0.4006,
            Spec_base: 0.7153,
            num_events: 8,
            num_baselines: 3,
          },
          raster_metrics: {
            mean_iou: 0.1809,
            mean_precision: 0.2178,
            mean_recall: 0.6214,
            mean_f1: 0.2846,
          },
        },
      },
      null,
      2
    ),
    errorCodes: [
      { code: 404, description: 'Файл ablation_results.json не найден' },
    ],
    buildUrl: () => '/api/v1/ablation',
    curlTemplate: () => `curl -X GET http://127.0.0.1:8000/api/v1/ablation`,
  },
  {
    id: 'metrics_official',
    method: 'GET',
    path: '/api/v1/metrics/official',
    title: 'Официальный Score и сходимость по ТЗ',
    description: 'Интегральная соревновательная метрика Score = 0.45*Q_flood + 0.25*Q_peak + 0.15*Q_pre + 0.15*Spec_base с детальным отчетом по всем 11 парам.',
    category: 'analytics',
    responseExample: JSON.stringify(
      {
        score: 0.403,
        q_flood: 0.2742,
        q_water_peak: 0.449,
        q_water_pre: 0.4006,
        spec_base: 0.7153,
        num_events: 8,
        num_baselines: 3,
        technical_points: 2.82,
        details: [
          {
            pair_id: 'flood_2019_07_amur__belogorsk',
            event_kind: 'rain_flood',
            aoi_ha: 125000.0,
            flood_sub_ha: 69.62,
            flood_ref_ha: 187.19,
            q_flood: 0.3719,
          },
        ],
      },
      null,
      2
    ),
    errorCodes: [
      { code: 404, description: 'submission.csv не найден' },
    ],
    buildUrl: () => '/api/v1/metrics/official',
    curlTemplate: () => `curl -X GET http://127.0.0.1:8000/api/v1/metrics/official`,
  },
  {
    id: 'metrics_validate',
    method: 'GET',
    path: '/api/v1/metrics/validate-submission',
    title: 'Валидация сабмита и растров (CRITERIA.md)',
    description: 'Проверка обязательных соревновательных критериев: 11 пар, отсутствие NaN, flood_ha <= water_peak_ha, проверка правила расхождения растровой маски и CSV <= 2%.',
    category: 'analytics',
    responseExample: JSON.stringify(
      {
        is_valid: true,
        num_pairs: 11,
        passed_checks: [
          'Columns match required schema [pair_id, flood_ha, water_pre_ha, water_peak_ha]',
          'All 11 pairs match official pairs registry',
          'No missing values or NaNs in table',
          'Physical constraints satisfied (non-negative and flood_ha <= water_peak_ha)',
          'All 11 GeoTIFF rasters match CSV areas within <= 2.0% divergence rule',
        ],
        errors: [],
        warnings: [],
      },
      null,
      2
    ),
    errorCodes: [],
    buildUrl: () => '/api/v1/metrics/validate-submission',
    curlTemplate: () => `curl -X GET http://127.0.0.1:8000/api/v1/metrics/validate-submission`,
  },
  {
    id: 'carbon_metrics',
    method: 'GET',
    path: '/api/v1/carbon-metrics/{pair_id}',
    title: 'Углеродный ущерб и ESG-кредиты (IPCC)',
    description: 'Расчет потерь углеродного пула в живой биомассе затопленных сельхозугодий и лесов (CF=0.47, 44/12 CO2-экв.) и потенциала углеродных единиц.',
    category: 'analytics',
    params: [
      {
        name: 'pair_id',
        type: 'string',
        required: true,
        description: 'Идентификатор пары',
        default: 'flood_2019_07_amur__blagoveshchensk',
        options: PAIR_OPTIONS,
      },
    ],
    responseExample: JSON.stringify(
      {
        pair_id: 'flood_2019_07_amur__blagoveshchensk',
        flood_ha: 996.37,
        biomass_loss_dry_matter_t: 9840.5,
        carbon_loss_tC: 4625.04,
        emissions_equivalent_tCO2e: 16958.46,
        cropland_loss_tC: 1572.3,
        forest_loss_tC: 1404.88,
        credit_potential: {
          is_available: true,
          status: 'success',
          Q_credits: 13248,
          UNC_deduction_rate: 0.08,
          buffer_reserve_B_tCO2e: 2337.8,
          valuations_rub: {
            '500': 6624000,
            '1500': 19872000,
            '4000': 52992000,
          },
        },
      },
      null,
      2
    ),
    errorCodes: [
      { code: 404, description: 'Пара не найдена' },
    ],
    buildUrl: (p: Record<string, string>) => `/api/v1/carbon-metrics/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}`,
    curlTemplate: (p: Record<string, string>) => `curl -X GET http://127.0.0.1:8000/api/v1/carbon-metrics/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}`,
  },
  {
    id: 'layers_geojson',
    method: 'GET',
    path: '/api/v1/layers/{pair_id}/geojson',
    title: 'Векторные контуры пары (GeoJSON)',
    description: 'Возвращает полную GeoJSON FeatureCollection с полигонами зон затопления и водного зеркала по спецификации OpenAPI.',
    category: 'layers',
    params: [
      {
        name: 'pair_id',
        type: 'string',
        required: true,
        description: 'Идентификатор пары',
        default: 'flood_2019_07_amur__blagoveshchensk',
        options: PAIR_OPTIONS,
      },
    ],
    responseExample: JSON.stringify(
      {
        type: 'FeatureCollection',
        name: 'flood_2019_07_amur__blagoveshchensk_flood',
        features: [
          {
            type: 'Feature',
            properties: {
              contour_id: 'flood_0001',
              area_ha: 34.06,
              pair_id: 'flood_2019_07_amur__blagoveshchensk',
              layer: 'flood',
              aoi_name: 'Благовещенск — слияние Амура и Зеи',
              event_name: 'Паводок в Приамурье, июль 2019',
              date_peak: '2019-07-25',
            },
            geometry: { type: 'Polygon', coordinates: [] },
          },
        ],
      },
      null,
      2
    ),
    errorCodes: [
      { code: 404, description: 'Контуры для пары не найдены' },
    ],
    buildUrl: (p) => `/api/v1/layers/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}/geojson`,
    curlTemplate: (p) =>
      `curl -X GET http://127.0.0.1:8000/api/v1/layers/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}/geojson`,
  },
  {
    id: 'layers_by_name',
    method: 'GET',
    path: '/api/v1/layers/{pair_id}/{layer}',
    title: 'Конкретный слой пары (GeoJSON)',
    description: 'Возвращает отдельный гео-слой по имени: flood (затопление), water_peak (вода пика), water_pre (вода до наводнения).',
    category: 'layers',
    params: [
      {
        name: 'pair_id',
        type: 'string',
        required: true,
        description: 'Идентификатор пары',
        default: 'flood_2019_07_amur__blagoveshchensk',
        options: PAIR_OPTIONS,
      },
      {
        name: 'layer',
        type: 'string',
        required: true,
        description: 'Имя слоя',
        default: 'flood',
        options: ['flood', 'water_peak', 'water_pre'],
      },
    ],
    responseExample: JSON.stringify(
      {
        type: 'FeatureCollection',
        name: 'flood_2019_07_amur__blagoveshchensk_flood',
        features: [
          {
            type: 'Feature',
            properties: {
              contour_id: 'flood_0001',
              area_ha: 34.06,
              pair_id: 'flood_2019_07_amur__blagoveshchensk',
              layer: 'flood',
            },
            geometry: { type: 'Polygon', coordinates: [] },
          },
        ],
      },
      null,
      2
    ),
    errorCodes: [
      { code: 404, description: 'Слой или пара не найдены' },
    ],
    buildUrl: (p) =>
      `/api/v1/layers/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}/${p.layer || 'flood'}`,
    curlTemplate: (p) =>
      `curl -X GET http://127.0.0.1:8000/api/v1/layers/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}/${p.layer || 'flood'}`,
  },
  {
    id: 'vectors',
    method: 'GET',
    path: '/api/v1/vectors/{layer_name}',
    title: 'Тематические векторы региона',
    description: 'Возвращает базовые гео-слои: hydrography_osm (гидросеть), basins_hydrosheds (водосборные бассейны), amur_oblast (граница области).',
    category: 'layers',
    params: [
      {
        name: 'layer_name',
        type: 'string',
        required: true,
        description: 'Название тематического слоя',
        default: 'hydrography_osm',
        options: ['hydrography_osm', 'basins_hydrosheds', 'amur_oblast', 'aoi'],
      },
    ],
    responseExample: JSON.stringify(
      {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: { name: 'Amur River' },
            geometry: { type: 'LineString', coordinates: [] },
          },
        ],
      },
      null,
      2
    ),
    errorCodes: [
      { code: 404, description: 'Векторный слой не найден' },
    ],
    buildUrl: (p) => `/api/v1/vectors/${p.layer_name || 'hydrography_osm'}`,
    curlTemplate: (p) =>
      `curl -X GET http://127.0.0.1:8000/api/v1/vectors/${p.layer_name || 'hydrography_osm'}`,
  },
  {
    id: 'export_vectors',
    method: 'GET',
    path: '/api/v1/export/{pair_id}/vectors',
    title: 'Экспорт векторных контуров',
    description: 'Экспортирует полигоны затопления в формате GeoJSON или архива Shapefile (.zip) для загрузки в ArcGIS / QGIS.',
    category: 'layers',
    params: [
      {
        name: 'pair_id',
        type: 'string',
        required: true,
        description: 'Идентификатор пары',
        default: 'flood_2019_07_amur__blagoveshchensk',
        options: PAIR_OPTIONS,
      },
      {
        name: 'format',
        type: 'string',
        required: false,
        description: 'Формат экспорта: geojson или shp',
        default: 'geojson',
        options: ['geojson', 'shp'],
      },
    ],
    responseExample: '{\n  "type": "FeatureCollection",\n  "features": [ ... ]\n}',
    errorCodes: [
      { code: 404, description: 'Пара не найдена' },
    ],
    buildUrl: (p) =>
      `/api/v1/export/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}/vectors?format=${p.format || 'geojson'}`,
    curlTemplate: (p) =>
      `curl -X GET "http://127.0.0.1:8000/api/v1/export/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}/vectors?format=${p.format || 'geojson'}"`,
  },
  {
    id: 'export_report',
    method: 'GET',
    path: '/api/v1/export/{pair_id}/report',
    title: 'Экспорт аналитического отчета',
    description: 'Экспорт сводного отчета в машиночитаемом формате (JSON или CSV с кодировкой UTF-8).',
    category: 'layers',
    params: [
      {
        name: 'pair_id',
        type: 'string',
        required: true,
        description: 'Идентификатор пары',
        default: 'flood_2019_07_amur__blagoveshchensk',
        options: PAIR_OPTIONS,
      },
      {
        name: 'format',
        type: 'string',
        required: false,
        description: 'Формат отчета: json или csv',
        default: 'json',
        options: ['json', 'csv'],
      },
    ],
    responseExample: '{\n  "pair_id": "flood_2019_07_amur__blagoveshchensk",\n  "flood_ha": 996.37\n}',
    errorCodes: [
      { code: 404, description: 'Пара не найдена' },
    ],
    buildUrl: (p) =>
      `/api/v1/export/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}/report?format=${p.format || 'json'}`,
    curlTemplate: (p) =>
      `curl -X GET "http://127.0.0.1:8000/api/v1/export/${p.pair_id || 'flood_2019_07_amur__blagoveshchensk'}/report?format=${p.format || 'json'}"`,
  },
  {
    id: 'recompute',
    method: 'POST',
    path: '/api/v1/recompute',
    title: 'Инкрементальный пересчёт',
    description: 'Инициирует оперативный пересчёт гидрологических контуров при поступлении новых спутниковых снимков Sentinel-1.',
    category: 'system',
    responseExample: JSON.stringify(
      {
        status: 'success',
        message: 'Инкрементальный пересчёт выполнен успешно',
        processing_time_sec: 12.4,
        memory_peak_gb: 1.8,
        timestamp_utc: '2026-09-21 14:32:00 UTC',
      },
      null,
      2
    ),
    errorCodes: [
      { code: 500, description: 'Ошибка запуска конвейера обработки' },
    ],
    buildUrl: () => '/api/v1/recompute',
    curlTemplate: () =>
      `curl -X POST http://127.0.0.1:8000/api/v1/recompute \\\n  -H "Content-Type: application/json"`,
  },
  {
    id: 'health',
    method: 'GET',
    path: '/api/v1/health',
    title: 'Статус доступности (Health Check)',
    description: 'Проверка работоспособности сервиса, активности фоновых очередей и доступности каталога данных.',
    category: 'system',
    responseExample: JSON.stringify({ status: 'ok' }, null, 2),
    errorCodes: [
      { code: 500, description: 'Сервис временно недоступен' },
    ],
    buildUrl: () => '/api/v1/health',
    curlTemplate: () => `curl -X GET http://127.0.0.1:8000/api/v1/health`,
  },
];

export const ApiDocs: React.FC = () => {
  const [selectedEndpointId, setSelectedEndpointId] = useState<string>('events');
  const [paramValues, setParamValues] = useState<Record<string, string>>({
    pair_id: 'flood_2019_07_amur__blagoveshchensk',
    layer: 'flood',
    layer_name: 'hydrography_osm',
    format: 'geojson',
  });
  const [postBodyText, setPostBodyText] = useState<string>(
    JSON.stringify({ pair_id: 'flood_2019_07_amur__blagoveshchensk' }, null, 2)
  );

  const [testResult, setTestResult] = useState<string | null>(null);
  const [responseStatus, setResponseStatus] = useState<number | null>(null);
  const [responseTimeMs, setResponseTimeMs] = useState<number | null>(null);
  const [isLoadingTest, setIsLoadingTest] = useState<boolean>(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<'docs' | 'try' | 'list'>('docs');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const currentEndpoint =
    ENDPOINTS.find((e) => e.id === selectedEndpointId) || ENDPOINTS[0];

  // Автозаполнение шаблона тела при переключении эндпоинта
  useEffect(() => {
    if (currentEndpoint.requestBody) {
      setPostBodyText(currentEndpoint.requestBody);
    }
  }, [selectedEndpointId]);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleParamChange = (name: string, val: string) => {
    setParamValues((prev) => ({ ...prev, [name]: val }));
  };

  const handleRunLiveRequest = async () => {
    setIsLoadingTest(true);
    setResponseStatus(null);
    setResponseTimeMs(null);

    const targetUrl = currentEndpoint.buildUrl(paramValues);
    const startTime = performance.now();

    try {
      const resp = await fetch(targetUrl, {
        method: currentEndpoint.method,
        headers: {
          'Content-Type': 'application/json',
        },
        body:
          currentEndpoint.method === 'POST' && postBodyText
            ? postBodyText
            : undefined,
      });

      const elapsed = Math.round(performance.now() - startTime);
      setResponseTimeMs(elapsed);
      setResponseStatus(resp.status);

      const contentType = resp.headers.get('content-type') || '';
      if (contentType.includes('application/json') || contentType.includes('application/geo+json')) {
        const json = await resp.json();
        setTestResult(JSON.stringify(json, null, 2));
      } else {
        const txt = await resp.text();
        setTestResult(txt);
      }
    } catch (err: any) {
      const elapsed = Math.round(performance.now() - startTime);
      setResponseStatus(0);
      setResponseTimeMs(elapsed);
      setTestResult(
        JSON.stringify(
          {
            error: 'Network Error',
            message: err.message || 'Не удалось связаться с сервером',
            targetUrl,
          },
          null,
          2
        )
      );
    } finally {
      setIsLoadingTest(false);
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-[#FAFBFC] text-text-primary font-sans flex flex-col">
      {/* Topbar */}
      <header className="h-14 bg-white border-b border-[#EAECF0] px-4 sm:px-6 flex items-center justify-between shrink-0 z-30 relative">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:bg-slate-50 md:hidden transition-colors"
            title="Меню навигации"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>

          <Link to="/" className="flex items-center gap-2">
            <img src="/icons/logo.png" alt="HydroWatch" className="w-6 h-6 sm:w-7 sm:h-7 object-contain" />
            <span className="font-bold text-base sm:text-lg text-text-primary">HydroWatch</span>
            <span className="text-text-muted text-xs sm:text-sm font-normal">Amur</span>
          </Link>
          <span className="bg-[#E0F2FE] text-[#0284C7] rounded px-1.5 py-0.5 text-[10px] sm:text-[11px] font-semibold uppercase">
            REST API v1
          </span>
        </div>

        <div className="hidden md:flex items-center gap-6 text-xs text-text-secondary">
          <Link to="/dashboard" className="hover:text-text-primary transition-colors">
            Дашборд
          </Link>
          <Link to="/methodology" className="hover:text-text-primary transition-colors">
            Методика
          </Link>
          <span className="text-[#0EA5E9] font-semibold">Документация API</span>
          <a
            href="https://github.com/p4ulbr4dl3y/cosmohack-hydro-2026"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 hover:text-text-primary transition-colors"
          >
            <span>GitHub</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden absolute top-14 left-0 right-0 bg-white/98 backdrop-blur-md border-b border-[#EAECF0] shadow-xl p-4 z-50 animate-in slide-in-from-top-2 duration-150">
            <div className="space-y-1">
              <Link
                to="/dashboard"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
              >
                <Map className="w-4 h-4 text-[#0EA5E9]" />
                <span>Дашборд с картой</span>
              </Link>
              <Link
                to="/methodology"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
              >
                <BookOpen className="w-4 h-4 text-[#0EA5E9]" />
                <span>Методика вычислений</span>
              </Link>
              <Link
                to="/api-docs"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-semibold text-[#0284C7] bg-[#E0F2FE] transition-colors"
              >
                <Terminal className="w-4 h-4 text-[#0EA5E9]" />
                <span>REST API Документация</span>
              </Link>
            </div>
          </div>
        )}
      </header>

      {/* Mobile Switcher Bar */}
      <div className="xl:hidden flex items-center justify-around bg-white border-b border-[#EAECF0] px-2 py-1.5 shrink-0 z-20 select-none">
        <button
          onClick={() => setMobileTab('docs')}
          className={`flex-1 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
            mobileTab === 'docs'
              ? 'bg-[#E0F2FE] text-[#0284C7]'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span>Документация</span>
        </button>
        <button
          onClick={() => setMobileTab('try')}
          className={`flex-1 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
            mobileTab === 'try'
              ? 'bg-[#0EA5E9] text-white shadow-xs'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <Send className="w-3.5 h-3.5" />
          <span>Try it ({currentEndpoint.method})</span>
        </button>
        <button
          onClick={() => setMobileTab('list')}
          className={`flex-1 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
            mobileTab === 'list'
              ? 'bg-slate-100 text-text-primary font-bold'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>Каталог ({ENDPOINTS.length})</span>
        </button>
      </div>

      {/* 3-Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Column: Endpoints Catalog Navigation */}
        <aside
          className={`bg-white border-r border-[#EAECF0] p-4 overflow-y-auto space-y-5 text-xs select-none shrink-0 ${
            mobileTab === 'list' ? 'w-full flex-1' : 'hidden xl:block xl:w-72'
          }`}
        >
          <div>
            <div className="text-[10px] font-bold text-text-muted tracking-wider uppercase mb-2">
              НАЧАЛО РАБОТЫ
            </div>
            <div className="p-2.5 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1 text-[11px] text-text-secondary">
              <div className="flex items-center justify-between">
                <span>Базовый URL:</span>
                <span className="font-mono font-semibold text-text-primary">/api/v1</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Формат данных:</span>
                <span className="font-mono text-text-primary">JSON, GeoJSON</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Проекция:</span>
                <span className="font-mono text-text-primary">EPSG:4326</span>
              </div>
            </div>
          </div>

          {/* Endpoints Groups */}
          <div className="space-y-2">
            <div className="text-[10px] font-bold text-text-muted tracking-wider uppercase">
              ЭНДПОИНТЫ ({ENDPOINTS.length})
            </div>
            <div className="space-y-1 font-mono text-[11px]">
              {ENDPOINTS.map((ep) => {
                const isSelected = ep.id === selectedEndpointId;
                const isGet = ep.method === 'GET';
                return (
                  <button
                    key={ep.id}
                    onClick={() => {
                      setSelectedEndpointId(ep.id);
                      setTestResult(null);
                      setResponseStatus(null);
                      setMobileTab('docs');
                    }}
                    className={`w-full text-left py-2 px-2.5 rounded-lg flex items-center gap-2 transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-[#E0F2FE] text-[#0284C7] font-bold shadow-xs'
                        : 'text-text-secondary hover:bg-slate-50'
                    }`}
                  >
                    <span
                      className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded shrink-0 ${
                        isGet
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-teal-100 text-teal-800'
                      }`}
                    >
                      {ep.method}
                    </span>
                    <span className="truncate text-text-primary">{ep.path}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Status Codes Legend */}
          <div className="pt-2 border-t border-[#F1F5F9] space-y-1.5">
            <div className="text-[10px] font-bold text-text-muted tracking-wider uppercase">
              КОДЫ ОШИБОК
            </div>
            <div className="space-y-1 text-[11px] text-text-secondary">
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-emerald-600">200</span>
                <span>Успешный ответ</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-amber-600">400</span>
                <span>Некорректный запрос</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-rose-600">404</span>
                <span>Ресурс не найден</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-rose-600">500</span>
                <span>Ошибка ML-пайплайна</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Center Column: Selected Endpoint Specification */}
        <main
          className={`overflow-y-auto p-4 sm:p-6 md:p-8 space-y-6 ${
            mobileTab === 'docs' ? 'flex-1 block' : 'hidden xl:block xl:flex-1'
          }`}
        >
          {/* Mobile Quick Dropdown */}
          <div className="xl:hidden pb-3 border-b border-[#EAECF0]">
            <label className="text-[11px] font-bold text-text-muted uppercase tracking-wider block mb-1">
              Выберите эндпоинт:
            </label>
            <select
              value={selectedEndpointId}
              onChange={(e) => {
                setSelectedEndpointId(e.target.value);
                setTestResult(null);
                setResponseStatus(null);
              }}
              className="w-full bg-white border border-[#EAECF0] rounded-lg px-3 py-2 text-xs font-mono font-medium text-text-primary focus:outline-none focus:border-[#0EA5E9]"
            >
              {ENDPOINTS.map((ep) => (
                <option key={ep.id} value={ep.id}>
                  {ep.method} {ep.path} — {ep.title}
                </option>
              ))}
            </select>
          </div>

          {/* Breadcrumb */}
          <div className="text-xs text-text-muted flex items-center gap-1.5 font-mono">
            <span>api</span>
            <span>/</span>
            <span>v1</span>
            <span>/</span>
            <span className="text-text-primary font-semibold">{currentEndpoint.id}</span>
          </div>

          {/* Endpoint Title & Badge */}
          <div className="flex items-center gap-3">
            <span
              className={`px-3 py-1 rounded-md font-bold text-xs font-mono tracking-wide ${
                currentEndpoint.method === 'GET'
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-teal-100 text-teal-800'
              }`}
            >
              {currentEndpoint.method}
            </span>
            <h1 className="text-2xl font-bold font-mono text-text-primary">
              {currentEndpoint.path}
            </h1>
          </div>

          <div className="text-sm font-semibold text-text-primary">
            {currentEndpoint.title}
          </div>

          <p className="text-xs md:text-sm text-text-secondary leading-relaxed">
            {currentEndpoint.description}
          </p>

          {/* Parameters Table (if any) */}
          {currentEndpoint.params && currentEndpoint.params.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-bold text-text-primary">
                Параметры запроса
              </div>
              <div className="border border-[#EAECF0] rounded-xl overflow-hidden bg-white">
                <table className="w-full text-xs text-left">
                  <thead className="border-b border-[#EAECF0] bg-[#F8FAFC] text-text-muted">
                    <tr>
                      <th className="py-2.5 px-4 font-semibold">Имя</th>
                      <th className="py-2.5 px-4 font-semibold">Тип</th>
                      <th className="py-2.5 px-4 font-semibold">Обязательный</th>
                      <th className="py-2.5 px-4 font-semibold">Описание</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F1F5F9]">
                    {currentEndpoint.params.map((p) => (
                      <tr key={p.name}>
                        <td className="py-2.5 px-4 font-mono font-semibold text-[#0EA5E9]">
                          {p.name}
                        </td>
                        <td className="py-2.5 px-4 font-mono text-text-secondary">{p.type}</td>
                        <td className="py-2.5 px-4">
                          {p.required ? (
                            <span className="text-rose-600 font-semibold">Да</span>
                          ) : (
                            <span className="text-text-muted">Нет</span>
                          )}
                        </td>
                        <td className="py-2.5 px-4 text-text-secondary">{p.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Request Body preview (if POST) */}
          {currentEndpoint.requestBody && (
            <div className="space-y-2">
              <div className="text-xs font-bold text-text-primary">
                Тело запроса (JSON payload)
              </div>
              <div className="border border-[#EAECF0] rounded-xl overflow-hidden bg-white">
                <div className="bg-[#F8FAFC] px-4 py-2 border-b border-[#EAECF0] flex items-center justify-between text-xs text-text-muted">
                  <span className="font-mono text-[11px]">application/json</span>
                  <button
                    onClick={() => handleCopy(currentEndpoint.requestBody || '', 'body_spec')}
                    className="flex items-center gap-1 text-[11px] text-text-secondary hover:text-text-primary cursor-pointer"
                  >
                    {copiedKey === 'body_spec' ? (
                      <Check className="w-3 h-3 text-emerald-600" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                    <span>{copiedKey === 'body_spec' ? 'Скопировано' : 'Копировать'}</span>
                  </button>
                </div>
                <pre className="p-4 text-xs font-mono text-text-primary overflow-x-auto bg-slate-50/50">
                  {currentEndpoint.requestBody}
                </pre>
              </div>
            </div>
          )}

          {/* Response 200 */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-text-primary">Ответ</span>
              <span className="bg-emerald-100 text-emerald-800 text-[11px] font-bold px-2 py-0.5 rounded">
                200 OK
              </span>
            </div>
            <div className="border border-[#EAECF0] rounded-xl overflow-hidden bg-white">
              <div className="bg-[#F8FAFC] px-4 py-2 border-b border-[#EAECF0] flex items-center justify-between text-xs text-text-muted">
                <span className="font-mono text-[11px]">application/json</span>
                <button
                  onClick={() => handleCopy(currentEndpoint.responseExample, 'resp_spec')}
                  className="flex items-center gap-1 text-[11px] text-text-secondary hover:text-text-primary cursor-pointer"
                >
                  {copiedKey === 'resp_spec' ? (
                    <Check className="w-3 h-3 text-emerald-600" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                  <span>{copiedKey === 'resp_spec' ? 'Скопировано' : 'Копировать'}</span>
                </button>
              </div>
              <pre className="p-4 text-xs font-mono text-text-primary overflow-x-auto bg-slate-50/50">
                {currentEndpoint.responseExample}
              </pre>
            </div>
          </div>

          {/* Error Codes Table */}
          {currentEndpoint.errorCodes && currentEndpoint.errorCodes.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-bold text-text-primary">
                Коды ошибок
              </div>
              <div className="border border-[#EAECF0] rounded-xl overflow-hidden bg-white">
                <table className="w-full text-xs text-left">
                  <thead className="border-b border-[#EAECF0] bg-[#F8FAFC] text-text-muted">
                    <tr>
                      <th className="py-2.5 px-4 font-semibold w-24">Код</th>
                      <th className="py-2.5 px-4 font-semibold">Описание</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F1F5F9]">
                    {currentEndpoint.errorCodes.map((err) => (
                      <tr key={err.code}>
                        <td className="py-2.5 px-4 font-mono font-semibold text-rose-600">
                          {err.code}
                        </td>
                        <td className="py-2.5 px-4 text-text-secondary">{err.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Dynamic cURL Example (Light Theme) */}
          <div className="space-y-2">
            <div className="text-xs font-bold text-text-primary flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-text-muted" />
              <span>cURL-пример</span>
            </div>
            <div className="border border-[#EAECF0] rounded-xl overflow-hidden bg-white shadow-2xs">
              <div className="bg-[#F8FAFC] px-4 py-2 border-b border-[#EAECF0] flex items-center justify-between text-xs text-text-muted">
                <span className="font-mono text-[11px] font-semibold text-text-secondary">bash</span>
                <button
                  onClick={() =>
                    handleCopy(
                      currentEndpoint.curlTemplate(paramValues, postBodyText),
                      'curl'
                    )
                  }
                  className="flex items-center gap-1 text-[11px] text-text-secondary hover:text-text-primary cursor-pointer transition-colors"
                >
                  {copiedKey === 'curl' ? (
                    <Check className="w-3 h-3 text-emerald-600" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                  <span>{copiedKey === 'curl' ? 'Скопировано' : 'Копировать'}</span>
                </button>
              </div>
              <pre className="p-4 text-xs font-mono text-slate-800 bg-[#F8FAFC]/50 overflow-x-auto whitespace-pre-wrap select-text selection:bg-[#E0F2FE]">
                {currentEndpoint.curlTemplate(paramValues, postBodyText)}
              </pre>
            </div>
          </div>
        </main>

        {/* Right Column: "Try it" Live Interactive Tester */}
        <aside
          className={`bg-white border-l border-[#EAECF0] p-4 sm:p-5 flex flex-col space-y-4 shrink-0 overflow-y-auto ${
            mobileTab === 'try' ? 'w-full flex-1' : 'hidden xl:flex xl:w-[420px]'
          }`}
        >
          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-text-primary flex items-center gap-2">
                <Send className="w-4 h-4 text-[#0EA5E9]" />
                <span>Try it ({currentEndpoint.method})</span>
              </h2>
              {responseStatus !== null && (
                <div className="flex items-center gap-1.5 text-xs font-mono">
                  <span
                    className={`px-2 py-0.5 rounded font-bold ${
                      responseStatus >= 200 && responseStatus < 300
                        ? 'bg-emerald-100 text-emerald-800'
                        : responseStatus === 0
                        ? 'bg-rose-100 text-rose-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {responseStatus === 0 ? 'ERR' : `${responseStatus}`}
                  </span>
                  {responseTimeMs !== null && (
                    <span className="text-text-muted">{responseTimeMs} ms</span>
                  )}
                </div>
              )}
            </div>
            <div className="text-[11px] text-text-muted mt-0.5">
              Живой запрос к локальному REST API
            </div>
          </div>

          {/* Interactive Inputs for Params */}
          {currentEndpoint.params && currentEndpoint.params.length > 0 && (
            <div className="space-y-3 bg-[#F8FAFC] p-3 rounded-xl border border-[#EAECF0]">
              <div className="text-[11px] font-bold text-text-secondary uppercase tracking-wider">
                Параметры
              </div>
              {currentEndpoint.params.map((param) => (
                <div key={param.name} className="space-y-1">
                  <label className="text-xs font-medium text-text-primary flex items-center justify-between">
                    <span className="font-mono text-[#0EA5E9]">{param.name}</span>
                    <span className="text-[10px] text-text-muted">{param.description}</span>
                  </label>
                  {param.options ? (
                    <select
                      value={paramValues[param.name] || param.default || ''}
                      onChange={(e) => handleParamChange(param.name, e.target.value)}
                      className="w-full bg-white border border-[#EAECF0] rounded-lg px-2.5 py-1.5 text-xs font-mono text-text-primary focus:outline-none focus:border-[#0EA5E9] cursor-pointer"
                    >
                      {param.options.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={paramValues[param.name] || ''}
                      onChange={(e) => handleParamChange(param.name, e.target.value)}
                      className="w-full bg-white border border-[#EAECF0] rounded-lg px-2.5 py-1.5 text-xs font-mono text-text-primary focus:outline-none focus:border-[#0EA5E9]"
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {/* POST Request Body Editor */}
          {currentEndpoint.method === 'POST' && (
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-secondary flex items-center justify-between">
                <span>Тело запроса (JSON)</span>
                <span className="text-[10px] text-text-muted font-mono">raw body</span>
              </label>
              <textarea
                rows={4}
                value={postBodyText}
                onChange={(e) => setPostBodyText(e.target.value)}
                className="w-full bg-[#F8FAFC] border border-[#EAECF0] rounded-lg p-2.5 text-xs font-mono text-text-primary focus:bg-white focus:outline-none focus:border-[#0EA5E9]"
              />
            </div>
          )}

          {/* Send Button */}
          <button
            onClick={handleRunLiveRequest}
            disabled={isLoadingTest}
            className="w-full bg-[#0EA5E9] hover:bg-[#0284C7] text-white text-xs font-semibold py-2.5 rounded-xl transition-all shadow-xs flex items-center justify-center gap-2 disabled:opacity-75 cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
            <span>
              {isLoadingTest
                ? 'Отправка...'
                : `Отправить запрос`}
            </span>
          </button>

          {/* Result Output */}
          <div className="flex-1 flex flex-col space-y-1.5 min-h-[220px]">
            <div className="flex items-center justify-between text-xs font-bold text-text-primary">
              <span>Результат</span>
              {testResult && (
                <button
                  onClick={() => handleCopy(testResult, 'res_box')}
                  className="flex items-center gap-1 text-[11px] font-normal text-text-muted hover:text-text-primary cursor-pointer"
                >
                  {copiedKey === 'res_box' ? (
                    <Check className="w-3 h-3 text-emerald-600" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                  <span>{copiedKey === 'res_box' ? 'Скопировано' : 'Копировать'}</span>
                </button>
              )}
            </div>

            <div className="border border-[#EAECF0] rounded-xl overflow-hidden bg-[#FAFBFC] flex-1 flex flex-col">
              <div className="bg-[#F1F5F9] px-3 py-1.5 border-b border-[#EAECF0] flex items-center justify-between text-xs text-text-muted font-mono text-[11px]">
                <span>{currentEndpoint.buildUrl(paramValues)}</span>
              </div>
              <pre className="p-3 text-[11px] font-mono text-text-primary overflow-auto flex-1 max-h-[350px] whitespace-pre-wrap select-text">
                {testResult || 'Нажмите «Отправить запрос» для получения ответа от сервера.'}
              </pre>
            </div>

            <div className="p-3 bg-[#F8FAFC] border border-[#EAECF0] rounded-xl flex items-start gap-2.5 text-xs text-text-secondary">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
              <p className="text-[11px] leading-relaxed">
                Живой интерактивный стенд. Запросы отправляются к действующему FastAPI бэкенду.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};
