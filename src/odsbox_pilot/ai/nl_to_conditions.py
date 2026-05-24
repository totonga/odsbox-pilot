"""Natural language to ODS query conditions parser."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict

from odsbox_pilot.ai.date_parser import parse_date_expressions
from odsbox_pilot.ai.llm_pipeline import OvLlmPipeline
from odsbox_pilot.model.search_index import ModelSearchIndex

log = logging.getLogger(__name__)


class ConditionDict(TypedDict):
    """Condition dictionary format compatible with browse._helpers."""

    entity: str  # Entity name (e.g., "AoMeasurement")
    attr: str  # Attribute name (e.g., "name")
    op: str  # Operator (e.g., "$like", "$eq", "$between")
    val: Any  # Value (string, int, float, or list for $between/$in)


@dataclass
class NlParseResult:
    """Result of parsing natural language into conditions."""

    conditions: list[ConditionDict]
    root_entity: str
    raw_response: str  # Raw LLM response for debugging
    invalid_conditions: list[
        dict[str, Any]
    ]  # Conditions the LLM produced that could not be resolved


class NlToConditions:
    """Parse natural language queries into ODS filter conditions.

    Combines semantic search over the ODS model with an LLM to extract
    structured conditions from user queries.
    """

    def __init__(self, model_index: ModelSearchIndex, pipeline: OvLlmPipeline) -> None:
        """Initialize the parser.

        Args:
            model_index: Semantic search index over ODS model.
            pipeline: OpenVINO GenAI LLM pipeline.
        """
        self._index = model_index
        self._pipeline = pipeline

    def parse(
        self,
        text: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> NlParseResult:
        """Parse natural language query into conditions.

        Args:
            text: Natural language query (e.g., "Zeig mir Messungen Profile_*").
            on_progress: Optional callback called with a short status message at
                each phase so the caller can update a progress indicator.

        Returns:
            NlParseResult containing conditions, root entity, and raw response.

        Raises:
            ValueError: If LLM response cannot be parsed or is invalid.
        """

        def _progress(msg: str) -> None:
            if on_progress is not None:
                on_progress(msg)

        # Step 1: Extract date expressions (rule-based)
        _progress("Parsing date expressions\u2026")
        date_conditions = parse_date_expressions(text)

        # Step 2: Build schema context via semantic search
        _progress("Building schema context\u2026")
        schema_context = self._build_schema_context(text)

        # Step 3: Build LLM prompt
        messages = self._build_prompt(text, schema_context, date_conditions)

        # Step 4: Call LLM
        _progress("Calling AI model\u2026")
        raw_response = self._pipeline.generate(messages, max_new_tokens=512, temperature=0.3)

        # Step 5: Parse and validate conditions
        _progress("Extracting conditions\u2026")
        conditions, invalid_conditions, root_entity = self._parse_response(
            raw_response, date_conditions
        )

        return NlParseResult(
            conditions=conditions,
            root_entity=root_entity,
            raw_response=raw_response,
            invalid_conditions=invalid_conditions,
        )

    def _build_schema_context(self, text: str, top_k: int = 30) -> str:
        """Build schema context by semantic search then expanding to full entity schemas.

        Rather than showing only the semantically matched attributes (which the
        LLM tends to ignore), this method surfaces the **complete** attribute
        list for each matched entity.  This prevents the LLM from inventing
        attribute names that do not exist in the model.

        Args:
            text: User query text.
            top_k: Number of top semantic matches used to identify relevant entities.

        Returns:
            Formatted schema context string, grouped by entity.
        """
        matches = self._index.search(text, top_k=top_k)

        # Collect unique entity names in order of relevance
        seen: dict[str, None] = {}
        for m in matches:
            if m.entity_name:
                seen[m.entity_name] = None

        # For each relevant entity show its attribute list (relations omitted —
        # FilterTree resolves join paths automatically, and relation lines are
        # expensive tokens on NPU which has a tight prompt-length budget).
        parts: list[str] = []
        for entity_name in list(seen.keys())[:4]:
            schema = self._index.entity_schema(entity_name)
            if schema:
                attr_only = "\n".join(
                    line
                    for line in schema.splitlines()
                    if not line.lstrip().startswith("relation ")
                )
                parts.append(attr_only)

        return "\n\n".join(parts)

    def _build_prompt(
        self,
        text: str,
        schema_context: str,
        date_conditions: list[Any],
    ) -> list[dict[str, str]]:
        """Build LLM prompt with system and user messages.

        Args:
            text: User query text.
            schema_context: Formatted schema context from semantic search.
            date_conditions: Pre-extracted date conditions from date_parser.

        Returns:
            OpenAI-style message list.
        """
        system_prompt = f"""You are an ODS (ASAM Open Data Services) query assistant.
Your task is to parse natural language queries into structured filter conditions.

## ODS Schema (entities and their exact attribute names)
{schema_context}

## CRITICAL RULES
- Use ONLY the entity names and attribute names listed above, EXACTLY as written (case-sensitive).
- Do NOT invent, guess, or paraphrase attribute names.
- If a concept has no matching attribute in the schema, omit that condition.
- For conditions on related entities (e.g. project name), use a separate condition object with the correct entity name and attribute.

## Output Format
Return a JSON object with:
- "root_entity": the primary entity to query (use exact name from schema)
- "conditions": array of condition objects

