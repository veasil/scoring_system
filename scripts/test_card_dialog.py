"""
Playwright test: Admin panel card management dialog.
Tests login, navigation to card management, card dialog open/tabs.
Screenshots saved to /tmp/card_dialog_*.png
"""

import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL = "http://localhost:8501"
DEV_KEY = "sj0127wqt"
SCREENSHOT_DIR = "/tmp"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.set_default_timeout(30000)

        results = {}

        # ── Step 1: Go to admin panel ──────────────────────────────────────
        print("[1] Navigating to admin panel...")
        page.goto(BASE_URL, wait_until="networkidle")
        time.sleep(2)
        page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_01_login_page.png", full_page=True)
        print("    Screenshot saved: card_dialog_01_login_page.png")

        # ── Step 2: Login with DEV_KEY ──────────────────────────────────────
        print("[2] Logging in with DEV_KEY...")
        try:
            # The login page has two tabs: "开发者模式" and "用户登录"
            # Click the first tab (Developer mode)
            dev_tab = page.locator("button[role='tab']").filter(has_text="开发者模式")
            if dev_tab.count() > 0:
                dev_tab.first.click()
                time.sleep(0.5)

            # Find the password input and enter the DEV_KEY
            key_input = page.locator("input[type='password']").first
            key_input.fill(DEV_KEY)
            time.sleep(0.3)

            # Click the submit button
            submit_btn = page.locator("button").filter(has_text="进入上帝模式")
            submit_btn.first.click()
            print("    Clicked login button, waiting for redirect...")

            # Wait for login to complete (sidebar should appear)
            page.wait_for_selector("section[data-testid='stSidebar']", timeout=20000)
            time.sleep(2)
            page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_02_logged_in.png", full_page=False)
            print("    Screenshot saved: card_dialog_02_logged_in.png")
            results["login"] = "SUCCESS"
            print("    Login: SUCCESS")

        except PWTimeout as e:
            page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_02_login_failed.png", full_page=True)
            print(f"    Login FAILED (timeout): {e}")
            results["login"] = f"FAILED: {e}"
            browser.close()
            return results

        # ── Step 3: Navigate to "卡牌管理" ──────────────────────────────────
        print("[3] Navigating to 卡牌管理...")
        try:
            # Look for the sidebar navigation - try radio button or selectbox
            sidebar = page.locator("section[data-testid='stSidebar']")

            # Try clicking the radio option for 卡牌管理
            card_nav = sidebar.locator("label").filter(has_text="卡牌管理")
            if card_nav.count() > 0:
                card_nav.first.click()
                print("    Clicked 卡牌管理 via label")
            else:
                # Try finding in selectbox
                card_nav2 = sidebar.locator("div").filter(has_text="🎴 卡牌管理").last
                card_nav2.click()
                print("    Clicked 卡牌管理 via div")

            # Wait for the card management page header to appear
            page.wait_for_selector("h1, h2, h3", timeout=15000)
            time.sleep(3)  # Wait for cards to load from API
            page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_03_card_mgmt_page.png", full_page=True)
            print("    Screenshot saved: card_dialog_03_card_mgmt_page.png")
            results["navigate_to_card_mgmt"] = "SUCCESS"

        except PWTimeout as e:
            page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_03_nav_failed.png", full_page=True)
            print(f"    Navigation FAILED: {e}")
            results["navigate_to_card_mgmt"] = f"FAILED: {e}"
            browser.close()
            return results

        # ── Step 4: Wait for cards to fully load ──────────────────────────
        print("[4] Waiting for cards to load...")
        try:
            # Wait for "查看详情" button (meaning cards have loaded)
            page.wait_for_selector("button:has-text('查看详情')", timeout=20000)
            card_count = page.locator("button:has-text('查看详情')").count()
            print(f"    Found {card_count} '查看详情' buttons")
            results["cards_loaded"] = f"SUCCESS - {card_count} cards visible"

        except PWTimeout:
            # Check what's on the page
            page_text = page.inner_text("body")[:500]
            print(f"    Cards NOT loaded. Page text preview: {page_text}")
            page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_04_no_cards.png", full_page=True)
            results["cards_loaded"] = "FAILED - no cards visible"
            browser.close()
            return results

        # ── Step 5: Click "查看详情" on the first card ────────────────────
        print("[5] Clicking '查看详情' on first card...")
        try:
            first_detail_btn = page.locator("button:has-text('查看详情')").first
            first_detail_btn.scroll_into_view_if_needed()
            time.sleep(0.5)
            first_detail_btn.click()
            print("    Clicked '查看详情', waiting for dialog...")

            # Streamlit dialog appears as a modal - wait for it
            # The dialog has title "🎴 卡牌详情"
            # It may take a few seconds to load since it re-renders
            time.sleep(3)

            # Wait for the dialog/modal element or tab elements
            # Streamlit dialogs use a [data-testid="stDialog"] or similar
            dialog_appeared = False
            try:
                page.wait_for_selector("[data-testid='stDialog']", timeout=8000)
                dialog_appeared = True
                print("    Dialog appeared via stDialog selector")
            except PWTimeout:
                pass

            if not dialog_appeared:
                # Try looking for the tab buttons inside the dialog
                try:
                    page.wait_for_selector("button[role='tab']:has-text('卡牌详情')", timeout=8000)
                    dialog_appeared = True
                    print("    Dialog appeared via tab selector")
                except PWTimeout:
                    pass

            if not dialog_appeared:
                # Try looking for any tab with relevant text
                try:
                    page.wait_for_selector("button[role='tab']", timeout=5000)
                    tabs_text = [t.inner_text() for t in page.locator("button[role='tab']").all()]
                    print(f"    Tabs found: {tabs_text}")
                    dialog_appeared = True
                except PWTimeout:
                    pass

            time.sleep(1)
            page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_05_dialog_opened.png", full_page=False)
            print("    Screenshot saved: card_dialog_05_dialog_opened.png")

        except PWTimeout as e:
            page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_05_dialog_failed.png", full_page=True)
            print(f"    Dialog open FAILED: {e}")
            results["dialog_open"] = f"FAILED: {e}"
            browser.close()
            return results

        # ── Step 6: Verify dialog contents ───────────────────────────────
        print("[6] Verifying dialog contents...")
        # Look for all tabs
        tabs = page.locator("button[role='tab']").all()
        tab_texts = [t.inner_text() for t in tabs]
        print(f"    Visible tabs: {tab_texts}")
        results["tabs_visible"] = tab_texts

        # Check for card ID info (contains "#" + number)
        page_body = page.inner_text("body")
        has_id = "ID #" in page_body or "# " in page_body
        results["has_card_id"] = has_id

        # Check for the 4 expected tabs
        expected_tabs = ["卡牌详情", "卡牌编辑", "批注历史", "版本历史"]
        found_expected = [t for t in expected_tabs if any(t in tab for tab in tab_texts)]
        results["expected_tabs_found"] = found_expected
        print(f"    Expected tabs found: {found_expected}")

        # Check for safety type / phase info
        has_safety = any(x in page_body for x in ["身体安全", "网络安全", "心理安全", "隐私安全", "社会安全"])
        has_phase = any(x in page_body for x in ["启蒙期", "成长期", "青春期"])
        results["has_safety_type"] = has_safety
        results["has_phase_badge"] = has_phase
        print(f"    Has safety type: {has_safety}")
        print(f"    Has phase badge: {has_phase}")

        # ── Step 7: Click "✏️ 卡牌编辑" tab ─────────────────────────────
        print("[7] Clicking '卡牌编辑' tab...")
        try:
            edit_tab = page.locator("button[role='tab']").filter(has_text="卡牌编辑")
            if edit_tab.count() > 0:
                edit_tab.first.click()
                time.sleep(2)
                page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_06_edit_tab.png", full_page=False)
                print("    Screenshot saved: card_dialog_06_edit_tab.png")

                # Verify edit form elements
                page_body_edit = page.inner_text("body")
                has_safety_select = "安全类型" in page_body_edit
                has_phase_select = "年龄阶段" in page_body_edit
                has_event_field = "事件描述" in page_body_edit
                has_options = any(f"选项 {o}" in page_body_edit for o in ["A", "B", "C"])

                results["edit_tab"] = {
                    "clicked": True,
                    "has_safety_select": has_safety_select,
                    "has_phase_select": has_phase_select,
                    "has_event_field": has_event_field,
                    "has_option_editors": has_options,
                }
                print(f"    Edit tab - safety select: {has_safety_select}, "
                      f"phase select: {has_phase_select}, "
                      f"event field: {has_event_field}, "
                      f"options: {has_options}")
            else:
                results["edit_tab"] = {"clicked": False, "reason": "tab not found"}
                print("    Edit tab not found")

        except Exception as e:
            results["edit_tab"] = {"clicked": False, "error": str(e)}
            print(f"    Edit tab click failed: {e}")

        # Final screenshot of current state
        page.screenshot(path=f"{SCREENSHOT_DIR}/card_dialog_07_final.png", full_page=False)
        print("    Screenshot saved: card_dialog_07_final.png")

        browser.close()
        return results


