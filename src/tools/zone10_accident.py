"""Zone 10 accident policy SQL tools — เขตสุขภาพที่ 10.

7 targeted tools for the 7 RTI policy questions across 4 categories:
  Q1-Q2: Hotspot
  Q3-Q4: Human Behavior  (proxy queries — fact_accident_person is empty)
  Q5:    Environment
  Q6-Q7: KPI / Trend

Each public tool is backed by a _query_* function so the SQL logic can be
tested directly without going through the CrewAI Tool wrapper.
"""
from crewai.tools import tool
from src.db.pool import query_db

ZONE10_PROVINCES = ["อุบลราชธานี", "ศรีสะเกษ", "ยโสธร", "อำนาจเจริญ", "มุกดาหาร"]

_PERSON_DATA_NOTE = (
    "⚠️ หมายเหตุข้อมูล: ตาราง fact_accident_person ไม่มีข้อมูล "
    "(CSV แหล่งนี้ไม่มีข้อมูลระดับบุคคล) ผลลัพธ์เป็นข้อมูลระดับเหตุการณ์แทน"
)


def _province_clause(alias: str, provinces: str) -> tuple[str, list]:
    """Return (WHERE fragment, params) for province_name ILIKE filter.

    Args:
        alias: table alias, e.g. 'g' → 'g.province_name', or '' for bare column
        provinces: comma-separated province names; empty = all 5 Zone 10 provinces
    """
    names = [p.strip() for p in provinces.split(",") if p.strip()] or ZONE10_PROVINCES
    col = f"{alias}.province_name" if alias else "province_name"
    parts = " OR ".join([f"{col} ILIKE %s"] * len(names))
    return f"({parts})", [f"%{n}%" for n in names]


# ── Q1 logic ─────────────────────────────────────────────────────────────────

