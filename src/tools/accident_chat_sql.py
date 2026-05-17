"""Accident Chat SQL tools — conversational data Q&A for Zone 10 RTI policy.

Covers all 4 policy question groups (20 questions + free-form):
  Group 1: Hotspot & Engineering     (Q1-Q5)
  Group 2: Behavioral & Campaign     (Q6-Q10) — fact_accident_person empty → disclaimer
  Group 3: Temporal & Seasonal       (Q11-Q15)
  Group 4: KPI Monitoring            (Q16-Q20)

DATA LIMITATIONS (communicated in all relevant tool outputs):
  - fact_accident_person: EMPTY — no helmet/seatbelt/age/sex person-level data
  - light_condition, road_condition: NULL in all rows (not in CSV source)
  - road_name: mostly NULL/empty in mart_province_road (CSV field blank)
  - Years in DB: CE (2021-2026); user questions use พ.ศ. → convert CE+543
"""
import json
import logging
from crewai.tools import tool
from src.db.pool import query_db

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

ZONE10_PROVINCES = ["อุบลราชธานี", "ศรีสะเกษ", "ยโสธร", "อำนาจเจริญ", "มุกดาหาร"]

_PERSON_EMPTY_NOTE = (
    "⚠️ ข้อจำกัดข้อมูล: ตาราง fact_accident_person ไม่มีข้อมูล "
    "(CSV แหล่งนี้ไม่มีข้อมูลระดับบุคคล เช่น การสวมหมวก การคาดเข็มขัด อายุ เพศ) "
    "ไม่สามารถตอบคำถามนี้ได้จากฐานข้อมูลปัจจุบัน"
)

_LIGHT_ROAD_NULL_NOTE = (
    "⚠️ ข้อจำกัดข้อมูล: คอลัมน์ light_condition และ road_condition เป็น NULL ทั้งหมด "
    "(ไม่มีใน CSV แหล่งข้อมูล) — ใช้ weather_condition และ accident_type แทนในการวิเคราะห์"
)

_YEAR_NOTE = "หมายเหตุ: ปีในฐานข้อมูลเป็น ค.ศ. — พ.ศ. = ค.ศ. + 543"


def _ce_to_be(year: int) -> int:
    return year + 543


def _province_ilike_clause(alias: str, province: str) -> tuple[str, list]:
    """Build WHERE fragment for a single province name using ILIKE."""
    col = f"{alias}.province_name" if alias else "province_name"
    if not province.strip():
        parts = " OR ".join([f"{col} ILIKE %s"] * len(ZONE10_PROVINCES))
        return f"({parts})", [f"%{p}%" for p in ZONE10_PROVINCES]
    return f"({col} ILIKE %s)", [f"%{province.strip()}%"]


def _serialize_rows(rows: list) -> list[dict]:
    clean = []
    for row in rows:
        r = {}
        for k, v in row.items():
            if v is None:
                r[k] = None
            elif hasattr(v, "__float__"):
                r[k] = float(v)
            elif hasattr(v, "isoformat"):
                r[k] = v.isoformat()
            else:
                r[k] = v
        clean.append(r)
    return clean


# ── Group 1: Hotspot & Engineering ────────────────────────────────────────────

