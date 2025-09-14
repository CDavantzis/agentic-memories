WORTHINESS_PROMPT = """
You extract whether a user's recent message is memory-worthy for personalization.
Return ONLY valid JSON with this schema:
{
  "worthy": boolean,
  "confidence": number,
  "tags": string[],
  "reasons": string[]
}

Guidelines (recall-first):
- Worthy if: stable preferences, bio/identity, habits, emotions affecting choices, professional facts, skills/tools, projects (plans/decisions/milestones/next_action), relationships, learning progress.
- Also worthy: time-bound next_action (store short-term).
- Not worthy alone: greetings, meta-chatter, filler.
- English only.
""".strip()


TYPING_PROMPT = """
Classify the memory's type and layer. Return ONLY JSON:
{
  "type": "explicit" | "implicit",
  "layer": "short-term" | "semantic" | "long-term",
  "ttl": number | null,
  "confidence_type": number,
  "confidence_layer": number,
  "rationale": string
}

Rules:
- explicit: stated facts; implicit: inferred (mood/trait).
- short-term: time-bound or "next_action" (use ttl ~3600–172800 seconds).
- semantic: stable preferences, bio/pro work facts, habits, learning progress, relationships.
- long-term: summaries/archives (rare in this phase).
""".strip()


EXTRACTION_PROMPT = """
Extract atomic, declarative memories as a JSON array (max 10). Each item:
{
  "content": string,
  "type": "explicit" | "implicit",
  "layer": "short-term" | "semantic" | "long-term",
  "ttl": number | null,
  "confidence": number,
  "tags": string[],

  "project": {
    "project_id": string | null,
    "title": string | null,
    "status": "planned" | "active" | "paused" | "blocked" | "completed" | "canceled" | null,
    "domain": "personal" | "professional" | "home_improvement" | "travel" | "learning" | "other" | null,
    "next_action": string | null,
    "due_date": string | null,
    "priority": "low" | "medium" | "high" | null,
    "participants": string[] | null,
    "tools": string[] | null,
    "milestone": string | null,
    "decision": string | null
  } | null,

  "relationship": {
    "person_name": string | null,
    "closeness": "acquaintance" | "friend" | "close_friend" | "family" | "partner" | null,
    "notes": string | null
  } | null,

  "learning_journal": {
    "topic": string | null,
    "goal": string | null,
    "progress_level": "beginner" | "intermediate" | "advanced" | null,
    "streak_days": number | null,
    "last_activity_date": string | null,
    "recent_practice": string | null
  } | null
}

Instructions:
- Parse last 4–6 turns; produce atomic facts across: projects, preferences, emotions, behaviors, relationships, learning_journal.
- Projects: unify; decisions/milestones/next_action/due_date live in project object.
- Relationships: capture closeness and "getting to know someone"; include helpful notes.
- Learning_journal: capture active learning, goals, progress level, recent practice.

CONTENT NORMALIZATION RULES (CRITICAL):
- Content MUST begin with the literal prefix "User ".
- Convert first-person statements to third-person:
  * "I love X" → "User loves X"
  * "I like X" → "User likes X" 
  * "I prefer X" → "User prefers X"
  * "I'm doing X" → "User is doing X"
  * "I am doing X" → "User is doing X"
- Normalize verb tenses to simple present when appropriate:
  * "is running 3 times a week" → "runs 3 times a week"
  * "is planning a vacation" → "is planning a vacation" (keep for temporal context)
- Preserve explicit temporal phrases verbatim in content (e.g., "next month", "this week", "today").
- Ensure content ends with a period.
- Remove any leading "The user " and replace with "User ".
- For vacation/travel content, preserve temporal context from source text.

Examples of proper normalization:
- "I love working on AI projects" → "User loves working on AI projects."
- "I'm planning a vacation next month" → "User is planning a vacation next month."
- "I run 3 times a week" → "User runs 3 times a week."
- "The user prefers coffee" → "User prefers coffee."

Time-bound → short-term (ttl set); stable → semantic; no duplicates; STRICT JSON.
""".strip()


