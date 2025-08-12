VIX options are weird — not because they want to be difficult, but because they’re fundamentally different animals from equity or ETF options.

Here’s why your “past Friday close + next Friday expiration” flow works for stocks/ETFs but breaks for VIX:
1️⃣ VIX options are cash-settled futures options, not spot index options

    VIX itself is a spot index, but you can’t actually trade it directly.

    VIX options are written on the VIX futures that expire on a specific Wednesday each month (and for weeklies, other Wednesdays).

    So the expiration date in the option chain isn’t tied to a Friday like SPY/QQQ — it’s tied to the corresponding VIX futures contract.

2️⃣ Expiration day is Wednesday morning, not Friday afternoon

    Settlement is based on the Special Opening Quotation (SOQ) for VIX, which is calculated from S&P 500 option prices that morning.

    This means:

        Last trading day is Tuesday before settlement.

        No trading on Wednesday — cash settlement happens after SOQ is published.

3️⃣ Weeklies ≠ calendar weeklies

    “VIX weekly” options expire on Wednesdays of non-standard weeks, tied to the relevant futures contract.

    If you try to grab “the Friday after last Friday” you’ll be looking at a date that doesn’t exist for VIX options.

4️⃣ Different underlying price behavior

    Your expected move formula probably uses the underlying price.

    For SPY, the underlying is the spot ETF.

    For VIX options, the underlying price is the relevant VIX future — not the VIX spot index you see on CNBC. This future can differ a lot from spot VIX (due to contango/backwardation).

5️⃣ Practical implication for fetching chains

If you want to fetch the “next expiration” for a given date:

    Step 1: Determine the correct VIX futures month and expiration Wednesday.

    Step 2: Pull the option chain for that expiration, not the Friday after.

    Step 3: Use the corresponding VIX future price in your expected move calculation, not VIX spot.

    Find the correct VIX expiration date:
    VIX options expire on Wednesdays, not Fridays. Look at the Cboe VIX expiration calendar, find the next Wednesday that is a listed expiration date, and use that for your option chain request. If today is Tuesday or later in the week, skip to the following Wednesday expiration.

    Find the correct underlying price:
    Each VIX option expiration is tied to a specific VIX futures contract. The underlying price is that futures contract’s price, not the VIX spot index. To get it, match your option’s expiration date to the VIX futures contract with the same settlement date, then pull that futures price (ticker format: VX<Month><Year>).

That’s it — you pull the options for the right Wednesday, and use the matching futures price for calculations.

VIX Date-to-Contract Cheat Sheet

(Settlement is always on a Wednesday morning — last trading day is the Tuesday before)

    January → VX1 (January futures)

    February → VX2

    March → VX3

    … continues monthly in sequence …

    VX<M> matches the calendar month of settlement (not the month you pull the data).

    Weekly expirations in between are still tied to the nearest active monthly futures contract — if the weekly is before the monthly settlement, it uses the front-month future; if after, it uses the next-month future.

