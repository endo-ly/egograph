import { runConfiguredSync } from "./sync.js";

type Message = { type?: string };

function registerListeners(): void {
  chrome.runtime.onStartup.addListener(() => {
    void runConfiguredSync();
  });

  chrome.runtime.onMessage.addListener((message: Message, _sender, sendResponse) => {
    if (message?.type !== "sync-now") {
      return false;
    }

    void runConfiguredSync()
      .then((result) => sendResponse(result))
      .catch((error: unknown) =>
        sendResponse({
          ok: false,
          message: error instanceof Error ? error.message : "Unknown error"
        })
      );
    return true;
  });
}

registerListeners();

export { registerListeners };
