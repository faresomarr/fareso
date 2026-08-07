import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BOT_CORE_FILE = BASE_DIR / "bot_core.py"


def main() -> None:
    if not BOT_CORE_FILE.exists():
        raise RuntimeError("تعذر العثور على bot_core.py")

    env = os.environ.copy()
    process = subprocess.run([sys.executable, str(BOT_CORE_FILE)], cwd=str(BASE_DIR), env=env)
    raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
