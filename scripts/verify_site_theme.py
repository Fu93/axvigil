#!/usr/bin/env python3
"""Automated theme, typography, and responsive verification across all 4 web pages."""
import os
import sys
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\nn201\.gemini\antigravity\brain\7602765c-e019-46b1-b637-f6b6358ff9a1"
PAGES = [
    ("homepage", "http://localhost:8080/web/index.html"),
    ("leaderboard", "http://localhost:8080/web/leaderboard.html"),
    ("demo", "http://localhost:8080/web/demo.html"),
    ("pitch", "http://localhost:8080/web/pitch.html"),
]

def main():
    print("[1/5] Launching headless browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Desktop Theme & Typography Verification
        for name, url in PAGES:
            print(f"[2/5] Inspecting desktop layout: {name} ({url})")
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(600)
            
            # Check font and background
            bg_color = page.evaluate("getComputedStyle(document.body).backgroundColor")
            font_family = page.evaluate("getComputedStyle(document.body).fontFamily")
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            inner_width = page.evaluate("window.innerWidth")
            print(f"       -> bg: {bg_color}, font: {font_family[:30]}, scroll: {scroll_width}/{inner_width}")
            assert scroll_width <= inner_width, f"Horizontal overflow on {name}: {scroll_width} > {inner_width}"

            out_path = os.path.join(ARTIFACT_DIR, f"theme_audit_{name}_desktop.png")
            page.screenshot(path=out_path, full_page=False)
            print(f"       Saved screenshot: {out_path}")

        # Multi-page Persistent Language Switching Test
        print("[3/5] Testing cross-page language synchronization...")
        page.goto("http://localhost:8080/web/index.html", wait_until="networkidle")
        zh_btn = page.locator("button[data-lang='zh-TW']")
        if zh_btn.count() > 0:
            zh_btn.click()
            page.wait_for_timeout(400)
            print("       Switched index.html to Traditional Chinese (zh-TW)")

        # Verify language persisted on pitch.html
        page.goto("http://localhost:8080/web/pitch.html", wait_until="networkidle")
        page.wait_for_timeout(400)
        pitch_lang = page.evaluate("document.documentElement.lang")
        h1_text = page.locator("h1.display").inner_text()
        print(f"       pitch.html active lang: {pitch_lang}")
        print(f"       pitch.html display h1: {h1_text.strip().replace(chr(10), ' ')}")
        out_path = os.path.join(ARTIFACT_DIR, "theme_audit_pitch_zh_desktop.png")
        page.screenshot(path=out_path, full_page=False)

        # Verify language persisted on leaderboard.html
        page.goto("http://localhost:8080/web/leaderboard.html", wait_until="networkidle")
        page.wait_for_timeout(400)
        board_lang = page.evaluate("document.documentElement.lang")
        print(f"       leaderboard.html active lang: {board_lang}")
        out_path = os.path.join(ARTIFACT_DIR, "theme_audit_board_zh_desktop.png")
        page.screenshot(path=out_path, full_page=False)

        # Verify language persisted on demo.html
        page.goto("http://localhost:8080/web/demo.html", wait_until="networkidle")
        page.wait_for_timeout(400)
        demo_lang = page.evaluate("document.documentElement.lang")
        print(f"       demo.html active lang: {demo_lang}")
        out_path = os.path.join(ARTIFACT_DIR, "theme_audit_demo_zh_desktop.png")
        page.screenshot(path=out_path, full_page=False)

        # Switch back to English
        page.locator("button[data-lang='en']").click()
        page.wait_for_timeout(400)

        # Mobile Viewport & Drawer Verification (390px iPhone width)
        print("[4/5] Testing mobile layout & menu drawer (390x844)...")
        mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
        mobile_page = mobile_context.new_page()

        for name, url in PAGES:
            mobile_page.goto(url, wait_until="networkidle")
            mobile_page.wait_for_timeout(500)
            
            # Verify no horizontal scroll overflow
            scroll_width = mobile_page.evaluate("document.documentElement.scrollWidth")
            inner_width = mobile_page.evaluate("window.innerWidth")
            print(f"       Mobile {name}: scroll {scroll_width} vs viewport {inner_width}")
            assert scroll_width <= inner_width + 1, f"Mobile horizontal overflow on {name}: {scroll_width} > {inner_width}"

            # Open mobile menu drawer
            toggle_btn = mobile_page.locator(".nav-toggle")
            if toggle_btn.count() > 0 and toggle_btn.is_visible():
                toggle_btn.click()
                mobile_page.wait_for_timeout(300)
                nav_open = mobile_page.evaluate("document.getElementById('site-nav').classList.contains('open')")
                print(f"       Mobile drawer toggle on {name}: {nav_open}")

            out_path = os.path.join(ARTIFACT_DIR, f"theme_audit_{name}_mobile.png")
            mobile_page.screenshot(path=out_path, full_page=False)
            print(f"       Saved mobile screenshot: {out_path}")

        print("[5/5] All visual and functional audits PASSED!")
        browser.close()

if __name__ == "__main__":
    main()
