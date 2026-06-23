import { mockDocuments } from "../mock/documents";
import type { DocumentItem, DocumentType } from "../types/document";

export async function listDocuments(): Promise<DocumentItem[]> {
  return mockDocuments.map((document) => ({ ...document }));
}

export async function uploadDocument(name: string, type: DocumentType): Promise<DocumentItem> {
  return {
    id: `doc-upload-${Date.now()}`,
    name,
    type,
    category: "uncategorized",
    parseStatus: "processing",
    enableStatus: "disabled",
    updatedAt: new Date().toLocaleString("sv-SE").replace("T", " "),
    failureReason: null,
    progress: 5
  };
}

export async function enableDocument(document: DocumentItem): Promise<DocumentItem> {
  return { ...document, enableStatus: "enabled" };
}

export async function disableDocument(document: DocumentItem): Promise<DocumentItem> {
  return { ...document, enableStatus: "disabled" };
}
