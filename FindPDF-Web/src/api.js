
const API_BASE_URL = "http://127.0.0.1:8000/api";

/**
 * Convert API errors into readable messages.
 * Supports FastAPI string errors and structured error responses.
 */
async function getErrorMessage(response) {
  let data;

  try {
    data = await response.json();
  } catch {
    return `Request failed (${response.status}). Please try again.`;
  }

  const detail = data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (detail && typeof detail === "object") {
    const messages = [];

    if (typeof detail.message === "string") {
      messages.push(detail.message);
    }

    if (Array.isArray(detail.errors)) {
      for (const item of detail.errors) {
        if (item && typeof item === "object") {
          messages.push(
            `${item.filename || "File"}: ${item.error || "Unknown error"}`
          );
        } else if (typeof item === "string") {
          messages.push(item);
        }
      }
    }

    if (messages.length > 0) {
      return messages.join("\n");
    }

    try {
      return JSON.stringify(detail);
    } catch {
      return `Request failed (${response.status}).`;
    }
  }

  return (
    data?.message ||
    `Request failed (${response.status}). Please try again.`
  );
}

/**
 * Central API request handler.
 */
async function apiRequest(url, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${url}`, options);
  } catch {
    throw new Error(
      "Cannot connect to FindPDF. Make sure the backend is running on port 8000."
    );
  }

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  try {
    return await response.json();
  } catch {
    throw new Error("The server returned an invalid response.");
  }
}

/**
 * Upload one or more PDF files.
 */
export async function uploadPDFs(files) {
  const selectedFiles =
    files instanceof File
      ? [files]
      : Array.from(files || []);

  if (selectedFiles.length === 0) {
    throw new Error("Please select at least one PDF.");
  }

  const formData = new FormData();

  for (const file of selectedFiles) {
    formData.append("files", file);
  }

  return apiRequest("/documents", {
    method: "POST",
    body: formData,
  });
}

/**
 * Retrieve uploaded documents.
 */
export async function getDocuments() {
  const data = await apiRequest("/documents");
  return data.documents || [];
}

/**
 * Delete a document.
 */
export async function deleteDocument(documentId) {
  if (!documentId) {
    throw new Error("A document ID is required.");
  }

  return apiRequest(
    `/documents/${encodeURIComponent(documentId)}`,
    {
      method: "DELETE",
    }
  );
}

/**
 * Ask a question about selected PDFs.
 */
export async function askQuestion(question, documentIds = []) {
  const cleanQuestion = String(question || "").trim();

  if (!cleanQuestion) {
    throw new Error("Please enter a question.");
  }

  return apiRequest("/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question: cleanQuestion,
      document_ids: documentIds,
    }),
  });
}
