"""Analyze current schema and data gaps."""
import csv
import os
import psycopg2
import psycopg2.extras
from pathlib import Path

conn = psycopg2.connect('host=localhost port=5432 dbname=chat-aio user=postgres password=1234')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

print("=== dim_road_segment columns ===")
cur.execute("""SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name='dim_road_segment' ORDER BY ordinal_position""")
for r in cur.fetchall(): print(f"  {r[0]}: {r[1]}")

print("\n=== Top 5 hotspots with province + road ===")
cur.execute("""
    SELECT h.hotspot_id, g.province_name, r.road_name, h.accident_count, h.hotspot_score
    FROM mart_accident_hotspot h
    JOIN dim_geography g ON h.geography_id = g.geography_id
    LEFT JOIN dim_road_segment r ON h.road_segment_id = r.road_segment_id
    ORDER BY h.hotspot_score DESC LIMIT 5
""")
for r in cur.fetchall(): print(" ", dict(r))

print("\n=== fact_accident_event NULLs ===")
cur.execute("SELECT COUNT(*) FROM fact_accident_event WHERE road_segment_id IS NULL")
print(f"  NULL road_segment: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM fact_accident_event WHERE geography_id IS NULL")
print(f"  NULL geography: {cur.fetchone()[0]}")

print("\n=== Does dim_road_segment have geography_id? ===")
cur.execute("""SELECT column_name FROM information_schema.columns
    WHERE table_name='dim_road_segment' AND column_name='geography_id'""")
print(f"  geography_id col exists: {cur.fetchone() is not None}")

print("\n=== Does dim_road_segment have road_code? ===")
cur.execute("""SELECT column_name FROM information_schema.columns
    WHERE table_name='dim_road_segment' AND column_name='road_code'""")
print(f"  road_code col exists: {cur.fetchone() is not None}")

print("\n=== CSV columns sample ===")
with open(Path(__file__).parent / 'accident2023.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = [next(reader) for _ in range(3)]
print("  Keys:", list(rows[0].keys()))
print("  Sample road:", [(r['รหัสสายทาง'], r['สายทาง'][:30], r['จังหวัด'], r['KM']) for r in rows])

print("\n=== Top 10 provinces by accident count ===")
cur.execute("""
    SELECT g.province_name, COUNT(*) as cnt, SUM(e.death_count) as deaths
    FROM fact_accident_event e
    JOIN dim_geography g ON e.geography_id = g.geography_id
    GROUP BY g.province_name ORDER BY cnt DESC LIMIT 10
""")
for r in cur.fetchall(): print(f"  {r['province_name']}: {r['cnt']} accidents, {r['deaths']} deaths")

print("\n=== road_segment: geography coverage ===")
cur.execute("""
    SELECT COUNT(DISTINCT e.road_segment_id) as road_segs,
           COUNT(DISTINCT e.geography_id) as geos
    FROM fact_accident_event e
""")
r = cur.fetchone()
print(f"  Unique road_segments in fact: {r[0]}, unique geos: {r[1]}")

cur.execute("SELECT COUNT(*) FROM dim_road_segment")
print(f"  Total dim_road_segment: {cur.fetchone()[0]}")

conn.close()
