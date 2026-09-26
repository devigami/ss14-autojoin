from __future__ import annotations

from ss14_autojoin.app import form_to_settings, settings_to_form
from ss14_autojoin.config import Settings


def test_form_round_trip() -> None:
    settings = Settings(server="ss14://host:1212", interval=2, margin=1, rejoin=True, max_attempts=3)
    parsed, problems = form_to_settings(settings_to_form(settings))
    assert problems == [] and parsed == settings


def test_form_reports_problems() -> None:
    parsed, problems = form_to_settings({"server": "http://nope", "interval": "abc", "margin": "1"})
    assert any("interval" in p for p in problems)
    assert any("server address" in p for p in problems)
    assert parsed.interval == 3.0 and parsed.margin == 1
