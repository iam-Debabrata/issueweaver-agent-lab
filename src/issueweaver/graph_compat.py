"""Tiny *test-only* graph fallback when offline environments cannot install LangGraph.

Production installations use the real langgraph.graph.StateGraph; this is not a fork.
"""

START, END = "__start__", "__end__"


class StateGraph:
    def __init__(self, schema):
        self.nodes = {}
        self.edges = {}
        self.conditions = {}

    def add_node(self, name, fn):
        self.nodes[name] = fn

    def add_edge(self, source, target):
        self.edges[source] = target

    def add_conditional_edges(self, source, fn, mapping):
        self.conditions[source] = (fn, mapping)

    def compile(self):
        return _Compiled(self.nodes, self.edges, self.conditions)


class _Compiled:
    def __init__(self, nodes, edges, conditions):
        self.nodes = nodes
        self.edges = edges
        self.conditions = conditions

    async def ainvoke(self, state):
        state = state.copy()
        cursor = self.edges[START]
        for _ in range(40):
            if cursor == END:
                return state
            update = await self.nodes[cursor](state)
            state.update(update)
            if cursor in self.conditions:
                route, mapping = self.conditions[cursor]
                cursor = mapping[route(state)]
            else:
                cursor = self.edges[cursor]
        raise RuntimeError("Agent graph step limit exceeded")
