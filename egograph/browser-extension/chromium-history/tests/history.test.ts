import { describe, expect, it, vi } from "vitest";

import {
  INCREMENTAL_SEARCH_PAGE_SIZE,
  INITIAL_SYNC_LIMIT,
  VISIT_FETCH_CONCURRENCY,
  collectHistoryItems
} from "../src/background/history.js";

function makeHistoryApi(visitCount: number) {
  return {
    async search() {
      return Array.from({ length: visitCount }, (_, index) => ({
        url: `https://example.com/${index}`,
        title: `Example ${index}`,
        visitCount: 1
      })) as chrome.history.HistoryItem[];
    },
    async getVisits({ url }: { url: string }) {
      const index = Number(url?.split("/").pop());
      return [
        {
          visitId: index,
          visitTime: Date.parse(`2026-03-22T12:${String(index % 60).padStart(2, "0")}:00Z`),
          transition: "link"
        }
      ] as chrome.history.VisitItem[];
    }
  };
}

describe("history collection", () => {
  it("caps the first sync to 50000 visits", async () => {
    const items = await collectHistoryItems(
      undefined,
      "2026-03-22T13:00:00.000Z",
      makeHistoryApi(51000)
    );

    expect(items).toHaveLength(INITIAL_SYNC_LIMIT);
  });

  it("filters visits older than the last successful sync", async () => {
    const historyApi = {
      async search() {
        return [
          {
            url: "https://example.com/new",
            title: "New",
            visitCount: 1
          },
          {
            url: "https://example.com/old",
            title: "Old",
            visitCount: 1
          }
        ] as chrome.history.HistoryItem[];
      },
      async getVisits({ url }: { url: string }) {
        if (url?.includes("new")) {
          return [
            {
              visitId: 2,
              visitTime: Date.parse("2026-03-22T12:30:00Z"),
              transition: "link"
            }
          ] as chrome.history.VisitItem[];
        }
        return [
          {
            visitId: 1,
            visitTime: Date.parse("2026-03-22T12:00:00Z"),
            transition: "link"
          }
        ] as chrome.history.VisitItem[];
      }
    };

    const items = await collectHistoryItems(
      "2026-03-22T12:15:00.000Z",
      "2026-03-22T12:40:00.000Z",
      historyApi
    );

    expect(items).toHaveLength(1);
    expect(items[0]?.url).toBe("https://example.com/new");
  });

  it("paginates incremental history queries until the window is drained", async () => {
    const search = vi
      .fn()
      .mockResolvedValueOnce(
        Array.from({ length: INCREMENTAL_SEARCH_PAGE_SIZE }, (_, index) => ({
          url: `https://example.com/${index}`,
          title: `Example ${index}`,
          visitCount: 1,
          lastVisitTime: Date.parse("2026-03-22T12:00:00Z") - index
        }))
      )
      .mockResolvedValueOnce([
        {
          url: "https://example.com/final",
          title: "Final",
          visitCount: 1,
          lastVisitTime: Date.parse("2026-03-22T10:00:00Z")
        }
      ]);
    const getVisits = vi.fn(async ({ url }: { url: string }) => [
      {
        visitId: url.length,
        visitTime: Date.parse("2026-03-22T12:30:00Z"),
        transition: "link"
      }
    ]) as unknown as typeof chrome.history.getVisits;

    const items = await collectHistoryItems(
      "2026-03-22T09:00:00.000Z",
      "2026-03-22T13:00:00.000Z",
      { search, getVisits }
    );

    expect(search).toHaveBeenCalledTimes(2);
    expect(items.length).toBe(INCREMENTAL_SEARCH_PAGE_SIZE + 1);
  });

  it("limits concurrent visit fetches during initial sync", async () => {
    let activeRequests = 0;
    let maxConcurrentRequests = 0;

    const historyApi = {
      async search() {
        return Array.from({ length: VISIT_FETCH_CONCURRENCY + 10 }, (_, index) => ({
          url: `https://example.com/${index}`,
          title: `Example ${index}`,
          visitCount: 1
        })) as chrome.history.HistoryItem[];
      },
      async getVisits({ url }: { url: string }) {
        activeRequests += 1;
        maxConcurrentRequests = Math.max(maxConcurrentRequests, activeRequests);

        await new Promise((resolve) => setTimeout(resolve, 0));

        activeRequests -= 1;
        return [
          {
            visitId: Number(url?.split("/").pop()),
            visitTime: Date.parse("2026-03-22T12:30:00Z"),
            transition: "link"
          }
        ] as chrome.history.VisitItem[];
      }
    };

    await collectHistoryItems(undefined, "2026-03-22T13:00:00.000Z", historyApi);

    expect(maxConcurrentRequests).toBeLessThanOrEqual(VISIT_FETCH_CONCURRENCY);
  });
});
