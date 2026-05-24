"""Integration tests for NL query pipeline (requires live ODS server)."""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestNlQueryPipelineIntegration:
    """Integration tests for end-to-end NL query pipeline.

    These tests require a live ODS server connection and AI dependencies installed.
    Skip with: pytest -m "not integration"
    """

    @pytest.mark.skip(reason="Requires live server and AI model download")
    def test_end_to_end_nl_to_query(self, con_i) -> None:  # type: ignore[no-untyped-def]
        """Test complete flow: NL text → conditions → JAQueL → query execution.

        This test demonstrates the intended usage but is skipped by default
        since it requires:
        - A live ODS server connection (con_i fixture)
        - AI dependencies installed (uv sync --extra ai)
        - AI model downloaded
        """
        from odsbox_pilot.ai import ModelManager, NlToConditions, OvLlmPipeline
        from odsbox_pilot.browse._helpers import _build_filter_nodes
        from odsbox_pilot.browse.filter_tree import FilterTree
        from odsbox_pilot.model.search_index import ModelSearchIndex

        # Initialize AI components
        manager = ModelManager()
        model_path = manager.get_model_path("OpenVINO/qwen2.5-1.5b-instruct-int4-ov")
        if model_path is None:
            pytest.skip("AI model not downloaded")

        pipeline = OvLlmPipeline(model_path, device="CPU")
        model = con_i.mc.model()
        search_index = ModelSearchIndex(model)
        nl_parser = NlToConditions(search_index, pipeline)

        # Parse NL query
        nl_text = "Show measurements starting with Profile_"
        result = nl_parser.parse(nl_text)

        assert result.root_entity != ""
        assert len(result.conditions) > 0

        # Build FilterTree
        filter_nodes = _build_filter_nodes(con_i.mc, result.conditions)
        filter_tree = FilterTree(con_i.mc, filter_nodes)

        # Generate JAQueL
        jaquel = filter_tree.generate_query(result.root_entity, attributes={"id": 1, "name": 1})

        assert isinstance(jaquel, dict)
        assert result.root_entity in jaquel

        # Execute query (this validates the generated JAQueL is correct)
        df = con_i.query(jaquel)
        assert df is not None
        # Results may be empty, but query should not raise

    @pytest.mark.skip(reason="Requires live server and AI model download")
    def test_date_expression_integration(self, con_i) -> None:  # type: ignore[no-untyped-def]
        """Test date expressions in NL queries.

        Validates that "letzten Jahr" / "last year" properly converts to
        $between conditions with ODS DT_DATE format.
        """
        from odsbox_pilot.ai import ModelManager, NlToConditions, OvLlmPipeline
        from odsbox_pilot.model.search_index import ModelSearchIndex

        # Setup
        manager = ModelManager()
        model_path = manager.get_model_path("OpenVINO/qwen2.5-1.5b-instruct-int4-ov")
        if model_path is None:
            pytest.skip("AI model not downloaded")

        pipeline = OvLlmPipeline(model_path, device="CPU")
        model = con_i.mc.model()
        search_index = ModelSearchIndex(model)
        nl_parser = NlToConditions(search_index, pipeline)

        # Parse query with date expression
        result = nl_parser.parse("Messungen vom letzten Jahr")

        # Should have date condition
        date_cond = next((c for c in result.conditions if c["op"] == "$between"), None)
        assert date_cond is not None
        assert len(date_cond["val"]) == 2
        # Values should be 20-char ODS DT_DATE strings
        assert len(date_cond["val"][0]) == 20
        assert len(date_cond["val"][1]) == 20
