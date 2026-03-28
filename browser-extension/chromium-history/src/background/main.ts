import { runConfiguredSync } from "./sync.js";

type Message = { type?: string };
const STARTUP_SYNC_ALARM = "startup-sync";
const STARTUP_SYNC_DELAY_MINUTES = 1;

function scheduleStartupSync(): void {
  chrome.alarms.create(STARTUP_SYNC_ALARM, {
    delayInMinutes: STARTUP_SYNC_DELAY_MINUTES
  });
}

function registerListeners(): void {
  chrome.runtime.onStartup.addListener(() => {
    scheduleStartupSync();
  });

  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name !== STARTUP_SYNC_ALARM) {
      return;
    }
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

export { STARTUP_SYNC_ALARM, STARTUP_SYNC_DELAY_MINUTES, registerListeners };
