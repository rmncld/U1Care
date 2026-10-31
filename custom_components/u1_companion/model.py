"""Pure maintenance calculations, shared catalogue, independent events.

No HA, network or filesystem dependencies: dates can be checked offline.
The state format is compatible with the Companion 0.2.0 official entries.
"""

from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime, timedelta
import math
from urllib.parse import urlparse

RANK = {"due": 0, "soon": 1, "unset": 2, "ok": 3, "conditional": 4}


def number(value, nullable=False, integer=False):
    if value is None and nullable:
        return
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value <= 1e9
            or (integer and int(value) != value)):
        raise ValueError("Invalid counter")


def valid_day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("Invalid calendar date")
    return date.fromisoformat(value)


def add_months(value, months):
    base = valid_day(value)
    index = base.year * 12 + base.month - 1 + months
    year, zero_month = divmod(index, 12)
    month = zero_month + 1
    return date(year, month, min(base.day, monthrange(year, month)[1])).isoformat()


def fresh(catalog):
    tasks = []
    for ref in catalog["tasks"]:
        tasks.append({**deepcopy(ref), "lastHours": None, "lastSwaps": None,
                      "lastDate": None, "calendarBaseDate": None,
                      "warningHours": 10, "warningDays": 7, "warningSwaps": 5000,
                      "conditionActive": False})
    return {"schemaVersion": 2, "catalogVersion": catalog["version"],
            "machine": {"brand": "Snapmaker", "model": "U1", "name": "Mon U1",
                        "hours": None, "swaps": None, "startDate": None,
                        "hoursSource": "unknown"},
            "connection": {"url": "", "enabled": True,
                           "status": "unknown", "lastSuccess": None},
            "tasks": tasks, "history": []}


def validate(state, catalog):
    """Reject corrupt/incompatible stores rather than replacing their events."""
    if not isinstance(state, dict) or state.get("schemaVersion") != 2:
        raise ValueError("Unsupported backup; use a Companion 0.2.0 JSON export")
    if state.get("catalogVersion") != catalog["version"]:
        raise ValueError("Incompatible catalogue version")
    machine = state.get("machine")
    if not isinstance(machine, dict) or not isinstance(machine.get("name"), str):
        raise ValueError("Invalid machine")
    number(machine["hours"], nullable=True)
    number(machine["swaps"], nullable=True, integer=True)
    telemetry = state.get("toolheadCounters")
    if telemetry is not None:
        if not isinstance(telemetry, dict) or set(telemetry) != {"last", "total"}:
            raise ValueError("Invalid toolhead counters")
        if not isinstance(telemetry["last"], list) or len(telemetry["last"]) != 4:
            raise ValueError("Invalid toolhead counters")
        for value in telemetry["last"]:
            number(value, integer=True)
        number(telemetry["total"], integer=True)
    if machine.get("startDate") is not None:
        valid_day(machine["startDate"])
    tasks = state.get("tasks")
    history = state.get("history")
    if not isinstance(tasks, list) or not isinstance(history, list) or len(tasks) > 60 or len(history) > 10000:
        raise ValueError("Invalid event store")
    refs = {t["id"]: t for t in catalog["tasks"]}
    ids = set()
    for task in tasks:
        task_id = task.get("id") if isinstance(task, dict) else None
        if not isinstance(task_id, str) or task_id in ids:
            raise ValueError("Duplicate or missing maintenance ID")
        ids.add(task_id)
        if not isinstance(task.get("title"), str) or not isinstance(task.get("frequency"), str):
            raise ValueError("Invalid maintenance description")
        if (not isinstance(task.get("steps"), list) or not 1 <= len(task["steps"]) <= 30
                or any(not isinstance(step, str) or len(step) > 1000 for step in task["steps"])):
            raise ValueError("Invalid maintenance procedure")
        if not isinstance(task.get("source"), str):
            raise ValueError("Invalid maintenance source")
        source = urlparse(task["source"])
        if source.scheme != "https" or not source.netloc or source.username or source.password:
            raise ValueError("HTTPS maintenance source required")
        if task_id in refs:
            for key, value in refs[task_id].items():
                if task.get(key) != value:
                    raise ValueError("Official catalogue altered")
        elif not task.get("legacy"):
            raise ValueError("Unknown maintenance ID")
        for key in ("lastHours", "lastSwaps"):
            number(task.get(key), nullable=True, integer=key == "lastSwaps")
        for key in ("warningHours", "warningDays", "warningSwaps"):
            number(task.get(key, 0))
        if task.get("calendarBaseDate"):
            valid_day(task["calendarBaseDate"])
        if task.get("lastDate"):
            datetime.fromisoformat(task["lastDate"].replace("Z", "+00:00"))
        for last, current in (("lastHours", "hours"), ("lastSwaps", "swaps")):
            if task.get(last) is not None and machine[current] is not None and task[last] > machine[current]:
                raise ValueError("Maintenance reference exceeds current counter")
    if not set(refs).issubset(ids):
        raise ValueError("Incomplete catalogue")
    for event in history:
        if (not isinstance(event, dict) or event.get("taskId") not in ids
                or not isinstance(event.get("note"), str) or len(event["note"]) > 2000
                or not isinstance(event.get("title"), str)):
            raise ValueError("Invalid maintenance event")
        datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        number(event.get("hours"), nullable=True)
        number(event.get("swaps"), nullable=True, integer=True)
    if not isinstance(state.get("connection"), dict):
        raise ValueError("Invalid connection state")
    for task in tasks:
        for key in ("intervalHours", "intervalDays", "intervalSwaps", "months", "earliestMonths"):
            if task.get(key) is not None:
                number(task[key], integer=key != "intervalHours")
                if task[key] <= 0:
                    raise ValueError("Invalid interval")
    return state


