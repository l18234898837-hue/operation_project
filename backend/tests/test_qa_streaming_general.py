import asyncio

import pytest

from app.services.qa_streaming import _StreamingAnswerClient


class FakeGeneralStreamingAnswerClient:
    async def stream_general(self, question, mode="general"):
        yield "hello "
        await asyncio.sleep(0)
        yield "there"

    async def generate_general(self, question, mode="general"):
        raise AssertionError("generate_general should not be used when stream_general exists")


@pytest.mark.asyncio
async def test_streaming_answer_client_streams_general_answers():
    queue = asyncio.Queue()
    client = _StreamingAnswerClient(FakeGeneralStreamingAnswerClient(), queue)

    answer = await client.generate_general("hello", mode="chitchat")

    assert answer == "hello there"
    assert await queue.get() == "hello "
    assert await queue.get() == "there"
    assert await queue.get() is None
