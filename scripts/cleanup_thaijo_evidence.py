"""One-time cleanup script — re-verify ThaiJO evidence_registry entries.

Uses same code path as POST /api/thaijo/search (Tab 1) — zero LLM hops.
Run once after deploying Tasks 1-3 to clean up historically hallucinated URLs.

Usage:
    python scripts/cleanup_thaijo_evidence.py
    python scripts/cleanup_thaijo_evidence.py --dry-run   # preview only, no DB writes

Algorithm per evidence_registry row (evidence_type = 'thaijo_article'):
  1. Check open_url against thaijo_search_cache via JSONB @> query
     → URL confirmed in cache → no change (leave as-is)
  2. Cache MISS + search_term → re-search via _search_thaijo_impl() (= Tab 1 path)
     → URL found in fresh search → confirmed, no change
     → thaijo_pdf_url found in fresh search → restore open_url from thaijo_pdf_url
     → Nothing found → clear open_url to ""
  3. open_url fails URL pattern → clear to ""
"""
import argparse
import json
import logging
import sys
import os

# Add project root to path so src.* imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("cleanup_thaijo_evidence")


def run_cleanup(dry_run: bool = False) -> None:
    from src.db.pool import query_db, execute_db
    from src.tools.thaijo import _is_valid_thaijo_url, _search_thaijo_impl

    mode_label = "[DRY-RUN] " if dry_run else ""

    rows = query_db(
        """SELECT evidence_id, source_ref, open_url,
                  thaijo_search_term, thaijo_pdf_url
           FROM evidence_registry
           WHERE evidence_type = 'thaijo_article'
           ORDER BY evidence_id""",
        [],
    )
    logger.info("%sFound %d ThaiJO evidence entries to check", mode_label, len(rows))

    confirmed = cleared = recovered = skipped = errors = 0

    for row in rows:
        ev_id = row["evidence_id"]
        current_url = row.get("open_url") or ""
        search_term = row.get("thaijo_search_term") or ""
        stored_pdf_url = row.get("thaijo_pdf_url") or ""

        # Step 0: no search term — nothing we can verify
        if not search_term:
            logger.info("  [skip] %s — no thaijo_search_term", ev_id)
            skipped += 1
            continue

        try:
            # Step 1: pattern check — fast reject
            if current_url and not _is_valid_thaijo_url(current_url):
                logger.warning("  [clear] %s — invalid URL pattern: %r", ev_id, current_url[:80])
                if not dry_run:
                    execute_db(
                        "UPDATE evidence_registry SET open_url = '' WHERE evidence_id = %s",
                        (ev_id,),
                    )
                cleared += 1
                continue

            # Step 2: check thaijo_search_cache (JSONB containment)
            if current_url:
                cache_rows = query_db(
                    "SELECT 1 FROM thaijo_search_cache "
                    "WHERE results_json @> %s::jsonb AND expires_at > NOW() LIMIT 1",
                    (json.dumps([{"pdf_url": current_url}]),),
                )
                if cache_rows:
                    logger.info("  [ok] %s — URL confirmed in cache", ev_id)
                    confirmed += 1
                    continue

            # Step 3: cache MISS — re-search via Tab 1 path (zero LLM hops)
            logger.info("  [search] %s — term=%r", ev_id, search_term[:60])
            try:
                raw = _search_thaijo_impl(search_term, size=10, strict=False)
                data = json.loads(raw)
            except Exception as search_exc:
                logger.warning("  [error] %s — search failed: %s", ev_id, search_exc)
                errors += 1
                continue

            results = data.get("results", [])
            real_urls = {r.get("pdf_url", "") for r in results if r.get("pdf_url")}

            # Current URL confirmed by fresh search
            if current_url and current_url in real_urls:
                logger.info("  [ok] %s — URL confirmed by fresh search", ev_id)
                confirmed += 1
                continue

            # thaijo_pdf_url (original) confirmed by fresh search → restore
            if stored_pdf_url and stored_pdf_url in real_urls:
                logger.info(
                    "  [recover] %s — restoring thaijo_pdf_url: %r", ev_id, stored_pdf_url[:80]
                )
                if not dry_run:
                    execute_db(
                        "UPDATE evidence_registry SET open_url = %s WHERE evidence_id = %s",
                        (stored_pdf_url, ev_id),
                    )
                recovered += 1
                continue

            # Nothing confirmed → clear URL if it's set
            if current_url:
                logger.warning(
                    "  [clear] %s — URL not found in search (hallucinated?): %r",
                    ev_id, current_url[:80],
                )
                if not dry_run:
                    execute_db(
                        "UPDATE evidence_registry SET open_url = '' WHERE evidence_id = %s",
                        (ev_id,),
                    )
                cleared += 1
            else:
                logger.info("  [skip] %s — open_url already empty, no search match", ev_id)
                skipped += 1

        except Exception as e:
            logger.error("  [error] %s — unexpected error: %s", ev_id, e)
            errors += 1

    total = len(rows)
    logger.info(
        "%sCleanup complete: %d confirmed | %d recovered | %d cleared | %d skipped | %d errors  (total=%d)",
        mode_label, confirmed, recovered, cleared, skipped, errors, total,
    )
    if dry_run:
        logger.info("DRY-RUN: no DB writes were made. Remove --dry-run to apply changes.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-verify ThaiJO evidence_registry open_url values against thaijo_search_cache"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to the database",
    )
    args = parser.parse_args()
    run_cleanup(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
