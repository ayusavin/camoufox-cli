"""Browser manager: launches and manages Camoufox instance."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from camoufox.sync_api import Camoufox
from playwright.sync_api import BrowserContext, Page, Request, Response

from .config import CAPSOLVER_XPI_PATH, has_capsolver_xpi, read_config
from .refs import RefRegistry

_MAX_REQUEST_BUFFER = 500


def _ensure_browser_installed() -> None:
    """Check that the Camoufox browser binary is installed, raise if not."""
    try:
        from camoufox.pkgman import get_path
        get_path("camoufox")
    except Exception:
        raise RuntimeError(
            "Browser not found. Run `camoufox-cli install` to download it."
        )


def _install_capsolver_to_profile(profile_path: str) -> None:
    """Copy CapSolver XPI into the Firefox profile's extensions directory."""
    cfg = read_config()
    if not cfg.get("capsolver_extension_id") or not has_capsolver_xpi():
        return

    ext_dir = Path(profile_path) / "extensions"
    ext_dir.mkdir(parents=True, exist_ok=True)
    dest_xpi = ext_dir / f"{cfg['capsolver_extension_id']}.xpi"
    if not dest_xpi.exists():
        shutil.copy2(str(CAPSOLVER_XPI_PATH), str(dest_xpi))


def _configure_capsolver_key(context: BrowserContext, profile_path: str) -> None:
    """
    Configure CapSolver API key in the extension after browser launch.
    Reads the Firefox-assigned UUID from extensions-uuid.json, navigates to
    the extension's options page, and injects the key via chrome.storage / localStorage.
    """
    cfg = read_config()
    if not cfg.get("capsolver_api_key") or not cfg.get("capsolver_extension_id"):
        return

    uuid_map_path = os.path.join(profile_path, "extensions-uuid.json")
    if not os.path.exists(uuid_map_path):
        return  # Extension not yet registered by Firefox

    try:
        with open(uuid_map_path) as f:
            uuid_map = json.load(f)
        uuid = uuid_map.get(cfg["capsolver_extension_id"])
        if not uuid:
            return
    except Exception:
        return

    page = context.new_page()
    try:
        page.goto(
            f"moz-extension://{uuid}/options.html",
            timeout=5000,
            wait_until="domcontentloaded",
        )
        # Inject the API key via chrome.storage and localStorage (both used by CapSolver)
        page.evaluate(
            """(key) => {
                const store =
                    (typeof chrome !== 'undefined' && chrome?.storage?.local) ||
                    (typeof browser !== 'undefined' && browser?.storage?.local);
                if (store) store.set({ apiKey: key });
                localStorage.setItem('capsolver_apikey', key);
                localStorage.setItem('apiKey', key);
            }""",
            cfg["capsolver_api_key"],
        )
    except Exception:
        # Options page not found or unavailable — non-fatal, user can configure manually
        pass
    finally:
        try:
            page.close()
        except Exception:
            pass


