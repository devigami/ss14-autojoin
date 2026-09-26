"""Settings file: a flat TOML table, read with the standard library, written by hand.

Location: ``%APPDATA%\\ss14-autojoin\\config.toml`` on Windows, ``~/.config/ss14-autojoin/config.toml``
elsewhere (``SS14_AUTOJOIN_CONFIG`` overrides the path). Flags on the command line win over the file.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .joiner import JoinerConfig
from .server import ServerAddress

DEFAULT_SERVER = "ss14s://lizard.spacestation14.io/server"


@dataclass(slots=True)
class Settings:
    launcher_dir: str = ""
    """Launcher install folder (the one with ``bin_x64``); empty means auto-detect."""
    server: str = DEFAULT_SERVER
    interval: float = 3.0
    margin: int = 0
    attempt_timeout: float = 60.0
    on_unknown: str = "keep"
    cooldown: float = 2.0
    max_attempts: int = 0
    """0 means unlimited."""
    rejoin: bool = False
    restart_launcher: bool = False
    skip_panic_bunker: bool = False
    sound: bool = True
    """Play the fanfare when the join lands."""

    def joiner_config(self) -> JoinerConfig:
        return JoinerConfig(
            address=ServerAddress.parse(self.server),
            interval=max(1.0, float(self.interval)),
            margin=max(0, int(self.margin)),
            attempt_timeout=max(20.0, float(self.attempt_timeout)),
            unknown_policy="retry" if self.on_unknown == "retry" else "keep",
            cooldown=max(0.0, float(self.cooldown)),
            max_attempts=int(self.max_attempts) or None,
            rejoin=bool(self.rejoin),
            restart_launcher=bool(self.restart_launcher),
            skip_panic_bunker=bool(self.skip_panic_bunker),
        )

    def validate(self) -> list[str]:
        """Human-readable problems, empty when the settings can be used."""
        problems = []
        try:
            ServerAddress.parse(self.server)
        except ValueError as e:
            problems.append(f"server address: {e}")
        if self.launcher_dir and not Path(self.launcher_dir).exists():
            problems.append(f"launcher folder does not exist: {self.launcher_dir}")
        if self.interval < 1:
            problems.append("poll interval must be at least 1 second")
        if self.on_unknown not in ("keep", "retry"):
            problems.append("on_unknown must be 'keep' or 'retry'")
        return problems


def config_path(env: dict[str, str] | None = None, home: Path | None = None) -> Path:
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    if env.get("SS14_AUTOJOIN_CONFIG"):
        return Path(env["SS14_AUTOJOIN_CONFIG"])
    if sys.platform == "win32" and env.get("APPDATA"):
        return Path(env["APPDATA"]) / "ss14-autojoin" / "config.toml"
    base = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else home / ".config"
    return base / "ss14-autojoin" / "config.toml"


def load(path: Path | None = None) -> Settings:
    """Read the file; missing file or unknown keys are fine, wrong types fall back to the default."""
    path = config_path() if path is None else Path(path)
    settings = Settings()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        return settings
    for f in fields(Settings):
        if f.name not in data:
            continue
        value = data[f.name]
        default = getattr(settings, f.name)
        try:
            if isinstance(default, bool):
                value = bool(value)
            elif isinstance(default, int):
                value = int(value)
            elif isinstance(default, float):
                value = float(value)
            else:
                value = str(value)
        except TypeError, ValueError:
            continue
        setattr(settings, f.name, value)
    return settings


def save(settings: Settings, path: Path | None = None) -> Path:
    path = config_path() if path is None else Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# ss14-autojoin settings. Edited by the app; hand edits are fine.", ""]
    for key, value in asdict(settings).items():
        lines.append(f"{key} = {_toml_value(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'
