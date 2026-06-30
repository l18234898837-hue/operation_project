import type { DocumentItem } from "../types/document";

async function parseDocumentResponse(response: Response): Promise<DocumentItem> {
  if (!response.ok) {
    throw new Error(`Document request failed: ${response.status}`);
  }

  return (await response.json()) as DocumentItem;
}

export async function listDocuments(): Promise<DocumentItem[]> {
  const response = await fetch("/api/documents");

  if (!response.ok) {
    throw new Error(`Document list request failed: ${response.status}`);
  }

  return (await response.json()) as DocumentItem[];
}

export async function setDocumentEnabled(id: string, enabled: boolean): Promise<DocumentItem> {
  const response = await fetch(`/api/documents/${id}/enabled`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ enabled })
  });

  return parseDocumentResponse(response);
}

export async function retryDocumentParse(id: string): Promise<DocumentItem> {
  const response = await fetch(`/api/documents/${id}/retry`, {
    method: "POST"
  });

  return parseDocumentResponse(response);
}
