/** Turnstile background checker: detects and clicks Cloudflare Turnstile checkbox. */

import type { BrowserManager } from "./browser.js";

export async function checkTurnstile(manager: BrowserManager): Promise<boolean> {
  if (!manager.isRunning) return false;
  try {
    const page = manager.getPage();
    const frame = page.frameLocator('iframe[src*="challenges.cloudflare.com"]');
    await frame.locator(".ctp-checkbox-container").click({ timeout: 500 });
    return true;
  } catch {
    return false; // No Turnstile present — this is normal
  }
}
