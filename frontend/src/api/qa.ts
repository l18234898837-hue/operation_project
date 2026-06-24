import type { QaAskRequest, QaAskResponse } from "../types/qa";

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
