"""
Migration runner script for Musya Agent.
Runs all SQL migrations in order.
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


async def create_migration_table():
    """Create migration_history table if it doesn't exist."""
    settings = get_settings()
    
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS migration_history (
            migration_id INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    await conn.close()
    logger.info("✅ migration_history table ready")


async def get_applied_migrations():
    """Get list of already applied migrations."""
    settings = get_settings()
    
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    
    rows = await conn.fetch("SELECT migration_id FROM migration_history ORDER BY migration_id")
    await conn.close()
    
    return [row['migration_id'] for row in rows]


async def run_migration(migration_file: Path):
    """Run a single migration file."""
    settings = get_settings()
    
    # Extract migration ID from filename (e.g., 001_shared_core.sql -> 1)
    migration_id = int(migration_file.stem.split('_')[0])
    description = '_'.join(migration_file.stem.split('_')[1:])
    
    logger.info(f"Running migration {migration_id:03d}: {description}")
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    
    try:
        # Run migration
        await conn.execute(sql)
        
        # Record in migration_history
        await conn.execute(
            "INSERT INTO migration_history (migration_id, description) VALUES ($1, $2)",
            migration_id,
            description
        )
        
        logger.info(f"✅ Migration {migration_id:03d} completed")
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration {migration_id:03d} failed: {e}")
        await conn.close()
        return False


async def main():
    """Run all pending migrations."""
    logger.info("\n" + "=" * 60)
    logger.info("Musya Agent - Database Migration Runner")
    logger.info("=" * 60 + "\n")
    
    # Find all migration files
    database_dir = Path(__file__).parent.parent / "database"
    migration_files = sorted(database_dir.glob("*.sql"))
    
    if not migration_files:
        logger.error("❌ No migration files found in database/")
        return False
    
    logger.info(f"Found {len(migration_files)} migration files")
    
    try:
        # Create migration table
        await create_migration_table()
        
        # Get applied migrations
        applied = await get_applied_migrations()
        logger.info(f"Already applied: {len(applied)} migrations")
        
        # Run pending migrations
        pending_count = 0
        success_count = 0
        
        for migration_file in migration_files:
            migration_id = int(migration_file.stem.split('_')[0])
            
            if migration_id in applied:
                logger.info(f"⏭️  Skipping {migration_id:03d} (already applied)")
                continue
            
            pending_count += 1
            success = await run_migration(migration_file)
            
            if success:
                success_count += 1
            else:
                logger.error(f"\n❌ Migration {migration_id:03d} failed. Stopping.")
                break
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total migrations: {len(migration_files)}")
        logger.info(f"Already applied: {len(applied)}")
        logger.info(f"Pending: {pending_count}")
        logger.info(f"Successfully applied: {success_count}")
        
        if success_count == pending_count:
            logger.info("\n🎉 All migrations completed successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Verify database: python scripts/check_database.py")
            logger.info("2. Upload samples: python scripts/prepare_sample_documents.py")
            logger.info("3. Start server: python -m uvicorn src.main:app --reload")
            return True
        else:
            logger.error("\n⚠️  Some migrations failed")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Migration runner failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
