#!/usr/bin/env python3
"""
WQT Staging Smoke Test
Run before promoting staging to production.
Exit 0 = all critical tests pass. Exit 1 = one or more failures.

Usage:
    python scripts/test_staging.py                          # test staging (default)
    python scripts/test_staging.py --env production         # test production
    python scripts/test_staging.py --api-url http://localhost:8080  # custom URL
    python scripts/test_staging.py --skip-browser           # skip Playwright tests
    python scripts/test_staging.py --verbose                # show response details
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

# ── Defaults ────────────────────────────────────────────────

ENVS = {
    "staging": {
        "api": "https://www.ai5000days.com/staging",
        "admin": "http://admin-test.ai5000days.com",
        "enterprise": "https://www.ai5000days.com/staging/enterprise/",
    },
    "production": {
        "api": "https://www.ai5000days.com",
        "admin": "http://admin.ai5000days.com",
        "enterprise": "https://www.ai5000days.com/enterprise/",
    },
}

DEFAULT_DEV_KEY = "sj0127wqt"
DEFAULT_TIMEOUT = 30  # seconds per request (generous for proxy/VPN setups)


# ── Data Structures ─────────────────────────────────────────

@dataclass
class TestResult:
    name: str
    category: str       # health, auth, flow, page
    status: str         # PASS, FAIL, SKIP
    duration_ms: float
    detail: str = ""
    critical: bool = True


@dataclass
class Ctx:
    api_url: str
    admin_url: str
    enterprise_url: str
    dev_key: str
    timeout: int = DEFAULT_TIMEOUT
    verbose: bool = False
    no_proxy: bool = False
    token: Optional[str] = None
    session_id: Optional[int] = None
    results: list = field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────

def _get_proxies(ctx: Ctx):
    """Return proxy settings. If --no-proxy, bypass system proxy."""
    if ctx.no_proxy:
        return {"http": None, "https": None}
    return None  # use system default


def api(ctx: Ctx, method: str, path: str, **kwargs):
    url = f"{ctx.api_url}{path}"
    headers = kwargs.pop("headers", {})
    if ctx.token:
        headers["Authorization"] = f"Bearer {ctx.token}"
    proxies = _get_proxies(ctx)
    if proxies:
        kwargs["proxies"] = proxies
    resp = getattr(requests, method)(url, headers=headers, timeout=ctx.timeout, **kwargs)
    if ctx.verbose:
        print(f"    {method.upper()} {path} → {resp.status_code}")
    return resp


def run_test(ctx: Ctx, name: str, category: str, critical: bool, fn):
    start = time.time()
    try:
        detail = fn(ctx)
        elapsed = (time.time() - start) * 1000
        ctx.results.append(TestResult(name, category, "PASS", elapsed, detail or "", critical))
    except AssertionError as e:
        elapsed = (time.time() - start) * 1000
        ctx.results.append(TestResult(name, category, "FAIL", elapsed, str(e), critical))
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        ctx.results.append(TestResult(name, category, "FAIL", elapsed, f"Exception: {e}", critical))


# ── Tier 1: Health (no auth) ────────────────────────────────

def test_settings(ctx):
    """Also serves as the server-alive check (first request)."""
    # Retry once on connection error (network warmup through proxy/VPN)
    for attempt in range(2):
        try:
            r = api(ctx, "get", "/api/settings")
            break
        except requests.exceptions.ConnectionError:
            if attempt == 0:
                time.sleep(1)
                continue
            raise
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data.get("ok") is True, f"Response ok != true"
    return f"{len(data.get('settings', {}))} settings"


def test_public_cards(ctx):
    r = api(ctx, "get", "/api/cards")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    cards = data.get("cards", [])
    assert len(cards) > 0, "Cards array is empty"
    first = cards[0]
    for f in ["key", "safetyType", "event", "options"]:
        assert f in first, f"Card missing field: {f}"
    return f"{len(cards)} cards, structure valid"


def test_card_groups(ctx):
    r = api(ctx, "get", "/api/card-groups")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    groups = data.get("groups", [])
    assert len(groups) > 0, "No card groups found"
    has_default = any(g.get("is_default") for g in groups)
    assert has_default, "No default card group"
    return f"{len(groups)} groups, default exists"


def test_auth_endpoint_exists(ctx):
    r = api(ctx, "post", "/api/auth/login", json={})
    assert r.status_code in (400, 401), f"Expected 400/401, got {r.status_code} (endpoint missing?)"
    return f"Status {r.status_code} (correct rejection)"


def test_static_index(ctx):
    proxies = _get_proxies(ctx)
    kwargs = {"timeout": ctx.timeout}
    if proxies:
        kwargs["proxies"] = proxies
    r = requests.get(f"{ctx.api_url}/", **kwargs)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "<title>" in r.text.lower() or "<title>" in r.text, "No <title> tag found"
    return f"Status 200, HTML present"


# ── Tier 2: Auth + Admin ────────────────────────────────────

def test_dev_login(ctx):
    proxies = _get_proxies(ctx)
    kwargs = {"json": {"key": ctx.dev_key}, "timeout": ctx.timeout}
    if proxies:
        kwargs["proxies"] = proxies
    r = requests.post(f"{ctx.api_url}/api/auth/dev-login", **kwargs)
    assert r.status_code == 200, f"Dev login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert "token" in data, "No token in response"
    user = data.get("user", {})
    assert user.get("role") == "boss", f"Expected role=boss, got {user.get('role')}"
    ctx.token = data["token"]
    return f"Logged in as {user.get('username')}"


def test_get_me(ctx):
    r = api(ctx, "get", "/api/me")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    user = r.json().get("user", {})
    assert user.get("role") == "boss", f"role={user.get('role')}"
    return f"user.id={user.get('id')}, role=boss"


def test_admin_cards(ctx):
    r = api(ctx, "get", "/api/admin/cards")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    cards = data if isinstance(data, list) else data.get("cards", [])
    return f"{len(cards)} cards"


def test_admin_card_groups(ctx):
    r = api(ctx, "get", "/api/admin/card-groups")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    return "OK"


def test_admin_activities(ctx):
    r = api(ctx, "get", "/api/admin/activities")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    return "OK"


# ── Tier 3: Game Flow ───────────────────────────────────────

def test_game_start(ctx):
    r = api(ctx, "post", "/api/game/start", json={
        "ts": int(time.time() * 1000),
        "location": "__SMOKE_TEST__",
        "mode": "standard",
        "players": [{"name": "SmokeTest", "role": "watcher"}],
    })
    assert r.status_code == 200, f"Game start failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert data.get("ok") is True, f"ok != true"
    ctx.session_id = data.get("sessionId")
    assert ctx.session_id, "No sessionId returned"
    return f"Session {ctx.session_id}"


def test_game_event(ctx):
    assert ctx.session_id, "No session (game start failed)"
    r = api(ctx, "post", "/api/game/event", json={
        "sessionId": ctx.session_id,
        "type": "card_choice",
        "payload": {"cardKey": "SMOKE_TEST_CARD", "choice": "A"},
    })
    assert r.status_code == 200, f"Event failed: {r.status_code}"
    assert r.json().get("ok") is True
    return "Event recorded"


def test_game_finish(ctx):
    assert ctx.session_id, "No session (game start failed)"
    r = api(ctx, "post", "/api/game/finish", json={
        "sessionId": ctx.session_id,
        "endedAt": int(time.time() * 1000),
        "finalScore": 0,
        "payload": {"smokeTest": True},
    })
    assert r.status_code == 200, f"Finish failed: {r.status_code}"
    assert r.json().get("ok") is True
    return "Session finished"


def test_last_session(ctx):
    r = api(ctx, "get", "/api/game/last-session")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    session = r.json().get("session")
    assert session, "No session returned"
    return f"Session {session.get('id')}"


# ── Tier 4: Browser Page Loads ──────────────────────────────

def run_browser_tests(ctx):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        ctx.results.append(TestResult(
            "Browser tests", "page", "SKIP", 0,
            "playwright not installed (pip install playwright && playwright install chromium)",
            critical=False,
        ))
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        js_errors = []
        page.on("console", lambda msg: js_errors.append(msg.text) if msg.type == "error" else None)

        # Main page
        def _main_page(c):
            js_errors.clear()
            page.goto(c.api_url + "/", wait_until="networkidle", timeout=15000)
            title = page.title()
            assert title, "Page has no title"
            body = page.inner_text("body")
            assert len(body) > 50, "Page body suspiciously short"
            warn = f" ({len(js_errors)} JS errors)" if js_errors else ""
            return f"Title: {title}{warn}"

        run_test(ctx, "Main page loads", "page", True, _main_page)

        # Profile page
        def _profile_page(c):
            page.goto(c.api_url + "/complete-profile.html", wait_until="networkidle", timeout=15000)
            assert page.query_selector("form") or page.query_selector("input"), "No form/input found"
            return "Form elements present"

        run_test(ctx, "Profile page loads", "page", False, _profile_page)

        # Admin panel (Streamlit loads asynchronously via JS)
        def _admin_page(c):
            page.goto(c.admin_url, wait_until="domcontentloaded", timeout=30000)
            # Streamlit serves an HTML shell, then renders via JS
            html = page.content()
            is_streamlit = "streamlit" in html.lower() or "stApp" in html
            assert page.url and (is_streamlit or len(html) > 500), \
                "Admin page did not load (no Streamlit markers or content)"
            return "Streamlit shell loaded"

        run_test(ctx, "Admin panel loads", "page", True, _admin_page)

        # Enterprise panel
        def _enterprise_page(c):
            page.goto(c.enterprise_url, wait_until="networkidle", timeout=15000)
            body = page.inner_text("body")
            assert len(body) > 10, "Enterprise page body too short"
            return "Vue app loaded"

        run_test(ctx, "Enterprise panel loads", "page", False, _enterprise_page)

        browser.close()


# ── Cleanup ──────────────────────────────────────────────────

def cleanup_smoke_data(ctx):
    """Delete smoke test sessions and events via direct DB on the server.
    Called via SSH since there's no delete-session API endpoint."""
    import subprocess

    if not ctx.session_id:
        print("  No smoke test session to clean up.")
        return

    ssh_key = "C:/Users/BibbTwigs/.ssh/id_rsa_antigravity"
    host = "root@8.210.121.92"
    db_path = "/home/admin/app/scoring_system/data/wqt.db"

    sql = (
        f"DELETE FROM game_events WHERE session_id = {ctx.session_id}; "
        f"DELETE FROM game_sessions WHERE id = {ctx.session_id} AND location = '__SMOKE_TEST__';"
    )

    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-i", ssh_key, host,
        f'sqlite3 "{db_path}" "{sql}"'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print(f"  Cleaned up smoke test session {ctx.session_id}")
        else:
            print(f"  Cleanup warning: {result.stderr.strip()}")
    except Exception as e:
        print(f"  Cleanup failed: {e}")


