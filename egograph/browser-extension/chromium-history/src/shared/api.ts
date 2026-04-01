import type { BrowserHistoryPayload, SyncOutcome } from "./types.js";

export async function postBrowserHistory(
  serverUrl: string,
  xApiKey: string,
  payload: BrowserHistoryPayload,
  fetchImpl: typeof fetch = fetch
): Promise<SyncOutcome> {
  const url = new URL("/v1/ingest/browser-history", serverUrl).toString();
  const response = await fetchImpl(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": xApiKey
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    return {
      ok: false,
      status: response.status,
      message: `Sync failed with status ${response.status}`
    };
  }

  const data = (await response.json()) as { accepted?: number };
  return {
    ok: true,
    accepted: data.accepted ?? payload.items.length,
    status: response.status
  };
}