def _query_hotspot_roads(province: str, top_n: int = 10,
                         year_start: int = 2021, year_end: int = 2026) -> str:
    top_n = min(int(top_n), 30)
    clause, params = _province_ilike_clause("", province)
    sql = f"""
        SELECT province_name, road_name, road_code,
               MAX(road_type_label)  AS road_type_label,
               STRING_AGG(DISTINCT district_name, ', '
                   ORDER BY district_name) FILTER (WHERE district_name IS NOT NULL
                   AND district_name <> '')  AS districts,
               SUM(accident_count)  AS total_accidents,
               SUM(death_count)     AS total_deaths,
               SUM(serious_injured) AS total_serious,
               MAX(hotspot_score)   AS hotspot_score,
               MAX(dominant_cause)  AS dominant_cause
        FROM mart_province_road
        WHERE {clause}
          AND year_no BETWEEN %s AND %s
        GROUP BY province_name, road_name, road_code
        ORDER BY hotspot_score DESC
        LIMIT %s
    """
    try:
        rows = query_db(sql, tuple(params + [year_start, year_end, top_n]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลจุดเสี่ยงได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลถนนสำหรับ '{province}'"

    year_label = f"พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(year_end)}"
    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    def _road_missing(rn):
        s = (rn or "").strip()
        return not s or s.lower() in ("unknown", "none")

    missing = sum(1 for r in rows if _road_missing(r["road_name"]))
    lines = [
        f"[Hotspot Roads] Top {top_n} ถนนเสี่ยง — {prov_label} ({year_label})",
        f"  {'#':<3} {'จังหวัด':<13} {'ประเภท':<8} {'ชื่อถนน':<31} {'อำเภอที่ผ่าน':<26} "
        f"{'คะแนน':>7} {'อุบัติ':>7} {'ตาย':>6} {'สาหัส':>6} {'สาเหตุหลัก'}",
        "  " + "-" * 140,
    ]
    for i, r in enumerate(rows, 1):
        rn = r["road_name"] or ""
        name = rn[:29] if not _road_missing(rn) else "ไม่ระบุ"
        dist = (r["districts"] or "ไม่ระบุ")[:24]
        rtype = (r.get("road_type_label") or "ไม่ระบุ")[:7]
        lines.append(
            f"  {i:<3} {r['province_name']:<13} {rtype:<8} {name:<31} {dist:<26} "
            f"{float(r['hotspot_score'] or 0):>7.0f} "
            f"{r['total_accidents'] or 0:>7,} "
            f"{r['total_deaths'] or 0:>6,} "
            f"{r['total_serious'] or 0:>6,} "
            f"  {r.get('dominant_cause') or 'N/A'}"
        )
    if missing:
        lines.append(
            f"\n  ⚠️ {missing}/{len(rows)} รายการไม่มีชื่อถนน — ข้อมูล CSV ไม่ระบุชื่อถนน"
        )
    return "\n".join(lines)


@tool("query_hotspot_roads")
def query_hotspot_roads(province: str = "", top_n: int = 10,
                        year_start: int = 2021, year_end: int = 2026) -> str:
    """Group 1 Q1: ถนนเส้นใดมีคะแนน Hotspot Score สูงที่สุด + สาเหตุหลัก + อำเภอที่ผ่าน.

    ข้อมูลจาก: mart_province_road (มี district_name ระบุอำเภอที่แต่ละถนนผ่าน)
    หมายเหตุ: ถนนสายยาวอาจผ่านหลายอำเภอ

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        top_n: จำนวนถนนที่ต้องการ (default 10)
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_hotspot_roads(province, top_n, year_start, year_end)


def _query_road_district_breakdown(province: str, road_name: str,
                                    year_start: int = 2021,
                                    year_end: int = 2026) -> str:
    """ดูรายละเอียดอุบัติเหตุของถนนแยกตามอำเภอ: สำหรับถนนสายยาวที่ผ่านหลายอำเภอ"""
    prov_clause, prov_params = _province_ilike_clause("", province)
    sql = f"""
        SELECT
            district_name,
            province_name,
            SUM(accident_count)   AS accident_count,
            SUM(death_count)      AS death_count,
            SUM(serious_injured)  AS serious_count,
            MAX(hotspot_score)    AS hotspot_score,
            MAX(dominant_cause)   AS dominant_cause
        FROM mart_province_road
        WHERE {prov_clause}
          AND road_name ILIKE %s
          AND year_no BETWEEN %s AND %s
        GROUP BY district_name, province_name
        ORDER BY death_count DESC, accident_count DESC
    """
    try:
        rows = query_db(sql, tuple(prov_params + [f"%{road_name.strip()}%", year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลสำหรับถนน '{road_name}' ในพื้นที่ '{province}'"

    year_label = f"พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(year_end)}"
    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    total_acc = sum(r["accident_count"] or 0 for r in rows)
    total_dth = sum(r["death_count"] or 0 for r in rows)
    lines = [
        f"[Road-District] '{road_name}' แยกตามอำเภอ — {prov_label} ({year_label})",
        f"  รวม: อุบัติเหตุ {total_acc:,} ครั้ง  เสียชีวิต {total_dth:,} ราย  (ผ่าน {len(rows)} อำเภอ)",
        "",
        f"  {'อำเภอ':<22} {'จังหวัด':<15} {'อุบัติเหตุ':>10} {'เสียชีวิต':>10} {'สาหัส':>7} {'คะแนน':>8} {'สาเหตุหลัก'}",
        "  " + "-" * 100,
    ]
    for r in rows:
        lines.append(
            f"  {(r['district_name'] or 'ไม่ระบุ'):<22} "
            f"{r['province_name']:<15} "
            f"{r['accident_count'] or 0:>10,} "
            f"{r['death_count'] or 0:>10,} "
            f"{r['serious_count'] or 0:>7,} "
            f"{float(r['hotspot_score'] or 0):>8.0f} "
            f"  {r['dominant_cause'] or 'N/A'}"
        )
    return "\n".join(lines)


@tool("query_road_district_breakdown")
def query_road_district_breakdown(province: str = "", road_name: str = "",
                                   year_start: int = 2021, year_end: int = 2026) -> str:
    """ดูอุบัติเหตุของถนนสายหนึ่งแยกตามอำเภอที่ถนนนั้นผ่าน.

    ใช้เมื่อต้องการรู้ว่าถนนสายนั้นผ่านอำเภอใดบ้าง และแต่ละอำเภอมีอุบัติเหตุกี่ครั้ง
    เหมาะสำหรับถนนสายยาวข้ามอำเภอ เช่น ตระการพืชผล - ห้วยยาง, วงแหวนรอบเมืองอุบลราชธานี

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        road_name: ชื่อถนน (บางส่วนก็ได้ ใช้ ILIKE) เช่น 'ตระการพืชผล'
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_road_district_breakdown(province, road_name, year_start, year_end)


def _classify_road_type_sql(road_type_col: str, road_code_col: str) -> str:
    """Return SQL CASE expression to classify road as สายหลัก/สายรอง/ไม่ระบุ."""
    return f"""CASE
        WHEN {road_type_col} IN ('กรมทางหลวง','การทางพิเศษแห่งประเทศไทย') THEN 'สายหลัก'
        WHEN {road_type_col} = 'กรมทางหลวงชนบท' THEN 'สายรอง'
        WHEN {road_code_col} ~ '^[0-9]+$' THEN 'สายหลัก'
        WHEN {road_code_col} IS NOT NULL AND {road_code_col} !~ '^[0-9]+$' THEN 'สายรอง'
        ELSE 'ไม่ระบุ'
    END"""


def _query_district_road_comparison(province: str,
                                     year_start: int = 2021,
                                     year_end: int = 2026) -> str:
    """Q2: ตารางผู้เสียชีวิตบนถนนสายหลักและสายรองแยกตามอำเภอ"""
    clause, params = _province_ilike_clause("", province)
    sql = f"""
        SELECT
            district_name,
            province_name,
            SUM(accident_count)                                            AS total_acc,
            SUM(death_count)                                               AS total_deaths,
            SUM(serious_injured)                                           AS total_serious,
            COALESCE(SUM(CASE WHEN road_type_label = 'สายหลัก'
                              THEN death_count ELSE 0 END), 0)             AS main_deaths,
            COALESCE(SUM(CASE WHEN road_type_label = 'สายรอง'
                              THEN death_count ELSE 0 END), 0)             AS secondary_deaths,
            COALESCE(SUM(CASE WHEN road_type_label = 'ไม่ระบุ'
                              THEN death_count ELSE 0 END), 0)             AS unknown_deaths,
            COALESCE(SUM(CASE WHEN road_type_label = 'สายหลัก'
                              THEN accident_count ELSE 0 END), 0)          AS main_acc,
            COALESCE(SUM(CASE WHEN road_type_label = 'สายรอง'
                              THEN accident_count ELSE 0 END), 0)          AS secondary_acc
        FROM mart_province_road
        WHERE {clause}
          AND year_no BETWEEN %s AND %s
        GROUP BY district_name, province_name
        ORDER BY province_name, district_name
    """
    try:
        rows = query_db(sql, tuple(params + [year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลอำเภอได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลอำเภอสำหรับ '{province}'"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    year_label = f"พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(year_end)}"
    lines = [
        f"[District Road Comparison] ผู้เสียชีวิตบนถนนสายหลักและสายรองแยกตามอำเภอ — {prov_label} ({year_label})",
        f"  {'อำเภอ':<22} {'จังหวัด':<15} {'เสียชีวิตรวม':>12} {'สายหลัก(ตาย)':>13} {'สายรอง(ตาย)':>12} {'ไม่ระบุ(ตาย)':>13} {'อุบัติ(สายหลัก)':>15} {'อุบัติ(สายรอง)':>14}",
        "  " + "-" * 125,
    ]
    tot_acc = tot_d = tot_m = tot_s = tot_u = tot_ma = tot_sa = 0
    for r in rows:
        lines.append(
            f"  {(r['district_name'] or 'ไม่ระบุ'):<22} "
            f"{r['province_name']:<15} "
            f"{r['total_deaths'] or 0:>12,} "
            f"{r['main_deaths'] or 0:>13,} "
            f"{r['secondary_deaths'] or 0:>12,} "
            f"{r['unknown_deaths'] or 0:>13,} "
            f"{r['main_acc'] or 0:>15,} "
            f"{r['secondary_acc'] or 0:>14,}"
        )
        tot_acc += r['total_acc'] or 0
        tot_d   += r['total_deaths'] or 0
        tot_m   += r['main_deaths'] or 0
        tot_s   += r['secondary_deaths'] or 0
        tot_u   += r['unknown_deaths'] or 0
        tot_ma  += r['main_acc'] or 0
        tot_sa  += r['secondary_acc'] or 0
    lines.append("  " + "-" * 125)
    lines.append(
        f"  {'รวม':<22} {'':<15} "
        f"{tot_d:>12,} "
        f"{tot_m:>13,} "
        f"{tot_s:>12,} "
        f"{tot_u:>13,} "
        f"{tot_ma:>15,} "
        f"{tot_sa:>14,}"
    )
    note_parts = []
    if tot_u > 0:
        note_parts.append(f"ไม่ระบุ = road_type/road_code ไม่มีข้อมูล ({tot_u:,} ราย)")
    note_parts.append("สายหลัก = กรมทางหลวง / รหัสตัวเลขล้วน | สายรอง = กรมทางหลวงชนบท / รหัสมีอักษรนำ")
    lines.append(f"\n  หมายเหตุ: {' | '.join(note_parts)}")
    return "\n".join(lines)


@tool("query_district_road_comparison")
def query_district_road_comparison(province: str = "",
                                    year_start: int = 2021,
                                    year_end: int = 2026) -> str:
    """Group 1 Q2: อำเภอใดมีผู้เสียชีวิตบนถนนสายรองมากกว่าถนนสายหลัก.

    ใช้ตอบคำถาม: ชี้เป้าให้ ศปถ.อำเภอ ลงไปคุมเข้มด่านชุมชน
    ข้อมูลจาก: fact_accident_event + dim_geography + dim_road_segment

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_district_road_comparison(province, year_start, year_end)


def _query_fatal_timeband(province: str,
                          year_start: int = 2021,
                          year_end: int = 2026) -> str:
    """Q3: จุดเสี่ยงที่มีผู้เสียชีวิต มักเกิดช่วงเวลาใด"""
    clause, params = _province_ilike_clause("g", province)
    sql = f"""
        SELECT
            EXTRACT(HOUR FROM e.event_datetime)::int AS hour_of_day,
            COUNT(*)                AS total_accidents,
            SUM(e.death_count)      AS total_deaths,
            SUM(e.serious_injured)  AS total_serious
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND e.event_datetime IS NOT NULL
          AND e.death_count > 0
          AND (e.csv_year BETWEEN %s AND %s OR e.csv_year IS NULL)
        GROUP BY hour_of_day
        ORDER BY total_deaths DESC
        LIMIT 24
    """
    try:
        rows = query_db(sql, tuple(params + [year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลช่วงเวลาได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลช่วงเวลาเสียชีวิตสำหรับ '{province}'"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    year_label = f"พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(year_end)}"
    top5 = {r["hour_of_day"] for r in rows[:5]}
    lines = [
        f"[Fatal Timeband] ช่วงเวลาที่มีผู้เสียชีวิตสูงสุด — {prov_label} ({year_label})",
        f"  {'ชั่วโมง':>7} {'เสียชีวิต':>10} {'อุบัติเหตุรวม':>13} {'สาหัส':>7}  ความเสี่ยง",
        "  " + "-" * 55,
    ]
    for r in sorted(rows, key=lambda x: x["hour_of_day"] or 0):
        h = r["hour_of_day"] or 0
        flag = " ◀ เสี่ยงสูง" if h in top5 else ""
        lines.append(
            f"  {h:02d}:00   "
            f"{r['total_deaths'] or 0:>10,} "
            f"{r['total_accidents'] or 0:>13,} "
            f"{r['total_serious'] or 0:>7,}"
            f"{flag}"
        )
    lines.append(f"\n  ช่วงเสี่ยงสูงสุด 5 อันดับ: {', '.join(f'{h:02d}:00' for h in sorted(top5))}")
    return "\n".join(lines)


@tool("query_fatal_timeband")
def query_fatal_timeband(province: str = "",
                         year_start: int = 2021,
                         year_end: int = 2026) -> str:
    """Group 1 Q3: ช่วงเวลาที่มีผู้เสียชีวิตสูงสุด เพื่อจัด EMS และตั้งจุดสกัด.

    ข้อมูลจาก: fact_accident_event + dim_geography

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_fatal_timeband(province, year_start, year_end)


def _query_weather_accident_stats(province: str,
                                   year_start: int = 2021,
                                   year_end: int = 2026) -> str:
    """Q4/Q5: weather_condition + accident_type fallback (light/road_condition = NULL)"""
    clause, params = _province_ilike_clause("g", province)
    sql = f"""
        SELECT
            e.weather_condition,
            e.accident_type,
            COUNT(*)               AS accident_count,
            SUM(e.death_count)     AS death_count,
            SUM(e.serious_injured) AS serious_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND (e.csv_year BETWEEN %s AND %s OR e.csv_year IS NULL)
        GROUP BY e.weather_condition, e.accident_type
        ORDER BY death_count DESC
        LIMIT 30
    """
    try:
        rows = query_db(sql, tuple(params + [year_start, year_end]))
    except Exception as exc:
        return f"{_LIGHT_ROAD_NULL_NOTE}\nไม่สามารถดึงข้อมูลได้: {exc}"

    if not rows:
        return f"{_LIGHT_ROAD_NULL_NOTE}\nไม่พบข้อมูลสำหรับ '{province}'"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    year_label = f"พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(year_end)}"
    lines = [
        f"[Weather/Accident Type Analysis] — {prov_label} ({year_label})",
        _LIGHT_ROAD_NULL_NOTE,
        "(ใช้ weather_condition + accident_type แทน light_condition/road_condition ที่ไม่มีข้อมูล)",
        f"  {'สภาพอากาศ':<25} {'ลักษณะการเกิดเหตุ':<25} {'อุบัติเหตุ':>10} {'เสียชีวิต':>10} {'สาหัส':>7}",
        "  " + "-" * 85,
    ]
    for r in rows:
        lines.append(
            f"  {(r['weather_condition'] or 'ไม่ระบุ'):<25} "
            f"{(r['accident_type'] or 'ไม่ระบุ')[:23]:<25} "
            f"{r['accident_count'] or 0:>10,} "
            f"{r['death_count'] or 0:>10,} "
            f"{r['serious_count'] or 0:>7,}"
        )
    return "\n".join(lines)


@tool("query_weather_accident_stats")
def query_weather_accident_stats(province: str = "",
                                  year_start: int = 2021,
                                  year_end: int = 2026) -> str:
    """Group 1 Q4/Q5: สภาพอากาศและลักษณะการเกิดเหตุที่ทำให้เกิดผู้เสียชีวิต/บาดเจ็บสาหัสมากที่สุด.

    หมายเหตุ: light_condition และ road_condition เป็น NULL ทั้งหมดในฐานข้อมูล
    ใช้ weather_condition + accident_type เป็น proxy แทน
    ข้อมูลจาก: fact_accident_event + dim_geography

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_weather_accident_stats(province, year_start, year_end)


# ── Group 2: Behavioral (person-level) — fact_accident_person is EMPTY ─────────

def _person_data_unavailable(topic: str) -> str:
    return f"[{topic}]\n{_PERSON_EMPTY_NOTE}"


@tool("query_behavior_stats")
def query_behavior_stats(topic: str = "helmet") -> str:
    """Group 2 Q6-Q10: ข้อมูลพฤติกรรมเสี่ยง (หมวก/เข็มขัด/อายุ/เพศ/บทบาท).

    ⚠️ ไม่มีข้อมูล: fact_accident_person ว่างทั้งหมด — ไม่สามารถตอบคำถามกลุ่มนี้ได้

    Args:
        topic: หัวข้อที่ต้องการ เช่น 'helmet', 'seatbelt', 'age', 'sex', 'role'
    """
    topic_map = {
        "helmet": "การสวมหมวกกันน็อก",
        "seatbelt": "การคาดเข็มขัดนิรภัย",
        "age": "การกระจายตามกลุ่มอายุ",
        "sex": "การกระจายตามเพศ",
        "role": "บทบาทผู้ประสบเหตุ (ขับขี่/โดยสาร)",
    }
    label = topic_map.get(topic.lower(), topic)
    return _person_data_unavailable(label)


# ── Group 3: Temporal & Seasonal ──────────────────────────────────────────────

def _query_seasonal_comparison(province: str, month1: int = 4, month2: int = 11,
                                year_start: int = 2021, year_end: int = 2026) -> str:
    """Q11: เปรียบเทียบสาเหตุหลักระหว่างสองเดือน (เช่น เมษายน vs พฤศจิกายน)"""
    clause, params = _province_ilike_clause("g", province)
    sql = f"""
        SELECT
            EXTRACT(MONTH FROM e.event_datetime)::int AS month_no,
            e.accident_type,
            COUNT(*)               AS accident_count,
            SUM(e.death_count)     AS death_count,
            SUM(e.serious_injured) AS serious_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND EXTRACT(MONTH FROM e.event_datetime)::int IN (%s, %s)
          AND e.event_datetime IS NOT NULL
          AND (e.csv_year BETWEEN %s AND %s OR e.csv_year IS NULL)
        GROUP BY month_no, e.accident_type
        ORDER BY month_no, death_count DESC
    """
    try:
        rows = query_db(sql, tuple(params + [month1, month2, year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลตามฤดูกาลได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลสำหรับ '{province}' เดือน {month1} และ {month2}"

    month_names = {
        1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
        5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
        9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม",
    }
    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    lines = [
        f"[Seasonal Comparison] {month_names.get(month1,'?')} vs {month_names.get(month2,'?')} — {prov_label}",
        f"  {'เดือน':<14} {'ลักษณะการเกิดเหตุ':<30} {'อุบัติเหตุ':>10} {'เสียชีวิต':>10} {'สาหัส':>7}",
        "  " + "-" * 77,
    ]
    for r in rows[:20]:
        lines.append(
            f"  {month_names.get(r['month_no'], str(r['month_no'])):<14} "
            f"{(r['accident_type'] or 'ไม่ระบุ')[:28]:<30} "
            f"{r['accident_count'] or 0:>10,} "
            f"{r['death_count'] or 0:>10,} "
            f"{r['serious_count'] or 0:>7,}"
        )
    return "\n".join(lines)


@tool("query_seasonal_comparison")
def query_seasonal_comparison(province: str = "", month1: int = 4, month2: int = 11,
                               year_start: int = 2021, year_end: int = 2026) -> str:
    """Group 3 Q11: เปรียบเทียบสาเหตุอุบัติเหตุระหว่างสองเดือน (เช่น สงกรานต์ vs เดือนปกติ).

    ข้อมูลจาก: fact_accident_event + dim_geography

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        month1: เดือนแรก (1-12, default 4 = เมษายน/สงกรานต์)
        month2: เดือนที่สอง (1-12, default 11 = พฤศจิกายน)
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_seasonal_comparison(province, month1, month2, year_start, year_end)


def _query_weekend_vs_weekday(province: str,
                               year_start: int = 2021,
                               year_end: int = 2026) -> str:
    """Q12: เวลาเสี่ยงวันหยุด vs วันธรรมดา"""
    clause, params = _province_ilike_clause("g", province)
    sql = f"""
        SELECT
            CASE WHEN EXTRACT(DOW FROM e.event_datetime)::int IN (0,6) THEN 'วันหยุด' ELSE 'วันธรรมดา' END AS day_type,
            EXTRACT(HOUR FROM e.event_datetime)::int AS hour_of_day,
            COUNT(*)               AS accident_count,
            SUM(e.death_count)     AS death_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND e.event_datetime IS NOT NULL
          AND (e.csv_year BETWEEN %s AND %s OR e.csv_year IS NULL)
        GROUP BY day_type, hour_of_day
        ORDER BY day_type, accident_count DESC
    """
    try:
        rows = query_db(sql, tuple(params + [year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลวันหยุด/วันธรรมดาได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลสำหรับ '{province}'"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    year_label = f"พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(year_end)}"
    from collections import defaultdict
    by_type: dict = defaultdict(list)
    for r in rows:
        by_type[r["day_type"]].append(r)

    lines = [f"[Weekend vs Weekday] รูปแบบชั่วโมงเสี่ยง — {prov_label} ({year_label})"]
    for day_type, day_rows in sorted(by_type.items()):
        top3 = sorted(day_rows, key=lambda x: x["accident_count"] or 0, reverse=True)[:3]
        lines.append(f"\n  {day_type}:")
        lines.append(f"    {'ชั่วโมง':>7} {'อุบัติเหตุ':>10} {'เสียชีวิต':>10}")
        for r in top3:
            h = r["hour_of_day"] or 0
            lines.append(f"    {h:02d}:00   {r['accident_count'] or 0:>10,} {r['death_count'] or 0:>10,}")
    return "\n".join(lines)


@tool("query_weekend_vs_weekday")
def query_weekend_vs_weekday(province: str = "",
                             year_start: int = 2021,
                             year_end: int = 2026) -> str:
    """Group 3 Q12: เปรียบเทียบช่วงเวลาเสี่ยงวันหยุดเสาร์-อาทิตย์ vs วันธรรมดา.

    ข้อมูลจาก: fact_accident_event + dim_geography

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_weekend_vs_weekday(province, year_start, year_end)


def _query_monthly_vehicle_pattern(province: str,
                                    year_start: int = 2021,
                                    year_end: int = 2026) -> str:
    """Q13: เดือนใดรถบรรทุก/รถเกษตรพุ่งสูง"""
    clause, params = _province_ilike_clause("g", province)
    sql = f"""
        SELECT
            EXTRACT(MONTH FROM e.event_datetime)::int AS month_no,
            e.vehicle_type,
            COUNT(*)               AS accident_count,
            SUM(e.death_count)     AS death_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND e.event_datetime IS NOT NULL
          AND (e.vehicle_type ILIKE '%บรรทุก%' OR e.vehicle_type ILIKE '%อีแต๋น%'
               OR e.vehicle_type ILIKE '%เกษตร%' OR e.vehicle_type ILIKE '%กระบะ%')
          AND (e.csv_year BETWEEN %s AND %s OR e.csv_year IS NULL)
        GROUP BY month_no, e.vehicle_type
        ORDER BY month_no, accident_count DESC
    """
    try:
        rows = query_db(sql, tuple(params + [year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลรถบรรทุก/เกษตรได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลรถบรรทุก/รถเกษตรสำหรับ '{province}'"

    month_names = {
        1: "ม.ค.", 2: "ก.พ.", 3: "มี.ค.", 4: "เม.ย.", 5: "พ.ค.", 6: "มิ.ย.",
        7: "ก.ค.", 8: "ส.ค.", 9: "ก.ย.", 10: "ต.ค.", 11: "พ.ย.", 12: "ธ.ค.",
    }
    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    from collections import defaultdict
    monthly: dict = defaultdict(int)
    for r in rows:
        monthly[r["month_no"]] += (r["accident_count"] or 0)

    lines = [
        f"[Monthly Vehicle Pattern] รถบรรทุก/เกษตร ตามเดือน — {prov_label}",
        f"  {'เดือน':<8} {'อุบัติเหตุรวม':>13}",
        "  " + "-" * 25,
    ]
    for m in sorted(monthly):
        bar = "█" * int(monthly[m] / max(monthly.values()) * 15)
        lines.append(f"  {month_names.get(m, str(m)):<8} {monthly[m]:>13,}  {bar}")
    peak_month = max(monthly, key=lambda x: monthly[x])
    lines.append(f"\n  เดือนสูงสุด: {month_names.get(peak_month, str(peak_month))} ({monthly[peak_month]:,} ครั้ง)")
    return "\n".join(lines)


@tool("query_monthly_vehicle_pattern")
def query_monthly_vehicle_pattern(province: str = "",
                                   year_start: int = 2021,
                                   year_end: int = 2026) -> str:
    """Group 3 Q13: เดือนใดรถบรรทุก/รถเกษตร (อีแต๋น/กระบะ) พุ่งสูงผิดปกติ.

    ข้อมูลจาก: fact_accident_event + dim_geography

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_monthly_vehicle_pattern(province, year_start, year_end)


def _query_late_night_vehicles(province: str,
                                year_start: int = 2021,
                                year_end: int = 2026) -> str:
    """Q14/Q15: ยานพาหนะหลังเที่ยงคืน (00:00-05:00)"""
    clause, params = _province_ilike_clause("g", province)
    sql = f"""
        SELECT
            e.vehicle_type,
            COUNT(*)               AS accident_count,
            SUM(e.death_count)     AS death_count,
            SUM(e.serious_injured) AS serious_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND e.event_datetime IS NOT NULL
          AND EXTRACT(HOUR FROM e.event_datetime)::int BETWEEN 0 AND 5
          AND (e.csv_year BETWEEN %s AND %s OR e.csv_year IS NULL)
        GROUP BY e.vehicle_type
        ORDER BY death_count DESC
        LIMIT 15
    """
    try:
        rows = query_db(sql, tuple(params + [year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลช่วงกลางคืนได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลช่วง 00:00-05:00 สำหรับ '{province}'"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    year_label = f"พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(year_end)}"
    lines = [
        f"[Late Night Vehicles] ยานพาหนะช่วง 00:00-05:00 — {prov_label} ({year_label})",
        f"  {'ยานพาหนะ':<30} {'อุบัติเหตุ':>10} {'เสียชีวิต':>10} {'สาหัส':>7}",
        "  " + "-" * 65,
    ]
    for r in rows:
        lines.append(
            f"  {(r['vehicle_type'] or 'ไม่ระบุ')[:28]:<30} "
            f"{r['accident_count'] or 0:>10,} "
            f"{r['death_count'] or 0:>10,} "
            f"{r['serious_count'] or 0:>7,}"
        )
    return "\n".join(lines)


@tool("query_late_night_vehicles")
def query_late_night_vehicles(province: str = "",
                              year_start: int = 2021,
                              year_end: int = 2026) -> str:
    """Group 3 Q14/Q15: ยานพาหนะที่มีผู้เสียชีวิตมากที่สุดในช่วงหลังเที่ยงคืน (00:00-05:00).

    ข้อมูลจาก: fact_accident_event + dim_geography

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_late_night_vehicles(province, year_start, year_end)


# ── Group 4: KPI Monitoring & Evaluation ──────────────────────────────────────

def _query_kpi_trend(province: str, year_start: int = 2021, year_end: int = 2026) -> str:
    """Q16: แนวโน้มผู้เสียชีวิตรายปี + อัตราลดลง"""
    clause, params = _province_ilike_clause("", province)
    sql = f"""
        SELECT year_no, province_name,
               accident_count, death_count, serious_injured, injured_count,
               top_cause, top_vehicle
        FROM mart_province_year
        WHERE {clause}
          AND year_no BETWEEN %s AND %s
        ORDER BY province_name, year_no
    """
    try:
        rows = query_db(sql, tuple(params + [year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูล KPI ได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูล KPI สำหรับ '{province}' ปี CE {year_start}-{year_end}"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    from collections import defaultdict
    by_prov: dict = defaultdict(list)
    for r in rows:
        by_prov[r["province_name"]].append(r)

    lines = [
        f"[KPI Trend] แนวโน้มรายปี (CE {year_start}-{year_end} / พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(year_end)}) — {prov_label}",
        f"  {_YEAR_NOTE}",
    ]
    for prov, prows in sorted(by_prov.items()):
        lines.append(f"\n  {prov}:")
        lines.append(
            f"    {'ปี ค.ศ.':>7} {'พ.ศ.':>6} {'อุบัติเหตุ':>10} {'เสียชีวิต':>10} {'Δ%เสียชีวิต':>11} {'สาหัส':>8}"
        )
        lines.append("    " + "-" * 56)
        prev_death = None
        for r in prows:
            pct = ""
            if prev_death is not None and prev_death > 0:
                chg = ((r["death_count"] or 0) - prev_death) / prev_death * 100
                pct = f"{'+' if chg > 0 else ''}{chg:.1f}%"
            lines.append(
                f"    {r['year_no']:>7} {_ce_to_be(r['year_no']):>6} "
                f"{r['accident_count'] or 0:>10,} "
                f"{r['death_count'] or 0:>10,} "
                f"{pct:>11} "
                f"{r['serious_injured'] or 0:>8,}"
            )
            prev_death = r["death_count"] or 0
    return "\n".join(lines)


@tool("query_kpi_trend")
def query_kpi_trend(province: str = "", year_start: int = 2021, year_end: int = 2026) -> str:
    """Group 4 Q16/Q19: แนวโน้มอุบัติเหตุ/เสียชีวิตรายปี + อัตราการเปลี่ยนแปลง.

    ข้อมูลจาก: mart_province_year
    ปีในฐานข้อมูลเป็น ค.ศ. (CE) — แปลงเป็น พ.ศ. โดย CE + 543

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_kpi_trend(province, year_start, year_end)


def _query_serious_injury_ratio(province: str = "", year: int = 2024) -> str:
    """Q17: อัตราส่วนผู้บาดเจ็บสาหัสต่ออุบัติเหตุ 1 ครั้ง"""
    clause, params = _province_ilike_clause("", province)
    sql = f"""
        SELECT province_name,
               SUM(accident_count)  AS total_accidents,
               SUM(death_count)     AS total_deaths,
               SUM(serious_injured) AS total_serious,
               CASE WHEN SUM(accident_count) > 0
                    THEN ROUND(SUM(serious_injured)::numeric / SUM(accident_count), 4)
                    ELSE 0 END AS serious_ratio
        FROM mart_province_year
        WHERE {clause}
          AND year_no = %s
        GROUP BY province_name
        ORDER BY serious_ratio DESC
    """
    try:
        rows = query_db(sql, tuple(params + [year]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลอัตราส่วนสาหัสได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูล CE {year} (พ.ศ. {_ce_to_be(year)}) สำหรับ '{province}'"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    lines = [
        f"[Serious Injury Ratio] อัตราส่วนบาดเจ็บสาหัสต่ออุบัติเหตุ 1 ครั้ง",
        f"  ปี CE {year} (พ.ศ. {_ce_to_be(year)}) — {prov_label}",
        f"  {'จังหวัด':<18} {'อุบัติเหตุ':>10} {'สาหัส':>8} {'อัตราส่วน':>10} {'เสียชีวิต':>10}",
        "  " + "-" * 62,
    ]
    for r in rows:
        lines.append(
            f"  {r['province_name']:<18} "
            f"{r['total_accidents'] or 0:>10,} "
            f"{r['total_serious'] or 0:>8,} "
            f"{float(r['serious_ratio'] or 0):>10.4f} "
            f"{r['total_deaths'] or 0:>10,}"
        )
    return "\n".join(lines)


@tool("query_serious_injury_ratio")
def query_serious_injury_ratio(province: str = "", year: int = 2024) -> str:
    """Group 4 Q17: อัตราส่วนผู้บาดเจ็บสาหัสต่ออุบัติเหตุ 1 ครั้ง (สะท้อนความรุนแรง + EMS).

    ข้อมูลจาก: mart_province_year

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year: ปี ค.ศ. (CE) เช่น 2024 = พ.ศ. 2567
    """
    return _query_serious_injury_ratio(province, year)


def _query_top_cause_shift(province: str, year1: int = 2023, year2: int = 2024) -> str:
    """Q18: สาเหตุหลักเปลี่ยนแปลงระหว่าง 2 ปีหรือไม่"""
    clause, params = _province_ilike_clause("", province)
    sql = f"""
        SELECT year_no, province_name, top_cause, top_vehicle,
               accident_count, death_count
        FROM mart_province_year
        WHERE {clause}
          AND year_no IN (%s, %s)
        ORDER BY province_name, year_no
    """
    try:
        rows = query_db(sql, tuple(params + [year1, year2]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลการเปลี่ยนแปลงสาเหตุได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูล CE {year1} หรือ {year2} สำหรับ '{province}'"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    from collections import defaultdict
    by_prov: dict = defaultdict(dict)
    for r in rows:
        by_prov[r["province_name"]][r["year_no"]] = r

    lines = [
        f"[Top Cause Shift] การเปลี่ยนสาเหตุหลัก CE {year1}→{year2} "
        f"(พ.ศ. {_ce_to_be(year1)}→{_ce_to_be(year2)}) — {prov_label}",
    ]
    for prov, ydata in sorted(by_prov.items()):
        r1 = ydata.get(year1, {})
        r2 = ydata.get(year2, {})
        cause_changed = r1.get("top_cause") != r2.get("top_cause")
        lines.append(
            f"\n  {prov}:"
            f"\n    พ.ศ. {_ce_to_be(year1)}: สาเหตุ = {r1.get('top_cause','N/A')}, เสียชีวิต = {r1.get('death_count', 0):,}"
            f"\n    พ.ศ. {_ce_to_be(year2)}: สาเหตุ = {r2.get('top_cause','N/A')}, เสียชีวิต = {r2.get('death_count', 0):,}"
            f"\n    {'⚠️ สาเหตุหลักเปลี่ยนแปลง' if cause_changed else '✓ สาเหตุหลักเหมือนเดิม'}"
        )
    return "\n".join(lines)


@tool("query_top_cause_shift")
def query_top_cause_shift(province: str = "", year1: int = 2023, year2: int = 2024) -> str:
    """Group 4 Q18: สาเหตุการตายอันดับ 1 เปลี่ยนแปลงระหว่าง 2 ปีหรือไม่.

    ข้อมูลจาก: mart_province_year

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year1: ปีแรก ค.ศ. (default 2023)
        year2: ปีที่สอง ค.ศ. (default 2024)
    """
    return _query_top_cause_shift(province, year1, year2)


def _query_district_death_vs_accident(province: str,
                                       year_start: int = 2021,
                                       year_end: int = 2026) -> str:
    """Q19: อำเภอที่อุบัติเหตุลดแต่เสียชีวิตเพิ่ม"""
    clause, params = _province_ilike_clause("g", province)
    mid_year = (year_start + year_end) // 2
    sql = f"""
        SELECT
            g.district_name, g.province_name,
            SUM(CASE WHEN e.csv_year <= %s THEN 1 ELSE 0 END) AS acc_early,
            SUM(CASE WHEN e.csv_year > %s THEN 1 ELSE 0 END) AS acc_late,
            SUM(CASE WHEN e.csv_year <= %s THEN e.death_count ELSE 0 END) AS death_early,
            SUM(CASE WHEN e.csv_year > %s THEN e.death_count ELSE 0 END) AS death_late
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND e.csv_year BETWEEN %s AND %s
        GROUP BY g.district_name, g.province_name
        HAVING SUM(e.death_count) > 0
        ORDER BY g.province_name, g.district_name
    """
    try:
        rows = query_db(sql, tuple([mid_year, mid_year, mid_year, mid_year] + params + [year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลอำเภอได้: {exc}"

    if not rows:
        return f"ไม่พบข้อมูลสำหรับ '{province}'"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    anomalies = [
        r for r in rows
        if (r["acc_late"] or 0) < (r["acc_early"] or 0)
        and (r["death_late"] or 0) > (r["death_early"] or 0)
    ]
    year_label_early = f"พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(mid_year)}"
    year_label_late = f"พ.ศ. {_ce_to_be(mid_year+1)}-{_ce_to_be(year_end)}"
    lines = [
        f"[Accident↓ Death↑] อำเภอที่อุบัติเหตุลดแต่เสียชีวิตเพิ่ม — {prov_label}",
        f"  (เปรียบเทียบ {year_label_early} vs {year_label_late})",
    ]
    if not anomalies:
        lines.append("  ไม่พบอำเภอที่มีรูปแบบ 'อุบัติเหตุลด แต่เสียชีวิตเพิ่ม'")
    else:
        lines.append(
            f"  {'อำเภอ':<20} {'จังหวัด':<15} {'อุบัติเหตุ(เก่า)':>16} "
            f"{'อุบัติเหตุ(ใหม่)':>16} {'เสียชีวิต(เก่า)':>15} {'เสียชีวิต(ใหม่)':>15}"
        )
        lines.append("  " + "-" * 100)
        for r in anomalies:
            lines.append(
                f"  {(r['district_name'] or 'ไม่ระบุ'):<20} "
                f"{r['province_name']:<15} "
                f"{r['acc_early'] or 0:>16,} "
                f"{r['acc_late'] or 0:>16,} "
                f"{r['death_early'] or 0:>15,} "
                f"{r['death_late'] or 0:>15,}"
            )
    return "\n".join(lines)


@tool("query_district_death_vs_accident")
def query_district_death_vs_accident(province: str = "",
                                      year_start: int = 2021,
                                      year_end: int = 2026) -> str:
    """Group 4 Q19: อำเภอที่อุบัติเหตุลดลงแต่จำนวนผู้เสียชีวิตกลับเพิ่มขึ้น (Mass Casualty pattern).

    ข้อมูลจาก: fact_accident_event + dim_geography

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_district_death_vs_accident(province, year_start, year_end)


def _query_district_summary(province: str, district: str = "",
                             year_start: int = 2021,
                             year_end: int = 2026) -> str:
    """สรุปอุบัติเหตุรายอำเภอ: อุบัติเหตุ/เสียชีวิต/สาหัส/สาเหตุ/ถนนเสี่ยง"""
    clause, params = _province_ilike_clause("g", province)
    if district.strip():
        clause = f"({clause} AND g.district_name ILIKE %s)"
        params = params + [f"%{district.strip()}%"]

    sql = f"""
        SELECT
            g.district_name,
            g.province_name,
            COUNT(*)                          AS accident_count,
            COALESCE(SUM(e.death_count), 0)   AS death_count,
            COALESCE(SUM(e.serious_injured), 0) AS serious_count,
            COALESCE(SUM(e.injured_count), 0)  AS injured_count,
            MODE() WITHIN GROUP (ORDER BY e.accident_type)  AS top_cause,
            MODE() WITHIN GROUP (ORDER BY e.vehicle_type)   AS top_vehicle,
            COUNT(DISTINCT e.road_segment_id)               AS road_count
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE {clause}
          AND (e.csv_year BETWEEN %s AND %s OR e.csv_year IS NULL)
        GROUP BY g.district_name, g.province_name
        HAVING COUNT(*) > 0
        ORDER BY death_count DESC, accident_count DESC
        LIMIT 30
    """
    try:
        rows = query_db(sql, tuple(params + [year_start, year_end]))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูลอำเภอได้: {exc}"

    if not rows:
        label = f"อำเภอ{district.strip()} จังหวัด{province.strip()}" if district.strip() else province.strip() or "เขต 10"
        return f"ไม่พบข้อมูลอำเภอสำหรับ {label}"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    dist_label = f" > อำเภอ{district.strip()}" if district.strip() else ""
    year_label = f"พ.ศ. {_ce_to_be(year_start)}-{_ce_to_be(year_end)}"

    lines = [
        f"[District Summary] สรุปรายอำเภอ — {prov_label}{dist_label} ({year_label})",
        f"  {'อำเภอ':<22} {'จังหวัด':<15} {'อุบัติเหตุ':>10} {'เสียชีวิต':>10} {'สาหัส':>7} {'สาเหตุหลัก':<28} {'ยานพาหนะ'}",
        "  " + "-" * 115,
    ]
    for r in rows:
        lines.append(
            f"  {(r['district_name'] or 'ไม่ระบุ'):<22} "
            f"{r['province_name']:<15} "
            f"{r['accident_count'] or 0:>10,} "
            f"{r['death_count'] or 0:>10,} "
            f"{r['serious_count'] or 0:>7,} "
            f"{(r['top_cause'] or 'N/A')[:26]:<28} "
            f"{r['top_vehicle'] or 'N/A'}"
        )

    # Top road per district (only if single district or small result)
    if district.strip() and rows:
        sql_road = f"""
            SELECT rs.road_name, rs.road_code,
                   COUNT(*) AS acc,
                   SUM(e.death_count) AS deaths
            FROM fact_accident_event e
            JOIN dim_geography g ON e.geography_id = g.geography_id
            LEFT JOIN dim_road_segment rs ON e.road_segment_id = rs.road_segment_id
            WHERE ({clause})
              AND (e.csv_year BETWEEN %s AND %s OR e.csv_year IS NULL)
            GROUP BY rs.road_name, rs.road_code
            ORDER BY deaths DESC, acc DESC
            LIMIT 5
        """
        try:
            road_rows = query_db(sql_road, tuple(params + [year_start, year_end]))
            if road_rows:
                lines.append(f"\n  ถนนเสี่ยงสูงสุดในอำเภอ{district.strip()}:")
                lines.append(f"  {'ชื่อถนน':<40} {'รหัส':<12} {'อุบัติเหตุ':>10} {'เสียชีวิต':>10}")
                lines.append("  " + "-" * 75)
                for rr in road_rows:
                    rname = (rr["road_name"] or "ไม่ระบุ")[:38]
                    lines.append(
                        f"  {rname:<40} {(rr['road_code'] or ''):<12} "
                        f"{rr['acc'] or 0:>10,} {rr['deaths'] or 0:>10,}"
                    )
        except Exception:
            pass

    lines.append(f"\n  รวม: {len(rows)} อำเภอ | รวมอุบัติเหตุ: {sum(r['accident_count'] or 0 for r in rows):,} ครั้ง | เสียชีวิตรวม: {sum(r['death_count'] or 0 for r in rows):,} ราย")
    return "\n".join(lines)


@tool("query_district_summary")
def query_district_summary(province: str = "", district: str = "",
                            year_start: int = 2021, year_end: int = 2026) -> str:
    """สรุปสถิติอุบัติเหตุรายอำเภอ พร้อมถนนเสี่ยงสูงสุด.

    ใช้ตอบคำถามระดับอำเภอ เช่น:
    - อำเภอเมืองอุบลราชธานี มีถนนเสี่ยงสูงสุดคือถนนใด?
    - เปรียบเทียบอุบัติเหตุแต่ละอำเภอในจังหวัดมุกดาหาร
    - อำเภอใดในจังหวัดศรีสะเกษมีผู้เสียชีวิตมากที่สุด?

    ข้อมูลจาก: fact_accident_event + dim_geography + dim_road_segment

    Args:
        province: ชื่อจังหวัด (ภาษาไทย) หรือ '' สำหรับเขต 10
        district: ชื่ออำเภอ (ภาษาไทย) หรือ '' สำหรับทุกอำเภอในจังหวัด
        year_start: ปีเริ่มต้น ค.ศ. (default 2021)
        year_end: ปีสิ้นสุด ค.ศ. (default 2026)
    """
    return _query_district_summary(province, district, year_start, year_end)


def _query_province_executive_summary(province: str, year: int = 2024) -> str:
    """Q20: Executive Summary 1 หน้า สำหรับผู้บริหาร"""
    clause_year, params_year = _province_ilike_clause("", province)
    clause_ev, params_ev = _province_ilike_clause("g", province)

    sql_year = f"""
        SELECT province_name, accident_count, death_count, serious_injured,
               injured_count, top_cause, top_vehicle, top_timeband
        FROM mart_province_year
        WHERE {clause_year} AND year_no = %s
        ORDER BY province_name
    """
    sql_road = f"""
        SELECT road_name, road_code, SUM(hotspot_score) AS score,
               SUM(death_count) AS deaths,
               MAX(dominant_cause) AS cause
        FROM mart_province_road
        WHERE {_province_ilike_clause('', province)[0]}
        GROUP BY road_name, road_code
        ORDER BY score DESC
        LIMIT 3
    """
    _, params_road = _province_ilike_clause("", province)

    try:
        year_rows = query_db(sql_year, tuple(params_year + [year]))
        road_rows = query_db(sql_road, tuple(params_road))
    except Exception as exc:
        return f"ไม่สามารถดึงข้อมูล Executive Summary ได้: {exc}"

    if not year_rows:
        return f"ไม่พบข้อมูลปี CE {year} (พ.ศ. {_ce_to_be(year)}) สำหรับ '{province}'"

    prov_label = province.strip() or "เขตสุขภาพที่ 10"
    lines = [
        f"╔═══════════════════════════════════════════════════════════╗",
        f"  EXECUTIVE SUMMARY — {prov_label}",
        f"  ปี พ.ศ. {_ce_to_be(year)} (CE {year})",
        f"╚═══════════════════════════════════════════════════════════╝",
    ]
    for r in year_rows:
        lines += [
            f"\n  จังหวัด: {r['province_name']}",
            f"  ├─ อุบัติเหตุทั้งหมด : {r['accident_count'] or 0:,} ครั้ง",
            f"  ├─ ผู้เสียชีวิต      : {r['death_count'] or 0:,} ราย",
            f"  ├─ ผู้บาดเจ็บสาหัส  : {r['serious_injured'] or 0:,} ราย",
            f"  ├─ สาเหตุหลัก        : {r.get('top_cause') or 'N/A'}",
            f"  ├─ ยานพาหนะหลัก      : {r.get('top_vehicle') or 'N/A'}",
            f"  └─ ช่วงเวลาเสี่ยงสูง : {r.get('top_timeband') or 'N/A'}",
        ]

    if road_rows:
        lines.append("\n  ถนนเสี่ยงสูงสุด Top 3:")
        for i, r in enumerate(road_rows, 1):
            rn = r["road_name"] or "ไม่ระบุ"
            lines.append(f"    {i}. {rn} (คะแนน {float(r['score'] or 0):.0f}, เสียชีวิต {r['deaths'] or 0:,}, สาเหตุ: {r['cause'] or 'N/A'})")

    lines.append(
        f"\n  ⚠️ ข้อมูลพฤติกรรม (helmet/seatbelt/อายุ/เพศ): ไม่มีในฐานข้อมูลปัจจุบัน"
    )
    return "\n".join(lines)


@tool("query_province_executive_summary")
def query_province_executive_summary(province: str = "มุกดาหาร", year: int = 2024) -> str:
    """Group 4 Q20: Executive Summary 1 หน้าสำหรับผู้บริหาร — รวม KPI, ถนนเสี่ยง, สาเหตุหลัก.

    ข้อมูลจาก: mart_province_year + mart_province_road

    Args:
        province: ชื่อจังหวัด (ภาษาไทย)
        year: ปี ค.ศ. (CE) เช่น 2024 = พ.ศ. 2567
    """
    return _query_province_executive_summary(province, year)


# ── Free-form SQL fallback ─────────────────────────────────────────────────────

@tool("execute_accident_sql")
def execute_accident_sql(sql_query: str) -> str:
    """Execute a custom SELECT query on the accident database (free-form fallback).

    Use this tool when none of the specific tools above cover the question.
    Only SELECT or WITH queries are allowed.

    Available tables: fact_accident_event, fact_accident_person (empty),
      dim_geography, dim_road_segment, dim_time, dim_source,
      mart_accident_summary, mart_accident_hotspot,
      mart_province_year, mart_province_road

    Args:
        sql_query: Valid PostgreSQL SELECT or WITH query.
    """
    sql = sql_query.strip()
    first_word = sql.split()[0].upper() if sql else ""
    if first_word not in ("SELECT", "WITH"):
        return json.dumps({"success": False, "error": "Only SELECT or WITH queries allowed"}, ensure_ascii=False)
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";") + " LIMIT 500"
    try:
        rows = query_db(sql)
        return json.dumps({
            "success": True,
            "rows": _serialize_rows(rows),
            "row_count": len(rows),
            "note": _YEAR_NOTE,
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc), "query": sql}, ensure_ascii=False)


@tool("get_accident_schema")
def get_accident_schema(table_name: str = "") -> str:
    """Get database schema / column list for accident tables.

    Args:
        table_name: Optional specific table. Empty = list all tables.
    """
    if not table_name:
        return json.dumps({
            "tables": [
                {"name": "fact_accident_event", "note": "Main fact table — event_datetime, geography_id, vehicle_type, death_count, serious_injured, weather_condition, accident_type, severity_level"},
                {"name": "fact_accident_person", "note": "EMPTY — no data (age, sex, helmet_used, seatbelt_used not available)"},
                {"name": "dim_geography", "note": "province_name, district_name, latitude, longitude"},
                {"name": "dim_road_segment", "note": "road_name, road_code, km_marker (road_name mostly NULL)"},
                {"name": "mart_province_year", "note": "year_no(CE), province_name, accident_count, death_count, serious_injured, top_cause, top_vehicle"},
                {"name": "mart_province_road", "note": "road_name, hotspot_score, accident_count, death_count, serious_injured, dominant_cause (road_name mostly NULL)"},
                {"name": "mart_accident_summary", "note": "year_no(CE), month_no, geography_id, accident_count, death_count, high_risk_timeband"},
                {"name": "mart_accident_hotspot", "note": "hotspot_score, accident_count, death_count, dominant_timeband"},
            ],
            "data_limitations": {
                "fact_accident_person": "EMPTY — no person-level data",
                "light_condition": "NULL in all rows — not in CSV",
                "road_condition": "NULL in all rows — not in CSV",
                "road_name": "Mostly NULL/empty in mart_province_road",
                "year_format": "CE (Christian Era) — add 543 for พ.ศ.",
            }
        }, ensure_ascii=False)

    sql = """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
    """
    try:
        rows = query_db(sql, (table_name,))
        return json.dumps({"table": table_name, "columns": [{"name": r["column_name"], "type": r["data_type"]} for r in rows]}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


# ── Tool list for agent ────────────────────────────────────────────────────────

ACCIDENT_CHAT_TOOLS = [
    query_hotspot_roads,
    query_district_road_comparison,
    query_fatal_timeband,
    query_weather_accident_stats,
    query_behavior_stats,
    query_seasonal_comparison,
    query_weekend_vs_weekday,
    query_monthly_vehicle_pattern,
    query_late_night_vehicles,
    query_kpi_trend,
    query_serious_injury_ratio,
    query_top_cause_shift,
    query_district_death_vs_accident,
    query_district_summary,
    query_road_district_breakdown,
    query_province_executive_summary,
    execute_accident_sql,
    get_accident_schema,
]
