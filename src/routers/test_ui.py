"""Test UI endpoints — tool testing and SQL query execution for the test dashboard."""
import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.db.pool import query_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/test", tags=["test"])


# ---- Request schemas ----

class ToolRequest(BaseModel):
    start_date: str = ""
    end_date: str = ""
    geography: str = ""
    top_n: int = 10
    province_name: str = ""
    keywords: str = ""
    topic: str = "accident"
    n_results: int = 5


class SQLRequest(BaseModel):
    sql: str


# ---- Tool test endpoints ----

def _thai_json(data: dict) -> JSONResponse:
    """Return JSON response with Thai characters unescaped (not ASCII-escaped)."""
    from fastapi.responses import Response
    return Response(
        content=json.dumps(data, ensure_ascii=False),
        media_type="application/json; charset=utf-8",
    )


@router.post("/tool/accident_summary")
async def test_accident_summary(req: ToolRequest):
    from src.tools.accident import get_accident_summary
    result = get_accident_summary.run(
        start_date=req.start_date, end_date=req.end_date, geography=req.geography
    )
    return _thai_json({"tool": "get_accident_summary", "result": result})


@router.post("/tool/hotspots")
async def test_hotspots(req: ToolRequest):
    from src.tools.accident import get_accident_hotspots
    result = get_accident_hotspots.run(top_n=req.top_n)
    return _thai_json({"tool": "get_accident_hotspots", "result": result})


@router.post("/tool/time_distribution")
async def test_time_distribution():
    from src.tools.accident import get_accident_time_distribution
    result = get_accident_time_distribution.run()
    return _thai_json({"tool": "get_accident_time_distribution", "result": result})


@router.post("/tool/road_condition_risk")
async def test_road_condition_risk():
    from src.tools.accident import get_road_condition_risk
    result = get_road_condition_risk.run()
    return _thai_json({"tool": "get_road_condition_risk", "result": result})


@router.post("/tool/geography")
async def test_geography(req: ToolRequest):
    from src.tools.common import get_geography_profile
    result = get_geography_profile.run(province_name=req.province_name or "กรุงเทพ")
    return _thai_json({"tool": "get_geography_profile", "result": result})


@router.post("/tool/search_documents")
async def test_search_documents(req: ToolRequest):
    from src.tools.common import search_documents
    result = search_documents.run(topic=req.topic, keywords=req.keywords or "อุบัติเหตุ", n_results=req.n_results)
    return _thai_json({"tool": "search_documents", "result": result})


@router.post("/tool/indicator_catalog")
async def test_indicator_catalog(req: ToolRequest):
    from src.tools.common import get_indicator_catalog
    result = get_indicator_catalog.run(topic=req.topic)
    return _thai_json({"tool": "get_indicator_catalog", "result": result})


# ---- Chart tool test endpoints ----

class ChartToolRequest(BaseModel):
    province: str = ""
    year: int = 0
    top_n: int = 10
    start_date: str = ""
    end_date: str = ""


@router.post("/chart/accident_trend")
async def test_chart_accident_trend(req: ChartToolRequest):
    from src.tools.chart_builder import build_accident_trend_chart
    result = build_accident_trend_chart.run(start_date=req.start_date, end_date=req.end_date)
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = {"raw": result}
    return _thai_json({"tool": "build_accident_trend_chart", "chart": parsed})


@router.post("/chart/hotspot")
async def test_chart_hotspot(req: ChartToolRequest):
    from src.tools.chart_builder import build_hotspot_bar_chart
    result = build_hotspot_bar_chart.run(top_n=req.top_n)
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = {"raw": result}
    return _thai_json({"tool": "build_hotspot_bar_chart", "chart": parsed})


@router.post("/chart/time_dist")
async def test_chart_time_dist():
    from src.tools.chart_builder import build_time_distribution_chart
    result = build_time_distribution_chart.run()
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = {"raw": result}
    return _thai_json({"tool": "build_time_distribution_chart", "chart": parsed})


@router.post("/chart/road_condition")
async def test_chart_road_condition():
    from src.tools.chart_builder import build_road_condition_pie_chart
    result = build_road_condition_pie_chart.run()
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = {"raw": result}
    return _thai_json({"tool": "build_road_condition_pie_chart", "chart": parsed})


@router.post("/chart/province_trend")
async def test_chart_province_trend(req: ChartToolRequest):
    from src.tools.chart_builder import build_province_year_trend_chart
    result = build_province_year_trend_chart.run(province=req.province, top_n=req.top_n)
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = {"raw": result}
    return _thai_json({"tool": "build_province_year_trend_chart", "chart": parsed})


@router.post("/chart/province_roads")
async def test_chart_province_roads(req: ChartToolRequest):
    from src.tools.chart_builder import build_province_roads_bar_chart
    result = build_province_roads_bar_chart.run(province=req.province, year=req.year, top_n=req.top_n)
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = {"raw": result}
    return _thai_json({"tool": "build_province_roads_bar_chart", "chart": parsed})


@router.post("/chart/monthly_death")
async def test_chart_monthly_death(req: ChartToolRequest):
    from src.tools.chart_builder import build_monthly_death_bar_chart
    result = build_monthly_death_bar_chart.run(year=req.year)
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = {"raw": result}
    return _thai_json({"tool": "build_monthly_death_bar_chart", "chart": parsed})


# ---- SQL query endpoint (read-only) ----

@router.post("/query")
async def run_query(req: SQLRequest):
    sql = req.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL cannot be empty")

    # Safety: only allow SELECT statements
    first_word = sql.split()[0].upper()
    if first_word not in ("SELECT", "WITH"):
        return {"error": "Only SELECT/WITH queries are allowed", "rows": []}

    try:
        rows = query_db(sql)
        # Convert Decimal and other non-JSON types
        clean_rows = []
        for row in rows:
            clean = {}
            for k, v in row.items():
                if hasattr(v, '__float__'):
                    clean[k] = float(v)
                elif hasattr(v, 'isoformat'):
                    clean[k] = v.isoformat()
                else:
                    clean[k] = v
            clean_rows.append(clean)
        return _thai_json({"rows": clean_rows[:100]})
    except Exception as e:
        logger.error(f"SQL query failed: {e}")
        return _thai_json({"error": str(e), "rows": []})
