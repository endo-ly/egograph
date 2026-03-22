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
}

const MAX_ITEMS_PER_REQUEST = 1000;

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
  now: () => new Date()
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
      const result = await deps.postBrowserHistory(
        settings.serverUrl,
        settings.xApiKey,
        payload
      );

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

export { MAX_ITEMS_PER_REQUEST };
