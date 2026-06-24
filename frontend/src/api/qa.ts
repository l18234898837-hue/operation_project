import type { AskQuestionStreamOptions, QaAskRequest, QaAskResponse, QaStreamEvent } from "../types/qa";

export async function askQuestion(payload: QaAskRequest): Promise<QaAskResponse> {
  const response = await fetch("/api/qa/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`QA request failed: ${response.status}`);
  }

  return (await response.json()) as QaAskResponse;
}

export async function askQuestionStream(
  payload: QaAskRequest,
  { signal, onEvent }: AskQuestionStreamOptions
): Promise<void> {
  const response = await fetch("/api/qa/ask/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    signal
  });

  if (!response.ok) {
    throw new Error(`QA stream request failed: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("QA stream response body is empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const event = parseSseEvent(part);
      if (event) {
        onEvent(event);
      }
    }
  }

  buffer += decoder.decode();
  const finalEvent = parseSseEvent(buffer);
  if (finalEvent) {
    onEvent(finalEvent);
  }
}

function parseSseEvent(raw: string): QaStreamEvent | null {
  const lines = raw.split(/\r?\n/);
  const eventLine = lines.find((line) => line.startsWith("event: "));
  const dataLine = lines.find((line) => line.startsWith("data: "));

  if (!eventLine || !dataLine) {
    return null;
  }

  return {
    event: eventLine.slice("event: ".length),
    data: JSON.parse(dataLine.slice("data: ".length))
  } as QaStreamEvent;
}
