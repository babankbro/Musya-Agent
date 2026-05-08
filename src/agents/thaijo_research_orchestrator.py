"""ThaiJO Research Report Orchestrator — 6-agent sequential pipeline."""
import json, logging, re, time
from crewai import Crew, Task, Process, LLM
from src.config import get_settings
from src.agents.thaijo_topic_parser import create_thaijo_topic_parser, THAIJO_TOPIC_PARSER_PROMPT
from src.agents.thaijo_searcher import create_thaijo_searcher, THAIJO_SEARCHER_PROMPT
from src.agents.thaijo_screener import create_thaijo_screener, THAIJO_SCREENER_PROMPT
from src.agents.citation_evidence import create_citation_evidence_agent, CITATION_EVIDENCE_PROMPT, parse_evidence_context
from src.agents.thaijo_research_synthesizer import create_thaijo_research_synthesizer, THAIJO_RESEARCH_SYNTHESIZER_PROMPT
from src.agents.thaijo_report_composer import create_thaijo_report_composer, THAIJO_REPORT_COMPOSER_PROMPT
from src.schemas.thaijo_research import ThaiJOResearchResponse
from src.schemas.response import Citation
from src.agents.progress import emit_progress
from src.agents.agent_defaults import kickoff_with_retry

logger = logging.getLogger(__name__)
AGENT_NAMES = ["Research Topic Parser","ThaiJO Searcher","Article Screener","Citation Generator","Research Synthesizer","Report Composer"]

def _llm(tier="fast"):
    s = get_settings()
    if tier == "pro":
        return LLM(model=f"gemini/{s.GEMINI_MODEL_PRO}", temperature=0.3, max_tokens=s.REPORT_MAX_TOKENS)
    return LLM(model=f"gemini/{s.GEMINI_MODEL}", temperature=0.2, max_tokens=4096)

def build_thaijo_research_crew():
    f, p = _llm("fast"), _llm("pro")
    return {"topic_parser": create_thaijo_topic_parser(f), "searcher": create_thaijo_searcher(f),
            "screener": create_thaijo_screener(f), "citation_gen": create_citation_evidence_agent(f),
            "synthesizer": create_thaijo_research_synthesizer(p), "composer": create_thaijo_report_composer(p)}

def _build_article_map_block(topic: str, max_articles: int) -> str:
    """Pre-search ThaiJO with the topic to build a ground-truth article_map block.

    Returns a compact JSON string (<=3000 chars) injected into the Citation task
    description so Citation Agent has verified urls/metadata without relying on
    LLM context chain from Searcher/Screener.
    """
    from src.tools.thaijo import _search_thaijo_impl
    import json as _json
    try:
        raw = _search_thaijo_impl(topic[:80], size=min(max_articles, 10))
        data = _json.loads(raw)
        articles = data.get("results", [])[:max_articles]
        if not articles:
            # retry non-strict
            raw2 = _search_thaijo_impl(topic[:80], size=min(max_articles, 10), strict=False)
            articles = _json.loads(raw2).get("results", [])[:max_articles]
        compact = [
            {k: v for k, v in art.items()
             if k in ("pdf_url", "title", "reference", "apa_authors", "apa_year", "apa_journal")}
            for art in articles if art.get("pdf_url")
        ]
        block = _json.dumps(compact, ensure_ascii=False)
        logger.info("_build_article_map_block: %d articles for topic=%r", len(compact), topic[:60])
        return block
    except Exception as e:
        logger.warning("_build_article_map_block failed (%s) — skipping injection", e)
        return "[]"