Logic to pick the right VIX date and futures contract:

    Get today’s date.

    Look up the official VIX expiration calendar (or pre-store it for the year).

    Find the soonest expiration date that is strictly after today (skip today if it's expiration day).

    If today is Tuesday before that expiration, note that it’s the last trading day for that cycle.

    Identify the futures contract whose settlement date matches that expiration.

    Pull the option chain for that expiration date.

    Pull the futures price for that contract (e.g., VXH25 for March 2025).

Pseudocode

# Assume: you have a list of official VIX expiration dates for the year (from Cboe)

today = get_today()

# 1. Find next expiration date
expirations = load_vix_expiration_calendar()  # list of datetime objects
next_exp = min(d for d in expirations if d > today)

# 2. Identify month/year for futures contract
#    Settlement month is next_exp.month, year is next_exp.year
futures_code = get_vx_symbol(next_exp)  # e.g., VXH25

# 3. Pull VIX option chain
option_chain = get_option_chain("VIX", expiration=next_exp)

# 4. Pull matching VIX futures price
futures_price = get_futures_price(futures_code)

# 5. Calculate Expected Move
atm_iv = get_atm_iv(option_chain)
days_to_exp = (next_exp - today).days
expected_move = futures_price * atm_iv * sqrt(days_to_exp / 365)

print(next_exp, futures_code, futures_price, expected_move)

Helper: Futures Month Code Mapping

month_map = {
    1: "F",  # January
    2: "G",  # February
    3: "H",  # March
    4: "J",  # April
    5: "K",  # May
    6: "M",  # June
    7: "N",  # July
    8: "Q",  # August
    9: "U",  # September
    10: "V", # October
    11: "X", # November
    12: "Z", # December
}

def get_vx_symbol(exp_date):
    month_code = month_map[exp_date.month]
    year_code = str(exp_date.year)[-2:]  # last two digits
    return f"VX{month_code}{year_code}"

VIX Expiration Calendar: Source & Access

    Macroption compiles and publishes a detailed VIX expiration calendar (including irregular dates when holidays push expirations to Tuesdays). For example, you’ll see dates like

        June 3, 2025 (Tuesday) due to July 4 holiday

        March 18, 2025 (Tuesday) due to Good Friday shift
        Macroption

    Macroption also clearly explains the rule:
    VIX options expire on the Wednesday that is 30 days before the third Friday of the following month—unless a holiday intervenes, in which case the expiration moves to the prior business day.
    Macroption

These are publicly accessible via the Macroption website and sourced from official CBOE timings.
Automating Calendar Handling: Options & Tooling
1. Use Macroption Data

    Simply copy the 2025 expiration list into your code (e.g. a Python list of dates). It’s accurate and handles irregular shifts already.

    This is fast and bulletproof until next year’s calendar arrives.

2. Use a Python Library – vix_utils

There's a handy open-source package called vix_utils which:

    Builds a mapping of trade dates → next VIX futures settlement dates,

    Downloads VIX futures data (via Quandl or CBOE),

    Helps construct continuous term-structures of VIX futures.

    You can install it via pip and integrate directly into your script.
    PyPI

This is great if you also want futures pricing and maturity mapping embedded in your workflow.
Plug-and-Play: 2025 VIX Expiration List

Here’s a Python-ready list of the 2025 VIX expiration dates (final settlement days):

vix_expirations_2025 = [
    "2025-01-22", "2025-02-19", "2025-03-18",  # March is Tuesday (holiday shift)
    "2025-04-16", "2025-05-21", "2025-06-18",
    "2025-07-16", "2025-08-20", "2025-09-17",
    "2025-10-22", "2025-11-19", "2025-12-17",
    "2025-06-03"  # irregular weekly expiration (Tuesday due to Jul 4 shift)
]

You can hard-code this or fetch it from Macroption dynamically if they provide a parsable format.
Recommended Workflow (Python Pseudocode)

today = get_today()

# Load your VIX expiration list/calendar
expirations = load_expirations()  # could be your 2025 list or resp. year

# Find next expiration after today
next_exp = min(date for date in expirations if date > today)

# Build futures symbol:
futures_code = get_vx_symbol(next_exp)  # as in your previous pseudocode

# Pull option chain and futures price
option_chain = get_option_chain("VIX", expiration=next_exp)
futures_price = get_futures_price(futures_code)

# Continue with expected move, etc...

Summary at a Glance:
Task	Approach
Get expiration dates	Copy from Macroption (rule-based and holiday-adjusted)
Automate calendar logic	Use vix_utils to map trade → settlement dates and load futures data
Routine refresh	Update list annually or switch to API/scrape if available


Implementation Notes (2025-08-11)
---------------------------------
- We implemented VIX handling with the following principles:
  - Expiration selection uses provider-listed expirations (Wednesdays) with a 2025 fallback list when needed.
  - Option chain analysis uses robust mids; ATM for VIX is chosen via min |call_mid − put_mid| per strike.
  - WEM denominator (Friday Close mode):
    - Prefers VX=F Friday close via provider (yfinance) when available.
    - Falls back to ^VIX Friday close via provider.
    - If both fail, makes a direct HTTP call to Yahoo Chart API for the day’s close, e.g.:
      `https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?symbol=%5EVIX&period1=<p1>&period2=<p2>&interval=1d`.
    - Only if all above fail do we compute an ATM parity proxy; we always tag the base source in metadata/Excel notes.
  - We do not rely on vix_utils for pricing. Any vix_utils adapter remains deprecated and unused for WEM calculations.

What changed relative to this doc:
- We used provider expirations and a rule-based VIX monthly expiration method instead of scraping calendars.
- For pricing, we confirm the note that futures underpin VIX options, but for resiliency we added ^VIX and direct Yahoo HTTP fallbacks to always get a Friday close denominator.
- The futures symbol (VX codes) is not required for WEM denominator; when VX=F is unavailable, ^VIX close is acceptable and clearly annotated.


Implementation Notes (2025-08-12)
---------------------------------
- Migrated VIX logic into a shared module `goldflipper/data/market/tickers/VIX/vix_lib.py`:
  - Rule-based monthly expiration generator (Wed ≈ 30 days before next month’s 3rd Fri, prior business day if holiday).
  - Cboe VIX EOD CSV fetch (`VIX_History.csv`) with simple schema (DATE, OPEN, HIGH, LOW, CLOSE).
  - Yahoo Chart API daily close helper (path-encoded symbol, UA header).
  - VIX chain extraction via robust mids and min |C−P| ATM.
- Friday Close denominator order for VIX (current):
  1) Providers (VX=F via yfinance; then ^VIX via providers)
  2) Cboe CSV close for the target Friday
  3) Yahoo Chart API
- Removed the parity proxy fallback for now to avoid ambiguity; may be re‑introduced later and reprioritized if needed.
- WEM page delegates to `vix_lib` for VIX expirations, EOD close resolution, and chain selection to keep the UI thin.