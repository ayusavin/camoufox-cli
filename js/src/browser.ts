/** Browser manager: launches and manages Camoufox instance. */

import * as fs from "node:fs";
import * as path from "node:path";
import { execFileSync } from "node:child_process";
import { Camoufox, launchOptions } from "camoufox-js";
import { firefox, type Browser, type BrowserContext, type Page } from "playwright-core";
import { RefRegistry } from "./refs.js";
import { readConfig, CAPSOLVER_XPI_PATH, hasCapsolverXpi } from "./config.js";

function ensureBrowserInstalled(): void {
  try {
    execFileSync("npx", ["camoufox-js", "path"], { stdio: "pipe" });
  } catch {
    throw new Error(
      "Browser not found. Run `camoufox-cli install` to download it."
    );
  }
}

/** Copy CapSolver XPI into the Firefox profile's extensions directory. */
function installCapsolverToProfile(profilePath: string): void {
  const cfg = readConfig();
  if (!cfg.capsolver_extension_id || !hasCapsolverXpi()) return;

  const extDir = path.join(profilePath, "extensions");
  fs.mkdirSync(extDir, { recursive: true });
  const destXpi = path.join(extDir, `${cfg.capsolver_extension_id}.xpi`);
  if (!fs.existsSync(destXpi)) {
    fs.copyFileSync(CAPSOLVER_XPI_PATH, destXpi);
  }
}

/**
 * Configure CapSolver API key in the extension after browser launch.
 * Reads the Firefox-assigned UUID from extensions-uuid.json, navigates to
 * the extension's options page, and injects the key via chrome.storage / localStorage.
 */
async function configureCapsolverKey(context: BrowserContext, profilePath: string): Promise<void> {
  const cfg = readConfig();
  if (!cfg.capsolver_api_key || !cfg.capsolver_extension_id) return;

  const uuidMapPath = path.join(profilePath, "extensions-uuid.json");
  if (!fs.existsSync(uuidMapPath)) return; // Extension not yet registered by Firefox

  let uuid: string;
  try {
    const uuidMap = JSON.parse(fs.readFileSync(uuidMapPath, "utf-8"));
    uuid = uuidMap[cfg.capsolver_extension_id];
    if (!uuid) return;
  } catch {
    return;
  }

  const optionsPage = await context.newPage();
  try {
    await optionsPage.goto(`moz-extension://${uuid}/options.html`, {
      timeout: 5000,
      waitUntil: "domcontentloaded",
    });
    await optionsPage.evaluate((key: string) => {
      // Try chrome.storage.local first (CapSolver uses Chrome extension APIs),
      // fall back to localStorage as a secondary mechanism.
      const store =
        (typeof chrome !== "undefined" && (chrome as any)?.storage?.local) ||
        (typeof browser !== "undefined" && (browser as any)?.storage?.local);
      if (store) store.set({ apiKey: key });
      localStorage.setItem("capsolver_apikey", key);
      localStorage.setItem("apiKey", key);
    }, cfg.capsolver_api_key);
  } catch {
    // Options page not found or unavailable — non-fatal, user can configure manually
  } finally {
    try { await optionsPage.close(); } catch {}
  }
}

export class BrowserManager {
  refs = new RefRegistry();
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private page: Page | null = null;
  private persistent: string | null;
  private proxy: string | null;
  private history: string[] = [];
  private historyIndex = -1;

  constructor(persistent: string | null = null, proxy: string | null = null) {
    this.persistent = persistent;
    this.proxy = proxy;
  }

  async launch(headless: boolean = true): Promise<void> {
    if (this.browser || this.context) return;

    ensureBrowserInstalled();

    if (this.proxy) {
      if (!this.proxy.includes("://")) {
        throw new Error(
          `Invalid proxy URL: ${this.proxy}. Expected format: http://host:port`
        );
      }
      const scheme = this.proxy.split("://")[0].toLowerCase();
      if (scheme !== "http" && scheme !== "https") {
        throw new Error(
          `Unsupported proxy scheme: ${scheme}. Only http:// and https:// proxies are supported.`
        );
      }
    }

    const launchOpts: Record<string, unknown> = { headless };
    if (this.proxy) launchOpts.proxy = this.proxy;

    if (this.persistent) {
      installCapsolverToProfile(this.persistent);

      const opts = await launchOptions(launchOpts);
      this.context = await firefox.launchPersistentContext(this.persistent, opts);
      const pages = this.context.pages();
      this.page = pages[0] || await this.context.newPage();

      await configureCapsolverKey(this.context, this.persistent);
    } else {
      this.browser = await Camoufox(launchOpts) as Browser;
      this.page = await this.browser.newPage();
      this.context = this.page.context();
    }
  }

  getPage(): Page {
    if (!this.page) throw new Error("Browser not launched. Send 'open' command first.");
    return this.page;
  }

  getContext(): BrowserContext {
    if (!this.context) throw new Error("Browser not launched. Send 'open' command first.");
    return this.context;
  }

  async getTabsAsync(): Promise<{ index: number; url: string; title: string; active: boolean }[]> {
    const ctx = this.getContext();
    const pages = ctx.pages();
    const tabs = [];
    for (let i = 0; i < pages.length; i++) {
      tabs.push({
        index: i,
        url: pages[i].url(),
        title: await pages[i].title(),
        active: pages[i] === this.page,
      });
    }
    return tabs;
  }

  async switchToTab(index: number): Promise<Page> {
    const ctx = this.getContext();
    const pages = ctx.pages();
    if (index < 0 || index >= pages.length) {
      throw new RangeError(`Tab index ${index} out of range (0-${pages.length - 1})`);
    }
    this.page = pages[index];
    await this.page.bringToFront();
    return this.page;
  }

  async closeCurrentTab(): Promise<void> {
    const ctx = this.getContext();
    const pages = ctx.pages();
    if (pages.length <= 1) {
      throw new Error("Cannot close the last tab. Use 'close' to shut down the browser.");
    }
    const current = this.page!;
    const idx = pages.indexOf(current);
    const newIdx = idx > 0 ? idx - 1 : 1;
    this.page = pages[newIdx];
    await this.page.bringToFront();
    await current.close();
  }

  pushHistory(url: string): void {
    this.history = this.history.slice(0, this.historyIndex + 1);
    this.history.push(url);
    this.historyIndex = this.history.length - 1;
  }

  async goBack(): Promise<string | null> {
    if (this.historyIndex <= 0) return null;
    this.historyIndex--;
    const url = this.history[this.historyIndex];
    await this.getPage().goto(url, { waitUntil: "domcontentloaded" });
    return url;
  }

  async goForward(): Promise<string | null> {
    if (this.historyIndex >= this.history.length - 1) return null;
    this.historyIndex++;
    const url = this.history[this.historyIndex];
    await this.getPage().goto(url, { waitUntil: "domcontentloaded" });
    return url;
  }

  async close(): Promise<void> {
    if (this.browser) {
      try { await this.browser.close(); } catch {}
      this.browser = null;
    }
    if (this.context && !this.browser) {
      // persistent context: close context directly
      try { await this.context.close(); } catch {}
    }
    this.context = null;
    this.page = null;
    this.history = [];
    this.historyIndex = -1;
  }

  get isRunning(): boolean {
    return this.browser !== null || this.context !== null;
  }
}
