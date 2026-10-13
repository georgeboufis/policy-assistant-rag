// Every call the app makes. Vite proxies /api to the Python server on port 8000.

async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    // FastAPI puts the reason in "detail". For a failure of the model that detail is an
    // object - what kind, which model, how long to wait - and the banner needs all of
    // it, so the Error carries it rather than being flattened into one string.
    let detail = null;
    try {
      detail = (await response.json())?.detail ?? null;
    } catch {
      /* no JSON body */
    }

    const problem = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || `${response.status} ${response.statusText}`
    );
    problem.status = response.status;
    if (detail && typeof detail === "object") {
      problem.kind = detail.kind;
      problem.model = detail.model;
      problem.retryAfter = detail.retry_after;
    }
    throw problem;
  }

  return response.status === 204 ? null : response.json();
}

export async function uploadDocument(file) {
  const form = new FormData();
  form.append("file", file);
  // No Content-Type header on purpose - the browser sets it, with the boundary.
  const response = await fetch("/api/documents", { method: "POST", body: form });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.detail || `${response.status}`);
  return body;
}

export const api = {
  settings: () => request("/settings"),
  stats: () => request("/stats"),
  reasons: () => request("/reasons"),
  cache: () => request("/cache"),
  clearCache: () => request("/cache", { method: "DELETE" }),
  documents: () => request("/documents"),
  removeDocument: (name) =>
    request(`/documents/${encodeURIComponent(name)}`, { method: "DELETE" }),
  rate: (messageId, verdict, reason) =>
    request(`/messages/${messageId}/rating`, {
      method: "PUT",
      body: JSON.stringify({ verdict, reason: reason ?? null }),
    }),
  clearRating: (messageId) =>
    request(`/messages/${messageId}/rating`, { method: "DELETE" }),
  listConversations: () => request("/conversations"),
  createConversation: () => request("/conversations", { method: "POST" }),
  getConversation: (id) => request(`/conversations/${id}`),
  rename: (id, title) =>
    request(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  remove: (id) => request(`/conversations/${id}`, { method: "DELETE" }),
  ask: (id, question) =>
    request(`/conversations/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
};
