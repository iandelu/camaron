"""The desktop app's places (renderer/src/places.json) against the CLI registry: a command's name must never be a view's
address segment (a place that is a view itself, flow/plan, has none to clash with), or `#/quality/<name>` would open the view instead of the command."""
from __future__ import annotations

import json

from conftest import REPO

PLACES = REPO / ".camarones" / "desktop" / "renderer" / "src" / "places.json"


def _places() -> dict:
    return json.loads(PLACES.read_text(encoding="utf-8"))


def _zones(kit) -> dict[str, str | None]:
    from lib.interfaces.cli import registry
    return {name: cmd.spec.zone for name, cmd in registry.load().items()}


def test_every_panel_is_a_registered_command(kit):
    zones = _zones(kit)
    missing = sorted({n for names in _places()["panels"].values() for n in names} - set(zones))
    assert not missing, f"panels name commands that are gone: {missing}"


def test_no_folded_command_is_named_like_a_view(kit):
    places, zones = _places(), _zones(kit)
    panelled = {n for names in places["panels"].values() for n in names}
    for place, place_zones in places["zones"].items():
        views = [] if "/" in place else places["views"].get(place, [])
        clash = sorted(n for n, z in zones.items() if z in place_zones and n not in panelled and n in views)
        assert not clash, f"{place}: commands named like a view: {clash}"
