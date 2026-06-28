import pytest

from app.services.answer_generation import stream_general_answer


class FakeStreamingChatClient:
    def __init__(self) -> None:
        self.calls = []

    async def chat(self, messages, temperature=0.1):
        raise AssertionError("stream_general_answer should use chat_stream")

    async def chat_stream(self, messages, temperature=0.1):
        self.calls.append({"messages": messages, "temperature": temperature})
        yield "part one"
        yield "part two"


@pytest.mark.asyncio
async def test_stream_general_answer_records_stream_diagnostics():
    client = FakeStreamingChatClient()
    diagnostics = {}

    chunks = [
        chunk
        async for chunk in stream_general_answer(
            chat_client=client,
            question="hello",
            mode="chitchat",
            diagnostics=diagnostics,
        )
    ]

    assert chunks == ["part one", "part two"]
    assert client.calls[0]["temperature"] == 0.1
    assert diagnostics["streamed"] is True
    assert diagnostics["mode"] == "chitchat"
    assert diagnostics["messages_count"] == 2
    assert diagnostics["evidence_count"] == 0
    assert diagnostics["chunk_count"] == 2
    assert diagnostics["output_chars"] == len("part onepart two")
    assert diagnostics["first_token_ms"] >= 0
