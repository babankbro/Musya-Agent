"""Deep analysis: province-level query capability."""
import psycopg2
import psycopg2.extras

conn = psycopg2.connect('host=localhost port=5432 dbname=chat-aio user=postgres password=1234')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

print("=== 1. mart_accident_summary: sample with province ===")
cur.execute("""
    SELECT s.year_no, s.month_no, g.province_name,
           s.accident_count, s.injured_count, s.death_count, s.high_risk_timeband
    FROM mart_accident_summary s
    JOIN dim_geography g ON s.geography_id = g.geography_id
    WHERE g.province_name = 'กรุงเทพมหานคร'
    ORDER BY s.year_no, s.month_no
    LIMIT 12
""")
for r in cur.fetchall():
    print(f"  {r['year_no']}-{r['month_no']:02d} {r['province_name']}: "
          f"accidents={r['accident_count']}, injured={r['injured_count']}, deaths={r['death_count']}, "
          f"timeband={r['high_risk_timeband']}")

print("\n=== 2. mart_accident_summary: year-level rollup by province ===")
cur.execute("""
    SELECT s.year_no, g.province_name,
           SUM(s.accident_count) as accidents,
           SUM(s.injured_count) as injured,
           SUM(s.death_count) as deaths
    FROM mart_accident_summary s
    JOIN dim_geography g ON s.geography_id = g.geography_id
    GROUP BY s.year_no, g.province_name
    ORDER BY s.year_no, accidents DESC
    LIMIT 15
""")
for r in cur.fetchall():
    print(f"  {r['year_no']} {r['province_name']}: accidents={r['accidents']}, deaths={r['deaths']}")

print("\n=== 3. mart_accident_summary: missing year column? ===")
cur.execute("""SELECT column_name FROM information_schema.columns
    WHERE table_name='mart_accident_summary' ORDER BY ordinal_position""")
print("  columns:", [r[0] for r in cur.fetchall()])

print("\n=== 4. mart_accident_hotspot: top roads per province ===")
cur.execute("""
    SELECT g.province_name, r.road_name, r.road_code,
           h.accident_count, h.injured_count, h.death_count, h.hotspot_score
    FROM mart_accident_hotspot h
    JOIN dim_geography g ON h.geography_id = g.geography_id
    LEFT JOIN dim_road_segment r ON h.road_segment_id = r.road_segment_id
    WHERE g.province_name = 'เชียงใหม่'
    ORDER BY h.hotspot_score DESC
    LIMIT 8
""")
for r in cur.fetchall():
    print(f"  {r['province_name']} | {r['road_name']} ({r['road_code']}): "
          f"accidents={r['accident_count']}, score={r['hotspot_score']}")

print("\n=== 5. mart_accident_hotspot columns ===")
cur.execute("""SELECT column_name FROM information_schema.columns
    WHERE table_name='mart_accident_hotspot' ORDER BY ordinal_position""")
print("  columns:", [r[0] for r in cur.fetchall()])

print("\n=== 6. Missing: mart_province_year — does it exist? ===")
cur.execute("""SELECT table_name FROM information_schema.tables
    WHERE table_name LIKE 'mart_province%'""")
print("  province mart tables:", [r[0] for r in cur.fetchall()])

print("\n=== 7. NULL geography in fact ===")
cur.execute("""SELECT COUNT(*) FROM fact_accident_event WHERE geography_id IS NULL""")
print(f"  fact NULLs: {cur.fetchone()[0]} rows")

print("\n=== 8. Province year summary (direct from fact) ===")
cur.execute("""
    SELECT EXTRACT(YEAR FROM e.event_datetime)::INT AS yr,
           g.province_name,
           COUNT(*) AS accidents,
           SUM(e.death_count) AS deaths,
           SUM(e.injured_count) AS injured
    FROM fact_accident_event e
    JOIN dim_geography g ON e.geography_id = g.geography_id
    GROUP BY yr, g.province_name
    ORDER BY yr, accidents DESC
    LIMIT 20
""")
for r in cur.fetchall():
    print(f"  {r['yr']} {r['province_name']}: accidents={r['accidents']}, deaths={r['deaths']}")

print("\n=== 9. Roads per province (top 5 per province for 3 provinces) ===")
cur.execute("""
    SELECT g.province_name, r.road_name, r.road_code,
           COUNT(e.accident_id) AS accidents,
           SUM(e.death_count) AS deaths,
           EXTRACT(YEAR FROM e.event_datetime)::INT AS yr
    FROM fact_accident_event e
    JOIN dim_geography g ON e.geography_id = g.geography_id
    JOIN dim_road_segment r ON e.road_segment_id = r.road_segment_id
    WHERE g.province_name IN ('กรุงเทพมหานคร', 'เชียงใหม่', 'ชลบุรี')
    GROUP BY g.province_name, r.road_name, r.road_code, yr
    ORDER BY g.province_name, yr, accidents DESC
    LIMIT 15
""")
for r in cur.fetchall():
    print(f"  {r['yr']} {r['province_name']} | {r['road_name'][:40]} ({r['road_code']}): {r['accidents']} accidents")

conn.close()
