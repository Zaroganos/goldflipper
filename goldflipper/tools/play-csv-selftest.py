import csv
import os
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.tools.play_csv_ingestion_tool import (  # type: ignore
    CALLS_END,
    CALLS_ENTRY,
    CALLS_START,
    PUTS_ENTRY,
    build_composite_headers,
    create_play_from_data,
    detect_puts_start,
    find_strike_index,
    is_data_row,
)


def _extract_trailing_summary(play):
    tp = play.get("take_profit") or {}
    cfg = tp.get("trailing_config") or {}
    enabled = bool(cfg.get("enabled"))
    pct = tp.get("trailing_activation_pct")
    return enabled, pct


def _col_letter(idx: int) -> str:
    idx += 1  # 1-based
    letters = []
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def print_column_letter_map(calls_start: int, puts_start: int) -> None:
    print("[SELF-TEST] Column letter map (key fields):")
    # Calls mapping
    print(" Calls:")
    print(f"  symbol @ {_col_letter(calls_start + CALLS_ENTRY['symbol'])}")
    print(f"  expiration_date @ {_col_letter(calls_start + CALLS_ENTRY['expiration_date'])}")
    print(f"  buy order_type @ {_col_letter(calls_start + CALLS_ENTRY['order_type'])}")
    print(
        f"  TP premium % @ {_col_letter(calls_start + 16)}  TP stock % @ {_col_letter(calls_start + 17)}  Trailing @ {_col_letter(calls_start + 18)}"
    )
    print(
        f"  Sell order_type @ {_col_letter(calls_start + 20)}  "
        f"SL price @ {_col_letter(calls_start + 21)}  "
        f"SL prem % @ {_col_letter(calls_start + 22)}"
    )
    # Puts mapping
    print(" Puts:")
    print(f"  symbol @ {_col_letter(puts_start + PUTS_ENTRY['symbol'])}")
    print(f"  expiration_date @ {_col_letter(puts_start + PUTS_ENTRY['expiration_date'])}")
    print(f"  buy order_type @ {_col_letter(puts_start + PUTS_ENTRY['order_type'])}")
    print(f"  TP premium % @ {_col_letter(puts_start + 16)}  TP stock % @ {_col_letter(puts_start + 17)}  Trailing @ {_col_letter(puts_start + 18)}")
    print(
        f"  Sell order_type @ {_col_letter(puts_start + 19)}  SL price @ {_col_letter(puts_start + 21)}  SL prem % @ {_col_letter(puts_start + 22)}"
    )


def run_self_test(template_path: str | None = None, max_rows: int = 25) -> None:
    if not template_path:
        template_path = os.path.join(project_root, "goldflipper", "strategy", "api_template_trailing_edition.csv")

    if not os.path.exists(template_path):
        print(f"[SELF-TEST] Template not found: {template_path}")
        return

    with open(template_path, newline="", encoding="utf-8") as csvfile:
        reader = list(csv.reader(csvfile))
    if not reader:
        print("[SELF-TEST] CSV template is empty.")
        return

    header_rows = []
    data_rows = []
    found_data = False
    for row in reader:
        if not found_data and is_data_row(row):
            found_data = True
        if found_data:
            data_rows.append(row)
        else:
            header_rows.append(row)

    composite_headers = build_composite_headers(header_rows)
    dynamic_puts_start = detect_puts_start(composite_headers)
    calls_headers = composite_headers[CALLS_START:CALLS_END]
    puts_headers = composite_headers[dynamic_puts_start:]
    strike_calls = find_strike_index(calls_headers) or []
    strike_puts = find_strike_index(puts_headers) or []
    strike_calls = strike_calls if strike_calls else [8]
    strike_puts = strike_puts if strike_puts else [8]

    print(f"[SELF-TEST] Using template: {template_path}")
    print_column_letter_map(CALLS_START, dynamic_puts_start)
    examined = 0
    for i, row in enumerate(data_rows, start=1):
        if examined >= max_rows:
            break
        # Calls side
        if len(row) > CALLS_START + CALLS_ENTRY["symbol"] and row[CALLS_START + CALLS_ENTRY["symbol"]].strip():
            play_calls, errors_calls = create_play_from_data("calls", row, calls_headers, CALLS_START, strike_calls, i)
            if play_calls:
                enabled, pct = _extract_trailing_summary(play_calls)
                activation = pct if pct else ("default" if enabled else "-")
                print(f"Row {i} Calls: symbol={play_calls.get('symbol')} trailing={'on' if enabled else 'off'} activation_pct={activation}")
            for err in errors_calls:
                print(f"[SELF-TEST][WARN] {err}")
            examined += 1
        # Puts side
        if len(row) > dynamic_puts_start + PUTS_ENTRY["symbol"] and row[dynamic_puts_start + PUTS_ENTRY["symbol"]].strip():
            play_puts, errors_puts = create_play_from_data("puts", row, puts_headers, dynamic_puts_start, strike_puts, i)
            if play_puts:
                enabled, pct = _extract_trailing_summary(play_puts)
                activation = pct if pct else ("default" if enabled else "-")
                print(f"Row {i} Puts: symbol={play_puts.get('symbol')} trailing={'on' if enabled else 'off'} activation_pct={activation}")
            for err in errors_puts:
                print(f"[SELF-TEST][WARN] {err}")


if __name__ == "__main__":
    template = None
    if len(sys.argv) > 1:
        template = sys.argv[1]
    run_self_test(template)
