from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.ask_question import ask_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive command-line QA chat for the RAG knowledge base.",
    )
    parser.add_argument(
        "--show-references",
        action="store_true",
        help="Show reference snippets after every answer.",
    )
    parser.add_argument(
        "--show-decision",
        action="store_true",
        help="Show routing, intent, score, and standalone question metadata.",
    )
    parser.add_argument(
        "--show-timing",
        action="store_true",
        help="Show per-stage latency returned by the QA service.",
    )
    parser.add_argument(
        "--new-session",
        action="store_true",
        help="Start without reusing a manually supplied session id.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Reuse an existing QA session id.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    session_id = None if args.new_session else args.session_id

    print("RAG 知识库命令行问答")
    print("输入问题后回车；输入 /exit 退出，/new 开启新会话，/refs 切换引用显示。")
    print()

    show_references = args.show_references
    while True:
        question = input("你：").strip()
        if not question:
            continue
        if question.lower() in {"/exit", "exit", "quit", "q"}:
            break
        if question.lower() == "/new":
            session_id = None
            print("系统：已开启新会话。")
            continue
        if question.lower() == "/refs":
            show_references = not show_references
            state = "开启" if show_references else "关闭"
            print(f"系统：引用显示已{state}。")
            continue

        try:
            response = await ask_once(question, session_id=session_id)
        except httpx.TimeoutException:
            print("系统：模型服务请求超时，请稍后重试。")
            continue

        session_id = response.session_id
        print()
        print(f"助手：{response.answer}")
        print()
        print(
            "会话："
            f"{response.session_id} | 类型：{response.answer_type} | "
            f"意图：{response.intent} | 置信度：{_format_score(response.confidence)}"
        )

        if args.show_decision:
            decision = response.decision
            print("决策：")
            print(f"  route = {decision.get('route')}")
            print(f"  standalone_question = {decision.get('standalone_question')}")
            print(f"  search_query = {decision.get('search_query')}")
            print(f"  top1_rerank_score = {decision.get('top1_rerank_score')}")
            print(f"  used_history = {decision.get('used_history')}")

        if args.show_timing:
            timings = response.decision.get("timings_ms") or {}
            print("耗时：")
            for key, value in sorted(
                timings.items(),
                key=lambda item: item[1],
                reverse=True,
            ):
                print(f"  {key} = {value} ms")

        if show_references and response.references:
            visible_refs = [
                reference for reference in response.references if reference.visible
            ]
            hidden_refs = [
                reference for reference in response.references if not reference.visible
            ]

            print("引用：")
            for reference in visible_refs:
                print(
                    f"  [{reference.rank}] {reference.heading_path} "
                    f"(rerank={_format_score(reference.rerank_score)})"
                )
                print(f"      {reference.excerpt}")
            if hidden_refs:
                print(f"  还有 {len(hidden_refs)} 条引用已折叠，可在接口返回中查看。")

        print()


def _format_score(score: float | None) -> str:
    if score is None:
        return "-"
    return f"{score:.3f}"


if __name__ == "__main__":
    asyncio.run(main())
