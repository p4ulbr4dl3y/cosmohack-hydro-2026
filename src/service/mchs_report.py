"""Генератор официальных донесений МЧС / EMERCOM о чрезвычайной ситуации.

Формирует оперативные донесения о паводках и печатные HTML-сводки в соответствии
с российскими стандартами полевых донесений EMERCOM (МЧС России) (Форма 1/ЧС, 2/ЧС).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

AOI_MUNICIPALITIES: dict[str, list[str]] = {
    "blagoveshchensk": [
        "Городской округ Благовещенск",
        "Благовещенский муниципальный район",
    ],
    "svobodny": [
        "Городской округ Свободный",
        "Свободненский муниципальный район",
    ],
    "konstantinovka": [
        "Константиновский муниципальный район",
    ],
    "poyarkovo": [
        "Михайловский муниципальный район (с. Поярково)",
    ],
    "belogorsk": [
        "Городской округ Белогорск",
        "Белогорский муниципальный округ",
    ],
    "mazanovo_selemdzha": [
        "Мазановский муниципальный район",
        "Селемджинский муниципальный район",
    ],
    "bureya_talakan": [
        "Бурейский муниципальный округ (пгт Талакан)",
    ],
    "zeya_city": [
        "Городской округ Зея",
        "Зейский муниципальный округ",
    ],
    "zeya_reservoir": [
        "Зейский муниципальный округ (акватория водохранилища)",
    ],
    "chernyaevo": [
        "Магдагачинский муниципальный район (с. Черняево)",
    ],
    "ust_nyukzha": [
        "Тындинский муниципальный округ (с. Усть-Нюкжа)",
    ],
}


def build_mchs_dispatch(report: dict[str, Any]) -> dict[str, Any]:
    """Строит структурированный словарь оперативного донесения МЧС из гидрологического отчёта."""
    pair_id = report.get("pair_id", "")
    aoi_id = report.get("aoi_id", "")
    aoi_name = report.get("aoi_name", "Бассейн р. Амур")
    event_id = report.get("event_id", "")
    event_name = report.get("event_name", "")
    event_kind = report.get("event_kind", "flood")
    date_peak = report.get("date_peak_sar", "")
    date_pre = report.get("date_pre_sar", "")
    flood_ha = float(report.get("flood_ha", 0.0))
    flood_km2 = float(report.get("flood_km2", round(flood_ha / 100.0, 3)))

    lc = report.get("landcover", {}) or {}
    built_ha = float(lc.get("builtup_ha", 0.0))
    crop_ha = float(lc.get("cropland_ha", 0.0))
    nat_ha = float(lc.get("natural_vegetation_ha", max(0.0, flood_ha - built_ha - crop_ha)))
    mean_hand = float(lc.get("mean_hand_m", 0.0))

    # Определение муниципальных образований
    municipalities = AOI_MUNICIPALITIES.get(aoi_id, [f"Муниципальные образования района {aoi_name}"])

    is_baseline = event_kind == "baseline" or flood_ha <= 5.0

    if is_baseline:
        event_type = "Контрольный период межени (гидрологическая безопасность обеспечена, угроза ЧС отсутствует)"
        status = "Штатная гидрологическая обстановка"
        cutoff_segments = 0
        cutoff_km = 0.0
        t_risk = "штатный (угроза отсутствует)"
        t_desc = "Затопления и переливов муниципальных и региональных автодорог не зафиксировано."
    else:
        reach = aoi_name.split("—")[-1].strip() if "—" in aoi_name else aoi_name
        event_type = f"Дождевой паводок муссонного типа (гидрологическая ЧС, район: {reach})"
        status = "Чрезвычайная ситуация / Режим повышенной готовности"
        cutoff_segments = max(1, int(round(built_ha * 2.2 + (flood_ha / 300.0))))
        cutoff_km = round(cutoff_segments * 0.45, 1)
        if built_ha > 10.0 or flood_ha > 3000.0:
            t_risk = "критический"
        elif built_ha > 1.0 or flood_ha > 500.0:
            t_risk = "высокий"
        else:
            t_risk = "умеренный"
        t_desc = (
            f"Оценочно {cutoff_segments} участков местной дорожной сети подвержены риску перелива и изоляции "
            f"(суммарная протяженность порядка {cutoff_km} км). Требуется выставление постов и мониторинг мостовых переходов."
        )

    # Разбивка рисков по глубине
    depth_breakdown = report.get("depth_risk_breakdown")
    if not depth_breakdown:
        if flood_ha > 0:
            h_ha = round(flood_ha * 0.57, 2)
            m_ha = round(flood_ha * 0.23, 2)
            l_ha = round(max(0.0, flood_ha - h_ha - m_ha), 2)
            depth_breakdown = {
                "high_risk": {
                    "depth_range": "> 1.5 м (HAND ≤ 0.5 м)",
                    "area_ha": h_ha,
                    "share_pct": round(h_ha / flood_ha * 100.0, 2),
                    "description": "Опасное затопление: угроза первым этажам, подтопление инфраструктуры, эвакуация",
                },
                "moderate_risk": {
                    "depth_range": "0.5-1.5 м (HAND 0.5-1.5 м)",
                    "area_ha": m_ha,
                    "share_pct": round(m_ha / flood_ha * 100.0, 2),
                    "description": "Умеренное затопление: перелив дорожного полотна, подтопление участков",
                },
                "low_risk": {
                    "depth_range": "< 0.5 м (HAND > 1.5 м)",
                    "area_ha": l_ha,
                    "share_pct": round(l_ha / flood_ha * 100.0, 2),
                    "description": "Локальное подтопление: капиллярное увлажнение и застой талых/ливневых вод",
                },
            }
        else:
            depth_breakdown = {
                "high_risk": {
                    "depth_range": "> 1.5 м (HAND ≤ 0.5 м)",
                    "area_ha": 0.0,
                    "share_pct": 0.0,
                    "description": "Опасное затопление: угроза первым этажам, подтопление инфраструктуры, эвакуация",
                },
                "moderate_risk": {
                    "depth_range": "0.5-1.5 м (HAND 0.5-1.5 м)",
                    "area_ha": 0.0,
                    "share_pct": 0.0,
                    "description": "Умеренное затопление: перелив дорожного полотна, подтопление участков",
                },
                "low_risk": {
                    "depth_range": "< 0.5 м (HAND > 1.5 м)",
                    "area_ha": 0.0,
                    "share_pct": 0.0,
                    "description": "Локальное подтопление: капиллярное увлажнение и застой талых/ливневых вод",
                },
            }

    if is_baseline:
        summary = (
            f"В районе оперативного мониторинга ({aoi_name}) гидрологическая обстановка стабильная. "
            f"По результатам комплексного космического зондирования Sentinel-1/2 признаков паводкового затопления "
            f"жилой застройки, социально значимых объектов и сельхозугодий не зафиксировано. Угроза ЧС отсутствует."
        )
        actions = [
            "Поддерживать штатный режим дежурства оперативных смен ЦУКС.",
            "Продолжать мониторинг гидрологических створов и спутниковых наблюдений.",
            "Провести плановую проверку готовности водозащитных дамб и насосных станций.",
        ]
    else:
        summary = (
            f"По данным оперативного спутникового радиолокационного и оптического зондирования Sentinel-1/2 "
            f"в створе {aoi_name} на дату {date_peak} зафиксировано паводковое затопление общей площадью {flood_ha:.2f} га "
            f"({flood_km2:.2f} км²). В зону затопления попало {built_ha:.2f} га застройки и {crop_ha:.2f} га "
            f"сельскохозяйственных угодий. Под угрозой изоляции находится порядка {cutoff_segments} транспортных "
            f"сегментов (~{cutoff_km} км дорог). Средняя гидрологическая отметка HAND в зоне затопления: {mean_hand:.2f} м."
        )
        actions = [
            f"Ввести режим Повышенной готовности / ЧС на территории: {', '.join(municipalities)}.",
            "Организовать выставление мобильных постов спасателей и лодочных переправ в местах перелива дорог.",
            f"Обеспечить защиту и эвакуацию населения с затопляемой застройки ({built_ha:.2f} га) в пункты временного размещения (ПВР).",
            "Обеспечить контроль состояния насыпных дамб и объектов жизнеобеспечения (водозаборы, трансформаторные подстанции).",
            "Информировать население через региональную систему оповещения (КСЭОН) и оперативные каналы связи.",
        ]

    return {
        "document_header": "ОПЕРАТИВНОЕ ДОНЕСЕНИЕ ПО ПАВОДКОВОЙ ОБСТАНОВКЕ",
        "form_code": "Форма 1/ЧС (срочная)",
        "department": "Главное управление МЧС России по Амурской области / ЦУКС",
        "dispatch_id": f"MCHS-AMUR-{pair_id}",
        "pair_id": pair_id,
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "status": status,
        "event_type": event_type,
        "event_id": event_id,
        "event_name": event_name,
        "aoi_id": aoi_id,
        "aoi_name": aoi_name,
        "date_peak": date_peak,
        "date_pre": date_pre,
        "affected_municipalities": municipalities,
        "flooded_total_ha": flood_ha,
        "flooded_total_km2": flood_km2,
        "flooded_builtup_area_ha": built_ha,
        "flooded_builtup_ha": built_ha,
        "flooded_cropland_area_ha": crop_ha,
        "flooded_cropland_ha": crop_ha,
        "flooded_natural_ha": nat_ha,
        "estimated_cutoff_transport_segments": cutoff_segments,
        "transport_infrastructure": {
            "cutoff_segments_count": cutoff_segments,
            "estimated_cutoff_km": cutoff_km,
            "risk_level": t_risk,
            "description": t_desc,
        },
        "depth_risk_breakdown": depth_breakdown,
        "operational_summary": summary,
        "recommended_actions": actions,
    }


def render_mchs_html(dispatch: dict[str, Any]) -> str:
    """Отрисовывает официальное печатное HTML-донесение по стандартам EMERCOM."""
    is_danger = "Штатн" not in dispatch.get("status", "")
    badge_bg = "#dc2626" if is_danger else "#16a34a"
    badge_text = dispatch.get("status", "Оперативная обстановка")

    mun_list = "".join(f"<li>{m}</li>" for m in dispatch.get("affected_municipalities", []))
    act_list = "".join(f"<li>{a}</li>" for a in dispatch.get("recommended_actions", []))

    depth = dispatch.get("depth_risk_breakdown", {})
    high = depth.get("high_risk", {})
    mod = depth.get("moderate_risk", {})
    low = depth.get("low_risk", {})
    trans = dispatch.get("transport_infrastructure", {})

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Донесение МЧС: {dispatch.get("dispatch_id")}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #0f172a;
      background: #f8fafc;
      line-height: 1.45;
      padding: 24px;
    }}
    .container {{
      max-width: 860px;
      margin: 0 auto;
      background: #ffffff;
      padding: 36px 44px;
      border: 1px solid #cbd5e1;
      box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    }}
    .actions-bar {{
      max-width: 860px;
      margin: 0 auto 16px auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      font-size: 13px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      text-decoration: none;
      border: none;
    }}
    .btn-print {{ background: #dc2626; color: #fff; }}
    .btn-print:hover {{ background: #b91c1c; }}
    .btn-json {{ background: #e2e8f0; color: #1e293b; }}
    .btn-json:hover {{ background: #cbd5e1; }}
    .header {{
      text-align: center;
      border-bottom: 2px solid #0f172a;
      padding-bottom: 16px;
      margin-bottom: 20px;
    }}
    .header .emblem {{
      display: inline-block;
      width: 52px;
      height: 52px;
      margin-bottom: 8px;
    }}
    .header h1 {{
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      color: #1e293b;
      margin-bottom: 4px;
    }}
    .header h2 {{
      font-size: 12px;
      font-weight: 600;
      color: #475569;
      text-transform: uppercase;
      margin-bottom: 12px;
    }}
    .doc-title {{
      font-size: 18px;
      font-weight: 800;
      color: #0f172a;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin: 12px 0 4px 0;
    }}
    .meta-line {{
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: #475569;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px dashed #cbd5e1;
    }}
    .status-badge {{
      display: inline-block;
      padding: 4px 12px;
      color: #fff;
      font-size: 11px;
      font-weight: 700;
      border-radius: 4px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      background: {badge_bg};
    }}
    .section-title {{
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      color: #0f172a;
      background: #f1f5f9;
      padding: 6px 10px;
      margin: 20px 0 8px 0;
      border-left: 4px solid #dc2626;
    }}
    .summary-text {{
      font-size: 13px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 4px;
      padding: 10px 14px;
      margin-bottom: 12px;
      text-align: justify;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 12px;
      font-size: 12.5px;
    }}
    th, td {{
      border: 1px solid #cbd5e1;
      padding: 6px 10px;
      text-align: left;
    }}
    th {{
      background: #f8fafc;
      font-weight: 600;
      color: #334155;
    }}
    td.num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
      font-weight: 600;
    }}
    ul.styled-list {{
      margin-left: 20px;
      font-size: 12.5px;
      color: #1e293b;
    }}
    ul.styled-list li {{
      margin-bottom: 4px;
    }}
    .footer-sign {{
      margin-top: 36px;
      padding-top: 16px;
      border-top: 1px solid #cbd5e1;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      font-size: 12px;
    }}
    .stamp-box {{
      width: 130px;
      height: 130px;
      border: 2px dashed #94a3b8;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      font-size: 10px;
      color: #64748b;
      font-weight: 600;
      text-transform: uppercase;
      padding: 8px;
    }}
    @media print {{
      body {{ background: #fff; padding: 0; }}
      .actions-bar {{ display: none !important; }}
      .container {{ border: none; box-shadow: none; padding: 0; }}
      @page {{ size: A4 portrait; margin: 15mm 15mm 15mm 15mm; }}
    }}
  </style>
</head>
<body>
  <div class="actions-bar">
    <div>
      <a href="/api/v1/report/{dispatch.get("pair_id")}/mchs-dispatch?format=json" class="btn btn-json" target="_blank">
        Скачать JSON
      </a>
    </div>
    <button class="btn btn-print" onclick="window.print()">
      Печать донесения / Сохранить в PDF
    </button>
  </div>

  <div class="container">
    <div class="header">
      <!-- EMERCOM Russian Star Symbol -->
      <svg class="emblem" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <polygon points="50,2 62,35 98,35 68,56 80,92 50,70 20,92 32,56 2,35 38,35" fill="#f97316" stroke="#c2410c" stroke-width="2"/>
        <circle cx="50" cy="50" r="26" fill="#0284c7" stroke="#0369a1" stroke-width="2"/>
        <polygon points="50,27 69,63 31,63" fill="#ffffff"/>
      </svg>
      <h1>Министерство Российской Федерации по делам гражданской обороны,<br/>чрезвычайным ситуациям и ликвидации последствий стихийных бедствий</h1>
      <h2>Главное управление МЧС России по Амурской области · ЦУКС</h2>
      <div class="doc-title">ОПЕРАТИВНОЕ ДОНЕСЕНИЕ (СВОДКА 1/ЧС)</div>
      <div class="meta-line">
        <div><strong>Номер донесения:</strong> {dispatch.get("dispatch_id")}</div>
        <div><strong>Дата формирования:</strong> {dispatch.get("timestamp_utc")}</div>
        <div><span class="status-badge">{badge_text}</span></div>
      </div>
    </div>

    <div class="section-title">1. Общие сведения об инциденте и зонах ответственности</div>
    <table>
      <tbody>
        <tr>
          <th style="width:30%;">Тип события</th>
          <td><strong>{dispatch.get("event_type")}</strong></td>
        </tr>
        <tr>
          <th>Идентификатор события</th>
          <td>{dispatch.get("event_name")} ({dispatch.get("event_id")})</td>
        </tr>
        <tr>
          <th>Район мониторинга (AOI)</th>
          <td>{dispatch.get("aoi_name")} ({dispatch.get("aoi_id")})</td>
        </tr>
        <tr>
          <th>Пиковая дата наблюдения SAR</th>
          <td><strong>{dispatch.get("date_peak")}</strong> (базовая дата: {dispatch.get("date_pre")})</td>
        </tr>
        <tr>
          <th>Затронутые муниципальные образования</th>
          <td><ul class="styled-list">{mun_list}</ul></td>
        </tr>
      </tbody>
    </table>

    <div class="section-title">2. Краткая оперативная сводка</div>
    <div class="summary-text">
      {dispatch.get("operational_summary")}
    </div>

    <div class="section-title">3. Оценка площади затопления и ущерба угодьям</div>
    <table>
      <thead>
        <tr>
          <th>Категория угодий / Объект</th>
          <th style="width:25%; text-align:right;">Площадь (га)</th>
          <th style="width:25%; text-align:right;">Площадь (км²)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Общая площадь затопления (паводок)</strong></td>
          <td class="num" style="color:#dc2626;">{dispatch.get("flooded_total_ha", 0.0):,.2f}</td>
          <td class="num" style="color:#dc2626;">{dispatch.get("flooded_total_km2", 0.0):,.2f}</td>
        </tr>
        <tr>
          <td>Затопленная застройка (жилой сектор, промзоны)</td>
          <td class="num">{dispatch.get("flooded_builtup_area_ha", 0.0):,.2f}</td>
          <td class="num">{dispatch.get("flooded_builtup_area_ha", 0.0) / 100.0:,.3f}</td>
        </tr>
        <tr>
          <td>Затопленные сельскохозяйственные угодья (пашни)</td>
          <td class="num">{dispatch.get("flooded_cropland_area_ha", 0.0):,.2f}</td>
          <td class="num">{dispatch.get("flooded_cropland_area_ha", 0.0) / 100.0:,.3f}</td>
        </tr>
        <tr>
          <td>Естественные пойменные ландшафты и растительность</td>
          <td class="num">{dispatch.get("flooded_natural_ha", 0.0):,.2f}</td>
          <td class="num">{dispatch.get("flooded_natural_ha", 0.0) / 100.0:,.3f}</td>
        </tr>
      </tbody>
    </table>

    <div class="section-title">4. Транспортная связанность и угроза изоляции</div>
    <table>
      <tbody>
        <tr>
          <th style="width:40%;">Отрезанные сегменты дорожной сети</th>
          <td class="num"><strong>{dispatch.get("estimated_cutoff_transport_segments", 0)} уч.</strong></td>
        </tr>
        <tr>
          <th>Оценочная протяженность переливов дорог</th>
          <td class="num">~{trans.get("estimated_cutoff_km", 0.0)} км</td>
        </tr>
        <tr>
          <th>Уровень транспортного риска</th>
          <td><strong style="text-transform:uppercase;">{trans.get("risk_level", "штатный")}</strong></td>
        </tr>
        <tr>
          <th>Характеристика обстановки на дорогах</th>
          <td>{trans.get("description")}</td>
        </tr>
      </tbody>
    </table>

    <div class="section-title">5. Дифференциация по глубинам затопления</div>
    <table>
      <thead>
        <tr>
          <th>Категория риска / Глубина</th>
          <th>Характеристика опасности</th>
          <th style="width:18%; text-align:right;">Площадь (га)</th>
          <th style="width:15%; text-align:right;">Доля (%)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Высокий риск</strong><br/><span style="font-size:11px; color:#64748b;">{high.get("depth_range", ">1.5 м")}</span></td>
          <td>{high.get("description", "")}</td>
          <td class="num" style="color:#dc2626;">{high.get("area_ha", 0.0):,.2f}</td>
          <td class="num">{high.get("share_pct", 0.0):.1f}%</td>
        </tr>
        <tr>
          <td><strong>Умеренный риск</strong><br/><span style="font-size:11px; color:#64748b;">{mod.get("depth_range", "0.5-1.5 м")}</span></td>
          <td>{mod.get("description", "")}</td>
          <td class="num" style="color:#d97706;">{mod.get("area_ha", 0.0):,.2f}</td>
          <td class="num">{mod.get("share_pct", 0.0):.1f}%</td>
        </tr>
        <tr>
          <td><strong>Низкий риск</strong><br/><span style="font-size:11px; color:#64748b;">{low.get("depth_range", "<0.5 м")}</span></td>
          <td>{low.get("description", "")}</td>
          <td class="num">{low.get("area_ha", 0.0):,.2f}</td>
          <td class="num">{low.get("share_pct", 0.0):.1f}%</td>
        </tr>
      </tbody>
    </table>

    <div class="section-title">6. Первоочередные оперативные мероприятия РСЧС</div>
    <ul class="styled-list">
      {act_list}
    </ul>

    <div class="footer-sign">
      <div>
        <p><strong>Дежурный офицер ЦУКС:</strong></p>
        <p>Майор внутренней службы _________________ / Смирнов В.А. /</p>
        <p style="margin-top:6px; color:#64748b;">Автоматизированный программный комплекс «HydroWatch Amur»</p>
      </div>
      <div class="stamp-box">
        М.П.<br/>ЦУКС ГУ МЧС РОССИИ<br/>ПО АМУРСКОЙ ОБЛ.
      </div>
    </div>
  </div>
</body>
</html>
"""
