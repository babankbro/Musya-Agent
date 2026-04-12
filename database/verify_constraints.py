#!/usr/bin/env python3
"""Verify UNIQUE constraints and indexes exist."""

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


def verify():
    """Check if UNIQUE indexes exist."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    cur = conn.cursor()
    
    print("=" * 70)
    print("  Verifying UNIQUE Indexes")
    print("=" * 70)
    
    # Check all indexes on relevant tables
    cur.execute("""
        SELECT 
            schemaname,
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename IN ('fact_accident_event', 'dim_geography', 'dim_road_segment')
          AND indexname LIKE '%unique%'
        ORDER BY tablename, indexname
    """)
    
    indexes = cur.fetchall()
    if indexes:
        print(f"\n  Found {len(indexes)} UNIQUE indexes:\n")
        for schema, table, name, definition in indexes:
            print(f"  Table: {table}")
            print(f"  Index: {name}")
            print(f"  Definition: {definition}")
            print()
    else:
        print("\n  ✗ No UNIQUE indexes found!")
        print("\n  Checking all indexes on these tables:")
        
        cur.execute("""
            SELECT tablename, indexname
            FROM pg_indexes
            WHERE tablename IN ('fact_accident_event', 'dim_geography', 'dim_road_segment')
            ORDER BY tablename, indexname
        """)
        
        all_indexes = cur.fetchall()
        for table, name in all_indexes:
            print(f"    {table}: {name}")
    
    cur.close()
    conn.close()
    print("=" * 70)


if __name__ == "__main__":
    verify()
