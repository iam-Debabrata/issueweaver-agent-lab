"""Architect -> Coder -> Tester -> Repair -> Reviewer -> optional PR publisher."""

from __future__ import annotations

from typing import Awaitable, Callable

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - installed production path uses LangGraph
    from .graph_compat import END, START, StateGraph

from .models import AgentState, TestResult
from .providers import AgentProvider
from .workspace import apply_proposal, source_context

PublishFn = Callable[[AgentState], Awaitable[str]]


def build_graph(provider: AgentProvider, sandbox: object, publish_fn: PublishFn | None = None):
    async def architect(state: AgentState) -> dict:
        plan = await provider.plan(
            state["issue_title"], state["issue_body"], source_context(state["workspace"])
        )
        return {"plan": plan, "trace": [*state.get("trace", []), f"Architect: {len(plan.tasks)} tasks"]}

    async def propose(state: AgentState, *, repair: bool) -> dict:
        attempt = state.get("attempt", 0) + (1 if repair else 0)
        feedback = state["test"].output if repair else ""
        proposal = await provider.code(
            state["issue_title"], state["issue_body"], state["plan"],
            source_context(state["workspace"]), attempt, feedback,
        )
        files = apply_proposal(state["workspace"], proposal)
        step = "Repair" if repair else "Coder"
        return {
            "files": {**state.get("files", {}), **files},
            "attempt": attempt,
            "trace": [*state.get("trace", []), f"{step}: {len(files)} file(s), revision {attempt}"],
        }

    async def coder(state: AgentState) -> dict:
        return await propose(state, repair=False)

    async def repair(state: AgentState) -> dict:
        return await propose(state, repair=True)

    async def tester(state: AgentState) -> dict:
        result: TestResult = await sandbox.run(state["workspace"])
        return {
            "test": result,
            "trace": [*state.get("trace", []), f"Tester: {'PASS' if result.passed else 'FAIL'}"],
        }

    def after_test(state: AgentState) -> str:
        if state["test"].passed:
            return "reviewer"
        if state["test"].exit_code == 124:  # infrastructure errors are not code bugs
            return "finish"
        if state.get("attempt", 0) < state.get("max_repairs", 2):
            return "repair"
        return "finish"

    async def reviewer(state: AgentState) -> dict:
        if not state["files"] or not state["test"].passed:
            return {"status": "review_rejected"}
        return {
            "status": "passed",
            "trace": [*state.get("trace", []), "Reviewer: tests green; human review required"],
        }

    async def publisher(state: AgentState) -> dict:
        if state.get("status") != "passed":
            return {"status": "review_rejected"}
        if not state.get("publish", False):
            return {"status": "passed_dry_run", "trace": [*state["trace"], "Publisher: dry-run"]}
        if publish_fn is None:
            raise ValueError("Publication requested but no GitHub publisher configured")
        url = await publish_fn(state)
        return {"status": "pr_created", "pr_url": url, "trace": [*state["trace"], "Publisher: PR created"]}

    async def finish(state: AgentState) -> dict:
        detail = ("sandbox infrastructure unavailable" if state["test"].exit_code == 124
                  else "repair budget exhausted")
        return {"status": "tests_failed", "trace": [*state["trace"], f"Stopped: {detail}"]}

    graph = StateGraph(AgentState)
    for name, fn in (
        ("architect", architect), ("coder", coder), ("repair", repair),
        ("tester", tester), ("reviewer", reviewer), ("publisher", publisher), ("finish", finish),
    ):
        graph.add_node(name, fn)
    graph.add_edge(START, "architect")
    graph.add_edge("architect", "coder")
    graph.add_edge("coder", "tester")
    graph.add_conditional_edges("tester", after_test, {
        "reviewer": "reviewer", "repair": "repair", "finish": "finish",
    })
    graph.add_edge("repair", "tester")
    graph.add_edge("reviewer", "publisher")
    graph.add_edge("publisher", END)
    graph.add_edge("finish", END)
    return graph.compile()
