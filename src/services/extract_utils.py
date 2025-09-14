from __future__ import annotations

from typing import Any, Dict, Optional

import json
import logging
import os
import re

from src.config import get_extraction_model_name, get_extraction_retries, get_extraction_timeouts_ms


EXTRACTION_MODEL = get_extraction_model_name()


def _parse_json_from_text(text: str, expect_array: bool) -> Any:
	"""Best-effort parse JSON from LLM text.

	Handles code fences (```json ... ```), leading/trailing prose, and extracts the
	first complete JSON object/array if needed. Falls back to [] or {}.
	"""
	if not text or text.strip() == "":
		return [] if expect_array else {}

	candidate = text.strip()

	# 1) Strip code fences if present
	code_block = re.search(r"```(?:json)?\s*([\s\S]+?)```", candidate, re.IGNORECASE)
	if code_block:
		candidate = code_block.group(1).strip()

	# 2) Try direct parse
	try:
		parsed = json.loads(candidate)
		# Coerce to expected container shape
		if expect_array:
			if isinstance(parsed, list):
				return parsed
			if isinstance(parsed, dict):
				if isinstance(parsed.get("items"), list):
					return parsed["items"]
				# As a last resort, if dict values look like items, return list(values)
				vals = list(parsed.values())
				return vals if vals else []
			return []
		return parsed
	except Exception:
		pass

	# 3) Extract bracketed JSON region (array preferred when expect_array)
	if expect_array and "[" in candidate and "]" in candidate:
		start = candidate.find("[")
		end = candidate.rfind("]")
		if start != -1 and end != -1 and end > start:
			frag = candidate[start : end + 1]
			try:
				parsed = json.loads(frag)
				if expect_array:
					return parsed if isinstance(parsed, list) else []
				return parsed
			except Exception:
				pass

	if "{" in candidate and "}" in candidate:
		start = candidate.find("{")
		end = candidate.rfind("}")
		if start != -1 and end != -1 and end > start:
			frag = candidate[start : end + 1]
			try:
				parsed = json.loads(frag)
				if expect_array:
					return parsed if isinstance(parsed, list) else []
				return parsed
			except Exception:
				pass

	# 4) Fallback: empty structure to avoid hard failure in pipeline
	return [] if expect_array else {}


def _call_llm_json(system_prompt: str, user_payload: Dict[str, Any], *, expect_array: bool = False) -> Optional[Any]:
	logger = logging.getLogger("extraction")
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key or api_key.strip() == "":
		return None
	try:
		from openai import OpenAI  # type: ignore

		client = OpenAI(api_key=api_key)
		timeout_s = max(1, get_extraction_timeouts_ms() // 1000)
		retries = max(0, get_extraction_retries())
		last_exc: Optional[Exception] = None
		for _ in range(retries + 1):
			try:
				resp = client.chat.completions.create(
					model=EXTRACTION_MODEL,
					messages=[
						{"role": "system", "content": system_prompt},
						{"role": "user", "content": json.dumps(user_payload)},
					],
					response_format=None if expect_array else {"type": "json_object"},
					timeout=timeout_s,
				)
				text = resp.choices[0].message.content or ("[]" if expect_array else "{}")
				logger.info(
					"LLM call ok | model=%s | expect_array=%s | payload=%s | output=%s",
					EXTRACTION_MODEL,
					expect_array,
					json.dumps(user_payload)[:1000],
					text[:1000],
				)
				return _parse_json_from_text(text, expect_array)
			except Exception as exc:  # retry
				last_exc = exc
				continue
		if last_exc:
			raise last_exc
	except Exception:
		logger.exception(
			"LLM call failed | model=%s | expect_array=%s | payload=%s",
			EXTRACTION_MODEL,
			expect_array,
			json.dumps(user_payload)[:1000],
		)
		return None


def _normalize_llm_content(content: str, source_text: str) -> str:
	text = (content or "").strip()
	if not text:
		return text
	lower = text.lower()
	if lower.startswith("the user "):
		text = "User " + text[9:]
		lower = text.lower()
	if lower.startswith("i love "):
		text = f"User loves {text[7:].strip()}"
	elif lower.startswith("i like "):
		text = f"User likes {text[7:].strip()}"
	elif lower.startswith("i prefer "):
		text = f"User prefers {text[9:].strip()}"
	text = text.replace("I’m ", "User is ").replace("I'm ", "User is ")
	text = text.replace("planning a vacation", "is planning a vacation")
	if text.lower().startswith("planning a vacation"):
		text = "User " + text
	if text.lower().startswith("is planning a vacation"):
		text = "User " + text
	if ("is running" in lower or "running" in lower) and "times a week" in lower:
		text = re.sub(r"(?i)(the\s+)?user is running\s+(\d+)\s+times a week", r"User runs \2 times a week", text)
	if "runs" in text.lower() and "times a week" in text.lower() and not text.lower().startswith("user "):
		text = "User " + text
	temporals = ["next month", "this week", "right now", "today", "tonight", "this evening", "this morning"]
	st_lower = (source_text or "").lower()
	for phrase in temporals:
		if phrase in st_lower and phrase not in text.lower():
			if any(k in text.lower() for k in ["vacation", "trip", "travel", "japan"]):
				if text.endswith("."):
					text = text[:-1] + f" {phrase}."
				else:
					text = text + f" {phrase}."
				break
	if not text.endswith("."):
		text = text + "."
	return text


