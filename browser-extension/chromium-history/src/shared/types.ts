export type BrowserId = "edge" | "brave" | "chrome";
const VALID_BROWSER_IDS: readonly BrowserId[] = ["edge", "brave", "chrome"];

export interface DraftExtensionSettings {
  serverUrl: string;
  xApiKey: string;
  browserId: BrowserId | "";
  deviceId: string;
  profile: string;
}

export interface ExtensionSettings {
  serverUrl: string;
  xApiKey: string;
  browserId: BrowserId;
  deviceId: string;
  profile: string;
}

export interface BrowserHistoryPayloadItem {
  url: string;
  title?: string;
  visit_time: string;
  visit_id?: string;
  referring_visit_id?: string;
  transition?: string;
  visit_count?: number;
}

export interface BrowserHistoryPayload {
  sync_id: string;
  source_device: string;
  browser: BrowserId;
  profile: string;
  synced_at: string;
  items: BrowserHistoryPayloadItem[];
}

export interface SyncOutcome {
  ok: boolean;
  accepted?: number;
  status?: number;
  message?: string;
}

export interface SyncStatus {
  lastSuccessfulSyncAt?: string;
  lastAttemptedSyncAt?: string;
  lastResult?: "success" | "error";
  lastErrorMessage?: string;
}

export interface SyncNowMessage {
  type: "sync-now";
}

export function isCompleteSettings(
  settings: Partial<DraftExtensionSettings>
): settings is ExtensionSettings {
  return (
    typeof settings.serverUrl === "string" &&
    settings.serverUrl.length > 0 &&
    typeof settings.xApiKey === "string" &&
    settings.xApiKey.length > 0 &&
    typeof settings.deviceId === "string" &&
    settings.deviceId.length > 0 &&
    typeof settings.profile === "string" &&
    settings.profile.length > 0 &&
    typeof settings.browserId === "string" &&
    VALID_BROWSER_IDS.includes(settings.browserId as BrowserId)
  );
}