if __name__ == "__main__":
    print("=" * 60)
    print("WQT Admin Panel - Card Dialog Playwright Test")
    print("=" * 60)
    results = run()
    print()
    print("=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    for key, value in results.items():
        print(f"  {key}: {value}")
    print("=" * 60)

    # Determine overall pass/fail
    login_ok = results.get("login") == "SUCCESS"
    nav_ok = results.get("navigate_to_card_mgmt") == "SUCCESS"
    cards_ok = "SUCCESS" in str(results.get("cards_loaded", ""))
    tabs = results.get("tabs_visible", [])
    expected_found = results.get("expected_tabs_found", [])
    all_4_tabs = len(expected_found) == 4

    print()
    print("PASS/FAIL:")
    print(f"  Login:               {'PASS' if login_ok else 'FAIL'}")
    print(f"  Navigation:          {'PASS' if nav_ok else 'FAIL'}")
    print(f"  Cards loaded:        {'PASS' if cards_ok else 'FAIL'}")
    print(f"  Dialog tabs (4/4):   {'PASS' if all_4_tabs else f'FAIL ({len(expected_found)}/4 found)'}")
    print(f"  Safety type shown:   {'PASS' if results.get('has_safety_type') else 'FAIL'}")
    print(f"  Phase badge shown:   {'PASS' if results.get('has_phase_badge') else 'FAIL'}")

    edit = results.get("edit_tab", {})
    if isinstance(edit, dict):
        edit_ok = edit.get("clicked") and edit.get("has_event_field")
        print(f"  Edit tab works:      {'PASS' if edit_ok else 'FAIL'}")

    sys.exit(0)
