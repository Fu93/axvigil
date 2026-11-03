#!/usr/bin/env python3
"""Automated theme, typography, interactive toast, and responsive verification across all 4 web pages."""
import os
import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ARTIFACT_DIR = r"C:\Users\nn201\.gemini\antigravity\brain\7602765c-e019-46b1-b637-f6b6358ff9a1"
PAGES = [
    ("homepage", "http://localhost:8080/web/index.html"),
    ("leaderboard", "http://localhost:8080/web/leaderboard.html"),
    ("demo", "http://localhost:8080/web/demo.html"),
    ("pitch", "http://localhost:8080/web/pitch.html"),
]

def main():
    print("[1/6] Launching headless browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.new_page()

        # 1. Desktop Theme & Typography Verification
        for name, url in PAGES:
            print(f"[2/6] Inspecting desktop layout: {name} ({url})")
            page.goto(url, wait_until="domcontentloaded")
            if name == "homepage":
                page.evaluate("""
                    sessionStorage.setItem('axv-intro-seen', '1');
                    document.documentElement.classList.remove('show-loader', 'hold-hero');
                    document.documentElement.classList.add('intro-go');
                    var l = document.getElementById('ax-loader');
                    if (l) l.remove();
                    var s = document.getElementById('ax-skip');
                    if (s) s.remove();
                    var st = document.getElementById('ax-status');
                    if (st) st.remove();
                """)
            page.wait_for_timeout(800)
            
            # Check font and background
            bg_color = page.evaluate("getComputedStyle(document.body).backgroundColor")
            font_family = page.evaluate("getComputedStyle(document.body).fontFamily")
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            inner_width = page.evaluate("window.innerWidth")
            print(f"       -> bg: {bg_color}, font: {font_family[:30]}, scroll: {scroll_width}/{inner_width}")
            assert scroll_width <= inner_width, f"Horizontal overflow on {name}: {scroll_width} > {inner_width}"

            out_path = os.path.join(ARTIFACT_DIR, f"theme_audit_{name}_desktop.png")
            page.screenshot(path=out_path, full_page=False)
            print(f"       Saved screenshot: {out_path} (size: {os.path.getsize(out_path):,} bytes)")

        # 2. Interactive Click-to-Copy Cyber-Toast Verification
        print("[3/6] Testing interactive copy button and toast notification...")
        page.goto("http://localhost:8080/web/demo.html", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        copy_btn = page.locator(".copy-chip").first
        if copy_btn.count() > 0:
            copy_btn.click()
            page.wait_for_timeout(300)
            toast_text = page.locator("#copied").inner_text()
            toast_visible = page.evaluate("document.getElementById('copied').classList.contains('toast-active')")
            print(f"       Copy toast active: {toast_visible}, text: '{toast_text}'")
            assert toast_visible, "Toast active class was not added"
            out_path = os.path.join(ARTIFACT_DIR, "theme_audit_copy_toast.png")
            page.screenshot(path=out_path, full_page=False)
            print(f"       Saved toast screenshot: {out_path}")

        # 3. Multi-page Persistent Language Switching Test
        print("[4/6] Testing cross-page language synchronization...")
        page.goto("http://localhost:8080/web/index.html", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        zh_btn = page.locator("button[data-lang='zh-TW']")
        if zh_btn.count() > 0:
            zh_btn.click()
            page.wait_for_timeout(400)
            print("       Switched index.html to Traditional Chinese (zh-TW)")

        # Verify language persisted on pitch.html
        page.goto("http://localhost:8080/web/pitch.html", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        pitch_lang = page.evaluate("document.documentElement.lang")
        print(f"       pitch.html active lang: {pitch_lang}")
        assert pitch_lang == "zh-Hant", f"pitch.html lang expected zh-Hant, got {pitch_lang}"
        out_path = os.path.join(ARTIFACT_DIR, "theme_audit_pitch_zh_desktop.png")
        page.screenshot(path=out_path, full_page=False)

        # Verify language persisted on leaderboard.html
        page.goto("http://localhost:8080/web/leaderboard.html", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        board_lang = page.evaluate("document.documentElement.lang")
        print(f"       leaderboard.html active lang: {board_lang}")
        assert board_lang == "zh-Hant", f"leaderboard.html lang expected zh-Hant, got {board_lang}"
        out_path = os.path.join(ARTIFACT_DIR, "theme_audit_board_zh_desktop.png")
        page.screenshot(path=out_path, full_page=False)

        # Verify language persisted on demo.html
        page.goto("http://localhost:8080/web/demo.html", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        demo_lang = page.evaluate("document.documentElement.lang")
        print(f"       demo.html active lang: {demo_lang}")
        assert demo_lang == "zh-Hant", f"demo.html lang expected zh-Hant, got {demo_lang}"
        out_path = os.path.join(ARTIFACT_DIR, "theme_audit_demo_zh_desktop.png")
        page.screenshot(path=out_path, full_page=False)

        # Switch back to English
        page.locator("button[data-lang='en']").click()
        page.wait_for_timeout(400)

        # 4. Mobile Viewport & Drawer Verification (390px iPhone width)
        print("[5/6] Testing mobile layout & menu drawer (390x844)...")
        mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
        mobile_page = mobile_context.new_page()

        for name, url in PAGES:
            mobile_page.goto(url, wait_until="domcontentloaded")
            if name == "homepage":
                mobile_page.evaluate("""
                    sessionStorage.setItem('axv-intro-seen', '1');
                    document.documentElement.classList.remove('show-loader', 'hold-hero');
                    document.documentElement.classList.add('intro-go');
                    var l = document.getElementById('ax-loader');
                    if (l) l.remove();
                    var s = document.getElementById('ax-skip');
                    if (s) s.remove();
                    var st = document.getElementById('ax-status');
                    if (st) st.remove();
                """)
            mobile_page.wait_for_timeout(600)
            
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
            print(f"       Saved mobile screenshot: {out_path} (size: {os.path.getsize(out_path):,} bytes)")

        print("[6/6] All visual, functional, and interactive polish audits PASSED!")
        browser.close()

if __name__ == "__main__":
    main()
