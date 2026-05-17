"""Chart builder tools — query DB and shape data into ChartSpec-ready payloads.

Each tool returns a JSON string with the exact shape that ChartSpec expects,
which in turn maps 1-to-1 with ChartRenderer's chartData prop on the frontend.

Supported chart types: bar | line | pie | doughnut
"""
import json
from crewai.tools import tool
from src.db.pool import query_db


# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------
_BAR_COLORS = [
    "#3b82f6", "#ef4444", "#f59e0b", "#10b981",
    "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16",
]
_PIE_COLORS = [
    "#3b82f6", "#ef4444", "#f59e0b", "#10b981",
    "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16",
    "#f97316", "#14b8a6",
]


def _chart_json(chart_type: str, title: str, labels: list, datasets: list, source_note: str = "") -> str:
    """Return JSON string matching ChartSpec / ChartRenderer contract."""
    payload = {
        "type": chart_type,
        "title": title,
        "data": {"labels": labels, "datasets": datasets},
        "options": {},
        "source_note": source_note,
    }
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool("build_accident_trend_chart")
def build_accident_trend_chart(start_date: str = "", end_date: str = "") -> str:
    """Build a monthly accident trend line chart from the accident summary mart.

    Args:
        start_date: Start date YYYY-MM-DD (optional)
        end_date:   End date   YYYY-MM-DD (optional)

    Returns:
        JSON string matching ChartSpec that can be passed directly to ChartRenderer.
        Chart type: line — axes: month/year vs counts (accidents, injuries, deaths).
    """
    conditions: list[str] = []
    params: list = []

    if start_date:
        y, m = start_date[:4], start_date[5:7]
        conditions.append("(year_no > %s OR (year_no = %s AND month_no >= %s))")
        params.extend([int(y), int(y), int(m)])
    if end_date:
        y, m = end_date[:4], end_date[5:7]
        conditions.append("(year_no < %s OR (year_no = %s AND month_no <= %s))")
        params.extend([int(y), int(y), int(m)])

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT year_no, month_no, accident_count, injured_count, death_count
        FROM mart_accident_summary
        {where}
        ORDER BY year_no, month_no
        LIMIT 36
    """
    try:
        rows = query_db(sql, tuple(params) if params else None)
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if not rows:
        return json.dumps({"error": "ไม่พบข้อมูลสรุปอุบัติเหตุ"})

    labels = [f"{r['year_no']}/{r['month_no']:02d}" for r in rows]
    datasets = [
        {
            "label": "อุบัติเหตุ",
            "data": [r["accident_count"] for r in rows],
            "borderColor": "#3b82f6",
            "backgroundColor": "#3b82f620",
        },
        {
            "label": "บาดเจ็บ",
            "data": [r["injured_count"] for r in rows],
            "borderColor": "#f59e0b",
            "backgroundColor": "#f59e0b20",
        },
        {
            "label": "เสียชีวิต",
            "data": [r["death_count"] for r in rows],
            "borderColor": "#ef4444",
            "backgroundColor": "#ef444420",
        },
    ]

    return _chart_json(
        chart_type="line",
        title="แนวโน้มอุบัติเหตุรายเดือน",
        labels=labels,
        datasets=datasets,
        source_note="mart_accident_summary",
    )


@tool("build_hotspot_bar_chart")
def build_hotspot_bar_chart(top_n: int = 10) -> str:
    """Build a horizontal bar chart of top accident hotspots ranked by score.

    Args:
        top_n: Number of top hotspot locations to include (default 10, max 20)

    Returns:
        JSON string matching ChartSpec for a bar chart:
        X-axis = hotspot rank label, Y-axis = hotspot score.
    """
    top_n = min(int(top_n), 20)
    sql = """
        SELECT hotspot_id, hotspot_score, accident_count, death_count
        FROM mart_accident_hotspot
        ORDER BY hotspot_score DESC
        LIMIT %s
    """
    try:
        rows = query_db(sql, (top_n,))
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if not rows:
        return json.dumps({"error": "ไม่พบข้อมูลจุดเสี่ยง"})

    labels = [f"จุดเสี่ยง #{r['hotspot_id']}" for r in rows]
    datasets = [
        {
            "label": "คะแนนความเสี่ยง",
            "data": [float(r["hotspot_score"] or 0) for r in rows],
            "backgroundColor": _BAR_COLORS[0],
        },
        {
            "label": "จำนวนอุบัติเหตุ",
            "data": [int(r["accident_count"] or 0) for r in rows],
            "backgroundColor": _BAR_COLORS[1],
        },
    ]

    return _chart_json(
        chart_type="bar",
        title=f"Top {top_n} จุดเสี่ยงอุบัติเหตุ",
        labels=labels,
        datasets=datasets,
        source_note="mart_accident_hotspot",
    )


@tool("build_time_distribution_chart")
def build_time_distribution_chart() -> str:
    """Build a bar chart showing accident count by hour of day.

    Returns:
        JSON string matching ChartSpec for a bar chart:
        X-axis = hour (0–23), Y-axis = total accident count.
    """
    sql = """
        SELECT
            EXTRACT(HOUR FROM event_datetime)::int AS hour_of_day,
            COUNT(*) AS accident_count
        FROM fact_accident_event
        GROUP BY hour_of_day
        ORDER BY hour_of_day
    """
    try:
        rows = query_db(sql)
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if not rows:
        return json.dumps({"error": "ไม่พบข้อมูลการกระจายเวลา"})

    hour_map: dict[int, int] = {r["hour_of_day"]: int(r["accident_count"]) for r in rows}
    labels = [f"{h:02d}:00" for h in range(24)]
    data = [hour_map.get(h, 0) for h in range(24)]

    datasets = [
        {
            "label": "จำนวนอุบัติเหตุ",
            "data": data,
            "backgroundColor": _BAR_COLORS[:1] * 24,
        }
    ]

    return _chart_json(
        chart_type="bar",
        title="การกระจายอุบัติเหตุตามชั่วโมงของวัน",
        labels=labels,
        datasets=datasets,
        source_note="fact_accident_event",
    )


@tool("build_road_condition_pie_chart")
def build_road_condition_pie_chart() -> str:
    """Build a pie chart of accident share by accident location type (บริเวณที่เกิดเหตุ).

    Returns:
        JSON string matching ChartSpec for a pie chart:
        slices = accident location categories, values = accident counts.
    """
    sql = """
        SELECT accident_location, COUNT(*) AS accident_count
        FROM fact_accident_event
        WHERE accident_location IS NOT NULL AND accident_location <> ''
        GROUP BY accident_location
        ORDER BY accident_count DESC
        LIMIT 8
    """
    try:
        rows = query_db(sql)
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if not rows:
        return json.dumps({"error": "ไม่พบข้อมูลบริเวณที่เกิดเหตุ"})

    labels = [r["accident_location"] for r in rows]
    data = [int(r["accident_count"]) for r in rows]

    datasets = [
        {
            "label": "อุบัติเหตุ",
            "data": data,
            "backgroundColor": _PIE_COLORS[: len(labels)],
        }
    ]

    return _chart_json(
        chart_type="pie",
        title="สัดส่วนอุบัติเหตุตามบริเวณที่เกิดเหตุ",
        labels=labels,
        datasets=datasets,
        source_note="fact_accident_event",
    )


@tool("build_province_year_trend_chart")
def build_province_year_trend_chart(province: str = "", top_n: int = 10) -> str:
    """Build a line/bar chart showing year-by-year accident trend for one province or top-N provinces.

    Args:
        province: Province name in Thai. Empty = show top-N provinces side-by-side (bar chart).
        top_n:    When province is empty, how many top provinces to show (default 10).

    Returns:
        JSON string matching ChartSpec for ChartRenderer.
        Single province → line chart (x=year, y=accidents/deaths).
        Multi-province  → bar chart (x=province, grouped by year or summed).
    """
    if province:
        sql = """
            SELECT year_no, accident_count, injured_count, serious_injured, death_count
            FROM mart_province_year
            WHERE province_name ILIKE %s
            ORDER BY year_no
        """
        try:
            rows = query_db(sql, (f"%{province}%",))
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        if not rows:
            return json.dumps({"error": f"ไม่พบข้อมูลจังหวัด {province}"})

        labels = [str(r["year_no"]) for r in rows]
        datasets = [
            {"label": "อุบัติเหตุ", "data": [r["accident_count"] for r in rows], "borderColor": "#3b82f6", "backgroundColor": "#3b82f620"},
            {"label": "บาดเจ็บสาหัส", "data": [r.get("serious_injured", 0) or 0 for r in rows], "borderColor": "#f59e0b", "backgroundColor": "#f59e0b20"},
            {"label": "เสียชีวิต", "data": [r["death_count"] for r in rows], "borderColor": "#ef4444", "backgroundColor": "#ef444420"},
        ]
        return _chart_json("line", f"แนวโน้มอุบัติเหตุจังหวัด{province} รายปี", labels, datasets, "mart_province_year")
    else:
        sql = """
            SELECT province_name,
                   SUM(accident_count) AS acc,
                   SUM(death_count)    AS dth
            FROM mart_province_year
            GROUP BY province_name
            ORDER BY acc DESC
            LIMIT %s
        """
        try:
            rows = query_db(sql, (top_n,))
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        if not rows:
            return json.dumps({"error": "ไม่พบข้อมูลจังหวัด"})

        labels = [r["province_name"] for r in rows]
        datasets = [
            {"label": "อุบัติเหตุรวม", "data": [int(r["acc"]) for r in rows], "backgroundColor": _BAR_COLORS[0]},
            {"label": "เสียชีวิตรวม", "data": [int(r["dth"]) for r in rows], "backgroundColor": _BAR_COLORS[2]},
        ]
        return _chart_json("bar", f"Top {top_n} จังหวัดที่มีอุบัติเหตุสูงสุด (ทุกปี)", labels, datasets, "mart_province_year")


@tool("build_province_roads_bar_chart")
def build_province_roads_bar_chart(province: str, year: int = 0, top_n: int = 10) -> str:
    """Build a bar chart of top dangerous roads in a province.

    Args:
        province: Province name in Thai (required).
        year:     Year CE 2020-2026, or 0 for all years.
        top_n:    Number of roads to show (default 10).

    Returns:
        JSON string matching ChartSpec for a bar chart:
        X-axis = road name, Y-axis = accident count + deaths.
    """
    if not province:
        return json.dumps({"error": "ต้องระบุชื่อจังหวัด"})

    year_clause = "AND year_no = %s" if year else ""
    params: list = [f"%{province}%"]
    if year:
        params.append(year)
    params.append(min(int(top_n), 20))

    sql = f"""
        SELECT road_name, road_code,
               SUM(accident_count) AS acc,
               SUM(serious_injured) AS ser,
               SUM(death_count)    AS dth
        FROM mart_province_road
        WHERE province_name ILIKE %s
          {year_clause}
        GROUP BY road_name, road_code
        ORDER BY acc DESC
        LIMIT %s
    """
    try:
        rows = query_db(sql, tuple(params))
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if not rows:
        return json.dumps({"error": f"ไม่พบข้อมูลถนนในจังหวัด {province}"})

    labels = [f"[{r['road_code'] or 'N/A'}] {r['road_name'][:30]}" for r in rows]
    datasets = [
        {"label": "อุบัติเหตุ", "data": [int(r["acc"]) for r in rows], "backgroundColor": _BAR_COLORS[0]},
        {"label": "บาดเจ็บสาหัส", "data": [int(r.get("ser", 0) or 0) for r in rows], "backgroundColor": _BAR_COLORS[2]},
        {"label": "เสียชีวิต", "data": [int(r["dth"]) for r in rows], "backgroundColor": _BAR_COLORS[1]},
    ]
    yr_label = f" ปี {year}" if year else " (ทุกปี)"
    return _chart_json("bar", f"ถนนเสี่ยงสูงจังหวัด{province}{yr_label}", labels, datasets, "mart_province_road")


@tool("build_monthly_death_bar_chart")
def build_monthly_death_bar_chart(year: int = 0) -> str:
    """Build a bar chart of monthly death counts, optionally filtered to a year.

    Args:
        year: Year to filter (e.g. 2566 for BE, or 2023 for CE). 0 = all years.

    Returns:
        JSON string matching ChartSpec for a bar chart:
        X-axis = month, Y-axis = death count.
    """
    if year:
        sql = """
            SELECT month_no, SUM(death_count) AS death_count
            FROM mart_accident_summary
            WHERE year_no = %s
            GROUP BY month_no
            ORDER BY month_no
        """
        try:
            rows = query_db(sql, (year,))
        except Exception as exc:
            return json.dumps({"error": str(exc)})
    else:
        sql = """
            SELECT month_no, SUM(death_count) AS death_count
            FROM mart_accident_summary
            GROUP BY month_no
            ORDER BY month_no
        """
        try:
            rows = query_db(sql)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    if not rows:
        return json.dumps({"error": "ไม่พบข้อมูลการเสียชีวิต"})

    month_names = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
                   "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    month_map: dict[int, int] = {int(r["month_no"]): int(r["death_count"] or 0) for r in rows}
    labels = month_names
    data = [month_map.get(m, 0) for m in range(1, 13)]

    datasets = [
        {
            "label": "ผู้เสียชีวิต",
            "data": data,
            "backgroundColor": "#ef4444",
        }
    ]

    title = f"การเสียชีวิตจากอุบัติเหตุรายเดือน{f' ปี {year}' if year else ''}"
    return _chart_json(
        chart_type="bar",
        title=title,
        labels=labels,
        datasets=datasets,
        source_note="mart_accident_summary",
    )
