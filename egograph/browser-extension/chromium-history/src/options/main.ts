import { getSettings, saveSettings } from "../background/storage.js";
import { isCompleteSettings, type ExtensionSettings, type SyncNowMessage } from "../shared/types.js";

function input(id: string): HTMLInputElement | HTMLSelectElement {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLSelectElement)) {
    throw new Error(`Missing element: ${id}`);
  }
  return element;
}

function setStatus(message: string): void {
  const status = document.getElementById("status");
  if (status) {
    status.textContent = message;
  }
}

function readForm(): Partial<ExtensionSettings> {
  return {
    serverUrl: input("server-url").value.trim(),
    xApiKey: input("x-api-key").value.trim(),
    browserId: input("browser-id").value.trim() as ExtensionSettings["browserId"],
    deviceId: input("device-id").value.trim(),
    profile: input("profile").value.trim()
  };
}

async function hydrateForm(): Promise<void> {
  const settings = await getSettings();
  input("server-url").value = settings.serverUrl ?? "";
  input("x-api-key").value = settings.xApiKey ?? "";
  input("browser-id").value = settings.browserId ?? "";
  input("device-id").value = settings.deviceId ?? "";
  input("profile").value = settings.profile ?? "";
}

async function handleSave(event: Event): Promise<void> {
  event.preventDefault();
  const settings = readForm();
  if (!isCompleteSettings(settings)) {
    setStatus("Please fill all settings.");
    return;
  }
  await saveSettings(settings);
  setStatus("Settings saved.");
}

async function handleSyncNow(): Promise<void> {
  const response = (await chrome.runtime.sendMessage({
    type: "sync-now"
  } satisfies SyncNowMessage)) as { ok?: boolean; message?: string } | undefined;

  if (response?.ok) {
    setStatus("Sync triggered.");
    return;
  }
  setStatus(response?.message ?? "Sync failed.");
}

function bindEvents(): void {
  const form = document.getElementById("settings-form");
  const syncButton = document.getElementById("sync-button");
  if (form) {
    form.addEventListener("submit", (event) => {
      void handleSave(event);
    });
  }
  if (syncButton) {
    syncButton.addEventListener("click", () => {
      void handleSyncNow();
    });
  }
}

void hydrateForm().then(bindEvents);
