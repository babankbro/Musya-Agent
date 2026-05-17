"""Accident domain database RAG tools."""
from crewai.tools import tool
from src.db.pool import query_db


# ── Province-level tools ──────────────────────────────────────────────────────

@tool("get_province_year_summary")
def get_province_year_summary(province: str = "", year: int = 0) -> str:
    """Get yearly accident summary for one province or all provinces, optionally filtered by year.

    Use this tool when the user asks about:
    - Accidents in a specific province (จังหวัด)
    - Year-by-year trend for a province
    - Comparing provinces across years
    - Top/worst provinces for a given year

    Args:
        province: Province name in Thai (e.g. 'เชียงใหม่', 'กรุงเทพมหานคร').
                  Leave empty to get all provinces.
        year:     Year (CE: 2020–2026). 0 = all years.

    Returns:
        Yearly accident/injury/death/road counts per province.
    """
    conditions: list[str] = []
    params: list = []

    if province:
        conditions.append("province_name ILIKE %s")
        params.append(f"%{province}%")
    if year:
        conditions.append("year_no = %s")
        params.append(year)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT year_no, province_name,
               accident_count, injured_count, serious_injured, death_count,
               road_count, top_vehicle, top_cause, top_timeband, top_weather
        FROM mart_province_year
        {where}
        ORDER BY province_name, year_no
        LIMIT 200
    """
    try:
        rows = query_db(sql, tuple(params) if params else None)
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลได้: {exc}"

    if not rows:
        label = f"จังหวัด {province}" if province else "ทุกจังหวัด"
        yr_label = f" ปี {year}" if year else ""
        return f"ไม่พบข้อมูล{label}{yr_label} — กรุณาตรวจสอบว่า import_csv_all_years.py ถูกรันแล้ว"

    header = f"ข้อมูลอุบัติเหตุ{'จังหวัด '+province if province else 'ทุกจังหวัด'}{'ปี '+str(year) if year else ' (ทุกปี 2020-2026)'}:"
    lines = [header]
    for r in rows:
        lines.append(
            f"  {r['year_no']} | {r['province_name']:<18} | "
            f"อุบัติเหตุ {r['accident_count']:>5} ครั้ง | "
            f"บาดเจ็บ {r['injured_count']:>5} คน | "
            f"บาดเจ็บสาหัส {r.get('serious_injured',0):>4} คน | "
            f"เสียชีวิต {r['death_count']:>4} คน | "
            f"ถนน {r['road_count']:>3} สาย | "
            f"ยานพาหนะหลัก: {r.get('top_vehicle','N/A')} | "
            f"สาเหตุหลัก: {r.get('top_cause','N/A')}"
        )

    # Totals if multi-year single province
    if province and not year:
        total_acc = sum(r['accident_count'] or 0 for r in rows)
        total_inj = sum(r['injured_count'] or 0 for r in rows)
        total_ser = sum((r.get('serious_injured') or 0) for r in rows)
        total_dth = sum(r['death_count'] or 0 for r in rows)
        lines.append(
            f"\n  รวมทุกปี: อุบัติเหตุ {total_acc} ครั้ง, "
            f"บาดเจ็บ {total_inj} คน, "
            f"บาดเจ็บสาหัส {total_ser} คน, "
            f"เสียชีวิต {total_dth} คน"
        )
    return "\n".join(lines)


@tool("get_province_roads")
def get_province_roads(province: str, year: int = 0, top_n: int = 15) -> str:
    """Get top accident-prone roads in a specific province, with year breakdown.

    Use this when the user asks:
    - Which roads in province X have the most accidents?
    - Road risk ranking for a province
    - Which road code / ถนน / สายทาง has most accidents

    Args:
        province: Province name in Thai (required, e.g. 'เชียงใหม่')
        year:     Year CE 2020–2026 to filter, or 0 for all years combined
        top_n:    How many roads to return (default 15)

    Returns:
        Top roads in the province ranked by hotspot score with accident/injury/death counts.
    """
    params: list = [f"%{province}%", min(int(top_n), 50)]
    year_clause = ""
    if year:
        year_clause = "AND year_no = %s"
        params.insert(1, year)

    sql = f"""
        SELECT year_no, road_name, road_code,
               accident_count, injured_count, serious_injured, death_count,
               hotspot_score, dominant_cause, dominant_vehicle
        FROM mart_province_road
        WHERE province_name ILIKE %s
          {year_clause}
        ORDER BY hotspot_score DESC
        LIMIT %s
    """
    try:
        rows = query_db(sql, tuple(params))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลถนนได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลถนนในจังหวัด {province} — ลองตรวจสอบชื่อจังหวัดหรือรัน import ก่อน"

    yr_label = f" ปี {year}" if year else " (ทุกปี)"
    lines = [f"ถนนที่เสี่ยงสูงในจังหวัด {province}{yr_label} (Top {top_n}):"]
    for i, r in enumerate(rows, 1):
        yr_txt = f"ปี {r['year_no']} | " if not year else ""
        lines.append(
            f"  {i:>2}. {yr_txt}"
            f"[{r.get('road_code','N/A')}] {r['road_name'][:50]} | "
            f"อุบัติเหตุ {r['accident_count']:>4} | "
            f"บาดเจ็บสาหัส {r.get('serious_injured',0):>3} | "
            f"เสียชีวิต {r['death_count']:>3} | "
            f"คะแนนเสี่ยง {r['hotspot_score']:>7.0f} | "
            f"ยานพาหนะ: {r.get('dominant_vehicle','N/A')} | "
            f"สาเหตุ: {r.get('dominant_cause','N/A')}"
        )
    return "\n".join(lines)


@tool("get_all_provinces_ranking")
def get_all_provinces_ranking(year: int = 0, sort_by: str = "accident_count", top_n: int = 77) -> str:
    """Get accident ranking across ALL 77 provinces for a given year or all years combined.

    Use this when the user asks:
    - Compare all provinces
    - Which province has the most/least accidents?
    - Provincial ranking by deaths, injuries, or accidents
    - สถิติอุบัติเหตุแต่ละจังหวัด

    Args:
        year:     Year CE 2020–2026 or 0 for all years summed
        sort_by:  Column to rank by: 'accident_count', 'death_count', 'injured_count' (default: accident_count)
        top_n:    Number of provinces to return (default 77 = all)

    Returns:
        Ranked table of all provinces with accident/injury/death totals.
    """
    valid_sorts = {"accident_count", "death_count", "injured_count", "serious_injured"}
    sort_col = sort_by if sort_by in valid_sorts else "accident_count"

    if year:
        sql = f"""
            SELECT year_no, province_name,
                   accident_count, injured_count, serious_injured, death_count,
                   road_count, top_vehicle, top_cause
            FROM mart_province_year
            WHERE year_no = %s
            ORDER BY {sort_col} DESC
            LIMIT %s
        """
        params: tuple = (year, min(int(top_n), 77))
    else:
        sql = f"""
            SELECT
                province_name,
                SUM(accident_count)   AS accident_count,
                SUM(injured_count)    AS injured_count,
                SUM(serious_injured)  AS serious_injured,
                SUM(death_count)      AS death_count,
                MAX(road_count)       AS road_count
            FROM mart_province_year
            GROUP BY province_name
            ORDER BY {sort_col} DESC
            LIMIT %s
        """
        params = (min(int(top_n), 77),)

    try:
        rows = query_db(sql, params)
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลได้: {exc}"

    if not rows:
        return "ไม่พบข้อมูลจังหวัด — กรุณา run import_csv_all_years.py ก่อน"

    yr_label = f"ปี {year}" if year else "รวมทุกปี (2020-2026)"
    lines = [f"การจัดอันดับจังหวัด {yr_label} (เรียงตาม {sort_col}):"]
    lines.append(f"  {'อันดับ':<5} {'จังหวัด':<20} {'อุบัติเหตุ':>9} {'บาดเจ็บ':>7} {'สาหัส':>6} {'เสียชีวิต':>9} {'ถนน':>5}")
    lines.append("  " + "-" * 70)
    for i, r in enumerate(rows, 1):
        lines.append(
            f"  {i:<5} {r['province_name']:<20} "
            f"{r['accident_count']:>9,} "
            f"{r['injured_count']:>7,} "
            f"{r.get('serious_injured',0):>6,} "
            f"{r['death_count']:>9,} "
            f"{r.get('road_count',0):>5}"
        )
    return "\n".join(lines)


@tool("get_accident_summary")
def get_accident_summary(start_date: str = "", end_date: str = "", geography: str = "") -> str:
    """Get accident summary statistics by time period and geography.
    
    Args:
        start_date: Start date (YYYY-MM-DD format) or empty for all
        end_date: End date (YYYY-MM-DD format) or empty for all
        geography: Province/district name in Thai, or empty for all areas
    
    Returns:
        Summary of accident counts, injuries, and deaths grouped by month/year and area.
    """
    # Try new mart table first, fallback to existing accident table
    try:
        return _query_mart_accident_summary(start_date, end_date, geography)
    except Exception:
        return _query_legacy_accident_table(start_date, end_date, geography)


def _query_mart_accident_summary(start_date: str, end_date: str, geography: str) -> str:
    conditions = []
    params: list = []

    if start_date:
        conditions.append("(year_no > %s OR (year_no = %s AND month_no >= %s))")
        y, m = start_date[:4], start_date[5:7]
        params.extend([int(y), int(y), int(m)])
    if end_date:
        conditions.append("(year_no < %s OR (year_no = %s AND month_no <= %s))")
        y, m = end_date[:4], end_date[5:7]
        params.extend([int(y), int(y), int(m)])

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT year_no, month_no, accident_count, injured_count, death_count,
               high_risk_timeband, dominant_road_cond
        FROM mart_accident_summary
        {where}
        ORDER BY year_no, month_no
        LIMIT 100
    """
    rows = query_db(sql, tuple(params) if params else None)
    if not rows:
        return "ไม่พบข้อมูลสรุปอุบัติเหตุในช่วงเวลาที่กำหนด"

    lines = ["สรุปข้อมูลอุบัติเหตุ:"]
    total_acc, total_inj, total_death = 0, 0, 0
    for r in rows:
        lines.append(
            f"  {r['year_no']}/{r['month_no']:02d}: "
            f"อุบัติเหตุ {r['accident_count']} ครั้ง, "
            f"บาดเจ็บ {r['injured_count']} คน, "
            f"เสียชีวิต {r['death_count']} คน"
        )
        total_acc += r['accident_count'] or 0
        total_inj += r['injured_count'] or 0
        total_death += r['death_count'] or 0

    lines.append(f"\nรวม: อุบัติเหตุ {total_acc} ครั้ง, บาดเจ็บ {total_inj} คน, เสียชีวิต {total_death} คน")
    return "\n".join(lines)


