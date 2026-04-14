"""Test pgvector connection and view data stored in PostgreSQL."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from src.config import get_settings


def main():
    print("=" * 70)
    print("pgvector (PostgreSQL) Vector Store Test")
    print("=" * 70)

    settings = get_settings()
    print(f"\n� Database:   {settings.DB_NAME} @ {settings.DB_HOST}:{settings.DB_PORT}")
    print(f"📚 Collection: {settings.PGVECTOR_COLLECTION}")
    print(f"🤖 Embedding Model: {settings.EMBEDDING_MODEL}")

    try:
        # Test connection
        print("\n🔌 Connecting to PostgreSQL...")
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            dbname=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        print("✅ Connected successfully!")

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Check pgvector extension
            cur.execute("SELECT installed_version FROM pg_available_extensions WHERE name = 'vector'")
            ext = cur.fetchone()
            if ext and ext["installed_version"]:
                print(f"✅ pgvector extension: v{ext['installed_version']}")
            else:
                print("⚠️  pgvector extension NOT installed — run migration 011_pgvector.sql")
                return 1

            # Check table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'document_embeddings'
                )
            """)
            table_exists = cur.fetchone()["exists"]
            if not table_exists:
                print("⚠️  Table 'document_embeddings' not found — run migration 011_pgvector.sql")
                return 1

            # Count total documents
            cur.execute("SELECT COUNT(*) AS total FROM document_embeddings")
            total = cur.fetchone()["total"]
            print(f"\n📊 Total document chunks: {total}")

            # Count per collection
            cur.execute("""
                SELECT collection, COUNT(*) AS cnt
                FROM document_embeddings
                GROUP BY collection
                ORDER BY cnt DESC
            """)
            print("\n� Documents per Collection:")
            for row in cur.fetchall():
                print(f"  • {row['collection']}: {row['cnt']} chunks")

            # Count per source file
            cur.execute("""
                SELECT source, COUNT(*) AS chunks, MAX(total_pages) AS pages
                FROM document_embeddings
                WHERE collection = %s
                GROUP BY source
                ORDER BY chunks DESC
            """, (settings.PGVECTOR_COLLECTION,))
            rows = cur.fetchall()
            if rows:
                print("\n📄 Documents in Collection:")
                for row in rows:
                    print(f"  • {row['source']}  ({row['chunks']} chunks, {row['pages']} pages)")
            else:
                print("\n⚠️  Collection is empty. Run ingestion first:")
                print("     python scripts/prepare_sample_documents.py")
                print("     curl -X POST http://localhost:8000/api/ingest")
                conn.close()
                return 0

            # Sample 5 chunks
            print("\n🔍 Sample Chunks (first 5):")
            cur.execute("""
                SELECT id, source, title, page_ref, section_label,
                       chunk_index, total_chunks,
                       LEFT(document, 120) AS snippet
                FROM document_embeddings
                WHERE collection = %s
                ORDER BY source, chunk_index
                LIMIT 5
            """, (settings.PGVECTOR_COLLECTION,))
            for i, row in enumerate(cur.fetchall(), 1):
                print(f"\n  [{i}] {row['source']}")
                print(f"      Title:   {row['title']}")
                print(f"      Page:    {row['page_ref']}  |  Chunk: {row['chunk_index']}/{row['total_chunks']}")
                if row["section_label"]:
                    print(f"      Section: {row['section_label']}")
                print(f"      Text:    {row['snippet']}...")

            # Semantic search test
            print("\n\n🔎 Semantic Search Test: 'อุบัติเหตุทางถนน'")
            print("   (loading embedding model — may take a moment on first run)")
            from src.rag.vector_store import search_documents
            results = search_documents("อุบัติเหตุทางถนน", n_results=3)
            if results:
                for i, r in enumerate(results, 1):
                    print(f"\n  Result {i} (distance: {r['distance']:.4f})")
                    print(f"    Source: {r['metadata'].get('source', 'N/A')}")
                    print(f"    Page:   {r['metadata'].get('page_ref', 'N/A')}")
                    print(f"    Text:   {r['text'][:150]}...")
            else:
                print("  No results returned.")

        conn.close()
        print("\n" + "=" * 70)
        print("✅ pgvector Test Complete")
        print("=" * 70)
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
