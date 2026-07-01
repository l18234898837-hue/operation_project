import type { DocumentDetail, DocumentItem } from "../types/document";

async function getDocumentErrorMessage(response: Response) {
  try {
    const errorBody = (await response.json()) as { message?: unknown; detail?: unknown };
    const message = errorBody.message ?? errorBody.detail;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  } catch {
    // Fall back to the status when the API does not return JSON.
  }

  return `Document request failed: ${response.status}`;
}

async function parseDocumentResponse(response: Response): Promise<DocumentItem> {
  if (!response.ok) {
    throw new Error(await getDocumentErrorMessage(response));
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

export async function getDocumentDetail(id: string): Promise<DocumentDetail> {
  const response = await fetch(`/api/documents/${id}`);
  if (!response.ok) {
    throw new Error(await getDocumentErrorMessage(response));
  }

  return (await response.json()) as DocumentDetail;
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/documents/upload", {
    method: "POST",
    body: formData
  });

  return parseDocumentResponse(response);
}