def _query_top_roads(provinces: str, top_n: int = 10) -> str:
    top_n = min(int(top_n), 20)
    clause, params = _province_clause("", provinces)
    sql = f"""
        SELECT province_name,
               road_name,
               road_code,
               SUM(accident_count)   AS total_accidents,
               SUM(death_count)      AS total_deaths,
               SUM(serious_injured)  AS total_serious,
               SUM(injured_count)    AS total_injured,
               MAX(hotspot_score)    AS hotspot_score,
               MAX(dominant_cause)   AS dominant_cause,
               MAX(dominant_vehicle) AS dominant_vehicle
        FROM mart_province_road
        WHERE {clause}
        GROUP BY province_name, road_name, road_code
        ORDER BY hotspot_score DESC
        LIMIT %s
    """
    try:
        rows = query_db(sql, tuple(params + [top_n]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลถนนได้: {exc}"

    if not rows:
        return "ไม่พบข้อมูลถนนในพื้นที่ที่ระบุ — ตรวจสอบว่า import_subdistrict_csv.py ถูกรันแล้ว"

    prov_label = provinces.strip() or "เขตสุขภาพที่ 10 (ทุกจังหวัด)"
    lines = [f"[Q1-Hotspot] ถนนเสี่ยงสูงสุด Top {top_n} — {prov_label}:"]
    lines.append(
        f"  {'#':<3} {'จังหวัด':<16} {'ถนน':<40} "
        f"{'คะแนน':>8} {'อุบัติเหตุ':>10} {'เสียชีวิต':>10} {'บาดเจ็บสาหัส':>13} {'สาเหตุหลัก'}"
    )
    lines.append("  " + "-" * 115)
    def _is_missing(rn):
        s = (rn or '').strip()
        return not s or s.lower() in ('unknown', 'none')

    road_name_missing = 0
    for i, r in enumerate(rows, 1):
        rname = r['road_name'] or ''
        display_name = rname[:38] if not _is_missing(rname) else 'ไม่ระบุ'
        if _is_missing(rname):
            road_name_missing += 1
        lines.append(
            f"  {i:<3} {r['province_name']:<16} "
            f"{display_name:<40} "
            f"{float(r['hotspot_score'] or 0):>8.0f} "
            f"{r['total_accidents'] or 0:>10,} "
            f"{r['total_deaths'] or 0:>10,} "
            f"{r['total_serious'] or 0:>13,} "
            f"  {r.get('dominant_cause') or 'N/A'}"
        )
    if road_name_missing > 0:
        lines.append(
            f"\n  ⚠️ หมายเหตุ: {road_name_missing}/{len(rows)} รายการไม่มีชื่อถนน (ไม่ระบุ) "
            "เนื่องจาก CSV แหล่งข้อมูลไม่มีข้อมูลชื่อถนน — แนะนำวิเคราะห์ตามพิกัด GPS แทน"
        )
    return "\n".join(lines)


@tool("get_zone10_top_roads")
def get_zone10_top_roads(provinces: str = "", top_n: int = 10) -> str:
    """Q1 (Hotspot): Top accident-prone roads in Zone 10 ranked by hotspot_score.

    Answers: "ถนนอันตรายที่สุดในเขตสุขภาพที่ 10 มีถนนใดบ้าง?"

    Args:
        provinces: Comma-separated Zone 10 province names (Thai). Empty = all 5.
        top_n: How many roads to return (default 10, max 20).
    """
    return _query_top_roads(provinces, top_n)


# ── Q2 logic ─────────────────────────────────────────────────────────────────

def _query_time_bands(provinces: str) -> str:
    clause, params = _province_clause("g", provinces)
    sql = f"""
        SELECT
            EXTRACT(HOUR FROM e.event_datetime)::int AS hour_of_day,
            COUNT(*)                AS accident_count,
            SUM(e.death_count)      AS death_count,
            SUM(e.serious_injured)  AS serious_count,
            SUM(e.injured_count)    AS injured_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND e.event_datetime IS NOT NULL
        GROUP BY hour_of_day
        ORDER BY accident_count DESC
        LIMIT 24
    """
    try:
        rows = query_db(sql, tuple(params))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลช่วงเวลาได้: {exc}"

    if not rows:
        return "ไม่พบข้อมูลช่วงเวลาอุบัติเหตุในพื้นที่ที่ระบุ"

    by_count = sorted(rows, key=lambda r: r["accident_count"] or 0, reverse=True)
    top5_hours = {r["hour_of_day"] for r in by_count[:5]}

    prov_label = provinces.strip() or "เขตสุขภาพที่ 10"
    lines = [f"[Q2-Hotspot] การกระจายอุบัติเหตุตามช่วงเวลา — {prov_label}:"]
    lines.append(f"  {'ชั่วโมง':>6} {'อุบัติเหตุ':>10} {'เสียชีวิต':>9} {'สาหัส':>6} {'บาดเจ็บ':>7}  {'ความเสี่ยง'}")
    lines.append("  " + "-" * 60)
    for r in sorted(rows, key=lambda x: x["hour_of_day"] or 0):
        h = r["hour_of_day"] or 0
        flag = " ◀ เสี่ยงสูง" if h in top5_hours else ""
        lines.append(
            f"  {h:02d}:00  "
            f"{r['accident_count'] or 0:>10,} "
            f"{r['death_count'] or 0:>9,} "
            f"{r['serious_count'] or 0:>6,} "
            f"{r['injured_count'] or 0:>7,}"
            f"{flag}"
        )
    lines.append(f"\n  ช่วงเสี่ยงสูงสุด 5 อันดับแรก: {', '.join(f'{h:02d}:00' for h in sorted(top5_hours))}")
    return "\n".join(lines)


@tool("get_zone10_time_bands")
def get_zone10_time_bands(provinces: str = "") -> str:
    """Q2 (Hotspot): Accident distribution by hour-of-day for Zone 10 EMS scheduling.

    Answers: "ช่วงเวลาไหนอุบัติเหตุชุกชุมที่สุด เพื่อวางแผน EMS?"

    Args:
        provinces: Comma-separated Zone 10 province names (Thai). Empty = all 5.
    """
    return _query_time_bands(provinces)


# ── Q3 logic ─────────────────────────────────────────────────────────────────

def _query_motorcycle_severity(provinces: str) -> str:
    clause, params = _province_clause("g", provinces)
    sql = f"""
        SELECT
            g.province_name,
            e.severity_level,
            COUNT(*)               AS accident_count,
            SUM(e.death_count)     AS death_count,
            SUM(e.serious_injured) AS serious_count,
            SUM(e.injured_count)   AS injured_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND e.vehicle_type ILIKE %s
        GROUP BY g.province_name, e.severity_level
        ORDER BY g.province_name, death_count DESC
    """
    try:
        rows = query_db(sql, tuple(params + ["%จักรยานยนต์%"]))
    except Exception as exc:
        return f"{_PERSON_DATA_NOTE}\nไม่สามารถดึงข้อมูลได้: {exc}"

    if not rows:
        return (
            f"{_PERSON_DATA_NOTE}\n"
            "ไม่พบข้อมูลอุบัติเหตุจักรยานยนต์ในพื้นที่ที่ระบุ"
        )

    prov_label = provinces.strip() or "เขตสุขภาพที่ 10"
    lines = [
        f"[Q3-Human Behavior] ความรุนแรงอุบัติเหตุจักรยานยนต์ — {prov_label}:",
        _PERSON_DATA_NOTE,
        "(ข้อมูลเหตุการณ์รวม — ไม่มีข้อมูลการสวมหมวกนิรภัยระดับบุคคล)",
        f"  {'จังหวัด':<16} {'ระดับความรุนแรง':<20} {'อุบัติเหตุ':>10} {'เสียชีวิต':>9} {'สาหัส':>6}",
        "  " + "-" * 68,
    ]
    for r in rows:
        lines.append(
            f"  {r['province_name']:<16} "
            f"{(r['severity_level'] or 'ไม่ระบุ'):<20} "
            f"{r['accident_count'] or 0:>10,} "
            f"{r['death_count'] or 0:>9,} "
            f"{r['serious_count'] or 0:>6,}"
        )
    total_deaths = sum(r["death_count"] or 0 for r in rows)
    total_acc = sum(r["accident_count"] or 0 for r in rows)
    lines.append(f"\n  รวม: อุบัติเหตุจักรยานยนต์ {total_acc:,} ครั้ง, เสียชีวิต {total_deaths:,} ราย")
    return "\n".join(lines)


@tool("get_zone10_motorcycle_severity")
def get_zone10_motorcycle_severity(provinces: str = "") -> str:
    """Q3 (Human Behavior): Motorcycle accident severity breakdown in Zone 10.

    Proxy for ผู้เสียชีวิตจักรยานยนต์ที่ไม่สวมหมวก — fact_accident_person is empty.
    Uses vehicle_type + severity_level from fact_accident_event instead.

    Args:
        provinces: Comma-separated Zone 10 province names (Thai). Empty = all 5.
    """
    return _query_motorcycle_severity(provinces)


# ── Q4 logic ─────────────────────────────────────────────────────────────────

def _query_car_serious_injuries(provinces: str) -> str:
    clause, params = _province_clause("g", provinces)
    sql = f"""
        SELECT
            g.province_name,
            e.vehicle_type,
            e.severity_level,
            COUNT(*)               AS accident_count,
            SUM(e.death_count)     AS death_count,
            SUM(e.serious_injured) AS serious_count,
            SUM(e.injured_count)   AS injured_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND e.vehicle_type NOT ILIKE %s
          AND e.vehicle_type IS NOT NULL
          AND e.vehicle_type <> ''
        GROUP BY g.province_name, e.vehicle_type, e.severity_level
        ORDER BY g.province_name, serious_count DESC
        LIMIT 60
    """
    try:
        rows = query_db(sql, tuple(params + ["%จักรยาน%"]))
    except Exception as exc:
        return f"{_PERSON_DATA_NOTE}\nไม่สามารถดึงข้อมูลได้: {exc}"

    if not rows:
        return (
            f"{_PERSON_DATA_NOTE}\n"
            "ไม่พบข้อมูลอุบัติเหตุรถยนต์/รถกระบะในพื้นที่ที่ระบุ"
        )

    prov_label = provinces.strip() or "เขตสุขภาพที่ 10"
    lines = [
        f"[Q4-Human Behavior] อุบัติเหตุรถยนต์/รถกระบะ (ไม่รวมจักรยานยนต์) — {prov_label}:",
        _PERSON_DATA_NOTE,
        "(ข้อมูลระดับเหตุการณ์ — ไม่มีข้อมูลการคาดเข็มขัดนิรภัย)",
        f"  {'จังหวัด':<16} {'ประเภทยานพาหนะ':<22} {'ระดับความรุนแรง':<20} {'สาหัส':>6} {'เสียชีวิต':>9}",
        "  " + "-" * 80,
    ]
    for r in rows:
        lines.append(
            f"  {r['province_name']:<16} "
            f"{(r['vehicle_type'] or 'ไม่ระบุ')[:20]:<22} "
            f"{(r['severity_level'] or 'ไม่ระบุ'):<20} "
            f"{r['serious_count'] or 0:>6,} "
            f"{r['death_count'] or 0:>9,}"
        )
    total_serious = sum(r["serious_count"] or 0 for r in rows)
    total_deaths = sum(r["death_count"] or 0 for r in rows)
    lines.append(f"\n  รวม (ยานพาหนะ 4 ล้อ): บาดเจ็บสาหัส {total_serious:,} คน, เสียชีวิต {total_deaths:,} ราย")
    return "\n".join(lines)


@tool("get_zone10_car_serious_injuries")
def get_zone10_car_serious_injuries(provinces: str = "") -> str:
    """Q4 (Human Behavior): Car/pickup accident serious-injury breakdown in Zone 10.

    Proxy for ผู้บาดเจ็บสาหัสในรถยนต์ที่ไม่คาดเข็มขัด — fact_accident_person is empty.
    Uses vehicle_type + severity_level from fact_accident_event instead.

    Args:
        provinces: Comma-separated Zone 10 province names (Thai). Empty = all 5.
    """
    return _query_car_serious_injuries(provinces)


# ── Q5 logic ─────────────────────────────────────────────────────────────────

def _query_environment_risk(provinces: str) -> str:
    clause, params = _province_clause("g", provinces)
    sql = f"""
        SELECT
            e.light_condition,
            e.road_condition,
            e.severity_level,
            COUNT(*)               AS accident_count,
            SUM(e.death_count)     AS death_count,
            SUM(e.serious_injured) AS serious_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
        GROUP BY e.light_condition, e.road_condition, e.severity_level
        ORDER BY death_count DESC
        LIMIT 40
    """
    try:
        rows = query_db(sql, tuple(params))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลสภาพแวดล้อมได้: {exc}"

    if not rows:
        return "ไม่พบข้อมูลสภาพแวดล้อมในพื้นที่ที่ระบุ"

    prov_label = provinces.strip() or "เขตสุขภาพที่ 10"
    lines = [
        f"[Q5-Environment] ความสัมพันธ์สภาพแสง/สภาพถนน กับความรุนแรง — {prov_label}:",
        f"  {'สภาพแสง':<25} {'สภาพถนน':<20} {'ระดับความรุนแรง':<18} {'อุบัติเหตุ':>10} {'เสียชีวิต':>9} {'สาหัส':>6}",
        "  " + "-" * 95,
    ]
    for r in rows:
        lines.append(
            f"  {(r['light_condition'] or 'ไม่ระบุ'):<25} "
            f"{(r['road_condition'] or 'ไม่ระบุ'):<20} "
            f"{(r['severity_level'] or 'ไม่ระบุ'):<18} "
            f"{r['accident_count'] or 0:>10,} "
            f"{r['death_count'] or 0:>9,} "
            f"{r['serious_count'] or 0:>6,}"
        )
    top3 = rows[:3]
    lines.append("\n  สภาพแวดล้อมที่มีผู้เสียชีวิตสูงสุด 3 อันดับแรก:")
    for i, r in enumerate(top3, 1):
        lines.append(
            f"    {i}. แสง: {r['light_condition'] or 'ไม่ระบุ'} | "
            f"ถนน: {r['road_condition'] or 'ไม่ระบุ'} → "
            f"เสียชีวิต {r['death_count'] or 0:,} ราย"
        )
    return "\n".join(lines)


@tool("get_zone10_environment_risk")
def get_zone10_environment_risk(provinces: str = "") -> str:
    """Q5 (Environment): Accident severity vs light_condition + road_condition in Zone 10.

    Answers: "สภาพแสงและสภาพถนนแบบใดทำให้เกิดอุบัติเหตุรุนแรงที่สุด?"

    Args:
        provinces: Comma-separated Zone 10 province names (Thai). Empty = all 5.
    """
    return _query_environment_risk(provinces)


# ── Q6 logic ─────────────────────────────────────────────────────────────────

def _pct_change(old, new) -> str:
    old = old or 0
    new = new or 0
    if old == 0:
        return "  N/A"
    pct = (new - old) / old * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def _query_yearly_kpi(provinces: str) -> str:
    clause, params = _province_clause("", provinces)
    sql = f"""
        SELECT year_no, province_name,
               accident_count, death_count, serious_injured, injured_count,
               top_vehicle, top_cause
        FROM mart_province_year
        WHERE {clause}
          AND year_no BETWEEN 2021 AND 2026
        ORDER BY province_name, year_no
    """
    try:
        rows = query_db(sql, tuple(params))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูล KPI ได้: {exc}"

    if not rows:
        return "ไม่พบข้อมูล KPI ในปีที่ระบุ — ตรวจสอบว่า import_subdistrict_csv.py ถูกรันแล้ว"

    from collections import defaultdict
    by_prov: dict[str, list] = defaultdict(list)
    for r in rows:
        by_prov[r["province_name"]].append(r)

    prov_label = provinces.strip() or "เขตสุขภาพที่ 10"
    lines = [f"[Q6-KPI] แนวโน้มรายปี อุบัติเหตุ/เสียชีวิต/บาดเจ็บสาหัส — {prov_label}:"]

    for prov, prov_rows in sorted(by_prov.items()):
        lines.append(f"\n  {prov}:")
        lines.append(f"    {'ปี':>4} {'อุบัติเหตุ':>10} {'Δ%':>6} {'เสียชีวิต':>9} {'Δ%':>6} {'สาหัส':>8} {'Δ%':>6}")
        lines.append("    " + "-" * 55)
        prev = None
        for r in prov_rows:
            if prev:
                d_acc = _pct_change(prev["accident_count"], r["accident_count"])
                d_dth = _pct_change(prev["death_count"], r["death_count"])
                d_ser = _pct_change(prev["serious_injured"], r["serious_injured"])
            else:
                d_acc = d_dth = d_ser = "   -"
            lines.append(
                f"    {r['year_no']:>4} "
                f"{r['accident_count'] or 0:>10,} "
                f"{d_acc:>6} "
                f"{r['death_count'] or 0:>9,} "
                f"{d_dth:>6} "
                f"{r['serious_injured'] or 0:>8,} "
                f"{d_ser:>6}"
            )
            prev = r

    totals: dict[int, dict] = {}
    for r in rows:
        yr = r["year_no"]
        if yr not in totals:
            totals[yr] = {"accident_count": 0, "death_count": 0, "serious_injured": 0}
        totals[yr]["accident_count"] += r["accident_count"] or 0
        totals[yr]["death_count"] += r["death_count"] or 0
        totals[yr]["serious_injured"] += r["serious_injured"] or 0

    lines.append("\n  สรุปภาพรวมเขตสุขภาพที่ 10:")
    lines.append(f"    {'ปี':>4} {'อุบัติเหตุรวม':>12} {'เสียชีวิตรวม':>12} {'สาหัสรวม':>10}")
    lines.append("    " + "-" * 42)
    for yr in sorted(totals):
        t = totals[yr]
        lines.append(
            f"    {yr:>4} "
            f"{t['accident_count']:>12,} "
            f"{t['death_count']:>12,} "
            f"{t['serious_injured']:>10,}"
        )
    return "\n".join(lines)


@tool("get_zone10_yearly_kpi")
def get_zone10_yearly_kpi(provinces: str = "") -> str:
    """Q6 (KPI): Year-over-year deaths and serious injuries for Zone 10 (2021-2026).

    Answers: "อัตราการเสียชีวิตและบาดเจ็บสาหัสในเขตสุขภาพที่ 10 เพิ่มขึ้นหรือลดลง?"
    Primary focus: ยโสธร, อำนาจเจริญ, มุกดาหาร per policy requirement.

    Args:
        provinces: Comma-separated Zone 10 province names (Thai). Empty = all 5.
    """
    return _query_yearly_kpi(provinces)


# ── Q7 logic ─────────────────────────────────────────────────────────────────

def _query_monthly_risk(provinces: str) -> str:
    clause, params = _province_clause("", provinces)
    sql = f"""
        SELECT year_no, month_no, province_name,
               accident_count, death_count, injured_count,
               high_risk_timeband, dominant_road_cond
        FROM mart_accident_summary
        WHERE {clause}
          AND year_no BETWEEN 2021 AND 2026
        ORDER BY province_name, year_no, month_no
    """
    try:
        rows = query_db(sql, tuple(params))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลรายเดือนได้: {exc}"

    if not rows:
        return "ไม่พบข้อมูลรายเดือนในพื้นที่ที่ระบุ"

    from collections import defaultdict
    monthly: dict[int, dict] = defaultdict(lambda: {"accident_count": 0, "death_count": 0, "injured_count": 0})
    for r in rows:
        m = r["month_no"]
        monthly[m]["accident_count"] += r["accident_count"] or 0
        monthly[m]["death_count"] += r["death_count"] or 0
        monthly[m]["injured_count"] += r["injured_count"] or 0

    month_names = {
        1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
        5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
        9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม",
    }
    festival_months = {
        1: "ปีใหม่",
        4: "สงกรานต์ (เสี่ยงสูงสุด)",
        12: "คริสต์มาส/ปีใหม่",
        11: "ลอยกระทง",
    }

    prov_label = provinces.strip() or "เขตสุขภาพที่ 10"
    max_acc = max((v["accident_count"] for v in monthly.values()), default=1)
    lines = [
        f"[Q7-KPI] ความเสี่ยงรายเดือน (รวมปี 2021-2026) — {prov_label}:",
        f"  {'เดือน':<14} {'อุบัติเหตุรวม':>12} {'เสียชีวิตรวม':>12} {'บาดเจ็บรวม':>10}  {'หมายเหตุ'}",
        "  " + "-" * 70,
    ]
    for m, data in sorted(monthly.items()):
        bar_len = int(data["accident_count"] / max_acc * 15)
        bar = "█" * bar_len
        festival = f" ← {festival_months[m]}" if m in festival_months else ""
        lines.append(
            f"  {month_names.get(m, str(m)):<14} "
            f"{data['accident_count']:>12,} "
            f"{data['death_count']:>12,} "
            f"{data['injured_count']:>10,}  "
            f"{bar}{festival}"
        )

    top3_months = sorted(monthly.items(), key=lambda x: x[1]["death_count"], reverse=True)[:3]
    lines.append("\n  เดือนที่มีผู้เสียชีวิตสูงสุด 3 อันดับ:")
    for rank, (m, data) in enumerate(top3_months, 1):
        lines.append(
            f"    {rank}. {month_names.get(m, str(m))}: เสียชีวิต {data['death_count']:,} ราย "
            f"({festival_months.get(m, '')})"
        )
    return "\n".join(lines)


@tool("get_zone10_monthly_risk")
def get_zone10_monthly_risk(provinces: str = "") -> str:
    """Q7 (KPI): Monthly accident distribution and high-risk periods for Zone 10.

    Answers: "เดือนไหนมีอุบัติเหตุสูงที่สุด? เทศกาลใดเสี่ยงกว่าปกติ?"

    Args:
        provinces: Comma-separated Zone 10 province names (Thai). Empty = all 5.
    """
    return _query_monthly_risk(provinces)