def _tasks(agents, topic, max_articles, max_queries, article_map_block: str = ""):
    t1 = Task(description=THAIJO_TOPIC_PARSER_PROMPT.replace("{topic}",topic).replace("{max_queries}",str(max_queries)).replace("{max_articles}",str(max_articles)),
              expected_output="JSON: main_topic, domain, search_queries, criteria", agent=agents["topic_parser"])
    t2 = Task(description=THAIJO_SEARCHER_PROMPT.replace("{search_queries}","ดึงจาก Topic Parser — ต้องเรียก search_thaijo สำหรับทุกๆ keyword query ที่ Topic Parser ให้มา ห้ามข้ามแม้แต่ข้อเดียว"),
              expected_output="JSON: total_queries, articles[], query_results[]", agent=agents["searcher"], context=[t1])
    t3 = Task(description=THAIJO_SCREENER_PROMPT.replace("{main_topic}",topic).replace("{domain}","ดึงจาก Topic Parser").replace("{inclusion_criteria}","ดึงจาก Topic Parser").replace("{exclusion_criteria}","ดึงจาก Topic Parser").replace("{articles_json}","ดึงจาก Searcher output"),
              expected_output="JSON: screened_articles[], total_included, total_excluded", agent=agents["screener"], context=[t1,t2])
    # B1: inject pre-searched article_map as ground truth — Citation Agent must use lookup_thaijo_evidence
    # tool to confirm each URL, but this block provides the authoritative fallback metadata
    map_section = ""
    if article_map_block and article_map_block != "[]":
        map_section = (
            f"\n\n## Ground-Truth Article Map (จาก ThaiJO API โดยตรง — ใช้เป็น reference เท่านั้น)\n"
            f"ข้อมูลด้านล่างคือ metadata ที่ได้จาก ThaiJO API จริง "
            f"ก่อนเรียก `lookup_thaijo_evidence` ใช้ pdf_url จาก list นี้เป็น input:\n"
            f"```json\n{article_map_block[:2500]}\n```\n"
            f"⚠️ ต้องเรียก `lookup_thaijo_evidence(pdf_url=..., search_term=...)` ก่อนสร้าง evidence_item ทุกชิ้น"
        )
    cdesc = CITATION_EVIDENCE_PROMPT + f"\n\n**ThaiJO Context:** หัวข้อ: {topic}\nC-200~C-299 for thaijo_article. reference→bibliography_text (ห้ามแต่ง). open_url=pdf_url. source_type=thaijo_article. trust_level=medium. Dedup by pdf_url." + map_section + "\n"
    t4 = Task(description=cdesc, expected_output="JSON: evidence_items, citations (C-200+), coverage", agent=agents["citation_gen"], context=[t2,t3])
    t5 = Task(description=THAIJO_RESEARCH_SYNTHESIZER_PROMPT.replace("{main_topic}",topic).replace("{screened_articles_json}","ดึงจาก Screener").replace("{citation_codes_json}","ดึงจาก Citation Generator"),
              expected_output="JSON: themes[], overall_findings, research_gaps[]", agent=agents["synthesizer"], context=[t3,t4])
    t6 = Task(description=THAIJO_REPORT_COMPOSER_PROMPT.replace("{main_topic}",topic).replace("{synthesis_json}","ดึงจาก Synthesizer").replace("{citations_json}","ดึงจาก Citation Generator"),
              expected_output="Markdown report + JSON table + JSON chart + APA refs + follow-ups", agent=agents["composer"], context=[t5,t4])
    return [t1,t2,t3,t4,t5,t6]

def run_thaijo_research(topic, max_articles=15, max_queries=4, min_relevance=5.0, session_id=None):
    start = time.time(); agents = build_thaijo_research_crew()
    article_map_block = _build_article_map_block(topic, max_articles)
    tasks = _tasks(agents, topic, max_articles, max_queries, article_map_block)
    crew = Crew(agents=list(agents.values()), tasks=tasks, process=Process.sequential, verbose=True)
    logger.info("🚀 [THAIJO RESEARCH] topic: %s", topic[:120])
    try:
        return _parse(kickoff_with_retry(crew), topic, time.time()-start)
    except Exception as e:
        return ThaiJOResearchResponse(content=f"เกิดข้อผิดพลาด: {e}", topic="error", metadata={"error":str(e),"elapsed_seconds":round(time.time()-start,1)})

def run_thaijo_research_with_progress(topic, max_articles=15, max_queries=4, min_relevance=5.0, session_id=None, request_id=None):
    start = time.time(); agents = build_thaijo_research_crew()
    article_map_block = _build_article_map_block(topic, max_articles)
    tasks = _tasks(agents, topic, max_articles, max_queries, article_map_block)
    idx=[0]; msgs={"ThaiJO Searcher":"กำลังค้นหา...","Article Screener":"กำลังคัดกรอง...","Citation Generator":"กำลังสร้าง citations...","Research Synthesizer":"กำลังสังเคราะห์...","Report Composer":"กำลังเรียบเรียง..."}
    def pcb(t):
        n=AGENT_NAMES[idx[0]] if idx[0]<len(AGENT_NAMES) else f"Agent"; emit_progress(request_id,n,"done","เสร็จ",time.time()-start)
        if idx[0]+1<len(AGENT_NAMES): emit_progress(request_id,AGENT_NAMES[idx[0]+1],"running",msgs.get(AGENT_NAMES[idx[0]+1],"กำลังทำงาน..."))
        idx[0]+=1
    emit_progress(request_id,AGENT_NAMES[0],"running","กำลังวิเคราะห์หัวข้อ...")
    crew = Crew(agents=list(agents.values()), tasks=tasks, process=Process.sequential, verbose=True, task_callback=pcb)
    try:
        return _parse(kickoff_with_retry(crew), topic, time.time()-start)
    except Exception as e:
        el=time.time()-start
        if idx[0]<len(AGENT_NAMES): emit_progress(request_id,AGENT_NAMES[idx[0]],"error",str(e)[:100],el)
        return ThaiJOResearchResponse(content=f"เกิดข้อผิดพลาด: {e}", topic="error", metadata={"error":str(e),"elapsed_seconds":round(el,1)})

