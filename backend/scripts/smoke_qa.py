from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.ask_question import ask_once


async def main() -> None:
    cases = [
        ("rag", "逆变器绝缘阻抗低怎么排查？"),
        ("general_or_rag", "什么是无功功率？"),
        ("realtime_boundary", "今天上海天气怎么样？"),
    ]

    for expected, question in cases:
        response = await ask_once(question, session_id=None)
        print("question =", question)
        print("answer_type =", response.answer_type)
        print("intent =", response.intent)
        print("references =", len(response.references))
        print("session_id =", response.session_id)
        print("---")

        if expected == "rag" and response.answer_type != "rag":
            raise SystemExit("RAG smoke case did not return rag")
        if expected == "realtime_boundary" and response.answer_type != "general_llm":
            raise SystemExit("Realtime smoke case did not return boundary answer")
        if expected == "general_or_rag" and response.answer_type not in {"general_llm", "rag"}:
            raise SystemExit("General smoke case returned unexpected answer_type")


if __name__ == "__main__":
    asyncio.run(main())
