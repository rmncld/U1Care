from copy import deepcopy
import json
from pathlib import Path

import pytest

from custom_components.u1_companion import model

CAT = json.loads((Path(__file__).parents[1] / "custom_components/u1_companion/catalog.json").read_text(encoding="utf-8"))


def state():
    return model.reference_date(model.fresh(CAT), "2026-10-01", "2026-10-15", CAT)


@pytest.mark.parametrize("base,months,expected", [
    ("2026-01-31", 1, "2026-02-28"), ("2028-01-31", 1, "2028-02-29"),
    ("2026-11-30", 3, "2027-02-28"), ("2026-12-31", 1, "2027-01-31")])
def test_calendar(base, months, expected):
    assert model.add_months(base, months) == expected


@pytest.mark.parametrize("day,level,remaining", [
    ("2026-10-24", "ok", 8), ("2026-10-25", "soon", 7),
    ("2026-11-01", "due", 0), ("2026-11-03", "due", -2)])
def test_boundaries(day, level, remaining):
    s = state()
    result = model.task_status(s["tasks"][0], s, day)
    assert (result["level"], result["remaining"]) == (level, remaining)


def test_unknown_not_zero_or_installation_date():
    s = model.fresh(CAT)
    assert s["machine"]["hours"] is None
    assert s["machine"]["startDate"] is None
    assert model.snapshot(s, "2026-10-15")["overall"]["label"] == "INCONNU"
    assert all(t["intervalHours"] is None for t in CAT["tasks"])


def test_pogo_range_and_cycles_independent():
    s = state()
    s["machine"]["swaps"] = 10
    t = next(t for t in s["tasks"] if t["id"] == "pogo-contacts")
    assert model.task_status(t, s, "2027-01-31")["level"] == "ok"
    assert model.task_status(t, s, "2027-02-01")["level"] == "soon"
    assert model.task_status(t, s, "2027-04-01")["level"] == "due"
    s["machine"]["swaps"] = 100000
    assert model.task_status(t, s, "2026-10-02")["level"] == "due"
    s["machine"]["swaps"] = None
    result = model.task_status(t, s, "2026-10-02")
    assert result["level"] == "unset"
    assert result["dueDate"] == "2027-04-01"


def test_completion_independent_and_round_trip():
    s = state()
    task = s["tasks"][0]
    updated = model.complete(s, task["id"], [True] * len(task["steps"]), "done", "2026-10-15", "2026-10-15", CAT)
    assert s["history"] == []
    assert len(updated["history"]) == 1
    assert updated["tasks"][1]["lastDate"] is None
    assert model.snapshot(updated, "2026-10-15")["tasks"][task["id"]]["dueDate"] == "2026-11-15"
    assert model.validate(json.loads(json.dumps(updated)), CAT) == updated


def test_checks_dates_and_backdated_counters():
    s = state()
    s["machine"]["hours"] = 123
    t = s["tasks"][0]
    for checks, day in [([False] * len(t["steps"]), "2026-10-15"), ([True] * len(t["steps"]), "2026-10-16")]:
        with pytest.raises(ValueError):
            model.complete(s, t["id"], checks, "", day, "2026-10-15", CAT)
    updated = model.complete(s, t["id"], [True] * len(t["steps"]), "", "2026-10-14", "2026-10-15", CAT)
    assert updated["history"][0]["hours"] is None
    assert updated["tasks"][0]["lastHours"] is None


def test_history_reset_and_manual_domains():
    s = state()
    s["machine"].update(hours=100, hoursSource="manual")
    s["tasks"][0]["lastHours"] = 90
    result = model.apply_history(s, 2)
    assert result["connection"]["previousManualHours"] == 100
    assert result["tasks"][0]["lastHours"] is None
    assert result["tasks"][0]["previousManualLastHours"] == 90
    with pytest.raises(ValueError, match="history_reset"):
        model.apply_history(result, 1)
    assert result["machine"]["hours"] == 2


@pytest.mark.parametrize("key,value", [("months", 99), ("source", "https://example.com"), ("steps", ["invented"])])
def test_catalog_tampering(key, value):
    s = state()
    s["tasks"][0][key] = value
    with pytest.raises(ValueError):
        model.validate(s, CAT)


def test_condition_activation_and_completion():
    s = state()
    t = s["tasks"][-1]
    assert model.task_status(t, s, "2026-10-15")["level"] == "conditional"
    t["conditionActive"] = True
    assert model.snapshot(s, "2026-10-15")["overall"]["level"] == "due"
    result = model.complete(s, t["id"], [True] * len(t["steps"]), "", "2026-10-15", "2026-10-15", CAT)
    assert result["tasks"][-1]["conditionActive"] is False


@pytest.mark.parametrize("value", [-1, True, float("nan"), float("inf"), "12"])
def test_invalid_counters(value):
    s = state()
    s["machine"]["hours"] = value
    with pytest.raises(ValueError):
        model.validate(s, CAT)
