"""Hydrological station gauge reference data for Amur Basin (Rosgidromet / Amur CGMS).

Includes reference water levels, critical thresholds (NPU / Normal Pool Level, OYA / Hazardous Phenomenon Level),
and historical peak observations for HydroWatch Amur events.
"""

from __future__ import annotations

from typing import Any

# Hydrological stations database for key observation posts in the Amur Basin
HYDROLOGICAL_GAUGES: dict[str, dict[str, Any]] = {
    "blagoveshchensk": {
        "station_id": "08001",
        "station_name": "Благовещенск",
        "river": "Амур / Зея",
        "basin": "Амурский",
        "coordinates": {"lat": 50.27, "lon": 127.53},
        "zero_altitude_bs77_m": 120.40,
        "critical_levels_cm": {
            "npu": 600,  # Выход на пойму / Нормальный подпорный уровень
            "nya": 700,  # Неблагоприятное явление (НЯ)
            "oya": 800,  # Опасное явление (ОЯ)
            "historic_max": 895,  # 1958 год
        },
        "event_levels_cm": {
            "baseline_2018_09_low": 240,  # Межень сентября 2018
            "flood_2019_07_amur": 745,  # Июль 2019
            "flood_2021_06_amur": 839,  # 26 июня 2021 (> ОЯ 800 см)
            "flood_2021_08_zeya": 718,  # Август 2021
            "flood_2022_08_amur": 620,  # Август 2022
            "flood_2026_08_amur": 790,  # Август 2026
        },
        "description": "Гидропост на слиянии Амура и Зеи. Контроль наводнений г. Благовещенск.",
    },
    "svobodny": {
        "station_id": "08015",
        "station_name": "Свободный",
        "river": "Зея",
        "basin": "Зейский",
        "coordinates": {"lat": 51.38, "lon": 128.14},
        "zero_altitude_bs77_m": 146.50,
        "critical_levels_cm": {
            "npu": 550,  # Выход на пойму
            "nya": 650,  # НЯ
            "oya": 750,  # ОЯ
            "historic_max": 870,  # 2013 год
        },
        "event_levels_cm": {
            "baseline_2018_09_low": 280,  # Межень 2018
            "flood_2019_07_amur": 680,  # Июль 2019
            "flood_2021_06_amur": 690,  # Июнь 2021
            "flood_2021_08_zeya": 810,  # Август 2021 (> ОЯ 750 см)
            "flood_2022_08_amur": 610,  # Август 2022
            "flood_2026_08_amur": 720,  # Август 2026
        },
        "description": "Гидропост в среднем течении р. Зея ниже Зейского водохранилища.",
    },
    "belogorsk": {
        "station_id": "08032",
        "station_name": "Белогорск",
        "river": "Томь",
        "basin": "Зейский",
        "coordinates": {"lat": 50.92, "lon": 128.47},
        "zero_altitude_bs77_m": 152.10,
        "critical_levels_cm": {
            "npu": 300,  # Выход на пойму
            "nya": 350,  # НЯ
            "oya": 400,  # ОЯ
            "historic_max": 515,  # Июль 2019
        },
        "event_levels_cm": {
            "baseline_2018_09_low": 120,  # Межень 2018
            "flood_2019_07_amur": 515,  # 31 июля 2019 (> ОЯ 400 см, исторический рекорд)
            "flood_2021_06_amur": 330,  # Июнь 2021
            "flood_2021_08_zeya": 380,  # Август 2021 (> НЯ)
            "flood_2022_08_amur": 290,  # Август 2022
            "flood_2026_08_amur": 370,  # Август 2026
        },
        "description": "Гидропост на р. Томь (левый приток Зеи). Подвержен быстрым дождевым паводкам.",
    },
    "poyarkovo": {
        "station_id": "08044",
        "station_name": "Поярково",
        "river": "Амур",
        "basin": "Амурский",
        "coordinates": {"lat": 49.63, "lon": 128.65},
        "zero_altitude_bs77_m": 105.80,
        "critical_levels_cm": {
            "npu": 650,  # Выход на пойму
            "nya": 750,  # НЯ
            "oya": 850,  # ОЯ
            "historic_max": 935,  # 2013 год
        },
        "event_levels_cm": {
            "baseline_2018_09_low": 310,  # Межень 2018
            "flood_2019_07_amur": 710,  # Июль 2019
            "flood_2021_06_amur": 875,  # Июнь-июль 2021 (> ОЯ 850 см)
            "flood_2021_08_zeya": 760,  # Август 2021 (> НЯ)
            "flood_2022_08_amur": 640,  # Август 2022
            "flood_2026_08_amur": 820,  # Август 2026
        },
        "description": "Гидропост в нижнем течении среднего Амура (Михайловский район).",
    },
    "konstantinovka": {
        "station_id": "08038",
        "station_name": "Константиновка",
        "river": "Амур",
        "basin": "Амурский",
        "coordinates": {"lat": 49.62, "lon": 127.99},
        "zero_altitude_bs77_m": 112.30,
        "critical_levels_cm": {
            "npu": 630,  # Выход на пойму
            "nya": 730,  # НЯ
            "oya": 830,  # ОЯ
            "historic_max": 912,  # 2013 год
        },
        "event_levels_cm": {
            "baseline_2018_09_low": 290,
            "flood_2019_07_amur": 725,
            "flood_2021_06_amur": 860,
            "flood_2021_08_zeya": 740,
            "flood_2022_08_amur": 630,
            "flood_2026_08_amur": 805,
        },
        "description": "Гидропост в пойменной части Амура (Константиновский район).",
    },
}


def get_gauge_for_aoi(aoi_id: str) -> dict[str, Any] | None:
    """Retrieve hydrological station information for a given AOI identifier."""
    return HYDROLOGICAL_GAUGES.get(aoi_id.lower().strip())


def get_gauge_status(aoi_id: str, event_id: str) -> dict[str, Any] | None:
    """Assess gauge stage relative to critical thresholds (NPU / OYA) for an event."""
    gauge = get_gauge_for_aoi(aoi_id)
    if not gauge:
        return None

    level_cm = gauge["event_levels_cm"].get(event_id)
    if level_cm is None:
        return None

    crit = gauge["critical_levels_cm"]
    npu_cm = crit["npu"]
    nya_cm = crit["nya"]
    oya_cm = crit["oya"]

    if level_cm >= oya_cm:
        risk_level = "danger_oya"  # Превышение отметки ОЯ (Опасное явление)
    elif level_cm >= nya_cm:
        risk_level = "warning_nya"  # Превышение отметки НЯ (Неблагоприятное явление)
    elif level_cm >= npu_cm:
        risk_level = "floodplain_npu"  # Выход воды на пойму (НПУ)
    else:
        risk_level = "normal"  # Норма / межень

    return {
        "station_id": gauge["station_id"],
        "station_name": gauge["station_name"],
        "river": gauge["river"],
        "observed_level_cm": level_cm,
        "npu_cm": npu_cm,
        "nya_cm": nya_cm,
        "oya_cm": oya_cm,
        "exceeds_npu": bool(level_cm >= npu_cm),
        "exceeds_oya": bool(level_cm >= oya_cm),
        "stage_risk": risk_level,
    }
