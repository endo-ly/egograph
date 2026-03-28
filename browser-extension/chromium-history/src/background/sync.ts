import { postBrowserHistory } from "../shared/api.js";
import type {
  BrowserHistoryPayload,
  ExtensionSettings,
  SyncOutcome
} from "../shared/types.js";
import { isCompleteSettings } from "../shared/types.js";
import { collectHistoryItems } from "./history.js";
import {
  getLastSuccessfulSyncAt,
  getSettings,
  setFailedSync,
  setSuccessfulSync
} from "./storage.js";

export interface SyncDependencies {
  getSettings: typeof getSettings;
  getLastSuccessfulSyncAt: typeof getLastSuccessfulSyncAt;
  collectHistoryItems: typeof collectHistoryItems;
  postBrowserHistory: typeof postBrowserHistory;
  setSuccessfulSync: typeof setSuccessfulSync;
  setFailedSync: typeof setFailedSync;
  createSyncId: () => string;
  now: () => Date;
  sleep: (ms: number) => Promise<void>;
}

const MAX_ITEMS_PER_REQUEST = 1000;
const MAX_POST_ATTEMPTS = 3;
const RETRY_DELAY_MS = 5000;

function randomUuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export const defaultSyncDependencies: SyncDependencies = {
  getSettings,
  getLastSuccessfulSyncAt,
  collectHistoryItems,
  postBrowserHistory,
  setSuccessfulSync,
  setFailedSync,
  createSyncId: randomUuid,
  now: () => new Date(),
  sleep: (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
};

export function buildPayload(
  settings: ExtensionSettings,
  items: BrowserHistoryPayload["items"],
  now: Date,
  syncId: string
): BrowserHistoryPayload {
  return {
    sync_id: syncId,
    source_device: settings.deviceId,
    browser: settings.browserId,
    profile: settings.profile,
    synced_at: now.toISOString(),
    items
  };
}

function chunkItems<T>(items: T[], chunkSize: number): T[][] {
  if (items.length === 0) {
    return [[]];
  }

  const chunks: T[][] = [];
  for (let index = 0; index < items.length; index += chunkSize) {
    chunks.push(items.slice(index, index + chunkSize));
  }
  return chunks;
}

function shouldRetrySyncOutcome(result: SyncOutcome): boolean {
  if (result.ok) {
    return false;
  }
  return result.message === "Failed to fetch";
}

async function postBrowserHistoryWithRetry(
  deps: SyncDependencies,
  settings: ExtensionSettings,
  payload: BrowserHistoryPayload
): Promise<SyncOutcome> {
  let lastResult: SyncOutcome | null = null;

  for (let attempt = 1; attempt <= MAX_POST_ATTEMPTS; attempt += 1) {
    try {
      const result = await deps.postBrowserHistory(
        settings.serverUrl,
        settings.xApiKey,
        payload
      );
      if (!shouldRetrySyncOutcome(result) || attempt === MAX_POST_ATTEMPTS) {
        return result;
      }
      lastResult = result;
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      lastResult = { ok: false, message };
      if (attempt === MAX_POST_ATTEMPTS || message !== "Failed to fetch") {
        return lastResult;
      }
    }

    await deps.sleep(RETRY_DELAY_MS);
  }

  return lastResult ?? { ok: false, message: "Sync failed" };
}

export async function runBrowserHistorySync(
  deps: SyncDependencies = defaultSyncDependencies
): Promise<SyncOutcome> {
  const settings = await deps.getSettings();
  if (!isCompleteSettings(settings)) {
    return { ok: false, message: "Incomplete settings" };
  }

  try {
    const lastSuccessfulSyncAt = await deps.getLastSuccessfulSyncAt();
    const syncStartedAt = deps.now();
    const items = await deps.collectHistoryItems(
      lastSuccessfulSyncAt,
      syncStartedAt.toISOString()
    );
    const batches = chunkItems(items, MAX_ITEMS_PER_REQUEST);
    let accepted = 0;

    for (const batch of batches) {
      const payload = buildPayload(
        settings,
        batch,
        syncStartedAt,
        deps.createSyncId()
      );
      const result = await postBrowserHistoryWithRetry(deps, settings, payload);

      if (!result.ok) {
        await deps.setFailedSync(result.message ?? "Sync failed");
        return result;
      }

      accepted += result.accepted ?? batch.length;
    }

    await deps.setSuccessfulSync(syncStartedAt.toISOString());
    return { ok: true, accepted, status: 200 };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    await deps.setFailedSync(message);
    return { ok: false, message };
  }
}

export function runConfiguredSync(): Promise<SyncOutcome> {
  return runBrowserHistorySync();
}

export { MAX_ITEMS_PER_REQUEST, MAX_POST_ATTEMPTS, RETRY_DELAY_MS };
