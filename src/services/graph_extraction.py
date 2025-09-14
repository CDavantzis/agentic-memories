from __future__ import annotations

from typing import Any, Dict, List, Optional

import json

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from src.services.prompts import WORTHINESS_PROMPT, EXTRACTION_PROMPT
from src.schemas import TranscriptRequest
from src.services.extract_utils import _call_llm_json


def build_extraction_graph() -> StateGraph:
	graph = StateGraph(dict)

	def node_worthiness(state: Dict[str, Any]) -> Dict[str, Any]:
		payload = {"history": state["history"][-6:]}
		resp = _call_llm_json(WORTHINESS_PROMPT, payload)
		state["worthy"] = bool(resp and resp.get("worthy", False))
		state["worthy_raw"] = resp
		return state

	def decide_next(state: Dict[str, Any]) -> str:
		return "extract" if state.get("worthy") else END

	def node_extract(state: Dict[str, Any]) -> Dict[str, Any]:
		payload = {"history": state["history"][-6:]}
		items = _call_llm_json(EXTRACTION_PROMPT, payload, expect_array=True) or []
		state["items"] = items
		return state

	graph.add_node("worth", node_worthiness)
	graph.add_node("extract", node_extract)
	graph.set_entry_point("worth")
	graph.add_conditional_edges("worth", decide_next, {"extract": "extract", END: END})
	graph.add_edge("extract", END)
	return graph


def run_extraction_graph(request: TranscriptRequest) -> Dict[str, Any]:
	graph = build_extraction_graph()
	state: Dict[str, Any] = {"history": [m.model_dump() for m in request.history]}
	result = graph.compile().invoke(state)
	return result