# ── Output ───────────────────────────────────────────────────

def print_results(ctx):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    sep = "=" * 64

    print(f"\n{sep}")
    print(f"  WQT Staging Smoke Test Results")
    print(f"  Target: {ctx.api_url}")
    print(f"  Time:   {now}")
    print(sep)

    # Column widths
    print(f"  {'#':>3}  {'Category':<8}  {'Test':<28}  {'Status':<6}  {'Time':>7}  Detail")
    print(f"  {'─'*3}  {'─'*8}  {'─'*28}  {'─'*6}  {'─'*7}  {'─'*20}")

    for i, r in enumerate(ctx.results, 1):
        t = f"{r.duration_ms:.0f}ms" if r.duration_ms < 1000 else f"{r.duration_ms/1000:.1f}s"
        detail = r.detail[:40] if r.detail else ""
        status_display = r.status
        print(f"  {i:>3}  {r.category:<8}  {r.name:<28}  {status_display:<6}  {t:>7}  {detail}")

    print(sep)

    passed = sum(1 for r in ctx.results if r.status == "PASS")
    failed = sum(1 for r in ctx.results if r.status == "FAIL")
    skipped = sum(1 for r in ctx.results if r.status == "SKIP")
    total = len(ctx.results)

    print(f"  SUMMARY: {passed}/{total} passed ({failed} failed, {skipped} skipped)")

    critical_failures = [r for r in ctx.results if r.status == "FAIL" and r.critical]
    if critical_failures:
        print(f"  CRITICAL FAILURES:")
        for r in critical_failures:
            print(f"     - {r.name}: {r.detail[:60]}")
        print(f"  NOT READY FOR PRODUCTION")
    else:
        non_critical_failures = [r for r in ctx.results if r.status == "FAIL" and not r.critical]
        if non_critical_failures:
            print(f"  NON-CRITICAL FAILURES:")
            for r in non_critical_failures:
                print(f"     - {r.name}: {r.detail[:60]}")
        print(f"  READY TO PROMOTE TO PRODUCTION")

    print(sep)