def _query_legacy_accident_table(start_date: str, end_date: str, geography: str) -> str:
    """Fallback query against the existing 'accident' table from ChatV1."""
    try:
        rows = query_db("SELECT column_name FROM information_schema.columns WHERE table_name = 'accident' ORDER BY ordinal_position")
        if not rows:
            return "ไม่พบตารางข้อมูลอุบัติเหตุ"
        columns = [r["column_name"] for r in rows]
    except Exception:
        return "ไม่พบตารางข้อมูลอุบัติเหตุ"

    sql = "SELECT * FROM accident LIMIT 50"
    rows = query_db(sql)
    if not rows:
        return "ไม่พบข้อมูลในตารางอุบัติเหตุ"

    lines = [f"ข้อมูลอุบัติเหตุจากตารางเดิม (คอลัมน์: {', '.join(columns)}):"]
    lines.append(f"จำนวนแถวที่แสดง: {len(rows)}")
    for r in rows[:10]:
        lines.append(f"  {r}")
    if len(rows) > 10:
        lines.append(f"  ... (แสดง 10 จาก {len(rows)} แถว)")
    return "\n".join(lines)


@tool("get_accident_hotspots")
def get_accident_hotspots(start_date: str = "", end_date: str = "", geography: str = "", top_n: int = 10) -> str:
    """Get top accident hotspot locations ranked by severity.
    
    Args:
        start_date: Start date (YYYY-MM-DD) or empty for all
        end_date: End date (YYYY-MM-DD) or empty for all
        geography: Province/district name filter or empty for all
        top_n: Number of top hotspots to return (default 10)
    
    Returns:
        Ranked list of accident hotspots with scores and key factors.
    """
    try:
        sql = """
            SELECT h.hotspot_id, h.accident_count, h.injured_count, h.death_count,
                   h.hotspot_score, h.dominant_timeband
            FROM mart_accident_hotspot h
            ORDER BY h.hotspot_score DESC
            LIMIT %s
        """
        rows = query_db(sql, (top_n,))
    except Exception:
        return "ยังไม่มีตาราง mart_accident_hotspot — กรุณา run migration ก่อน"

    if not rows:
        return "ไม่พบข้อมูลจุดเสี่ยง"

    lines = [f"จุดเสี่ยงอุบัติเหตุ Top {top_n}:"]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"  {i}. คะแนนเสี่ยง: {r['hotspot_score']}, "
            f"อุบัติเหตุ: {r['accident_count']}, "
            f"บาดเจ็บ: {r['injured_count']}, "
            f"เสียชีวิต: {r['death_count']}, "
            f"ช่วงเวลาเสี่ยง: {r.get('dominant_timeband', 'N/A')}"
        )
    return "\n".join(lines)


