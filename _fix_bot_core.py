#!/usr/bin/env python3
"""fix_bot_core(path_in, path_out)

Replaces the broken r''' literal that starts at line 6864 with a safe,
empty string assignment, so Python can parse the rest of the module.
"""
import sys

TS = chr(39) + chr(39) + chr(39)   # triple-single-quote via concatenation

def fix_bot_core(src_path: str, dst_path: str) -> None:
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()

    marker = "EMBEDDED_SERVER_JS = r" + TS
    if marker not in src:
        raise SystemExit("FAIL: marker not found - file may already be fixed")

    idx = src.index(marker)
    head = src[:idx]

    note = (
        "EMBEDDED_SERVER_JS = ''\n"
        "\n"
        "# =====================================================================\n"
        "#  FIX NOTE — Multi-Session hotfix for bot_core.py\n"
        "# =====================================================================\n"
        "#  Original file contained a broken raw triple-quoted string literal at\n"
        "#  line 6864 (opening r" + TS + " but no closing " + TS + " at EOF, which\n"
        "#  ended at line 7334). Python refused to parse the module, killing\n"
        "#  the bot entirely:\n"
        "#      File \"/app/bot_core.py\", line 6864\n"
        "#        EMBEDDED_SERVER_JS = r" + TS + "const express = require(...\n"
        "#                                 ^\n"
        "#      SyntaxError: unterminated triple-quoted string literal\n"
        "#                   (detected at line 7334)\n"
        "#\n"
        "#  The broken block was a *duplicate* of the valid EMBEDDED_SERVER_JS\n"
        "#  defined earlier at lines 5956->6652. The on-disk server.js file is\n"
        "#  what actually runs, so disabling the duplicate string here is safe.\n"
        "#\n"
        "#  Real multi-session isolation lives in:\n"
        "#    lib/sessionManager.js (per-phone folders: sessions/<phone>/)\n"
        "#    lib/pairingBridge.js  (Map<phone, socket>, no primarySocket)\n"
        "#    index.js + server.js  (waClients Map<phone, socket>)\n"
        "# =====================================================================\n"
        "\n"
    )

    fixed = head + note
    if not fixed.endswith("\n"):
        fixed += "\n"

    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(fixed)

    print(f"WROTE: {dst_path}")
    print(f"OLD LINE COUNT: {src.count(chr(10))}")
    print(f"NEW LINE COUNT: {fixed.count(chr(10))}")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "bot_core.py"
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    fix_bot_core(src, dst)
