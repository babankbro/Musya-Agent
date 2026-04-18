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

def _tasks(agents, topic, max_articles, max_queries):
    t1 = Task(description=THAIJO_TOPIC_PARSER_PROMPT.replace("{topic}",topic).replace("{max_queries}",str(max_queries)).replace("{max_articles}",str(max_articles)),
              expected_output="JSON: main_topic, domain, search_queries, criteria", agent=agents["topic_parser"])
    t2 = Task(description=THAIJO_SEARCHER_PROMPT.replace("{search_queries}","ดึงจาก Topic Parser — ต้องเรียก search_thaijo สำหรับทุกๆ keyword query ที่ Topic Parser ให้มา ห้ามข้ามแม้แต่ข้อเดียว"),
              expected_output="JSON: total_queries, articles[], query_results[]", agent=agents["searcher"], context=[t1])
    t3 = Task(description=THAIJO_SCREENER_PROMPT.replace("{main_topic}",topic).replace("{domain}","ดึงจาก Topic Parser").replace("{inclusion_criteria}","ดึงจาก Topic Parser").replace("{exclusion_criteria}","ดึงจาก Topic Parser").replace("{articles_json}","ดึงจาก Searcher output"),
              expected_output="JSON: screened_articles[], total_included, total_excluded", agent=agents["screener"], context=[t1,t2])
    cdesc = CITATION_EVIDENCE_PROMPT + f"\n\n**ThaiJO Context:** หัวข้อ: {topic}\nC-200~C-299 for thaijo_article. reference→bibliography_text (ห้ามแต่ง). open_url=pdf_url. source_type=thaijo_article. trust_level=medium. Dedup by pdf_url.\n"
    t4 = Task(description=cdesc, expected_output="JSON: evidence_items, citations (C-200+), coverage", agent=agents["citation_gen"], context=[t2,t3])
    t5 = Task(description=THAIJO_RESEARCH_SYNTHESIZER_PROMPT.replace("{main_topic}",topic).replace("{screened_articles_json}","ดึงจาก Screener").replace("{citation_codes_json}","ดึงจาก Citation Generator"),
              expected_output="JSON: themes[], overall_findings, research_gaps[]", agent=agents["synthesizer"], context=[t3,t4])
    t6 = Task(description=THAIJO_REPORT_COMPOSER_PROMPT.replace("{main_topic}",topic).replace("{synthesis_json}","ดึงจาก Synthesizer").replace("{citations_json}","ดึงจาก Citation Generator"),
              expected_output="Markdown report + JSON table + JSON chart + APA refs + follow-ups", agent=agents["composer"], context=[t5,t4])
    return [t1,t2,t3,t4,t5,t6]

def run_thaijo_research(topic, max_articles=15, max_queries=4, min_relevance=5.0, session_id=None):
    start = time.time(); agents = build_thaijo_research_crew(); tasks = _tasks(agents, topic, max_articles, max_queries)
    crew = Crew(agents=list(agents.values()), tasks=tasks, process=Process.sequential, verbose=True)
    logger.info("🚀 [THAIJO RESEARCH] topic: %s", topic[:120])
    try:
        return _parse(crew.kickoff(), topic, time.time()-start)
    except Exception as e:
        return ThaiJOResearchResponse(content=f"เกิดข้อผิดพลาด: {e}", topic="error", metadata={"error":str(e),"elapsed_seconds":round(time.time()-start,1)})

def run_thaijo_research_with_progress(topic, max_articles=15, max_queries=4, min_relevance=5.0, session_id=None, request_id=None):
    start = time.time(); agents = build_thaijo_research_crew(); tasks = _tasks(agents, topic, max_articles, max_queries)
    idx=[0]; msgs={"ThaiJO Searcher":"กำลังค้นหา...","Article Screener":"กำลังคัดกรอง...","Citation Generator":"กำลังสร้าง citations...","Research Synthesizer":"กำลังสังเคราะห์...","Report Composer":"กำลังเรียบเรียง..."}
    def pcb(t):
        n=AGENT_NAMES[idx[0]] if idx[0]<len(AGENT_NAMES) else f"Agent"; emit_progress(request_id,n,"done","เสร็จ",time.time()-start)
        if idx[0]+1<len(AGENT_NAMES): emit_progress(request_id,AGENT_NAMES[idx[0]+1],"running",msgs.get(AGENT_NAMES[idx[0]+1],"กำลังทำงาน..."))
        idx[0]+=1
    emit_progress(request_id,AGENT_NAMES[0],"running","กำลังวิเคราะห์หัวข้อ...")
    crew = Crew(agents=list(agents.values()), tasks=tasks, process=Process.sequential, verbose=True, task_callback=pcb)
    try:
        return _parse(crew.kickoff(), topic, time.time()-start)
    except Exception as e:
        el=time.time()-start
        if idx[0]<len(AGENT_NAMES): emit_progress(request_id,AGENT_NAMES[idx[0]],"error",str(e)[:100],el)
        return ThaiJOResearchResponse(content=f"เกิดข้อผิดพลาด: {e}", topic="error", metadata={"error":str(e),"elapsed_seconds":round(el,1)})

def _parse(result, topic, elapsed):
    raw=str(result); to=getattr(result,"tasks_output",None); charts=_charts(raw); tables=_tables(raw); citations=[]; af=0; asel=0
    if to and len(to)>=4:
        try:
            ev=parse_evidence_context(getattr(to[3],"raw","") or str(to[3]))
            citations=[Citation(citation_code=c.citation_code,source_type=c.source_type,source_ref=c.source_ref,citation_text=c.citation_text,open_url=c.open_url,bibliography_text=c.bibliography_text) for c in ev.citations if c.citation_code.startswith("C-2")]
        except Exception as e: logger.warning("Citation parse failed: %s",e)
    if to and len(to)>=3:
        try:
            m=re.search(r'"total_unique_articles"\s*:\s*(\d+)',getattr(to[1],"raw","") or ""); af=int(m.group(1)) if m else 0
            m2=re.search(r'"total_included"\s*:\s*(\d+)',getattr(to[2],"raw","") or ""); asel=int(m2.group(1)) if m2 else 0
        except: pass
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