def _fix_searcher_urls(articles: list) -> list:
    """F3: Remap each Searcher article pdf_url against DB cache ground truth.

    The LLM Searcher sometimes substitutes embedded summary URLs for the
    validated pdf_url returned by search_thaijo.  This function cross-checks
    each url against the thaijo_search_cache JSONB and corrects or clears it.

    Strategy (per article):
      1. url already valid in cache → keep as-is
      2. url invalid pattern → try to find a matching cached article by summary
         similarity → replace if found, else clear url
      3. url not found in cache (valid pattern but hallucinated) → clear url

    Fails open on DB error (returns articles unchanged).
    """
    from src.tools.thaijo import _is_valid_thaijo_url, _normalize_to_view_url
    from src.db.pool import query_db
    import json as _json

    try:
        rows = query_db(
            "SELECT results_json FROM thaijo_search_cache WHERE expires_at > NOW()",
            [],
        )
    except Exception as e:
        logger.warning("_fix_searcher_urls: DB error — fail open: %s", e)
        return articles

    # Build two lookups: raw pdf_url → article, and article_id → article
    import re as _re
    cache_url_map: dict = {}
    cache_id_map: dict = {}   # article_id (str) → best cached article
    for row in rows:
        for art in (row.get("results_json") or []):
            url = art.get("pdf_url", "")
            if url and url not in cache_url_map:
                cache_url_map[url] = art
            m = _re.search(r'/article/(?:view|download)/(\d+)', url)
            if m:
                aid = m.group(1)
                if aid not in cache_id_map or (art.get("title") and not cache_id_map[aid].get("title")):
                    cache_id_map[aid] = art

    def _apply_cache(art: dict, cached: dict, src_url: str) -> dict:
        art = dict(art)
        art["pdf_url"] = cached.get("pdf_url", src_url)
        art["article_url"] = cached.get("article_url", "")
        for field in ("title", "apa_authors", "apa_year", "apa_journal", "reference"):
            if cached.get(field) is not None:
                art[field] = cached[field]
        return art

    fixed = []
    for art in articles:
        raw_url = art.get("pdf_url", "")

        # Case 1: exact raw URL in cache
        if raw_url and raw_url in cache_url_map:
            fixed.append(_apply_cache(art, cache_url_map[raw_url], raw_url))
            continue

        # Case 2: same article ID in cache (handles /view/ID vs /view/ID/FILEID mismatch)
        m = _re.search(r'/article/(?:view|download)/(\d+)', raw_url)
        if m and m.group(1) in cache_id_map:
            cached = cache_id_map[m.group(1)]
            logger.info("_fix_searcher_urls: id-match %r → %r", raw_url[:60], cached.get("pdf_url","")[:60])
            fixed.append(_apply_cache(art, cached, raw_url))
            continue

        # Case 3: URL invalid or unknown — try summary-based fuzzy match
        art_summary = (art.get("summary") or "")[:300]
        best_url, best_ratio = "", 0.0
        if art_summary:
            import difflib
            for cached_url, cached_art in cache_url_map.items():
                cs = (cached_art.get("summary") or "")[:300]
                ratio = difflib.SequenceMatcher(None, art_summary, cs).ratio()
                if ratio > best_ratio:
                    best_ratio, best_url = ratio, cached_url

        if best_ratio >= 0.75 and best_url:
            logger.info("_fix_searcher_urls: summary-match %r → %r (ratio=%.2f)", raw_url[:60], best_url[:60], best_ratio)
            fixed.append(_apply_cache(art, cache_url_map[best_url], raw_url))
        elif raw_url and _is_valid_thaijo_url(raw_url):
            # Valid pattern but not in cache — keep as-is
            fixed.append(dict(art))
        else:
            logger.warning("_fix_searcher_urls: clearing unresolvable url=%r", raw_url[:80])
            art = dict(art)
            art["pdf_url"] = ""
            fixed.append(art)

    return fixed