@tool("get_accident_time_distribution")
def get_accident_time_distribution(start_date: str = "", end_date: str = "", geography: str = "") -> str:
    """Get accident distribution by time of day and day of week.
    
    Args:
        start_date: Start date (YYYY-MM-DD) or empty for all
        end_date: End date (YYYY-MM-DD) or empty for all
        geography: Province/district name filter or empty for all
    
    Returns:
        Accident counts by hour and day-of-week for identifying risky time periods.
    """
    try:
        sql = """
            SELECT
                EXTRACT(HOUR FROM event_datetime) AS hour_of_day,
                EXTRACT(DOW FROM event_datetime) AS day_of_week,
                COUNT(*) AS accident_count,
                SUM(injured_count) AS total_injured,
                SUM(death_count) AS total_deaths
            FROM fact_accident_event
            GROUP BY hour_of_day, day_of_week
            ORDER BY accident_count DESC
            LIMIT 30
        """
        rows = query_db(sql)
    except Exception:
        return "ยังไม่มีตาราง fact_accident_event — กรุณา run migration ก่อน"

    if not rows:
        return "ไม่พบข้อมูลการกระจายเวลาอุบัติเหตุ"

    day_names = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"]
    lines = ["การกระจายอุบัติเหตุตามช่วงเวลา:"]
    for r in rows:
        dow = int(r.get("day_of_week", 0))
        day_name = day_names[dow] if 0 <= dow < 7 else str(dow)
        lines.append(
            f"  วัน{day_name} เวลา {int(r.get('hour_of_day', 0)):02d}:00 - "
            f"อุบัติเหตุ {r['accident_count']} ครั้ง, "
            f"บาดเจ็บ {r.get('total_injured', 0)}, "
            f"เสียชีวิต {r.get('total_deaths', 0)}"
        )
    return "\n".join(lines)


