from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure direct LLM streaming latency without QA business logic.",
    )
    parser.add_argument("--question", default="你好", help="Question sent to the chat model.")
    parser.add_argument("--repeat", type=int, default=1, help="Number of repeated requests.")
    parser.add_argument(
        "--model",
        default=settings.qa_chat_model or settings.llm_model,
        help="Model name. Defaults to QA_CHAT_MODEL, then LLM_MODEL.",
    )
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=64)
    return parser.parse_args()


def _read_stream_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""

    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if isinstance(content, str):
        return content

    return ""


async def measure_once(
    *,
    question: str,
    model: str,
    temperature: float,
    max_tokens: int,
    run_index: int,
) -> None:
    timeout = httpx.Timeout(settings.model_api_timeout_seconds)
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个简洁的光伏运维助手。"},
            {"role": "user", "content": question},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    start = time.perf_counter()
    first_sse_at: float | None = None
    first_content_at: float | None = None
    sse_count = 0
    content_chunk_count = 0
    output_parts: list[str] = []

    async with httpx.AsyncClient(base_url=settings.llm_base_url, timeout=timeout) as client:
        async with client.stream(
            "POST",
            "/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            print(f"run={run_index} status={response.status_code} model={model}")
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue

                payload_text = line.removeprefix("data:").strip()
                if payload_text == "[DONE]":
                    break

                now = time.perf_counter()
                if first_sse_at is None:
                    first_sse_at = now
                sse_count += 1

                try:
                    data = json.loads(payload_text)
                except json.JSONDecodeError:
                    print(f"invalid_stream_payload={payload_text[:200]}")
                    continue

                content = _read_stream_content(data)
                if not content:
                    continue

                if first_content_at is None:
                    first_content_at = now
                content_chunk_count += 1
                output_parts.append(content)

    total_ms = int((time.perf_counter() - start) * 1000)
    first_sse_ms = None if first_sse_at is None else int((first_sse_at - start) * 1000)
    first_content_ms = None if first_content_at is None else int((first_content_at - start) * 1000)
    output = "".join(output_parts)
    chars_per_second = round(len(output) / (total_ms / 1000), 2) if total_ms > 0 else None

    print(
        "metrics "
        f"first_sse_ms={first_sse_ms} "
        f"first_content_ms={first_content_ms} "
        f"total_ms={total_ms} "
        f"sse_chunks={sse_count} "
        f"content_chunks={content_chunk_count} "
        f"output_chars={len(output)} "
        f"chars_per_second={chars_per_second}"
    )
    print(f"preview={output[:120]}")
    print("---")


async def main() -> None:
    args = parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat must be >= 1")
    if not settings.llm_base_url:
        raise SystemExit("LLM_BASE_URL is not configured.")
    if not settings.llm_api_key:
        raise SystemExit("LLM_API_KEY is not configured.")
    if not args.model:
        raise SystemExit("QA_CHAT_MODEL or LLM_MODEL is not configured.")

    print(f"base_url={settings.llm_base_url}")
    print(f"question={args.question}")
    print(f"repeat={args.repeat}")
    print("---")

    for index in range(1, args.repeat + 1):
        await measure_once(
            question=args.question,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            run_index=index,
        )


if __name__ == "__main__":
    asyncio.run(main())
