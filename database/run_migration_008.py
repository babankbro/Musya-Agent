#!/usr/bin/env python3
"""Run migration 008 to add UNIQUE constraints and prevent duplicates."""

import os
import sys
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


def run_migration():
    """Execute migration 008 SQL file."""
    migration_file = Path(__file__).parent / "008_prevent_duplicates.sql"
    
    if not migration_file.exists():
        print(f"ERROR: Migration file not found: {migration_file}")
        sys.exit(1)
    
    print("=" * 70)
    print("  Running Migration 008: Prevent Duplicates")
    print("=" * 70)
    print(f"  Database: {DB_NAME}")
    print(f"  Host: {DB_HOST}:{DB_PORT}")
    print(f"  Migration file: {migration_file.name}")
    print()
    
    # Read migration SQL
    with open(migration_file, "r", encoding="utf-8") as f:
        sql = f.read()
    
    # Connect and execute
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        print("  Executing migration SQL...")
        cur.execute(sql)
        
        print("  ✓ Migration completed successfully!")
        print()
        
        # Verify constraints were created
        print("  Verifying UNIQUE constraints...")
        cur.execute("""
            SELECT 
                conname AS constraint_name,
                conrelid::regclass AS table_name
            FROM pg_constraint
            WHERE conname LIKE '%unique%'
              AND conrelid::regclass::text IN (
                'fact_accident_event', 
                'dim_geography', 
                'dim_road_segment'
              )
            ORDER BY table_name, constraint_name
        """)
        
        constraints = cur.fetchall()
        if constraints:
            print(f"  Found {len(constraints)} UNIQUE constraints:")
            for name, table in constraints:
                print(f"    - {table}: {name}")
        else:
            print("  WARNING: No UNIQUE constraints found!")
        
        cur.close()
        conn.close()
        
        print()
        print("=" * 70)
        print("  Migration 008 Complete!")
        print("  You can now run: python database/import_csv_all_years.py")
        print("=" * 70)
        
    except psycopg2.Error as e:
        print(f"  ✗ ERROR: {e}")
        print()
        print("  Migration failed. Please check the error above.")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