@tool("get_road_condition_risk")
def get_road_condition_risk(start_date: str = "", end_date: str = "", geography: str = "") -> str:
    """Analyze accident risk by accident location type and weather conditions.
    
    Args:
        start_date: Start date (YYYY-MM-DD) or empty for all
        end_date: End date (YYYY-MM-DD) or empty for all
        geography: Province/district name filter or empty for all
    
    Returns:
        Accident location types and weather associated with highest accident rates.
    """
    try:
        sql = """
            SELECT
                e.accident_location,
                e.weather_condition,
                r.road_type,
                COUNT(*) AS accident_count,
                SUM(e.injured_count) AS total_injured,
                SUM(e.death_count) AS total_deaths
            FROM fact_accident_event e
            LEFT JOIN dim_road_segment r ON e.road_segment_id = r.road_segment_id
            GROUP BY e.accident_location, e.weather_condition, r.road_type
            ORDER BY accident_count DESC
            LIMIT 20
        """
        rows = query_db(sql)
    except Exception:
        return "ยังไม่มีตาราง fact_accident_event / dim_road_segment — กรุณา run migration ก่อน"

    if not rows:
        return "ไม่พบข้อมูลความเสี่ยงสภาพแวดล้อม"

    lines = ["ความเสี่ยงอุบัติเหตุตามบริเวณที่เกิดเหตุ:"]
    for r in rows:
        lines.append(
            f"  บริเวณ: {r.get('accident_location', 'ไม่ระบุ')}, "
            f"สภาพอากาศ: {r.get('weather_condition', 'N/A')}, "
            f"ประเภทถนน: {r.get('road_type', 'N/A')}, "
            f"อุบัติเหตุ: {r['accident_count']}, "
            f"บาดเจ็บ: {r.get('total_injured', 0)}, "
            f"เสียชีวิต: {r.get('total_deaths', 0)}"
        )
    return "\n".join(lines)
