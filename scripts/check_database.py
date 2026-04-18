"""
Database connection verification script for Musya Agent.
Checks if PostgreSQL database exists and is accessible.
Verifies all required tables are present.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from src.config import get_settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def check_database_connection():
    """Check if database connection is possible."""
    logger.info("=" * 60)
    logger.info("Step 1: Testing Database Connection")
    logger.info("=" * 60)
    
    settings = get_settings()
    
    logger.info(f"Database Host: {settings.DB_HOST}")
    logger.info(f"Database Port: {settings.DB_PORT}")
    logger.info(f"Database Name: {settings.DB_NAME}")
    logger.info(f"Database User: {settings.DB_USER}")
    
    try:
        conn = await asyncpg.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        
        version = await conn.fetchval("SELECT version()")
        logger.info(f"✅ Connected to PostgreSQL")
        logger.info(f"   Version: {version.split(',')[0]}")
        
        await conn.close()
        return True
        
    except asyncpg.exceptions.InvalidCatalogNameError:
        logger.error(f"❌ Database '{settings.DB_NAME}' does not exist")
        logger.info("\nTo create the database:")
        logger.info(f"  1. Connect to PostgreSQL: psql -U {settings.DB_USER} -h {settings.DB_HOST}")
        logger.info(f"  2. Create database: CREATE DATABASE {settings.DB_NAME};")
        return False
        
    except asyncpg.exceptions.InvalidPasswordError:
        logger.error("❌ Invalid database password")
        logger.info("Check your .env file for correct DB_PASSWORD")
        return False
        
    except ConnectionRefusedError:
        logger.error(f"❌ Connection refused to {settings.DB_HOST}:{settings.DB_PORT}")
        logger.info("\nPossible causes:")
        logger.info("  1. PostgreSQL is not running")
        logger.info("  2. Docker container is not started")
        logger.info("  3. Wrong host/port in .env file")
        logger.info("\nTo start PostgreSQL with Docker:")
        logger.info("  docker-compose up -d postgres")
        return False
        
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        return False


async def check_database_exists():
    """Check if the database exists by trying to list databases."""
    logger.info("\n" + "=" * 60)
    logger.info("Step 2: Verifying Database Exists")
    logger.info("=" * 60)
    
    settings = get_settings()
    
    try:
        # Connect to default 'postgres' database to check if our database exists
        conn = await asyncpg.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database='postgres',
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
            settings.DB_NAME
        )
        
        if result:
            logger.info(f"✅ Database '{settings.DB_NAME}' exists")
            await conn.close()
            return True
        else:
            logger.error(f"❌ Database '{settings.DB_NAME}' does not exist")
            logger.info("\nCreate it with:")
            logger.info(f"  CREATE DATABASE {settings.DB_NAME};")
            await conn.close()
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to verify database: {e}")
        return False


async def check_tables():
    """Check if required tables exist."""
    logger.info("\n" + "=" * 60)
    logger.info("Step 3: Checking Required Tables")
    logger.info("=" * 60)
    
    required_tables = [
        # Core tables (Migration 001)
        "dim_geography",
        "dim_time",
        
        # Document RAG tables (Migration 002)
        "document_registry",
        "document_embeddings",
        
        # Accident domain tables (Migration 003)
        "fact_accident_event",
        "fact_accident_person",
        "accident",
        
        # Citation & Evidence tables (Migration 010)
        "evidence_registry",
        "claim_evidence_link",
    ]
    
    settings = get_settings()
    
    try:
        conn = await asyncpg.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        
        existing_tables = []
        missing_tables = []
        
        for table in required_tables:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = $1
                )
                """,
                table
            )
            
            if exists:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                logger.info(f"✅ {table:30} ({count:,} rows)")
                existing_tables.append(table)
            else:
                logger.warning(f"⚠️  {table:30} (missing)")
                missing_tables.append(table)
        
        await conn.close()
        
        logger.info(f"\nSummary: {len(existing_tables)}/{len(required_tables)} tables exist")
        
        if missing_tables:
            logger.warning("\nMissing tables detected. Run migrations:")
            logger.info("  python scripts/run_migrations.py")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to check tables: {e}")
        return False


