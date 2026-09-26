"""The window: settings panel, Start/Stop, and a log of what the loop does.

Thin by design: every decision lives in ``joiner``, ``launcher``, ``config``. The joiner runs in a worker
thread and reports through a queue that the Tk main loop drains. Nothing here is imported by the CLI except
:func:`main`; the PyInstaller entry script is ``gui_main.py``.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .config import Settings, config_path, load, save
from .joiner import Joiner
from .launcher import find_launcher, launcher_data_dir, running_launcher_exes
from .notify import play_success

TITLE = "SS14 Auto-Join"


def settings_to_form(settings: Settings) -> dict[str, str | bool]:
    """Values for the widgets (strings for entries, bools for check boxes)."""
    return {
        "launcher_dir": settings.launcher_dir,
        "server": settings.server,
        "interval": f"{settings.interval:g}",
        "margin": str(settings.margin),
        "attempt_timeout": f"{settings.attempt_timeout:g}",
        "cooldown": f"{settings.cooldown:g}",
        "max_attempts": str(settings.max_attempts),
        "on_unknown": settings.on_unknown,
        "rejoin": settings.rejoin,
        "restart_launcher": settings.restart_launcher,
        "skip_panic_bunker": settings.skip_panic_bunker,
        "sound": settings.sound,
    }


def form_to_settings(form: dict[str, str | bool]) -> tuple[Settings, list[str]]:
    """Parse widget values; returns the settings and a list of problems (empty when usable)."""
    problems: list[str] = []

    def number(key: str, kind: type, default: float | int) -> float | int:
        raw = str(form.get(key, "")).strip()
        try:
            return kind(raw) if raw else default
        except ValueError:
            problems.append(f"{key.replace('_', ' ')}: not a number ({raw!r})")
            return default

    settings = Settings(
        launcher_dir=str(form.get("launcher_dir", "")).strip(),
        server=str(form.get("server", "")).strip(),
        interval=number("interval", float, 3.0),
        margin=number("margin", int, 0),
        attempt_timeout=number("attempt_timeout", float, 60.0),
        cooldown=number("cooldown", float, 2.0),
        max_attempts=number("max_attempts", int, 0),
        on_unknown=str(form.get("on_unknown", "keep")),
        rejoin=bool(form.get("rejoin", False)),
        restart_launcher=bool(form.get("restart_launcher", False)),
        skip_panic_bunker=bool(form.get("skip_panic_bunker", False)),
        sound=bool(form.get("sound", True)),
    )
    problems += settings.validate()
    return settings, problems


class App:
    def __init__(self, root: tk.Tk, settings: Settings, path: Path) -> None:
        self.root = root
        self.path = path
        self.settings = settings
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.joiner: Joiner | None = None
        self.worker: threading.Thread | None = None
        self.vars: dict[str, tk.Variable] = {}
        root.title(TITLE)
        root.minsize(640, 520)
        self._set_icon()
        self._build()
        self._fill(settings_to_form(settings))
        if not settings.launcher_dir:
            self.detect_launcher(quiet=True)
        root.after(200, self._drain)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def _set_icon(self) -> None:
        """Title bar and taskbar icon from the bundled files; silently keep Tk's default if anything fails."""
        try:
            from importlib import resources  # noqa: PLC0415

            data = resources.files("ss14_autojoin").joinpath("data")
            png = Path(str(data.joinpath("icon.png")))
            if png.is_file():
                self._icon_image = tk.PhotoImage(file=str(png))  # keep a reference or Tk drops it
                self.root.iconphoto(True, self._icon_image)
            ico = Path(str(data.joinpath("icon.ico")))
            if sys.platform == "win32" and ico.is_file():
                self.root.iconbitmap(default=str(ico))
        except Exception:  # noqa: BLE001
            pass

    # -- layout --------------------------------------------------------------------------------------------------

    def _build(self) -> None:
        pad = {"padx": 6, "pady": 3}
        box = ttk.LabelFrame(self.root, text="Settings")
        box.pack(fill="x", padx=8, pady=8)
        box.columnconfigure(1, weight=1)

        def entry(row: int, key: str, label: str, width: int = 12) -> None:
            ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", **pad)
            var = tk.StringVar()
            self.vars[key] = var
            ttk.Entry(box, textvariable=var, width=width).grid(row=row, column=1, sticky="we", **pad)

        entry(0, "launcher_dir", "Game / launcher folder", 60)
        buttons = ttk.Frame(box)
        buttons.grid(row=0, column=2, sticky="e", **pad)
        ttk.Button(buttons, text="Browse…", command=self.browse).pack(side="left")
        ttk.Button(buttons, text="Detect", command=self.detect_launcher).pack(side="left", padx=(4, 0))
        entry(1, "server", "Server address (ss14:// or ss14s://)", 60)

        numbers = ttk.Frame(box)
        numbers.grid(row=2, column=0, columnspan=3, sticky="w")
        for col, (key, label) in enumerate(
            [
                ("interval", "Poll every (s)"),
                ("margin", "Extra free slots"),
                ("attempt_timeout", "Decide after (s)"),
                ("cooldown", "Cooldown (s)"),
                ("max_attempts", "Max attempts (0 = ∞)"),
            ]
        ):
            ttk.Label(numbers, text=label).grid(row=0, column=col, sticky="w", **pad)
            var = tk.StringVar()
            self.vars[key] = var
            ttk.Entry(numbers, textvariable=var, width=8).grid(row=1, column=col, sticky="w", **pad)

        options = ttk.Frame(box)
        options.grid(row=3, column=0, columnspan=3, sticky="w")
        for col, (key, label) in enumerate(
            [
                ("rejoin", "Rejoin after the client exits or is disconnected"),
                ("restart_launcher", "Restart a stuck launcher"),
                ("skip_panic_bunker", "Skip while panic bunker is on"),
                ("sound", "Play a fanfare when joined"),
            ]
        ):
            var = tk.BooleanVar()
            self.vars[key] = var
            ttk.Checkbutton(options, text=label, variable=var).grid(row=0, column=col, sticky="w", **pad)
        ttk.Label(options, text="If unsure after the timeout:").grid(row=1, column=0, sticky="e", **pad)
        var = tk.StringVar()
        self.vars["on_unknown"] = var
        ttk.Combobox(options, textvariable=var, values=("keep", "retry"), state="readonly", width=8).grid(
            row=1, column=1, sticky="w", **pad
        )
        ttk.Label(options, text="keep = leave the game running and stop; retry = close it and try again").grid(
            row=1, column=2, sticky="w", **pad
        )

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", padx=8)
        self.start_button = ttk.Button(actions, text="Start watching", command=self.start)
        self.start_button.pack(side="left")
        ttk.Button(actions, text="Save settings", command=self.save_settings).pack(side="left", padx=6)
        self.status = ttk.Label(actions, text="idle")
        self.status.pack(side="left", padx=12)

        self.log = scrolledtext.ScrolledText(self.root, height=16, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.append("log", f"settings file: {self.path}")

    def _fill(self, form: dict[str, str | bool]) -> None:
        for key, value in form.items():
            if key in self.vars:
                self.vars[key].set(value)

    def _form(self) -> dict[str, str | bool]:
        return {key: var.get() for key, var in self.vars.items()}

    # -- actions -------------------------------------------------------------------------------------------------

    def browse(self) -> None:
        chosen = filedialog.askdirectory(title="Folder that holds bin_x64 (the launcher install)")
        if chosen:
            self.vars["launcher_dir"].set(chosen)

    def detect_launcher(self, quiet: bool = False) -> None:
        data_dir = launcher_data_dir()
        install = find_launcher(None, launcher_log_dir=data_dir / "logs", process_exes=running_launcher_exes)
        if install is None:
            if not quiet:
                messagebox.showinfo(
                    TITLE, "No launcher installation found. Use Browse to pick the folder that holds bin_x64."
                )
            return
        self.vars["launcher_dir"].set(str(install.root))
        self.append("log", f"launcher detected via {install.source}: {install.root}")

    def save_settings(self) -> bool:
        settings, problems = form_to_settings(self._form())
        if problems:
            messagebox.showerror(TITLE, "Please fix:\n\n" + "\n".join(problems))
            return False
        self.settings = settings
        save(settings, self.path)
        self.append("log", "settings saved")
        return True

    def start(self) -> None:
        if self.joiner is not None:
            self.stop()
            return
        if not self.save_settings():
            return
        from .runtime import RealPorts  # noqa: PLC0415 - psutil only when actually running

        data_dir = launcher_data_dir()
        configured = Path(self.settings.launcher_dir) if self.settings.launcher_dir else None
        install = find_launcher(configured, launcher_log_dir=data_dir / "logs", process_exes=running_launcher_exes)
        if install is None:
            messagebox.showerror(TITLE, "Launcher installation not found. Pick the folder that holds bin_x64.")
            return
        config = self.settings.joiner_config()
        ports = RealPorts(install, data_dir)
        self.joiner = Joiner(config, ports, listener=lambda kind, msg: self.events.put((kind, msg)))
        self.append("log", f"launcher: {install.launcher_exe}")
        self.append("log", f"watching {config.address.uri} via {config.address.status_url}")
        self.worker = threading.Thread(target=self._run, daemon=True, name="joiner")
        self.worker.start()
        self.start_button.configure(text="Stop")
        self.status.configure(text="watching")

    def _run(self) -> None:
        assert self.joiner is not None
        try:
            outcome = self.joiner.run()
            self.events.put(("done", outcome.message))
        except Exception as e:  # noqa: BLE001 - surface anything to the window
            self.events.put(("done", f"error: {e!r}"))

    def stop(self) -> None:
        if self.joiner is not None:
            self.joiner.stop()
            self.status.configure(text="stopping…")

    def close(self) -> None:
        self.stop()
        self.root.after(300, self.root.destroy)

    # -- events --------------------------------------------------------------------------------------------------

    def _drain(self) -> None:
        try:
            while True:
                kind, message = self.events.get_nowait()
                self.append(kind, message)
                if kind in ("status", "attempt", "joined", "failed", "stuck"):
                    self.status.configure(text=message[:80])
                if kind == "done":
                    self.joiner = None
                    self.start_button.configure(text="Start watching")
                    self.status.configure(text=message[:80])
                    self.root.lift()
                if kind == "joined" and self.settings.sound:
                    threading.Thread(target=play_success, daemon=True).start()
        except queue.Empty:
            pass
        self.root.after(200, self._drain)

    def append(self, kind: str, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"[{time.strftime('%H:%M:%S')}] {kind:8s} {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")


def main() -> int:
    path = config_path()
    root = tk.Tk()
    App(root, load(path), path)
    root.mainloop()
    return 0