Each condition object has:
- "entity": entity name (exact, from schema)
- "attr": attribute name (exact, from schema)
- "op": operator — one of: "$like", "$eq", "$gt", "$lt", "$gte", "$lte", "$between", "$in"
- "val": value (string, number, or array for $between/$in)

## Examples
User: "Show me measurements starting with Profile_"
Output: {{"root_entity": "<entity>", "conditions": [{{"entity": "<entity>", "attr": "Name", "op": "$like", "val": "Profile_*"}}]}}

User: "Records with ID between 100 and 200"
Output: {{"root_entity": "<entity>", "conditions": [{{"entity": "<entity>", "attr": "Id", "op": "$between", "val": [100, 200]}}]}}

Only return the JSON object, no additional text."""

        user_prompt = f"Parse this query: {text}"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_response(
        self,
        raw_response: str,
        date_conditions: list[Any],
    ) -> tuple[list[ConditionDict], list[dict[str, Any]], str]:
        """Parse LLM JSON response into conditions.

        Tries multiple extraction strategies:
        1. Direct JSON parse
        2. Extract from markdown code blocks
        3. Regex fallback

        Args:
            raw_response: Raw LLM response text.
            date_conditions: Pre-extracted date conditions to merge.

        Returns:
            Tuple of (conditions list, invalid_conditions list, root_entity).

        Raises:
            ValueError: If response cannot be parsed.
        """
        # Strategy 1: Direct JSON parse
        try:
            data = json.loads(raw_response.strip())
            return self._extract_conditions(data, date_conditions)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code blocks
        code_block_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            raw_response,
            re.DOTALL | re.IGNORECASE,
        )
        if code_block_match:
            try:
                data = json.loads(code_block_match.group(1))
                return self._extract_conditions(data, date_conditions)
            except json.JSONDecodeError:
                pass

        # Strategy 3: Regex fallback for JSON object
        json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return self._extract_conditions(data, date_conditions)
            except json.JSONDecodeError:
                pass

        # All strategies failed
        msg = f"Failed to parse LLM response as JSON:\n{raw_response}"
        raise ValueError(msg)

    def _extract_conditions(
        self,
        data: dict[str, Any],
        date_conditions: list[Any],
    ) -> tuple[list[ConditionDict], list[dict[str, Any]], str]:
        """Extract conditions from parsed JSON data.

        Args:
            data: Parsed JSON dict.
            date_conditions: Pre-extracted date conditions to merge.

        Returns:
            Tuple of (conditions list, invalid_conditions list, root_entity).

        Raises:
            ValueError: If data is missing required fields.
        """
        if "root_entity" not in data or "conditions" not in data:
            msg = f"LLM response missing 'root_entity' or 'conditions': {data}"
            raise ValueError(msg)

        # Validate and resolve the root entity against the real model
        root_entity_raw = data["root_entity"]
        root_entity = self._index.resolve_entity(root_entity_raw)
        if root_entity is None:
            msg = f"LLM returned unknown root_entity {root_entity_raw!r} — cannot build query"
            raise ValueError(msg)
        if root_entity != root_entity_raw:
            log.info("Corrected root_entity %r → %r", root_entity_raw, root_entity)

        conditions: list[ConditionDict] = []
        invalid_conditions: list[dict[str, Any]] = []

        for cond in data["conditions"]:
            if not all(k in cond for k in ("entity", "attr", "op", "val")):
                log.warning(f"Invalid condition (missing keys): {cond}")
                invalid_conditions.append(
                    {**cond, "reason": "Missing required keys (entity/attr/op/val)"}
                )
                continue

            entity_raw = cond["entity"]
            entity = self._index.resolve_entity(entity_raw)
            if entity is None:
                log.warning(
                    "Entity %r not found in model — marking condition invalid: %r",
                    entity_raw,
                    cond,
                )
                invalid_conditions.append({**cond, "reason": f"Unknown entity {entity_raw!r}"})
                continue
            if entity != entity_raw:
                log.info("Corrected condition entity %r → %r", entity_raw, entity)

            attr = cond["attr"]

            # Validate the attribute name against the real model.  If the LLM
            # invented a name, resolve_attribute finds the closest real one.
            resolved = self._index.resolve_attribute(entity, attr)
            if resolved is None:
                log.warning(
                    "Attribute %r not found on entity %r — marking condition invalid",
                    attr,
                    entity,
                )
                invalid_conditions.append(
                    {**cond, "entity": entity, "reason": f"Unknown attribute {attr!r} on {entity}"}
                )
                continue
            if resolved != attr:
                log.info("Corrected attribute %s.%r → %r", entity, attr, resolved)
                attr = resolved

            conditions.append(
                ConditionDict(
                    entity=entity,
                    attr=attr,
                    op=cond["op"],
                    val=cond["val"],
                )
            )

        # Merge date conditions — find the actual date attribute from the model
        for dc in date_conditions:
            date_attr = self._index.find_date_attribute(root_entity)
            if date_attr is None:
                log.warning(
                    "No DT_DATE attribute found on entity %r — skipping date condition",
                    root_entity,
                )
                continue
            conditions.append(
                ConditionDict(
                    entity=root_entity,
                    attr=date_attr,
                    op="$between",
                    val=[dc.start_ods, dc.end_ods],
                )
            )

        return conditions, invalid_conditions, root_entity
