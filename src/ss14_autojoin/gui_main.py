"""PyInstaller entry script for the window. Nothing imports this module (frozen entry scripts are not importable)."""

from ss14_autojoin.app import main

if __name__ == "__main__":
    raise SystemExit(main())
