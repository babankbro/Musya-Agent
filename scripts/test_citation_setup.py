"""
Test script to verify Citation & Evidence Agent setup:
1. Run migration 010 (evidence_registry, claim_evidence_link)
2. Verify database tables exist
3. Test evidence insertion and retrieval
4. Verify MinIO connection
5. Test RAG integration
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db.pool import get_async_pool, query_db
from src.db.minio_client import list_documents, download_document
from src.rag.vector_store import get_collection
from src.schemas.evidence import EvidenceItem, Claim, ClaimEvidenceLink
import asyncpg
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def run_migration_010():
    """Run migration 010 to create evidence tables."""
    logger.info("=" * 60)
    logger.info("STEP 1: Running Migration 010")
    logger.info("=" * 60)
    
    migration_file = Path(__file__).parent.parent / "database" / "010_evidence_citation.sql"
    
    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        return False
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(sql)
            logger.info("✅ Migration 010 executed successfully")
            return True
        except asyncpg.exceptions.DuplicateTableError:
            logger.info("⚠️  Tables already exist (migration already run)")
            return True
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return False


async def verify_tables():
    """Verify that evidence tables exist."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 2: Verifying Database Tables")
    logger.info("=" * 60)
    
    tables_to_check = [
        "evidence_registry",
        "claim_evidence_link"
    ]
    
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        for table in tables_to_check:
            result = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = $1
                )
                """,
                table
            )
            
            if result:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                logger.info(f"✅ Table '{table}' exists ({count} rows)")
            else:
                logger.error(f"❌ Table '{table}' does not exist")
                return False
    
    return True


async def test_evidence_insertion():
    """Test inserting and retrieving evidence."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 3: Testing Evidence Insertion")
    logger.info("=" * 60)
    
    test_evidence = {
        "evidence_id": "TEST-EV-001",
        "evidence_type": "document",
        "source_ref": "test_document.pdf",
        "title": "Test Document Title",
        "page_ref": "12",
        "section_label": "Section 3.2",
        "chunk_id": "test-chunk-123",
        "text_snippet": "This is a test evidence snippet for verification.",
        "trust_level": "high",
        "original_url": "minio://test/test_document.pdf",
        "open_url": "/api/documents/open/1?page=12",
        "session_id": "test-session-001"
    }
    
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        try:
            # Insert test evidence
            await conn.execute(
                """
                INSERT INTO evidence_registry (
                    evidence_id, evidence_type, source_ref, title, page_ref,
                    section_label, chunk_id, text_snippet, trust_level,
                    original_url, open_url, session_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (evidence_id) DO UPDATE SET
                    text_snippet = EXCLUDED.text_snippet
                """,
                test_evidence["evidence_id"],
                test_evidence["evidence_type"],
                test_evidence["source_ref"],
                test_evidence["title"],
                test_evidence["page_ref"],
                test_evidence["section_label"],
                test_evidence["chunk_id"],
                test_evidence["text_snippet"],
                test_evidence["trust_level"],
                test_evidence["original_url"],
                test_evidence["open_url"],
                test_evidence["session_id"]
            )
            logger.info(f"✅ Inserted test evidence: {test_evidence['evidence_id']}")
            
            # Retrieve it back
            row = await conn.fetchrow(
                "SELECT * FROM evidence_registry WHERE evidence_id = $1",
                test_evidence["evidence_id"]
            )
            
            if row:
                logger.info(f"✅ Retrieved evidence: {dict(row)}")
                return True
            else:
                logger.error("❌ Failed to retrieve inserted evidence")
                return False
                
        except Exception as e:
            logger.error(f"❌ Evidence insertion test failed: {e}")
            return False


