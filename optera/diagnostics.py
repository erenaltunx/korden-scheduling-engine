"""Human-readable, evidence-bounded diagnostics for production scheduling.

Reporting is intentionally separate from optimization. A failure by a
particular *dispatch order* is not proof that the entire MILP is infeasible.
Only flag a structural calendar shortage when no qualifying resource
combination offers a continuous interval long enough for the operation.
"""
from __future__ import annotations

from .model import downtime_by_machine, horizon


def _max_continuous_available(blocked: list[tuple[int, int]], start: int, end: int) -> int:
    """Longest uninterrupted free interval within [start, end]."""
    cursor = start
    longest = 0
    for a, b in sorted(blocked):
        if b <= cursor or a >= end:
            continue
        longest = max(longest, max(0, min(end, a) - cursor))
        cursor = max(cursor, min(end, b))
    return max(longest, max(0, end - cursor))


def _calendar_evidence(data: dict, job: dict, operation: dict) -> dict:
    """Optimistic static calendar bound (ignores previously scheduled tasks).

    Fixed supports must be concurrently available. For a selectable support,
    at least one choice must be available. An interval shorter than duration
    even under this optimistic bound is a provable calendar-only blocker.
    """
    unavailable = downtime_by_machine(data)
    until = horizon(data)
    ready = job["release"]
    choices = operation.get("support_options") or [None]
    results = []
    for machine in operation["machines"]:
        for choice in choices:
            resources = [machine, *operation.get("support_resources", [])]
            if choice is not None:
                resources.append(choice)
            unavailable_windows = [
                interval for resource in resources
                for interval in unavailable[resource]
            ]
            longest = _max_continuous_available(unavailable_windows, ready, until)
            results.append((longest, machine, choice, tuple(resources)))
    best = max(results, key=lambda item: item[0])
    return {
        "longest_open_period": best[0],
        "machine": best[1],
        "resources": list(best[3]),
        "duration": operation["duration"],
        "release": ready,
    }


def explain_scheduling_error(error: ValueError, data: dict | None = None) -> dict:
    """Return safe structured hints; do not claim that a solver proved infeasibility.

    Keep the API's existing detail string unchanged for older clients.
    """
    raw = str(error)
    scenario = data if isinstance(data, dict) else {}

    if raw.startswith("No feasible working period for order "):
        for job in scenario.get("jobs", []):
            if not isinstance(job, dict):
                continue
            for operation in job.get("operations", []):
                if not isinstance(operation, dict):
                    continue
                expected = (
                    f"No feasible working period for order {job.get('id')} "
                    f"operation {operation.get('id')};"
                )
                if raw.startswith(expected):
                    try:
                        evidence = _calendar_evidence(scenario, job, operation)
                    except (ValueError, KeyError, TypeError):
                        break
                    duration = evidence["duration"]
                    longest = evidence["longest_open_period"]
                    resources = ", ".join(evidence["resources"])
                    if longest < duration:
                        return {
                            "code": "WORK_PERIOD_TOO_SHORT",
                            "title": "No continuous work period is long enough",
                            "explanation": (
                                f"Order {job['id']} / operation {operation['id']} needs "
                                f"{duration} uninterrupted time units. The longest "
                                f"available period on a qualifying resource combination "
                                f"({resources}) is {longest} time units, starting no "
                                f"earlier than the order release at {evidence['release']}."
                            ),
                            "next_step": (
                                "Extend an allowed working period, review maintenance "
                                "hours, assign another qualified machine or check "
                                "the operation duration. A single operation cannot "
                                "cross a closed shift."
                            ),
                            "job_id": job["id"],
                            "operation_id": operation["id"],
                            "machine_ids": list(operation["machines"]),
                            "duration": duration,
                            "longest_open_period": longest,
                        }
                    return {
                        "code": "DISPATCH_CALENDAR_CONFLICT",
                        "title": "The selected job sequence could not be scheduled",
                        "explanation": (
                            f"Order {job['id']} / operation {operation['id']} was not "
                            "placed before the available schedule ended. An individual "
                            "work period may be long enough, but earlier orders, "
                            "setup changes or shared-resource reservations could "
                            "consume the remaining capacity."
                        ),
                        "next_step": (
                            "Try adjusting order priorities, adding a working period "
                            "or another qualified resource. This dispatch failure "
                            "does not prove every possible schedule is infeasible."
                        ),
                        "job_id": job["id"],
                        "operation_id": operation["id"],
                        "machine_ids": list(operation["machines"]),
                    }

    if "working periods must not overlap" in raw or "invalid working period" in raw:
        return {
            "code": "INVALID_WORK_CALENDAR",
            "title": "Check the machine's working periods",
            "explanation": raw,
            "next_step": (
                "Each period must have integer start and end values, with start "
                "earlier than end. Sort intervals and remove any overlaps."
            ),
        }
    if "working_windows must contain" in raw:
        return {
            "code": "INVALID_WORK_CALENDAR",
            "title": "Working periods are missing or invalid",
            "explanation": raw,
            "next_step": (
                "Provide one to 32 explicit non-overlapping working periods. "
                "Omit working_windows entirely for unrestricted hours."
            ),
        }
    if "downtime" in raw.lower():
        return {
            "code": "INVALID_DOWNTIME",
            "title": "Check machine maintenance or outage hours",
            "explanation": raw,
            "next_step": (
                "Make sure each outage has an integer start earlier than end, "
                "and merge overlapping outages on the same resource."
            ),
        }
    if "machines must be valid unique machine IDs" in raw:
        return {
            "code": "UNKNOWN_MACHINE",
            "title": "An operation references an unknown machine",
            "explanation": raw,
            "next_step": (
                "Use resource IDs exactly as listed in the machine table. "
                "Each operation must have at least one known, eligible machine."
            ),
        }
    if "duration must be" in raw:
        return {
            "code": "INVALID_DURATION",
            "title": "Check the operation duration",
            "explanation": raw,
            "next_step": (
                "Enter a positive whole-number duration using the scenario's "
                "time unit. Check that hours and minutes were not mixed."
            ),
        }

    return {
        "code": "INVALID_PLAN_INPUT",
        "title": "The production plan could not be generated",
        "explanation": raw,
        "next_step": (
            "Review the machine list, order steps, operation durations and "
            "availability settings, then validate and try again."
        ),
    }
