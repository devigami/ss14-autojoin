from __future__ import annotations

from pathlib import Path

from ss14_autojoin import config
from ss14_autojoin.config import Settings, config_path, load, save


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "cfg" / "config.toml"
    settings = Settings(
        launcher_dir=r"D:\Games\SteamLibrary\steamapps\common\Space Station 14 Playtest",
        server="ss14s://lizard.spacestation14.io/server",
        interval=2.5,
        margin=1,
        rejoin=True,
        on_unknown="retry",
        max_attempts=5,
    )
    save(settings, path)
    text = path.read_text()
    assert 'launcher_dir = "D:\\\\Games\\\\SteamLibrary\\\\steamapps\\\\common\\\\Space Station 14 Playtest"' in text
    assert "rejoin = true" in text and "interval = 2.5" in text and "max_attempts = 5" in text
    assert load(path) == settings


def test_load_defaults_and_tolerance(tmp_path: Path) -> None:
    assert load(tmp_path / "missing.toml") == Settings()
    bad = tmp_path / "bad.toml"
    bad.write_text('server = "ss14://host"\ninterval = "fast"\nunknown_key = 1\nmargin = 2.0\n')
    settings = load(bad)
    assert settings.server == "ss14://host"
    assert settings.interval == 3.0  # wrong type -> default
    assert settings.margin == 2
    bad.write_text("this is not toml")
    assert load(bad) == Settings()


def test_joiner_config_and_validation() -> None:
    settings = Settings(interval=0.2, attempt_timeout=5, max_attempts=0, on_unknown="retry")
    cfg = settings.joiner_config()
    assert cfg.interval == 1.0 and cfg.attempt_timeout == 20.0 and cfg.max_attempts is None
    assert cfg.unknown_policy == "retry" and cfg.address.uri == config.DEFAULT_SERVER
    assert Settings().validate() == []
    problems = Settings(server="http://x", launcher_dir="/nope/never", interval=0.5, on_unknown="maybe").validate()
    assert len(problems) == 4


def test_config_path(tmp_path: Path) -> None:
    assert config_path({"SS14_AUTOJOIN_CONFIG": str(tmp_path / "x.toml")}, tmp_path) == tmp_path / "x.toml"
    default = config_path({}, tmp_path)
    assert default.name == "config.toml" and default.parent.name == "ss14-autojoin"
    assert config_path({"XDG_CONFIG_HOME": str(tmp_path / "xdg")}, tmp_path).parent.parent.name in (
        "xdg",
        "ss14-autojoin",
    )