async def test_claim_evidence_link():
    """Test claim-evidence linking."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 4: Testing Claim-Evidence Links")
    logger.info("=" * 60)
    
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        try:
            # Insert test link
            await conn.execute(
                """
                INSERT INTO claim_evidence_link (
                    claim_id, evidence_id, relevance_score, session_id
                ) VALUES ($1, $2, $3, $4)
                ON CONFLICT (claim_id, evidence_id) DO UPDATE SET
                    relevance_score = EXCLUDED.relevance_score
                """,
                "TEST-CLAIM-001",
                "TEST-EV-001",
                0.95,
                "test-session-001"
            )
            logger.info("✅ Inserted claim-evidence link")
            
            # Retrieve it
            row = await conn.fetchrow(
                """
                SELECT * FROM claim_evidence_link 
                WHERE claim_id = $1 AND evidence_id = $2
                """,
                "TEST-CLAIM-001",
                "TEST-EV-001"
            )
            
            if row:
                logger.info(f"✅ Retrieved link: {dict(row)}")
                return True
            else:
                logger.error("❌ Failed to retrieve link")
                return False
                
        except Exception as e:
            logger.error(f"❌ Claim-evidence link test failed: {e}")
            return False


def test_minio_connection():
    """Test MinIO connection and list documents."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 5: Testing MinIO Connection")
    logger.info("=" * 60)
    
    try:
        docs = list_documents(prefix="")
        logger.info(f"✅ MinIO connected. Found {len(docs)} documents:")
        for doc in docs[:5]:  # Show first 5
            logger.info(f"   - {doc['name']} ({doc['size']} bytes)")
        
        if len(docs) > 5:
            logger.info(f"   ... and {len(docs) - 5} more")
        
        return True
    except Exception as e:
        logger.error(f"❌ MinIO connection failed: {e}")
        return False


def test_chromadb_connection():
    """Test ChromaDB connection."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 6: Testing ChromaDB Connection")
    logger.info("=" * 60)
    
    try:
        collection = get_collection()
        count = collection.count()
        logger.info(f"✅ ChromaDB connected. Collection has {count} chunks")
        
        # Try a sample search
        if count > 0:
            results = collection.query(
                query_texts=["อุบัติเหตุ"],
                n_results=3
            )
            logger.info(f"✅ Sample search returned {len(results['documents'][0])} results")
        
        return True
    except Exception as e:
        logger.error(f"❌ ChromaDB connection failed: {e}")
        return False


async def verify_enhanced_metadata():
    """Verify that document_registry has enhanced columns."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 7: Verifying Enhanced Metadata Columns")
    logger.info("=" * 60)
    
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        try:
            # Check if new columns exist
            columns = await conn.fetch(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'document_registry'
                """
            )
            
            column_names = [row['column_name'] for row in columns]
            required_columns = ['file_path', 'total_pages', 'original_url', 'open_url']
            
            for col in required_columns:
                if col in column_names:
                    logger.info(f"✅ Column '{col}' exists in document_registry")
                else:
                    logger.warning(f"⚠️  Column '{col}' missing (may need migration)")
            
            # Check document_chunks
            chunks_columns = await conn.fetch(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'document_chunks'
                """
            )
            
            chunks_column_names = [row['column_name'] for row in chunks_columns]
            chunks_required = ['section_label', 'heading_text']
            
            for col in chunks_required:
                if col in chunks_column_names:
                    logger.info(f"✅ Column '{col}' exists in document_chunks")
                else:
                    logger.warning(f"⚠️  Column '{col}' missing (may need migration)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Metadata verification failed: {e}")
            return False


async def main():
    """Run all tests."""
    logger.info("\n" + "🔍" * 30)
    logger.info("Citation & Evidence Agent Setup Verification")
    logger.info("🔍" * 30 + "\n")
    
    results = {}
    
    # Step 1: Run migration
    results['migration'] = await run_migration_010()
    
    # Step 2: Verify tables
    if results['migration']:
        results['tables'] = await verify_tables()
    else:
        results['tables'] = False
    
    # Step 3: Test evidence insertion
    if results['tables']:
        results['evidence_insert'] = await test_evidence_insertion()
    else:
        results['evidence_insert'] = False
    
    # Step 4: Test claim-evidence links
    if results['evidence_insert']:
        results['claim_link'] = await test_claim_evidence_link()
    else:
        results['claim_link'] = False
    
    # Step 5: Test MinIO
    results['minio'] = test_minio_connection()
    
    # Step 6: Test ChromaDB
    results['chromadb'] = test_chromadb_connection()
    
    # Step 7: Verify enhanced metadata
    results['metadata'] = await verify_enhanced_metadata()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    for step, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {step}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n🎉 All tests passed! Citation & Evidence Agent is ready.")
        logger.info("\nNext steps:")
        logger.info("1. Start the Agent server: python -m uvicorn src.main:app --reload")
        logger.info("2. Open the test UI: http://localhost:8000/static/citation_test_ui.html")
        logger.info("3. Ingest sample documents if needed: POST /api/ingest")
        logger.info("4. Test the full pipeline with a chat message")
    else:
        logger.error("\n⚠️  Some tests failed. Please review the errors above.")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
