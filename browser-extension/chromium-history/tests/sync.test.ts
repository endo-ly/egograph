import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  MAX_ITEMS_PER_REQUEST,
  runBrowserHistorySync
} from "../src/background/sync.js";

const completeSettings = {
  serverUrl: "https://example.com",
  xApiKey: "secret",
  browserId: "edge" as const,
  deviceId: "device-1",
  profile: "Default"
};

describe("sync", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("advances the cursor on successful sync", async () => {
    const setSuccessfulSync = vi.fn();
    const setFailedSync = vi.fn();

    const result = await runBrowserHistorySync({
      getSettings: async () => completeSettings,
      getLastSuccessfulSyncAt: async () => "2026-03-22T11:00:00.000Z",
      collectHistoryItems: async () => [
        {
          url: "https://example.com",
          visit_time: "2026-03-22T12:00:00.000Z"
        }
      ],
      postBrowserHistory: async () => ({ ok: true, accepted: 1, status: 200 }),
      setSuccessfulSync,
      setFailedSync,
      createSyncId: () => "sync-1",
      now: () => new Date("2026-03-22T12:30:00.000Z")
    });

    expect(result.ok).toBe(true);
    expect(setSuccessfulSync).toHaveBeenCalledWith("2026-03-22T12:30:00.000Z");
    expect(setFailedSync).not.toHaveBeenCalled();
  });

  it("does not advance the cursor when the API call fails", async () => {
    const setSuccessfulSync = vi.fn();
    const setFailedSync = vi.fn();

    const result = await runBrowserHistorySync({
      getSettings: async () => completeSettings,
      getLastSuccessfulSyncAt: async () => "2026-03-22T11:00:00.000Z",
      collectHistoryItems: async () => [],
      postBrowserHistory: async () => ({
        ok: false,
        status: 500,
        message: "server failed"
      }),
      setSuccessfulSync,
      setFailedSync,
      createSyncId: () => "sync-1",
      now: () => new Date("2026-03-22T12:30:00.000Z")
    });

    expect(result.ok).toBe(false);
    expect(setSuccessfulSync).not.toHaveBeenCalled();
    expect(setFailedSync).toHaveBeenCalledWith("server failed");
  });

  it("skips sync when settings are incomplete", async () => {
    const result = await runBrowserHistorySync({
      getSettings: async () => ({ serverUrl: "https://example.com" }),
      getLastSuccessfulSyncAt: async () => undefined,
      collectHistoryItems: async () => [],
      postBrowserHistory: async () => ({ ok: true }),
      setSuccessfulSync: vi.fn(),
      setFailedSync: vi.fn(),
      createSyncId: () => "sync-1",
      now: () => new Date("2026-03-22T12:30:00.000Z")
    });

    expect(result).toEqual({ ok: false, message: "Incomplete settings" });
  });

  it("records thrown failures in sync status", async () => {
    const setFailedSync = vi.fn();

    const result = await runBrowserHistorySync({
      getSettings: async () => completeSettings,
      getLastSuccessfulSyncAt: async () => "2026-03-22T11:00:00.000Z",
      collectHistoryItems: async () => {
        throw new Error("network down");
      },
      postBrowserHistory: async () => ({ ok: true, accepted: 1, status: 200 }),
      setSuccessfulSync: vi.fn(),
      setFailedSync,
      createSyncId: () => "sync-1",
      now: () => new Date("2026-03-22T12:30:00.000Z")
    });

    expect(result).toEqual({ ok: false, message: "network down" });
    expect(setFailedSync).toHaveBeenCalledWith("network down");
  });

  it("sends large syncs in bounded chunks before advancing the cursor", async () => {
    const postBrowserHistory = vi.fn(async () => ({
      ok: true,
      accepted: MAX_ITEMS_PER_REQUEST,
      status: 200
    }));
    const setSuccessfulSync = vi.fn();

    const items = Array.from({ length: MAX_ITEMS_PER_REQUEST + 1 }, (_, index) => ({
      url: `https://example.com/${index}`,
      visit_time: "2026-03-22T12:00:00.000Z"
    }));

    const result = await runBrowserHistorySync({
      getSettings: async () => completeSettings,
      getLastSuccessfulSyncAt: async () => "2026-03-22T11:00:00.000Z",
      collectHistoryItems: async () => items,
      postBrowserHistory,
      setSuccessfulSync,
      setFailedSync: vi.fn(),
      createSyncId: () => "sync-1",
      now: () => new Date("2026-03-22T12:30:00.000Z")
    });

    expect(postBrowserHistory).toHaveBeenCalledTimes(2);
    expect(setSuccessfulSync).toHaveBeenCalledWith("2026-03-22T12:30:00.000Z");
    expect(result.ok).toBe(true);
  });

  it("startup and sync-now share the same sync function", async () => {
    const startupAddListener = vi.fn();
    const messageAddListener = vi.fn();
    const runConfiguredSync = vi.fn().mockResolvedValue(undefined);

    vi.doMock("../src/background/sync.js", () => ({
      runConfiguredSync
    }));

    globalThis.chrome = {
      runtime: {
        onStartup: { addListener: startupAddListener },
        onMessage: { addListener: messageAddListener }
      }
    } as unknown as typeof chrome;

    await import("../src/background/main.js");

    expect(startupAddListener).toHaveBeenCalledOnce();
    expect(messageAddListener).toHaveBeenCalledOnce();
  });
});
