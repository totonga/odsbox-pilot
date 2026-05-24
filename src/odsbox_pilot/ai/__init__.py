"""AI-powered query generation from natural language.

This module provides components for parsing natural language queries into
structured ODS JAQueL queries using an OpenVINO GenAI LLM pipeline combined
with semantic search over the ODS model schema.

Public API:
    - OvLlmPipeline: OpenVINO GenAI LLM wrapper
    - NlToConditions: Natural language → conditions parser
    - ModelManager: Model download and lifecycle management
    - parse_date_expressions: Date expression parser
"""

from odsbox_pilot.ai.date_parser import DateCondition, parse_date_expressions
from odsbox_pilot.ai.llm_pipeline import OvLlmPipeline
from odsbox_pilot.ai.model_manager import ModelManager
from odsbox_pilot.ai.nl_to_conditions import ConditionDict, NlParseResult, NlToConditions

__all__ = [
    "ConditionDict",
    "DateCondition",
    "ModelManager",
    "NlParseResult",
    "NlToConditions",
    "OvLlmPipeline",
    "parse_date_expressions",
]
