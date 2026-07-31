import json
from typing import Any, cast

import pytest
from google.protobuf.json_format import MessageToJson, ParseDict
from odsbox.jaquel import jaquel_to_ods
from odsbox.model_cache import ModelCache
from odsbox.proto import ods
from wodson.utils.query import ods_to_jaquel

from odsbox_pilot.query.editor_panel import convert_query_format


@pytest.fixture
def mdm_nvh_model() -> ods.Model:
    from pathlib import Path

    _FIXTURE = Path(__file__).parent.parent / "data" / "mdm_nvh_model.json"
    with _FIXTURE.open(encoding="utf-8") as fh:
        return cast(ods.Model, ParseDict(json.load(fh), ods.Model()))


def test_wodson_ods_to_jaquel_and_back(mdm_nvh_model: ods.Model) -> None:

    mc: ModelCache = ModelCache(mdm_nvh_model)

    _, select = jaquel_to_ods(mc.model(), {"AoTest": {}})
    select_dict = json.loads(MessageToJson(select))
    # select statement can be identified by the presence of a "columns" list
    assert isinstance(select_dict.get("columns"), list)

    jaquel = ods_to_jaquel(mc, select)
    # if an entity named columns exists in the model
    assert jaquel.get("columns") is None or not isinstance(jaquel.get("columns"), list)
    select2 = jaquel_to_ods(mc.model(), jaquel)[1]
    select2_dict2: dict[str, Any] = json.loads(MessageToJson(select2))

    # if dict contains columns list we know it is no jaquel but an ods.SelectStatement
    assert isinstance(select2_dict2.get("columns"), list)
    select2_message = ods.SelectStatement()
    ParseDict(select_dict, select2_message)  # raises if not equivalent

    assert select == select2_message

    ods_to_jaquel(mc, select2_message)


def test_convert_query_format_round_trip(mdm_nvh_model: ods.Model) -> None:
    mc: ModelCache = ModelCache(mdm_nvh_model)

    jaquel = {"AoTest": {}}
    converted = convert_query_format(json.dumps(jaquel), mc)
    converted_dict = json.loads(converted)
    assert isinstance(converted_dict.get("columns"), list)

    round_tripped = convert_query_format(converted, mc)
    round_tripped_dict = json.loads(round_tripped)
    assert isinstance(round_tripped_dict, dict)
    assert round_tripped_dict.get("columns") is None or not isinstance(
        round_tripped_dict.get("columns"), list
    )
