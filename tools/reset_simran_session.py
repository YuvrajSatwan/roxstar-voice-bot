"""Let a user talk to Simran again (for testing the "one conversation per user" rule).

Usage (from the sts_lab folder):
    py tools/reset_simran_session.py 990835     # one user (their RoxStar user id)
    py tools/reset_simran_session.py all        # everybody
    py tools/reset_simran_session.py list       # show who has used their conversation
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sts_lab.session_gate import SessionGate  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    arg = sys.argv[1].strip().lower()
    gate = SessionGate(enabled=True)
    if arg == "list":
        used = gate._read()  # noqa: SLF001 - small admin tool
        print(f"{len(used)} room(s) have used their conversation:")
        for room in sorted(used):
            print("  ", room)
        return 0
    if arg == "all":
        print(f"Cleared {gate.reset(None)} room(s).")
        return 0
    if not arg.isdigit():
        print("Give a numeric user id, 'all' or 'list'.")
        return 2
    print(f"Cleared {gate.reset(f'sts-simran-{arg}')} room(s) for user {arg}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