def all_critical_passed(ctx):
    return all(r.status != "FAIL" for r in ctx.results if r.critical)


# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WQT Staging Smoke Test")
    parser.add_argument("--env", choices=["staging", "production"], default="staging",
                        help="Target environment (default: staging)")
    parser.add_argument("--api-url", help="Override API base URL")
    parser.add_argument("--admin-url", help="Override admin panel URL")
    parser.add_argument("--dev-key", default=DEFAULT_DEV_KEY, help="Dev login key")
    parser.add_argument("--skip-browser", action="store_true", help="Skip Playwright browser tests")
    parser.add_argument("--no-proxy", action="store_true", help="Bypass system proxy (direct connection)")
    parser.add_argument("--cleanup", action="store_true", help="Delete smoke test data after run (SSH to server)")
    parser.add_argument("--verbose", action="store_true", help="Show response details")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout in seconds")
    args = parser.parse_args()

    env = ENVS[args.env]
    ctx = Ctx(
        api_url=(args.api_url or env["api"]).rstrip("/"),
        admin_url=(args.admin_url or env["admin"]).rstrip("/"),
        enterprise_url=env["enterprise"],
        dev_key=args.dev_key,
        timeout=args.timeout,
        no_proxy=args.no_proxy,
        verbose=args.verbose,
    )

    print(f"\nTesting {ctx.api_url} ...")

    # Tier 1: Health (no auth)
    run_test(ctx, "Settings endpoint",    "health", True,  test_settings)
    run_test(ctx, "Public cards",         "health", True,  test_public_cards)
    run_test(ctx, "Card groups",          "health", True,  test_card_groups)
    run_test(ctx, "Auth endpoint exists", "health", False, test_auth_endpoint_exists)
    run_test(ctx, "Static index.html",    "health", True,  test_static_index)

    # Tier 2: Auth + Admin (depends on dev-login)
    run_test(ctx, "Dev login", "auth", True, test_dev_login)

    if ctx.token:
        run_test(ctx, "Get current user",  "auth", True,  test_get_me)
        run_test(ctx, "Admin cards list",  "auth", True,  test_admin_cards)
        run_test(ctx, "Admin card groups", "auth", False, test_admin_card_groups)
        run_test(ctx, "Admin activities",  "auth", False, test_admin_activities)

        # Tier 3: Game flow (depends on auth)
        run_test(ctx, "Game start",  "flow", True, test_game_start)
        if ctx.session_id:
            run_test(ctx, "Game event",  "flow", True, test_game_event)
            run_test(ctx, "Game finish", "flow", True, test_game_finish)
        run_test(ctx, "Session retrieval", "flow", True, test_last_session)
    else:
        for name in ["Get current user", "Admin cards list", "Admin card groups",
                      "Admin activities", "Game start", "Game event",
                      "Game finish", "Session retrieval"]:
            ctx.results.append(TestResult(name, "auth", "SKIP", 0, "Dev login failed", True))

    # Tier 4: Browser tests (optional)
    if not args.skip_browser:
        run_browser_tests(ctx)

    # Cleanup smoke test data (shared DB, keep it clean)
    if args.cleanup:
        cleanup_smoke_data(ctx)

    print_results(ctx)
    sys.exit(0 if all_critical_passed(ctx) else 1)


if __name__ == "__main__":
    main()
