"""Tests for Shared Foundation factory (Agents 1-4).

Covers:
  - Task 1: Tool name parity — execute_custom_sql (not execute_sql)
  - Task 5: academic_search_needed flag in retrieve task description
  - Task 6: Agent wiring — context chains for full / short / policy modes
"""
import pytest
from unittest.mock import patch, MagicMock

MOCK_LLM = "gemini/gemini-2.0-flash"


# ═══════════════════════════════════════════════════════════════════
# Task 1 — Tool name parity
# ═══════════════════════════════════════════════════════════════════

class TestSqlToolNameParity:
    """execute_custom_sql is the authoritative name — doc previously said execute_sql."""

    def test_execute_custom_sql_decorator_name(self):
        """@tool decorator must register 'execute_custom_sql', not 'execute_sql'."""
        from src.tools.sql_tools import execute_custom_sql
        assert execute_custom_sql.name == "execute_custom_sql"

    def test_explain_schema_decorator_name(self):
        from src.tools.sql_tools import explain_schema
        assert explain_schema.name == "explain_schema"

    def test_sql_specialist_agent_has_correct_tool_names(self):
        """create_sql_specialist() must expose 'execute_custom_sql' in its tool list."""
        from src.agents.sql_specialist import create_sql_specialist
        agent = create_sql_specialist(MOCK_LLM)
        tool_names = [t.name for t in agent.tools]
        assert "execute_custom_sql" in tool_names
        assert "explain_schema" in tool_names
        # The legacy name from the doc must NOT be present
        assert "execute_sql" not in tool_names


# ═══════════════════════════════════════════════════════════════════
# Task 5 — academic_search_needed routing in retrieve task description
# ═══════════════════════════════════════════════════════════════════

class TestAcademicSearchNeedRouting:
    """build_foundation_tasks() must make academic_search_needed explicit in retrieve task."""

    def _build_tasks(self, message: str, mode: str = "full"):
        from src.agents.shared_foundation import build_foundation_agents, build_foundation_tasks
        agents = build_foundation_agents(MOCK_LLM, mode=mode)
        return build_foundation_tasks(agents, message, mode=mode)

    def test_retrieve_task_description_references_academic_search_flag(self):
        """full-mode retrieve task description must mention academic_search_needed."""
        tasks = self._build_tasks("งานวิจัยอุบัติเหตุทางถนน ปัจจัยเสี่ยง")
        assert "academic_search_needed" in tasks["retrieve"].description

    def test_retrieve_task_description_references_search_thaijo(self):
        """full-mode retrieve task must explicitly instruct calling search_thaijo."""
        tasks = self._build_tasks("บทความวิชาการ สุขภาพจิต วัยรุ่น")
        assert "search_thaijo" in tasks["retrieve"].description

    def test_short_mode_retrieve_task_exists(self):
        """short-mode retrieve task must exist (no error when mode='short')."""
        tasks = self._build_tasks("จุดเสี่ยงอุบัติเหตุ จ.อุบล", mode="short")
        assert "retrieve" in tasks


# ═══════════════════════════════════════════════════════════════════
# Task 6 — Integration smoke test: context chains
# ═══════════════════════════════════════════════════════════════════

