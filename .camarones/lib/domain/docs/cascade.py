"""L3 freshness: a page that cites another page passes on that page's state (R30). Pure: each page's own source
results come in as data."""
from __future__ import annotations

OUT_OF_DATE = ("suspect", "stale")


def settle(own: dict[str, dict], cites: dict[str, list[tuple[str, str]]]) -> dict[str, dict]:
    """Every page's {state, changed, missing}: `own` is its result per non-page source (a page with none is not in it:
    unverified), `cites` the page sources it names with the page each one is. Repeated until nothing changes, so
    chains and cycles settle."""
    result: dict[str, dict] = {}

    def summarise(logical: str) -> dict:
        if logical not in own:
            return {"state": "unverified", "changed": [], "missing": []}
        res = dict(own[logical])
        for s, cited in cites[logical]:
            if cited not in cites:
                res[s] = "missing"
            else:
                res[s] = "changed" if result.get(cited, {}).get("state") in OUT_OF_DATE else "fresh"
        changed = [s for s, r in res.items() if r == "changed"]
        missing = [s for s, r in res.items() if r == "missing"]
        return {"state": "stale" if missing else "suspect" if changed else "fresh", "changed": changed,
                "missing": missing}
    for _ in range(len(cites) + 1):
        new = {logical: summarise(logical) for logical in cites}
        if new == result:
            break
        result = new
    return result