class BrowserManager:
    def __init__(self, persistent: str | None = None, proxy: str | None = None):
        self._camoufox: Camoufox | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self.refs = RefRegistry()
        self._headless: bool = True
        self._persistent = persistent
        self._proxy = proxy
        # Camoufox spoofs history API for anti-fingerprinting,
        # so we track navigation history ourselves.
        self._history: list[str] = []
        self._history_index: int = -1
        # Network capture
        self._request_buffer: list[dict] = []
        self._pending_requests: dict[int, tuple[Request, dict]] = {}
        self._request_counter: int = 0

    def _on_request(self, request: Request) -> None:
        entry: dict = {
            "id": self._request_counter,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "url": request.url,
            "resourceType": request.resource_type,
            "requestHeaders": dict(request.headers),
            "requestBody": request.post_data,
        }
        self._request_counter += 1
        self._pending_requests[id(request)] = (request, entry)
        self._request_buffer.append(entry)
        if len(self._request_buffer) > _MAX_REQUEST_BUFFER:
            self._request_buffer.pop(0)

    def _on_response(self, response: Response) -> None:
        key = id(response.request)
        pair = self._pending_requests.pop(key, None)
        if pair:
            _, entry = pair
            entry["status"] = response.status
            entry["statusText"] = response.status_text
            entry["responseHeaders"] = dict(response.headers)

    def _setup_network_capture(self, context: BrowserContext) -> None:
        context.on("request", self._on_request)
        context.on("response", self._on_response)

    def get_requests(self, filter_str: str | None = None, n: int | None = None) -> list[dict]:
        result = [r for r in self._request_buffer if filter_str is None or filter_str in r["url"]]
        if n is not None and n > 0:
            result = result[-n:]
        return result

    def clear_requests(self) -> None:
        self._request_buffer.clear()
        self._pending_requests.clear()

    def launch(self, headless: bool = True) -> None:
        if self._camoufox is not None:
            return
        self._headless = headless

        _ensure_browser_installed()

        kwargs: dict = {"headless": headless}
        if self._proxy:
            parsed = urlparse(self._proxy)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"Unsupported proxy scheme: {parsed.scheme}. Only http:// and https:// proxies are supported."
                )
            if not parsed.hostname:
                raise ValueError(
                    f"Invalid proxy URL: {self._proxy}. Expected format: http://host:port"
                )
            host_port = parsed.hostname
            if parsed.port:
                host_port += f":{parsed.port}"
            proxy: dict = {"server": f"{parsed.scheme}://{host_port}"}
            if parsed.username:
                proxy["username"] = parsed.username
            if parsed.password:
                proxy["password"] = parsed.password
            kwargs["proxy"] = proxy
        if self._persistent:
            _install_capsolver_to_profile(self._persistent)
            kwargs["persistent_context"] = True
            kwargs["user_data_dir"] = self._persistent

        self._camoufox = Camoufox(**kwargs)
        result = self._camoufox.__enter__()

        if self._persistent:
            # persistent_context returns BrowserContext directly
            self._context = result
            pages = self._context.pages
            self._page = pages[0] if pages else self._context.new_page()

            _configure_capsolver_key(self._context, self._persistent)
        else:
            # Normal mode: result is Browser, new_page() creates default context + page
            self._page = result.new_page()
            self._context = self._page.context

        self._setup_network_capture(self._context)

    def get_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not launched. Send 'open' command first.")
        return self._page

    def get_context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser not launched. Send 'open' command first.")
        return self._context

    def get_tabs(self) -> list[dict]:
        ctx = self.get_context()
        tabs = []
        for i, p in enumerate(ctx.pages):
            tabs.append({
                "index": i,
                "url": p.url,
                "title": p.title(),
                "active": p is self._page,
            })
        return tabs

    def switch_to_tab(self, index: int) -> Page:
        ctx = self.get_context()
        pages = ctx.pages
        if index < 0 or index >= len(pages):
            raise IndexError(f"Tab index {index} out of range (0-{len(pages) - 1})")
        self._page = pages[index]
        self._page.bring_to_front()
        return self._page

    def close_current_tab(self) -> None:
        ctx = self.get_context()
        pages = ctx.pages
        if len(pages) <= 1:
            raise RuntimeError("Cannot close the last tab. Use 'close' to shut down the browser.")
        current = self._page
        # Switch to another tab before closing
        idx = pages.index(current)
        new_idx = idx - 1 if idx > 0 else 1
        self._page = pages[new_idx]
        self._page.bring_to_front()
        current.close()

    def push_history(self, url: str) -> None:
        """Record a URL in our navigation history."""
        # Truncate forward history when navigating to a new page
        self._history = self._history[:self._history_index + 1]
        self._history.append(url)
        self._history_index = len(self._history) - 1

    def go_back(self) -> str | None:
        """Go back in history. Returns the URL or None if at start."""
        if self._history_index <= 0:
            return None
        self._history_index -= 1
        url = self._history[self._history_index]
        self.get_page().goto(url, wait_until="domcontentloaded")
        return url

    def go_forward(self) -> str | None:
        """Go forward in history. Returns the URL or None if at end."""
        if self._history_index >= len(self._history) - 1:
            return None
        self._history_index += 1
        url = self._history[self._history_index]
        self.get_page().goto(url, wait_until="domcontentloaded")
        return url

    def close(self) -> None:
        if self._camoufox is not None:
            try:
                self._camoufox.__exit__(None, None, None)
            except Exception:
                pass
            self._camoufox = None
            self._context = None
            self._page = None
            self._history.clear()
            self._history_index = -1
            self._request_buffer.clear()
            self._pending_requests.clear()

    @property
    def is_running(self) -> bool:
        return self._camoufox is not None