def _unknown(reason):
    return {"level": "unset", "label": "INCONNU", "remaining": None,
            "unit": "", "reason": reason}


def _status(remaining, warning, unit):
    level = "due" if remaining <= 0 else "soon" if remaining <= warning else "ok"
    return {"level": level, "label": level.upper(), "remaining": remaining, "unit": unit}


def task_status(task, state, today):
    today = valid_day(today)
    states = []
    base = task.get("calendarBaseDate") or (task.get("lastDate") or "")[:10] or state["machine"].get("startDate")
    if task.get("months") or task.get("intervalDays"):
        if not base:
            states.append(_unknown("Date de référence ou de dernier entretien inconnue"))
        else:
            due = (add_months(base, task["months"]) if task.get("months") else
                   (valid_day(base) + timedelta(days=task["intervalDays"])).isoformat())
            remaining = (valid_day(due) - today).days
            warning = task.get("warningDays", 7)
            if task.get("earliestMonths"):
                warning = (valid_day(due) - valid_day(add_months(base, task["earliestMonths"]))).days
            states.append({**_status(remaining, warning, "j"), "dueDate": due})
    if task.get("intervalSwaps"):
        swaps = state["machine"].get("swaps")
        if swaps is None or (task.get("lastDate") and task.get("lastSwaps") is None):
            states.append(_unknown("Cycles non exposés : consulter le rappel écran U1"))
        else:
            remaining = (task.get("lastSwaps") or 0) + task["intervalSwaps"] - swaps
            states.append(_status(remaining, task.get("warningSwaps", 5000), "cy"))
    if task.get("intervalHours"):
        hours = state["machine"].get("hours")
        if hours is None or task.get("lastHours") is None:
            states.append(_unknown("Compteur horaire inconnu"))
        else:
            states.append(_status(round(task["lastHours"] + task["intervalHours"] - hours, 2), task.get("warningHours", 10), "h"))
    if task.get("conditionActive"):
        states.append({**_status(0, 0, ""), "reason": task.get("condition")})
    if not states:
        return {"level": "conditional", "label": "SI BESOIN", "remaining": None,
                "unit": "", "reason": task.get("condition")}
    selected = min(states, key=lambda item: RANK[item["level"]])
    return {**selected, "dueDate": next((s["dueDate"] for s in states if "dueDate" in s), None),
            "deadlines": states}