class TestFoundationFullMode:
    """Full mode (4 agents, 4 tasks) context chain verification."""

    @pytest.fixture(scope="class")
    def agents_and_tasks(self):
        from src.agents.shared_foundation import build_foundation_agents, build_foundation_tasks
        agents = build_foundation_agents(MOCK_LLM, include_thaijo=True)
        tasks = build_foundation_tasks(agents, "สถิติอุบัติเหตุ จ.เชียงใหม่")
        return agents, tasks

    def test_returns_all_four_agents(self, agents_and_tasks):
        agents, _ = agents_and_tasks
        assert agents["interpreter"] is not None
        assert agents["retriever"] is not None
        assert agents["sql_specialist"] is not None
        assert agents["citation_evidence"] is not None

    def test_returns_all_four_task_keys(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        assert set(tasks.keys()) == {"interpret", "retrieve", "sql", "citation"}

    def test_interpret_task_has_no_context(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        ctx = tasks["interpret"].context
        # CrewAI uses _NotSpecified sentinel when context is not set;
        # accept either sentinel or an empty list
        is_empty = not isinstance(ctx, list) or len(ctx) == 0
        assert is_empty

    def test_retrieve_context_contains_interpret_task(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        assert tasks["interpret"] in tasks["retrieve"].context

    def test_sql_context_contains_retrieve_task(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        assert tasks["retrieve"] in tasks["sql"].context

    def test_citation_context_contains_retrieve_task(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        assert tasks["retrieve"] in tasks["citation"].context

    def test_citation_context_contains_sql_task(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        assert tasks["sql"] in tasks["citation"].context

    def test_retriever_has_11_tools_with_thaijo(self, agents_and_tasks):
        agents, _ = agents_and_tasks
        assert len(agents["retriever"].tools) == 11

    def test_retriever_has_10_tools_without_thaijo(self):
        from src.agents.shared_foundation import build_foundation_agents
        agents = build_foundation_agents(MOCK_LLM, include_thaijo=False)
        assert len(agents["retriever"].tools) == 10

    def test_retriever_tool_names_include_search_thaijo(self, agents_and_tasks):
        agents, _ = agents_and_tasks
        tool_names = [t.name for t in agents["retriever"].tools]
        assert "search_thaijo" in tool_names

    def test_retriever_tool_names_include_search_documents(self, agents_and_tasks):
        agents, _ = agents_and_tasks
        tool_names = [t.name for t in agents["retriever"].tools]
        assert "search_documents" in tool_names


class TestFoundationShortMode:
    """Short mode (2 agents, 2 tasks) — SQL and Citation skipped."""

    @pytest.fixture(scope="class")
    def agents_and_tasks(self):
        from src.agents.shared_foundation import build_foundation_agents, build_foundation_tasks
        agents = build_foundation_agents(MOCK_LLM, mode="short")
        tasks = build_foundation_tasks(agents, "จุดเสี่ยงอุบัติเหตุ จ.อุบล", mode="short")
        return agents, tasks

    def test_short_mode_sql_specialist_is_none(self, agents_and_tasks):
        agents, _ = agents_and_tasks
        assert agents["sql_specialist"] is None

    def test_short_mode_citation_evidence_is_none(self, agents_and_tasks):
        agents, _ = agents_and_tasks
        assert agents["citation_evidence"] is None

    def test_short_mode_tasks_has_only_interpret_and_retrieve(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        assert set(tasks.keys()) == {"interpret", "retrieve"}

    def test_short_mode_no_sql_task(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        assert "sql" not in tasks

    def test_short_mode_no_citation_task(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        assert "citation" not in tasks

    def test_short_mode_retriever_has_3_tools_with_thaijo(self, agents_and_tasks):
        agents, _ = agents_and_tasks
        assert len(agents["retriever"].tools) == 3

    def test_short_mode_retriever_has_2_tools_without_thaijo(self):
        from src.agents.shared_foundation import build_foundation_agents
        agents = build_foundation_agents(MOCK_LLM, mode="short", include_thaijo=False)
        assert len(agents["retriever"].tools) == 2

    def test_short_mode_retrieve_context_contains_interpret(self, agents_and_tasks):
        _, tasks = agents_and_tasks
        assert tasks["interpret"] in tasks["retrieve"].context


class TestFoundationPolicyMode:
    """Policy mode adds NLM tools (+2) to retriever."""

    @pytest.fixture(scope="class")
    def agents(self):
        from src.agents.shared_foundation import build_foundation_agents
        return build_foundation_agents(
            MOCK_LLM,
            include_nlm=True,
            include_thaijo=True,
            province="อุบลราชธานี",
            notebook_id="test-notebook-id",
        )

    def test_policy_mode_retriever_has_13_tools(self, agents):
        assert len(agents["retriever"].tools) == 13

    def test_policy_mode_includes_nlm_ask(self, agents):
        # Actual decorator name from src/tools/notebooklm.py
        tool_names = [t.name for t in agents["retriever"].tools]
        assert "NotebookLM Ask Tool" in tool_names

    def test_policy_mode_includes_get_supported_provinces(self, agents):
        tool_names = [t.name for t in agents["retriever"].tools]
        assert "Get Supported Provinces" in tool_names

    def test_policy_mode_includes_search_thaijo(self, agents):
        tool_names = [t.name for t in agents["retriever"].tools]
        assert "search_thaijo" in tool_names

    def test_policy_mode_sql_specialist_not_none(self, agents):
        assert agents["sql_specialist"] is not None

    def test_policy_mode_citation_evidence_not_none(self, agents):
        assert agents["citation_evidence"] is not None