def _parse(result, topic, elapsed):
    import json
    import difflib
    from src.tools.thaijo import _is_valid_thaijo_url
    raw=str(result); to=getattr(result,"tasks_output",None); charts=_charts(raw); tables=_tables(raw); citations=[]; af=0; asel=0

    # Build searcher_articles from Searcher output (to[1]) — closer to API truth than Screener
    searcher_articles = []
    if to and len(to)>=2:
        try:
            m=re.search(r'"total_unique_articles"\s*:\s*(\d+)',getattr(to[1],"raw","") or ""); af=int(m.group(1)) if m else 0
            searcher_raw = getattr(to[1],"raw","") or str(to[1])
            s=searcher_raw.find("{"); e=searcher_raw.rfind("}")
            if s != -1 and e > s:
                searcher_data = json.loads(searcher_raw[s:e+1])
                searcher_articles = _fix_searcher_urls(searcher_data.get("articles", []))
        except: pass

    if to and len(to)>=3:
        try:
            m2=re.search(r'"total_included"\s*:\s*(\d+)',getattr(to[2],"raw","") or ""); asel=int(m2.group(1)) if m2 else 0
        except: pass

    # Build exact url → article map from searcher output
    searcher_url_map = {art.get("pdf_url",""): art for art in searcher_articles if art.get("pdf_url")}

    if to and len(to)>=4:
        try:
            ev=parse_evidence_context(getattr(to[3],"raw","") or str(to[3]))
            citations=[Citation(citation_code=c.citation_code,source_type=c.source_type,source_ref=c.source_ref,citation_text=c.citation_text,open_url=c.open_url,bibliography_text=c.bibliography_text) for c in ev.citations if c.citation_code.startswith("C-2")]

            # RC-4 fix: priority-based URL correction using searcher data (not screener)
            for c in citations:
                # Priority 1: exact match in searcher map — already correct, reinforce reference
                if c.open_url and c.open_url in searcher_url_map:
                    art = searcher_url_map[c.open_url]
                    if art.get("reference"):
                        c.bibliography_text = art["reference"]
                    continue

                # Priority 2: URL fails pattern check → clear immediately
                if c.open_url and not _is_valid_thaijo_url(c.open_url):
                    logger.warning("ThaiJO: invalid URL pattern in citation %s → clearing", c.citation_code)
                    c.open_url = ""
                    continue

                # Priority 3: fuzzy match on searcher articles with threshold 0.6
                if searcher_articles:
                    best_match, best_ratio = None, 0.0
                    for art in searcher_articles:
                        ref2 = art.get("reference") or art.get("summary","")
                        ratio = difflib.SequenceMatcher(None,(c.bibliography_text or "")[:200],ref2[:200]).ratio()
                        if ratio > best_ratio:
                            best_ratio, best_match = ratio, art
                    if best_match and best_ratio >= 0.6:
                        c.open_url = best_match.get("pdf_url", c.open_url)
                        if best_match.get("reference"):
                            c.bibliography_text = best_match["reference"]
                    else:
                        # No reliable match — clear rather than serve wrong URL
                        if c.open_url:
                            logger.warning("ThaiJO: fuzzy ratio %.2f < 0.6 for %s → clearing", best_ratio, c.citation_code)
                            c.open_url = ""

        except Exception as e: logger.warning("Citation parse failed: %s",e)

    # Citation guard: log how many ThaiJO URLs were cleared (hallucination detection)
    cleared = [c for c in citations if c.source_type == "thaijo_article" and not c.open_url]
    if cleared:
        logger.warning("Citation guard: %d ThaiJO citation(s) had URLs cleared (hallucination detected)", len(cleared))

    fus=_followups(raw)
    return ThaiJOResearchResponse(content=raw,topic=topic,articles_found=af,articles_selected=asel,charts=charts,tables=tables,citations=[c.model_dump() for c in citations],follow_ups=fus,metadata={"elapsed_seconds":round(elapsed,1),"pipeline":"thaijo_research","agent_count":6,"citation_count":len(citations)})

def _charts(text):
    out=[]; s=text.find("["); e=text.rfind("]")
    if s==-1 or e<=s: return out
    try:
        for i in json.loads(text[s:e+1]):
            if isinstance(i,dict) and i.get("type") in ("bar","line","pie","doughnut") and "data" in i: out.append(i)
    except: pass
    return out

def _tables(text):
    out=[]; m=re.search(r'"title"\s*:\s*"[^"]*สรุป[^"]*".*?"headers"\s*:.*?"rows"\s*:\s*\[',text,re.DOTALL)
    if m:
        try:
            start=text.rfind("{",0,m.start()); end=text.find("}",text.find("]",m.start()))+1
            d=json.loads(text[start:end]); out.append(d)
        except: pass
    return out

def _followups(text):
    f=[]; lines=text.split("\n"); on=False
    for l in lines:
        s=l.strip()
        if any(k in s.lower() for k in ["คำถามวิจัย","คำถามติดตาม","follow-up","research question"]): on=True; continue
        if on and s:
            c=s.lstrip("- •·*").lstrip("0123456789.").strip()
            if c and len(c)>5: f.append(c)
            if len(f)>=3: break
    return f[:3]
