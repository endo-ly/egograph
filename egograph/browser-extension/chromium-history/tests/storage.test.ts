import { describe, expect, it } from "vitest";

import {
  getLastSuccessfulSyncAt,
  getSettings,
  saveSettings,
  setSuccessfulSync
} from "../src/background/storage.js";
import type { ExtensionSettings } from "../src/shared/types.js";

function createStorageArea() {
  const state: Record<string, unknown> = {};
  return {
    async get(key: string) {
      return { [key]: state[key] };
    },
    async set(value: Record<string, unknown>) {
      Object.assign(state, value);
    }
  } as chrome.storage.StorageArea;
}

describe("storage", () => {
  it("reads and writes settings", async () => {
    const storage = createStorageArea();
    const settings: ExtensionSettings = {
      serverUrl: "https://example.com",
      xApiKey: "secret",
      browserId: "edge",
      deviceId: "device-1",
      profile: "Default"
    };

    await saveSettings(settings, storage);
    await expect(getSettings(storage)).resolves.toEqual(settings);
  });

  it("returns the last successful sync cursor", async () => {
    const storage = createStorageArea();

    await setSuccessfulSync("2026-03-22T12:00:00.000Z", storage);

    await expect(getLastSuccessfulSyncAt(storage)).resolves.toBe(
      "2026-03-22T12:00:00.000Z"
    );
  });
});
