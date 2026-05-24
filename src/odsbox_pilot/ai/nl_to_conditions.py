"""Natural language to ODS query conditions parser."""

from __future__ import annotations

import json
import logging
import re
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

    def parse(self, text: str) -> NlParseResult:
        """Parse natural language query into conditions.

        Args:
            text: Natural language query (e.g., "Zeig mir Messungen Profile_*").

        Returns:
            NlParseResult containing conditions, root entity, and raw response.

        Raises:
            ValueError: If LLM response cannot be parsed or is invalid.
        """
        # Step 1: Extract date expressions (rule-based)
        date_conditions = parse_date_expressions(text)

        # Step 2: Build schema context via semantic search
        schema_context = self._build_schema_context(text)

        # Step 3: Build LLM prompt
        messages = self._build_prompt(text, schema_context, date_conditions)

        # Step 4: Call LLM
        raw_response = self._pipeline.generate(messages, max_new_tokens=512, temperature=0.3)

        # Step 5: Parse JSON response
        conditions, root_entity = self._parse_response(raw_response, date_conditions)

        return NlParseResult(
            conditions=conditions,
            root_entity=root_entity,
            raw_response=raw_response,
        )

    def _build_schema_context(self, text: str, top_k: int = 20) -> str:
        """Build schema context by running semantic search on text.

        Args:
            text: User query text.
            top_k: Number of top matches to include.

        Returns:
            Formatted schema context string.
        """
        matches = self._index.search(text, top_k=top_k)
        lines: list[str] = []
        for m in matches:
            if m.kind == "attribute":
                lines.append(f"  - {m.entity_name}.{m.item_name} (attribute, type={m.data_type})")
            elif m.kind == "relation":
                lines.append(f"  - {m.entity_name}.{m.item_name} (relation → {m.data_type})")
            elif m.kind == "enumeration":
                lines.append(f"  - {m.item_name} (enumeration)")
        return "\n".join(lines)

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

## ODS Schema (relevant entities and attributes)
{schema_context}

## Output Format
Return a JSON object with:
- "root_entity": the primary entity to query (e.g., "AoMeasurement", "AoTest")
- "conditions": array of condition objects

Each condition object has:
- "entity": entity name
- "attr": attribute name
- "op": operator (one of: "$like", "$eq", "$gt", "$lt", "$gte", "$lte", "$between", "$in")
- "val": value (string, number, or array for $between/$in)

## Examples
User: "Show me measurements starting with Profile_"
Output: {{"root_entity": "AoMeasurement", "conditions": [{{"entity": "AoMeasurement", "attr": "name", "op": "$like", "val": "Profile_*"}}]}}

User: "Tests with ID between 100 and 200"
Output: {{"root_entity": "AoTest", "conditions": [{{"entity": "AoTest", "attr": "id", "op": "$between", "val": [100, 200]}}]}}

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
    ) -> tuple[list[ConditionDict], str]:
        """Parse LLM JSON response into conditions.

        Tries multiple extraction strategies:
        1. Direct JSON parse
        2. Extract from markdown code blocks
        3. Regex fallback

        Args:
            raw_response: Raw LLM response text.
            date_conditions: Pre-extracted date conditions to merge.

        Returns:
            Tuple of (conditions list, root_entity).

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
    ) -> tuple[list[ConditionDict], str]:
        """Extract conditions from parsed JSON data.

        Args:
            data: Parsed JSON dict.
            date_conditions: Pre-extracted date conditions to merge.

        Returns:
            Tuple of (conditions list, root_entity).

        Raises:
            ValueError: If data is missing required fields.
        """
        if "root_entity" not in data or "conditions" not in data:
            msg = f"LLM response missing 'root_entity' or 'conditions': {data}"
            raise ValueError(msg)

        root_entity = data["root_entity"]
        conditions: list[ConditionDict] = []

        for cond in data["conditions"]:
            if not all(k in cond for k in ("entity", "attr", "op", "val")):
                log.warning(f"Skipping malformed condition: {cond}")
                continue
            conditions.append(
                ConditionDict(
                    entity=cond["entity"],
                    attr=cond["attr"],
                    op=cond["op"],
                    val=cond["val"],
                )
            )

        # Merge date conditions (if any)
        for dc in date_conditions:
            # Assume date conditions apply to root entity's date attribute
            # (would need smarter logic to detect attribute name from schema)
            conditions.append(
                ConditionDict(
                    entity=root_entity,
                    attr="measurement_begin",  # Heuristic: common date attr
                    op="$between",
                    val=[dc.start_ods, dc.end_ods],
                )
            )

        return conditions, root_entity
