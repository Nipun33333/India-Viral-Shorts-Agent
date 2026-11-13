import pytest
from shorts_agent.main import get_slots
from shorts_agent.writer import fallback_script, _valid_script
from shorts_agent.trends import SEED_TOPICS


def test_fallback_has_five_four_second_scenes():
    result = fallback_script(SEED_TOPICS[0], 1)
    assert _valid_script(result)
    assert len(result["scenes"]) * 4 == 20


def test_slot_selection():
    assert get_slots("1") == [1]
    assert get_slots("2") == [2]
    assert get_slots("all") == [1, 2]
    with pytest.raises(ValueError):
        get_slots("3")
