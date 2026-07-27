"""Interactive login helper for MoneyForward Attendance.

Run this once (or whenever the session expires) to sign in manually via
a visible Chromium window. After you finish logging in and see the
attendance page, come back to the terminal and press Enter — the browser
cookies are then saved to storage_state.json so bulk_stamp.py can reuse
the session headlessly.

Usage:
    python login.py
"""

from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
STORAGE_STATE = HERE / "storage_state.json"
ATTENDANCE_URL = "https://attendance.moneyforward.com/my_page/attendances"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(ATTENDANCE_URL)

        print(
            "Sign in to MoneyForward in the opened browser window.\n"
            "When you can see the attendance page, come back here and press Enter.",
            file=sys.stderr,
        )
        try:
            input()
        except EOFError:
            pass

        context.storage_state(path=str(STORAGE_STATE))
        browser.close()
        print(f"Saved session to {STORAGE_STATE}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
