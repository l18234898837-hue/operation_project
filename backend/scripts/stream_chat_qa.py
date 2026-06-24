from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings


async def main() -> None:
    print("RAG SSE 流式问答")
    print("输入 /exit 退出。运行前请先启动后端 API 服务。")
    async with httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{settings.app_port}",
        timeout=None,
    ) as client:
        session_id = None
        while True:
            question = input("你：").strip()
            if not question:
                continue
            if question.lower() in {"/exit", "exit", "quit", "q"}:
                break
            payload = {"question": question, "session_id": session_id}
            async with client.stream(
                "POST",
                "/api/qa/ask/stream",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = json.loads(line.removeprefix("data: "))
                    if "message" in data:
                        print(f"\n[{data['message']}]")
                    if "text" in data:
                        print(data["text"], end="", flush=True)
                    if "session_id" in data:
                        session_id = data["session_id"]
                print()


if __name__ == "__main__":
    asyncio.run(main())
