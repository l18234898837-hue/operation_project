export type CopyResult =
  | { ok: true; method: "clipboard" | "fallback" }
  | { ok: false; reason: "empty" | "unsupported" };

function fallbackCopy(text: string): boolean {
  if (typeof document === "undefined") {
    return false;
  }

  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.setAttribute("readonly", "");
  textArea.style.position = "fixed";
  textArea.style.left = "-9999px";
  textArea.style.top = "0";

  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();

  try {
    return document.execCommand("copy");
  } finally {
    document.body.removeChild(textArea);
  }
}

export async function copyTextToClipboard(text: string): Promise<CopyResult> {
  const normalizedText = text.trim();

  if (!normalizedText) {
    return { ok: false, reason: "empty" };
  }

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return { ok: true, method: "clipboard" };
    }
  } catch {
    // Some browsers expose Clipboard API but reject it outside secure contexts.
  }

  if (fallbackCopy(text)) {
    return { ok: true, method: "fallback" };
  }

  return { ok: false, reason: "unsupported" };
}
