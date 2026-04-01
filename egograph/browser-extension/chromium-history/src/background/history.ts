import type { BrowserHistoryPayloadItem } from "../shared/types.js";

const INITIAL_SYNC_LIMIT = 50000;
const VISIT_FETCH_CONCURRENCY = 25;
const INCREMENTAL_SEARCH_PAGE_SIZE = 10000;

export interface HistoryApi {
  search(query: chrome.history.HistoryQuery): Promise<chrome.history.HistoryItem[]>;
  getVisits(details: { url: string }): Promise<chrome.history.VisitItem[]>;
}

function toIsoString(visitTime?: number): string | undefined {
  return typeof visitTime === "number" ? new Date(visitTime).toISOString() : undefined;
}

async function collectVisitsForItem(
  api: HistoryApi,
  item: chrome.history.HistoryItem
): Promise<BrowserHistoryPayloadItem[]> {
  if (!item.url) {
    return [];
  }

  const visits = await api.getVisits({ url: item.url });
  return visits
    .filter((visit) => typeof visit.visitTime === "number")
    .map((visit) => ({
      url: item.url as string,
      title: item.title ?? undefined,
      visit_time: new Date(visit.visitTime as number).toISOString(),
      visit_id: visit.visitId !== undefined ? String(visit.visitId) : undefined,
      referring_visit_id:
        visit.referringVisitId !== undefined ? String(visit.referringVisitId) : undefined,
      transition: visit.transition
    }));
}

async function searchHistoryItems(
  historyApi: HistoryApi,
  startTime: number,
  endTime: number | undefined,
  isInitialSync: boolean
): Promise<chrome.history.HistoryItem[]> {
  if (isInitialSync) {
    return historyApi.search({
      text: "",
      startTime,
      endTime,
      maxResults: INITIAL_SYNC_LIMIT
    });
  }

  const allItems: chrome.history.HistoryItem[] = [];
  let cursorEndTime = endTime;

  while (true) {
    const page = await historyApi.search({
      text: "",
      startTime,
      endTime: cursorEndTime,
      maxResults: INCREMENTAL_SEARCH_PAGE_SIZE
    });
    allItems.push(...page);

    if (page.length < INCREMENTAL_SEARCH_PAGE_SIZE) {
      break;
    }

    const oldestLastVisitTime = page.at(-1)?.lastVisitTime;
    if (typeof oldestLastVisitTime !== "number") {
      break;
    }
    cursorEndTime = oldestLastVisitTime - 1;
  }

  return allItems;
}

async function mapWithConcurrencyLimit<T, TResult>(
  items: readonly T[],
  concurrency: number,
  mapper: (item: T) => Promise<TResult>
): Promise<TResult[]> {
  const results = new Array<TResult>(items.length);
  let nextIndex = 0;

  async function worker(): Promise<void> {
    while (nextIndex < items.length) {
      const currentIndex = nextIndex;
      nextIndex += 1;
      results[currentIndex] = await mapper(items[currentIndex] as T);
    }
  }

  const workerCount = Math.min(concurrency, items.length);
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return results;
}

export async function collectHistoryItems(
  lastSuccessfulSyncAt?: string,
  syncedBeforeAt?: string,
  historyApi?: HistoryApi
): Promise<BrowserHistoryPayloadItem[]> {
  const resolvedHistoryApi = historyApi ?? chrome.history;
  const isInitialSync = !lastSuccessfulSyncAt;
  const startTime = lastSuccessfulSyncAt
    ? new Date(lastSuccessfulSyncAt).getTime()
    : 0;
  const endTime = syncedBeforeAt ? new Date(syncedBeforeAt).getTime() : undefined;

  const historyItems = await searchHistoryItems(
    resolvedHistoryApi,
    startTime,
    endTime,
    isInitialSync
  );

  const collected = await mapWithConcurrencyLimit(
    historyItems,
    VISIT_FETCH_CONCURRENCY,
    (item) => collectVisitsForItem(resolvedHistoryApi, item)
  );

  const flattened = collected
    .flat()
    .filter((item) => {
      if (!lastSuccessfulSyncAt) {
        return !syncedBeforeAt || item.visit_time <= syncedBeforeAt;
      }
      return (
        item.visit_time > lastSuccessfulSyncAt &&
        (!syncedBeforeAt || item.visit_time <= syncedBeforeAt)
      );
    })
    .sort((left, right) => right.visit_time.localeCompare(left.visit_time));

  return isInitialSync ? flattened.slice(0, INITIAL_SYNC_LIMIT) : flattened;
}

export { INCREMENTAL_SEARCH_PAGE_SIZE, INITIAL_SYNC_LIMIT, VISIT_FETCH_CONCURRENCY, toIsoString };
