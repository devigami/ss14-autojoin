"""PyInstaller entry script for the console tool. Nothing imports this module."""

from ss14_autojoin.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
