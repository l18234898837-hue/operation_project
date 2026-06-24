from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.ask_question import ask_once


async def main() -> None:
    first = await ask_once("逆变器绝缘阻抗低怎么排查？", session_id=None)
    second = await ask_once("那下雨天才出现呢？", session_id=first.session_id)

    print("first_session_id =", first.session_id)
    print("second_session_id =", second.session_id)
    print("second_answer_type =", second.answer_type)
    print("second_intent =", second.intent)
    print("standalone_question =", second.decision.get("standalone_question"))
    print("used_history =", second.decision.get("used_history"))
    print("references =", len(second.references))

    if second.session_id != first.session_id:
        raise SystemExit("Multi-turn smoke did not reuse session_id")
    if not second.decision.get("standalone_question"):
        raise SystemExit("Multi-turn smoke did not include standalone_question")


if __name__ == "__main__":
    asyncio.run(main())
