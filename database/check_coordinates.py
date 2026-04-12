#!/usr/bin/env python3
"""Check if coordinates were imported successfully."""

import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "chat-aio")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
)
cur = conn.cursor()

print("=" * 70)
print("  Coordinate Import Verification")
print("=" * 70)

# Check overall statistics
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(latitude) as with_lat,
        COUNT(longitude) as with_lon,
        COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as with_both
    FROM fact_accident_event
""")
stats = cur.fetchone()
total, with_lat, with_lon, with_both = stats

print(f"\n  Total events: {total:,}")
print(f"  With latitude: {with_lat:,} ({with_lat/total*100:.1f}%)")
print(f"  With longitude: {with_lon:,} ({with_lon/total*100:.1f}%)")
print(f"  With both coordinates: {with_both:,} ({with_both/total*100:.1f}%)")

# Sample coordinates
print("\n  Sample coordinates (first 5 events with lat/lon):")
cur.execute("""
    SELECT latitude, longitude, event_datetime, csv_year
    FROM fact_accident_event 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL 
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"    Lat: {row[0]:>10.6f}, Lon: {row[1]:>10.6f}, Date: {row[2]}, Year: {row[3]}")

# Check by year
print("\n  Coordinates by year:")
cur.execute("""
    SELECT 
        csv_year,
        COUNT(*) as total,
        COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as with_coords,
        ROUND(COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END)::NUMERIC / COUNT(*) * 100, 1) as pct
    FROM fact_accident_event
    GROUP BY csv_year
    ORDER BY csv_year
""")
for row in cur.fetchall():
    year, total, with_coords, pct = row
    print(f"    {year}: {with_coords:>6,}/{total:>6,} ({pct}%)")

cur.close()
conn.close()

print("=" * 70)
