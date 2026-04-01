import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  MAX_POST_ATTEMPTS,
  MAX_ITEMS_PER_REQUEST,
  RETRY_DELAY_MS,
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
      now: () => new Date("2026-03-22T12:30:00.000Z"),
      sleep: vi.fn()
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
      now: () => new Date("2026-03-22T12:30:00.000Z"),
      sleep: vi.fn()
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
      now: () => new Date("2026-03-22T12:30:00.000Z"),
      sleep: vi.fn()
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
      now: () => new Date("2026-03-22T12:30:00.000Z"),
      sleep: vi.fn()
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
      now: () => new Date("2026-03-22T12:30:00.000Z"),
      sleep: vi.fn()
    });

    expect(postBrowserHistory).toHaveBeenCalledTimes(2);
    expect(setSuccessfulSync).toHaveBeenCalledWith("2026-03-22T12:30:00.000Z");
    expect(result.ok).toBe(true);
  });

  it("startup and sync-now share the same sync function", async () => {
    const startupAddListener = vi.fn();
    const alarmAddListener = vi.fn();
    const createAlarm = vi.fn();
    const messageAddListener = vi.fn();
    const runConfiguredSync = vi.fn().mockResolvedValue(undefined);

    vi.doMock("../src/background/sync.js", () => ({
      runConfiguredSync
    }));

    globalThis.chrome = {
      alarms: {
        create: createAlarm,
        onAlarm: { addListener: alarmAddListener }
      },
      runtime: {
        onStartup: { addListener: startupAddListener },
        onMessage: { addListener: messageAddListener }
      }
    } as unknown as typeof chrome;

    await import("../src/background/main.js");

    expect(startupAddListener).toHaveBeenCalledOnce();
    expect(alarmAddListener).toHaveBeenCalledOnce();
    expect(messageAddListener).toHaveBeenCalledOnce();
  });

  it("retries failed fetches before succeeding", async () => {
    const postBrowserHistory = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, message: "Failed to fetch" })
      .mockResolvedValueOnce({ ok: false, message: "Failed to fetch" })
      .mockResolvedValueOnce({ ok: true, accepted: 1, status: 200 });
    const sleep = vi.fn();
    const setSuccessfulSync = vi.fn();

    const result = await runBrowserHistorySync({
      getSettings: async () => completeSettings,
      getLastSuccessfulSyncAt: async () => "2026-03-22T11:00:00.000Z",
      collectHistoryItems: async () => [
        {
          url: "https://example.com",
          visit_time: "2026-03-22T12:00:00.000Z"
        }
      ],
      postBrowserHistory,
      setSuccessfulSync,
      setFailedSync: vi.fn(),
      createSyncId: () => "sync-1",
      now: () => new Date("2026-03-22T12:30:00.000Z"),
      sleep
    });

    expect(result.ok).toBe(true);
    expect(postBrowserHistory).toHaveBeenCalledTimes(3);
    expect(sleep).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenNthCalledWith(1, RETRY_DELAY_MS);
    expect(sleep).toHaveBeenNthCalledWith(2, RETRY_DELAY_MS);
    expect(setSuccessfulSync).toHaveBeenCalledOnce();
  });

  it("stops retrying after the max failed fetch attempts", async () => {
    const setFailedSync = vi.fn();
    const postBrowserHistory = vi
      .fn()
      .mockResolvedValue({ ok: false, message: "Failed to fetch" });
    const sleep = vi.fn();

    const result = await runBrowserHistorySync({
      getSettings: async () => completeSettings,
      getLastSuccessfulSyncAt: async () => "2026-03-22T11:00:00.000Z",
      collectHistoryItems: async () => [
        {
          url: "https://example.com",
          visit_time: "2026-03-22T12:00:00.000Z"
        }
      ],
      postBrowserHistory,
      setSuccessfulSync: vi.fn(),
      setFailedSync,
      createSyncId: () => "sync-1",
      now: () => new Date("2026-03-22T12:30:00.000Z"),
      sleep
    });

    expect(result).toEqual({ ok: false, message: "Failed to fetch" });
    expect(postBrowserHistory).toHaveBeenCalledTimes(MAX_POST_ATTEMPTS);
    expect(sleep).toHaveBeenCalledTimes(MAX_POST_ATTEMPTS - 1);
    expect(setFailedSync).toHaveBeenCalledWith("Failed to fetch");
  });
});