async def check_migrations():
    """Check migration history."""
    logger.info("\n" + "=" * 60)
    logger.info("Step 4: Checking Migration History")
    logger.info("=" * 60)
    
    settings = get_settings()
    
    try:
        conn = await asyncpg.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        
        # Check if migration_history table exists
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'migration_history'
            )
            """
        )
        
        if not exists:
            logger.warning("⚠️  migration_history table does not exist")
            logger.info("   No migrations have been run yet")
            await conn.close()
            return False
        
        # Get migration history
        migrations = await conn.fetch(
            """
            SELECT migration_id, description, applied_at 
            FROM migration_history 
            ORDER BY migration_id
            """
        )
        
        if migrations:
            logger.info(f"✅ Found {len(migrations)} applied migrations:")
            for m in migrations:
                logger.info(f"   {m['migration_id']:3} - {m['description']}")
        else:
            logger.warning("⚠️  No migrations found in history")
        
        await conn.close()
        return len(migrations) > 0
        
    except Exception as e:
        logger.error(f"❌ Failed to check migrations: {e}")
        return False


def check_env_file():
    """Check if .env file exists and has required variables."""
    logger.info("\n" + "=" * 60)
    logger.info("Step 5: Checking Environment Configuration")
    logger.info("=" * 60)
    
    env_file = Path(__file__).parent.parent / ".env"
    
    if not env_file.exists():
        logger.error("❌ .env file not found")
        logger.info("\nCreate .env file with:")
        logger.info("""
DB_HOST=localhost
DB_PORT=5432
DB_NAME=musya_agent
DB_USER=postgres
DB_PASSWORD=your_password

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=musya-documents

CHROMA_PERSIST_DIR=.chromadb

GEMINI_API_KEY=your_gemini_api_key
GOOGLE_API_KEY=your_gemini_api_key
""")
        return False
    
    logger.info("✅ .env file exists")
    
    required_vars = [
        "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
        "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY",
        "GEMINI_API_KEY"
    ]
    
    settings = get_settings()
    missing_vars = []
    
    for var in required_vars:
        value = getattr(settings, var, None)
        if value:
            # Mask sensitive values
            if "PASSWORD" in var or "KEY" in var:
                display_value = "***" + str(value)[-4:] if len(str(value)) > 4 else "***"
            else:
                display_value = value
            logger.info(f"   {var:20} = {display_value}")
        else:
            logger.warning(f"   {var:20} = (not set)")
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"\n⚠️  Missing variables: {', '.join(missing_vars)}")
        return False
    
    return True


async def main():
    """Run all database checks."""
    logger.info("\n" + "🔍" * 30)
    logger.info("Musya Agent - Database Connection Check")
    logger.info("🔍" * 30 + "\n")
    
    results = {}
    
    # Step 1: Check .env file
    results['env'] = check_env_file()
    
    if not results['env']:
        logger.error("\n❌ Environment configuration incomplete")
        logger.info("Fix .env file before proceeding")
        return False
    
    # Step 2: Check database connection
    results['connection'] = await check_database_connection()
    
    if not results['connection']:
        logger.error("\n❌ Cannot connect to database")
        logger.info("Fix database connection before proceeding")
        return False
    
    # Step 3: Verify database exists
    results['database'] = await check_database_exists()
    
    if not results['database']:
        logger.error("\n❌ Database does not exist")
        return False
    
    # Step 4: Check migrations
    results['migrations'] = await check_migrations()
    
    # Step 5: Check tables
    results['tables'] = await check_tables()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    for step, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {step}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n🎉 Database is ready!")
        logger.info("\nNext steps:")
        logger.info("1. Upload sample documents: python scripts/prepare_sample_documents.py")
        logger.info("2. Run setup test: python scripts/test_citation_setup.py")
        logger.info("3. Start server: python -m uvicorn src.main:app --reload")
    else:
        logger.error("\n⚠️  Database setup incomplete")
        
        if not results.get('migrations') or not results.get('tables'):
            logger.info("\nRun migrations to create tables:")
            logger.info("  python scripts/run_migrations.py")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
