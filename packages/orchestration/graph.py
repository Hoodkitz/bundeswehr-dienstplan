"""LangGraph workflow for roster optimization."""
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
from uuid import UUID


class RosterState(TypedDict):
    tenant_id: str
    planungszeitraum_start: str
    planungszeitraum_ende: str
    status: str
    roster_data: Optional[dict]
    validation_result: Optional[dict]
    approval_status: Optional[str]


def build_graph():
    graph = StateGraph(RosterState)

    def fetch_data(state: RosterState) -> RosterState:
        state["status"] = "DATA_FETCHING"
        return state

    def validate_constraints(state: RosterState) -> RosterState:
        state["status"] = "CONSTRAINT_VALIDATION"
        return state

    def optimize(state: RosterState) -> RosterState:
        state["status"] = "SOLVER_OPTIMIZING"
        return state

    def check_feasibility(state: RosterState) -> RosterState:
        state["status"] = "HARDFEASIBILITY_CHECK"
        return state

    def simulate(state: RosterState) -> RosterState:
        state["status"] = "SIMULATION_REVIEW"
        return state

    def approval_interrupt(state: RosterState) -> RosterState:
        state["status"] = "COMMAND_APPROVAL_INTERRUPT"
        return state

    graph.add_node("fetch_data", fetch_data)
    graph.add_node("validate", validate_constraints)
    graph.add_node("optimize", optimize)
    graph.add_node("feasibility", check_feasibility)
    graph.add_node("simulate", simulate)
    graph.add_node("approval", approval_interrupt)

    graph.set_entry_point("fetch_data")
    graph.add_edge("fetch_data", "validate")
    graph.add_edge("validate", "optimize")
    graph.add_edge("optimize", "feasibility")
    graph.add_edge("feasibility", "simulate")
    graph.add_edge("simulate", "approval")
    graph.add_edge("approval", END)

    return graph.compile()


graph = build_graph()
