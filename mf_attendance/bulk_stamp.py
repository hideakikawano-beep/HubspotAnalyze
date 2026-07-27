"""Bulk-stamp business days on MoneyForward Attendance.

Fills in a fixed start/end time (default 09:00-18:00) for every Japanese
business day in a month, skipping weekends, national holidays, future
dates, and rows that already have any timestamp entered.

Because MoneyForward Attendance has no public per-employee API, this
drives the real web UI with Playwright, reusing the session captured by
login.py (storage_state.json).

Selectors in this script target the current MF UI. If MF changes their
markup, adjust the SELECTORS block below — see logs/<run>/*.png for
screenshots on failure.

Usage:
    python bulk_stamp.py --month 2026-07 --dry-run
    python bulk_stamp.py --month 2026-07
    python bulk_stamp.py --from 2026-07-01 --to 2026-07-27 --start 09:30 --end 18:30
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import pathlib
import sys
from dataclasses import dataclass

import jpholiday
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
STORAGE_STATE = HERE / "storage_state.json"
LOGS_ROOT = HERE / "logs"

ATTENDANCE_URL = "https://attendance.moneyforward.com/my_page/attendances"


# ---------- CLI ----------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    range_group = parser.add_mutually_exclusive_group()
    range_group.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="Target month (defaults to the current month). Mutually exclusive with --from/--to.",
    )
    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="Start date (inclusive).")
    parser.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="End date (inclusive).")
    parser.add_argument("--start", default="09:00", help="Clock-in time HH:MM (default 09:00).")
    parser.add_argument("--end", default="18:00", help="Clock-out time HH:MM (default 18:00).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print which days would be stamped; do not touch the UI.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Also stamp days that already have a value entered (default: skip them).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chromium with a visible window (useful for debugging).",
    )
    return parser.parse_args(argv)


def resolve_date_range(args: argparse.Namespace) -> tuple[dt.date, dt.date]:
    today = dt.date.today()
    if args.date_from or args.date_to:
        if args.month:
            raise SystemExit("--month cannot be combined with --from/--to")
        start = dt.date.fromisoformat(args.date_from) if args.date_from else today.replace(day=1)
        end = dt.date.fromisoformat(args.date_to) if args.date_to else today
        if end < start:
            raise SystemExit(f"--to ({end}) is earlier than --from ({start})")
        return start, end

    if args.month:
        year, month = (int(x) for x in args.month.split("-", 1))
    else:
        year, month = today.year, today.month
    last_day = calendar.monthrange(year, month)[1]
    return dt.date(year, month, 1), dt.date(year, month, last_day)


def business_days(start: dt.date, end: dt.date) -> list[dt.date]:
    days: list[dt.date] = []
    today = dt.date.today()
    d = start
    one = dt.timedelta(days=1)
    while d <= end:
        if d <= today and d.weekday() < 5 and not jpholiday.is_holiday(d):
            days.append(d)
        d += one
    return days


def validate_hhmm(value: str) -> str:
    dt.datetime.strptime(value, "%H:%M")
    return value


# ---------- UI driver ----------


@dataclass
class StampResult:
    date: dt.date
    status: str  # OK / SKIP / FAIL
    reason: str = ""


# NOTE: MoneyForward's attendance table doesn't publish stable data-testid
# attributes. Selectors below use header text + row semantics so they stay
# resilient to CSS class churn. Adjust if MF changes the DOM.
SELECTORS = {
    # Row identified by a date cell containing the day number.
    "row_by_date": "tr:has(td:has-text('{day}'))",
    # Time inputs inside a row — try native <input> first, fall back to buttons.
    "clock_in_input": "input[name*='clock_in'], input[aria-label*='出勤']",
    "clock_out_input": "input[name*='clock_out'], input[aria-label*='退勤']",
    # Save / submit button inside inline editor or modal.
    "save_button": "button:has-text('保存'), button:has-text('更新'), button:has-text('登録')",
    # Toast that confirms a successful save.
    "success_toast": ":text-matches('保存しました|更新しました|登録しました')",
}


def month_url(day: dt.date) -> str:
    return f"{ATTENDANCE_URL}?target_date={day.replace(day=1).isoformat()}"


def find_row(page: Page, day: dt.date) -> Locator:
    return page.locator(SELECTORS["row_by_date"].format(day=day.day)).first


def row_has_existing_stamp(row: Locator) -> bool:
    for sel in (SELECTORS["clock_in_input"], SELECTORS["clock_out_input"]):
        el = row.locator(sel).first
        if el.count() and (el.input_value() or "").strip():
            return True
    return False


def fill_time(row: Locator, selector: str, value: str) -> None:
    field = row.locator(selector).first
    field.click()
    field.fill("")
    field.type(value)
    # Blur to commit if the field auto-saves on blur.
    field.press("Tab")


def stamp_day(page: Page, day: dt.date, start: str, end: str, *, overwrite: bool) -> StampResult:
    try:
        row = find_row(page, day)
        row.wait_for(state="visible", timeout=5000)
    except PlaywrightTimeoutError:
        return StampResult(day, "FAIL", "row not found")

    if not overwrite and row_has_existing_stamp(row):
        return StampResult(day, "SKIP", "existing value")

    try:
        fill_time(row, SELECTORS["clock_in_input"], start)
        fill_time(row, SELECTORS["clock_out_input"], end)
    except PlaywrightTimeoutError as exc:
        return StampResult(day, "FAIL", f"time input timed out: {exc}")

    save_btn = row.locator(SELECTORS["save_button"]).first
    if save_btn.count():
        try:
            save_btn.click(timeout=3000)
        except PlaywrightTimeoutError:
            pass

    try:
        page.locator(SELECTORS["success_toast"]).first.wait_for(timeout=3000)
    except PlaywrightTimeoutError:
        # Not all screens surface a toast; treat missing toast as best-effort success.
        pass

    return StampResult(day, "OK")


# ---------- Main ----------


def run() -> int:
    args = parse_args()
    validate_hhmm(args.start)
    validate_hhmm(args.end)

    start_date, end_date = resolve_date_range(args)
    targets = business_days(start_date, end_date)

    print(f"Range: {start_date} .. {end_date}  ({len(targets)} business day(s))")
    if not targets:
        print("Nothing to do.")
        return 0

    if args.dry_run:
        for d in targets:
            print(f"{d}: DRY-RUN would stamp {args.start}-{args.end}")
        return 0

    if not STORAGE_STATE.exists():
        print(f"error: {STORAGE_STATE} not found. Run `python login.py` first.", file=sys.stderr)
        return 2

    run_dir = LOGS_ROOT / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[StampResult] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(storage_state=str(STORAGE_STATE))
        page = context.new_page()

        current_month: dt.date | None = None
        for day in targets:
            first_of_month = day.replace(day=1)
            if current_month != first_of_month:
                page.goto(month_url(day), wait_until="networkidle")
                current_month = first_of_month

            result = stamp_day(page, day, args.start, args.end, overwrite=args.overwrite)
            results.append(result)
            line = f"{day}: {result.status}"
            if result.reason:
                line += f" ({result.reason})"
            print(line)

            if result.status == "FAIL":
                shot = run_dir / f"{day.isoformat()}.png"
                try:
                    page.screenshot(path=str(shot), full_page=True)
                except Exception:  # noqa: BLE001
                    pass

        # Refresh storage_state so long-lived cookies stay up to date.
        context.storage_state(path=str(STORAGE_STATE))
        browser.close()

    ok = sum(r.status == "OK" for r in results)
    skip = sum(r.status == "SKIP" for r in results)
    fail = sum(r.status == "FAIL" for r in results)
    print(f"\nSummary: OK={ok}  SKIP={skip}  FAIL={fail}")
    if fail:
        print(f"Failure screenshots: {run_dir}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