def snapshot(state, today):
    tasks = {t["id"]: {**task_status(t, state, today), "title": t["title"],
             "lastDate": t.get("lastDate"), "source": t["source"], "frequency": t["frequency"],
             "steps": t["steps"]} for t in state["tasks"]}
    overall = min(tasks.values(), key=lambda item: (RANK[item["level"]],
                  item["remaining"] if item.get("unit") == "j" and item["remaining"] is not None else math.inf))
    return {"tasks": tasks, "overall": overall}


def complete(state, task_id, checked, note, completed_day, today, catalog):
    """Record only the selected maintenance; previous events are never erased."""
    next_state = deepcopy(validate(state, catalog))
    task = next((t for t in next_state["tasks"] if t["id"] == task_id), None)
    if task is None or len(checked) != len(task["steps"]) or not all(v is True for v in checked):
        raise ValueError("check_all_steps")
    if not isinstance(note, str) or len(note) > 2000:
        raise ValueError("invalid_note")
    day = valid_day(completed_day)
    if day > valid_day(today) or (task.get("lastDate") and completed_day < task["lastDate"][:10]):
        raise ValueError("invalid_date")
    # A backdated intervention cannot be assigned today's printer counters.
    hours = next_state["machine"].get("hours") if completed_day == today else None
    swaps = next_state["machine"].get("swaps") if completed_day == today else None
    task.update(lastDate=completed_day, calendarBaseDate=completed_day,
                lastHours=hours, lastSwaps=swaps, conditionActive=False)
    next_state["history"].append({"date": task["lastDate"], "hours": hours, "swaps": swaps,
        "taskId": task_id, "title": task["title"], "note": note,
        "hoursSource": next_state["machine"].get("hoursSource", "unknown"),
        "catalogVersion": catalog["version"], "datePrecision": "day"})
    return validate(next_state, catalog)


def reference_date(state, value, today, catalog):
    next_state = deepcopy(validate(state, catalog))
    if valid_day(value) > valid_day(today):
        raise ValueError("invalid_date")
    next_state["machine"]["startDate"] = value
    return next_state


def apply_history(state, hours):
    """Keep domains separate and flag a reset instead of inventing continuity."""
    number(hours)
    next_state = deepcopy(state)
    old = next_state["connection"].get("lastReadingHours")
    if old is not None and hours < old:
        raise ValueError("history_reset")
    if not next_state["connection"].get("enabled", True):
        return next_state
    if next_state["machine"].get("hoursSource") != "moonraker-history":
        if next_state["machine"].get("hours") is not None:
            next_state["connection"]["previousManualHours"] = next_state["machine"]["hours"]
        for task in next_state["tasks"]:
            if task.get("lastHours") is not None:
                task["previousManualLastHours"] = task["lastHours"]
                task["lastHours"] = None
    next_state["machine"].update(hours=hours, hoursSource="moonraker-history")
    next_state["connection"]["lastReadingHours"] = hours
    return next_state


def apply_heads(state, heads, accept_reset=False):
    """A sum of four lifetime counts, then positive deltas; never sum snapshots.

    An existing manual total is a floor on initial migration. A decrease in any
    head requires explicit acknowledgement; old totals and events are retained.
    Partial snapshots never advance the persisted baseline.
    """
    if not isinstance(heads, list) or len(heads) != 4:
        raise ValueError("heads_missing")
    counts = [h.get("switch_count") for h in heads]
    for value in counts:
        number(value, integer=True)
    next_state = deepcopy(state)
    machine = next_state["machine"]
    if machine.get("swapsSource") == "manual":
        return next_state
    previous = next_state.get("toolheadCounters")
    if previous is None:
        total = max(machine.get("swaps") or 0, sum(counts))
    else:
        decreased = any(a < b for a, b in zip(counts, previous["last"]))
        if decreased and not accept_reset:
            raise ValueError("head_counter_reset")
        total = previous["total"] + (0 if decreased else sum(
            a - b for a, b in zip(counts, previous["last"])))
        total = max(total, machine.get("swaps") or 0)
    number(total, integer=True)
    next_state["toolheadCounters"] = {"last": counts, "total": total}
    machine.update(swaps=total, swapsSource="u1-extruders")
    return next_state
