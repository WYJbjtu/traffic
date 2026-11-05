"""Reproducible real-browser smoke test; run against localhost:8501.

Requires Playwright and Chromium (see docs/research_explorer_96.md). Screenshots
are UI evidence only; this script does not create or change research data.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/research_explorer_96_integration"
OUTPUT.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("RESEARCH_EXPLORER_URL", "http://localhost:8501")
EXE = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")


def visit(page, label: str, witness: str, screenshot: str) -> str:
    """Navigate one actual Streamlit view and retain its rendered text/screenshot."""
    page.get_by_text(label, exact=True).first.click()
    page.get_by_text(witness, exact=False).first.wait_for(timeout=45000)
    page.wait_for_timeout(1000)
    body = page.locator("body").inner_text()
    page.screenshot(path=str(OUTPUT / screenshot), full_page=True)
    if "Traceback" in body or "Uncaught app execution" in body:
        raise AssertionError(f"Streamlit error on {label}")
    return body


def main() -> None:
    checks = {}
    with sync_playwright() as playwright:
        options = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        browser_path = EXE
        if browser_path is None and not Path(playwright.chromium.executable_path).is_file():
            # Accept an already installed Playwright Chromium revision when the
            # Python package's exact default revision is not present locally.
            installed = sorted((Path.home() / ".cache/ms-playwright").glob(
                "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
            browser_path = str(installed[-1]) if installed else None
        if browser_path:
            options["executable_path"] = browser_path
        browser = playwright.chromium.launch(**options)
        page = browser.new_page(viewport={"width": 1365, "height": 850}, device_scale_factor=1)
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        if "--missing" in sys.argv:
            overview = visit(page, "概览", "研究产物不可用", "missing-overview-browser.png")
            page.get_by_text("道路网络", exact=True).first.click()
            page.get_by_text("本地空间证据不可用", exact=False).wait_for(timeout=30000)
            missing = page.locator("body").inner_text()
            page.screenshot(path=str(OUTPUT / "missing-network-browser.png"), full_page=True)
            checks = {"missing_event_status": "本地：96 车道事件" in overview and "不可用" in overview,
                      "missing_network_status": "本地空间证据不可用" in missing,
                      "no_page_errors": not errors}
            result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "url": URL,
                      "browser": "Playwright Chromium, 1365x850; empty artifact root",
                      "checks": checks, "page_errors": errors}
            (OUTPUT / "browser-missing-validation.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            if not all(checks.values()):
                raise AssertionError("Missing-artifact browser validation failed")
            return
        overview = visit(page, "概览", "35,782,769 条五分钟交通记录", "overview-browser.png")
        checks["overview_counts"] = "30,452 个真实恢复事件" in overview
        network = visit(page, "道路网络", "本视图道路分块", "network-browser.png")
        checks["official_geometry"] = "条真实官方路线" in network and page.locator("canvas").count() > 0
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.get_by_role("option", name="AID01111").click()
        page.get_by_text("推断邻路 2 条", exact=False).wait_for(timeout=30000)
        selected_network = page.locator("body").inner_text()
        page.screenshot(path=str(OUTPUT / "network-selected-browser.png"), full_page=True)
        checks["detector_selection"] = "AID01111 · North East · Fast Lane" in selected_network
        checks["inferred_path"] = "AID01111 → AID01112" in selected_network and "96.4 m" in selected_network
        event = visit(page, "事件浏览", "真实结果：", "event-browser.png")
        page.get_by_text("Local ·", exact=False).first.wait_for(timeout=30000)
        event = page.locator("body").inner_text()
        page.screenshot(path=str(OUTPUT / "event-browser.png"), full_page=True)
        checks["real_event"] = "lane-observed-confirmation-v1" in event and "Local ·" in event
        checks["detector_persists_to_event"] = "AID01111 · North East · Fast Lane" in event
        checks["neighbor_curve"] = "Upstream ·" in event or "Downstream ·" in event
        checks["future_separated"] = "retrospective" in event and "预测时点" in event
        features = visit(page, "空间特征", "道路端点与路口形成节点", "features-browser.png")
        checks["saved_spatial_features"] = "S1 · 基本邻域" in features and "S4 · 邻路时间变化" in features
        models = visit(page, "模型比较", "M0 0.7250 → M1 0.7523", "models-browser.png")
        checks["frozen_model_metrics"] = "M0 0.7250 → M1 0.7523" in models
        checks["controls"] = "C1 地理邻近" in models and "C5 P2 高置信网络" in models
        methods = visit(page, "研究方法", "recovery_start_sustained_v1", "methods-browser.png")
        checks["scientific_limits"] = "P3 0 获批连接" in methods and "2026" in methods
        checks["no_page_errors"] = not errors
        checks["no_horizontal_overflow"] = page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth + 3")
        browser.close()
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "url": URL,
              "browser": "Playwright Chromium, 1365x850", "checks": checks,
              "page_errors": errors, "screenshots": [f"{name}-browser.png" for name in
                  ("overview", "network", "network-selected", "event", "features", "models", "methods")]}
    (OUTPUT / "browser-validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        raise AssertionError("Browser validation failed; see browser-validation.json")


if __name__ == "__main__":
    main()
