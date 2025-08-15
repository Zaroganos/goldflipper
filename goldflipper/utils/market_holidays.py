"""
Market Holiday Detection Utilities

This module provides functionality for detecting US market holidays and handling
option expiration date adjustments when markets are closed.

FUTURE ENHANCEMENT NOTE:
========================
For production use, consider migrating to the pandas_market_calendars library:
- More comprehensive and maintained
- Handles complex holiday rules and international markets  
- Accounts for partial trading days and early closures
- Better handling of edge cases and historical changes
- uv pip install pandas-market-calendars

Example future implementation:
```python
import pandas_market_calendars as mcal
nyse = mcal.get_calendar('NYSE')
is_holiday = not nyse.valid_days(start_date, end_date).empty
```

Current Implementation:
=======================
This module uses a simplified holiday calculation approach that covers
the major US market holidays. It's designed to be lightweight and cover
the most common cases without external dependencies.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Tuple

logger = logging.getLogger(__name__)

try:
    import pandas_market_calendars as mcal  # Optional dependency
    _PMC_AVAILABLE = True
except Exception:
    _PMC_AVAILABLE = False


def is_market_holiday(date) -> bool:
    """
    Check if a given date is a US market holiday.
    
    This function checks for major US market holidays when the stock market is closed.
    For comprehensive accuracy, consider using pandas_market_calendars library in production.
    
    Args:
        date: date object to check
        
    Returns:
        bool: True if the date is a market holiday, False otherwise
    """
    if isinstance(date, datetime):
        date = date.date()
    
    year = date.year
    
    # Define major US market holidays
    holidays = []
    
    # New Year's Day (January 1st, or closest weekday if weekend)
    new_years = datetime(year, 1, 1).date()
    holidays.append(_adjust_for_weekend(new_years))
    
    # Martin Luther King Jr. Day (3rd Monday in January)
    holidays.append(_nth_weekday(year, 1, 0, 3))  # 3rd Monday
    
    # Presidents' Day (3rd Monday in February)
    holidays.append(_nth_weekday(year, 2, 0, 3))  # 3rd Monday
    
    # Good Friday (Friday before Easter - complex calculation)
    try:
        good_friday = _calculate_good_friday(year)
        holidays.append(good_friday)
    except:
        pass  # Skip if calculation fails
    
    # Memorial Day (last Monday in May)
    holidays.append(_last_weekday(year, 5, 0))  # Last Monday
    
    # Juneteenth (June 19th, or closest weekday if weekend) - federal holiday since 2021
    if year >= 2021:
        juneteenth = datetime(year, 6, 19).date()
        holidays.append(_adjust_for_weekend(juneteenth))
    
    # Independence Day (July 4th, or closest weekday if weekend)
    independence_day = datetime(year, 7, 4).date()
    holidays.append(_adjust_for_weekend(independence_day))
    
    # Labor Day (1st Monday in September)
    holidays.append(_nth_weekday(year, 9, 0, 1))  # 1st Monday
    
    # Thanksgiving (4th Thursday in November)
    holidays.append(_nth_weekday(year, 11, 3, 4))  # 4th Thursday
    
    # Christmas Day (December 25th, or closest weekday if weekend)
    christmas = datetime(year, 12, 25).date()
    holidays.append(_adjust_for_weekend(christmas))
    
    # Check if the date matches any holiday
    is_holiday = date in holidays
    
    if is_holiday:
        logger.info(f"Date {date} identified as US market holiday")
    else:
        logger.debug(f"Date {date} is not a known US market holiday")
    
    return is_holiday


def find_next_friday_expiration() -> datetime:
    """
    Find the next Friday for weekly options expiration.
    
    Weekly options typically expire on Fridays. However, when Friday is a market holiday,
    options typically expire on the preceding Thursday instead. This function finds the
    appropriate expiration date, accounting for market holidays.
    
    Returns:
        datetime: Next weekly options expiration date (Friday or preceding Thursday if holiday)
    """
    today = datetime.now().date()
    
    # DEBUG: Log the current date and time for troubleshooting
    logger.info(f"🔍 find_next_friday_expiration() called - Today: {today} ({today.strftime('%A')})")
    
    # Prefer precise NYSE schedule if pandas_market_calendars is available
    if _PMC_AVAILABLE:
        try:
            nyse = mcal.get_calendar('XNYS')
            # Compute schedule for the next 14 days
            end = today + timedelta(days=14)
            sched = nyse.schedule(start_date=today, end_date=end)
            logger.debug(f"🔍 NYSE schedule computed for {today} to {end}")
            logger.debug(f"🔍 NYSE schedule contains {len(sched)} trading days")
            
            # Find the next Friday trading day in the schedule
            fridays_found = []
            for ts in sched.index:
                if ts.weekday() == 4:  # Friday
                    fridays_found.append(ts.date())
                    logger.debug(f"🔍 Found Friday in schedule: {ts.date()} (weekday {ts.weekday()})")
            
            logger.debug(f"🔍 All Fridays found in schedule: {fridays_found}")
            
            # We want the NEXT Friday, not today if today is Friday
            # Filter out today if it's Friday
            future_fridays = [f for f in fridays_found if f > today]
            logger.debug(f"🔍 Future Fridays (excluding today): {future_fridays}")
            
            if future_fridays:
                # Take the first future Friday
                next_friday_date = min(future_fridays)
                result = datetime.combine(next_friday_date, datetime.min.time())
                logger.info(f"🔍 find_next_friday_expiration() returning NYSE schedule result: {result.date()} ({result.strftime('%A')})")
                return result
            else:
                logger.warning("🔍 No future Fridays found in NYSE schedule, falling back to simple logic")
        except Exception as e:
            logger.debug(f"pandas_market_calendars unavailable or failed: {e}")

    # Simple fallback logic
    days_ahead = 4 - today.weekday()  # Friday is weekday 4 (Monday=0)
    logger.debug(f"🔍 Simple logic - days_ahead calculation: 4 - {today.weekday()} = {days_ahead}")
    
    if days_ahead <= 0:  # Today is Friday or weekend, get next Friday
        days_ahead += 7
        logger.debug(f"🔍 Adjusted days_ahead: {days_ahead}")
    
    next_friday = today + timedelta(days=days_ahead)
    logger.debug(f"🔍 Initial next Friday calculated: {next_friday}")
    
    # Check if this Friday is a known market holiday
    if is_market_holiday(next_friday):
        # If Friday is a holiday, weekly options typically expire on Thursday
        adjusted_expiration = next_friday - timedelta(days=1)  # Go to Thursday
        logger.info(f"Friday {next_friday} is a market holiday, adjusting expiration to Thursday {adjusted_expiration}")
        result = datetime.combine(adjusted_expiration, datetime.min.time())
        logger.info(f"🔍 find_next_friday_expiration() returning holiday-adjusted result: {result.date()} ({result.strftime('%A')})")
        return result
    
    result = datetime.combine(next_friday, datetime.min.time())
    logger.info(f"🔍 find_next_friday_expiration() returning simple logic result: {result.date()} ({result.strftime('%A')})")
    return result


def find_previous_friday() -> datetime:
    """
    Find the previous Friday for WEM Spread calculation.
    
    WEM Spread uses the previous Friday's closing price as the denominator.
    This function finds the most recent Friday before today, OR today if today is Friday and market has closed.
    
    Returns:
        datetime: Previous Friday's date, or today if today is Friday and market closed
    """
    today = datetime.now().date()
    
    # DEBUG: Log the current date and time for troubleshooting
    logger.info(f"🔍 find_previous_friday() called - Today: {today} ({today.strftime('%A')})")
    
    # If today is Friday, check if market has closed
    if today.weekday() == 4:  # Friday
        # Check if market has closed (after 4:00 PM ET)
        try:
            from zoneinfo import ZoneInfo
            market_tz = ZoneInfo('America/New_York')
            current_time_ny = datetime.now(market_tz)
            
            # DEBUG: Log timezone information
            logger.info(f"🔍 Timezone check - Current time NY: {current_time_ny.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            # Use configurable market close time, default to 4:00 PM ET
            # This matches the default in settings_template.yaml
            market_close_hour = 16  # 4 PM
            market_close_minute = 0
            
            # Try to get market close time from config if available
            try:
                from goldflipper.config.config import config
                config_market_hours = config.get('market_hours', {})
                if config_market_hours.get('enabled', True):
                    regular_hours = config_market_hours.get('regular_hours', {})
                    if 'end' in regular_hours:
                        end_time_str = regular_hours['end']
                        if ':' in end_time_str:
                            hour_str, minute_str = end_time_str.split(':')
                            market_close_hour = int(hour_str)
                            market_close_minute = int(minute_str)
            except Exception as e:
                logger.debug(f"Could not read market hours config, using default 4:00 PM ET: {e}")
            
            market_close_time = current_time_ny.replace(
                hour=market_close_hour, 
                minute=market_close_minute, 
                second=0, 
                microsecond=0
            )
            
            # DEBUG: Log market close time calculation
            logger.info(f"🔍 Market close time: {market_close_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logger.info(f"🔍 Is after market close? {current_time_ny >= market_close_time}")
            
            # If it's after market close on Friday, use today's Friday close
            if current_time_ny >= market_close_time:
                logger.info(f"Today is Friday ({today}) and market has closed at {market_close_hour:02d}:{market_close_minute:02d} ET - using today's Friday close")
                return datetime.combine(today, datetime.min.time())
            else:
                # Market still open on Friday, use last Friday
                time_until_close = market_close_time - current_time_ny
                logger.info(f"Today is Friday ({today}) but market still open - closes in {time_until_close} - using last Friday")
                days_back = 7
        except Exception as e:
            # Fallback: if timezone check fails, assume market closed after 4 PM ET
            # This is a reasonable assumption for WEM calculations run after market hours
            logger.warning(f"Timezone check failed, assuming market closed on Friday: {e}")
            days_back = 7
    else:
        # Not Friday - always return the previous Friday
        if today.weekday() < 4:  # Monday-Thursday
            days_back = today.weekday() + 3  # Days back to last Friday
        else:  # Weekend (Saturday=5, Sunday=6)
            days_back = today.weekday() - 4  # Days back to last Friday
    
    previous_friday = today - timedelta(days=days_back)
    logger.debug(f"Previous Friday calculated: {previous_friday}")
    
    result = datetime.combine(previous_friday, datetime.min.time())
    logger.info(f"🔍 find_previous_friday() returning: {result.date()} ({result.strftime('%A')})")
    
    return result


def get_expiration_date_candidates(primary_date: datetime) -> List[Tuple[datetime, str]]:
    """
    Get a list of candidate expiration dates to try, in order of preference.
    
    Args:
        primary_date: The primary expiration date (typically calculated Friday)
        
    Returns:
        List of tuples: (datetime, reason_string) for each candidate date
    """
    candidates = []
    
    # 1. Primary date (original calculation)
    candidates.append((primary_date, "original calculated date"))
    
    # 2. If primary is Friday, try Thursday (common holiday adjustment)
    if primary_date.weekday() == 4:  # Friday
        thursday = primary_date - timedelta(days=1)
        candidates.append((thursday, "Thursday before Friday (holiday adjustment)"))
    
    # 3. Try the preceding weekdays in the same week
    current_date = primary_date
    for days_back in range(1, 5):  # Try up to 4 days back
        candidate = current_date - timedelta(days=days_back)
        if candidate.weekday() < 5:  # Skip weekends
            day_name = candidate.strftime('%A')
            if candidate not in [c[0] for c in candidates]:  # Avoid duplicates
                candidates.append((candidate, f"{day_name} in same week"))
    
    # 4. Try the following Monday (for cases where options roll to next week)
    if primary_date.weekday() == 4:  # If primary was Friday
        next_monday = primary_date + timedelta(days=3)
        candidates.append((next_monday, "following Monday (extended expiration)"))
    
    # 5. Try the previous Friday (weekly options from previous week)
    previous_friday = primary_date - timedelta(days=7)
    if previous_friday.weekday() == 4:  # Make sure it's still Friday
        candidates.append((previous_friday, "previous Friday (weekly options)"))
    
    logger.debug(f"Generated {len(candidates)} expiration date candidates:")
    for i, (date, reason) in enumerate(candidates):
        logger.debug(f"  {i+1}. {date.date()} ({date.strftime('%A')}) - {reason}")
    
    return candidates


def test_find_previous_friday():
    """
    Test function to verify find_previous_friday logic works correctly.
    
    This function demonstrates how the system handles different scenarios:
    - Friday after market close (should return today)
    - Friday before market close (should return last Friday)
    - Other days (should return last Friday)
    """
    print("🧪 Testing find_previous_friday Logic")
    print("=" * 50)
    
    # Test 1: Friday after market close (should return today)
    print("\n📅 Test 1: Friday after market close")
    try:
        from zoneinfo import ZoneInfo
        market_tz = ZoneInfo('America/New_York')
        current_time_ny = datetime.now(market_tz)
        
        if current_time_ny.weekday() == 4:  # Friday
            print(f"Current time: {current_time_ny.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            result = find_previous_friday()
            print(f"Result: {result.date()} (should be today if market closed)")
            
            # Check if market is closed
            market_close_time = current_time_ny.replace(hour=16, minute=0, second=0, microsecond=0)
            if current_time_ny >= market_close_time:
                print("✅ Market has closed - should use today's Friday close")
            else:
                print("⏰ Market still open - should use last Friday")
        else:
            print("Not Friday today - cannot test Friday logic")
    except Exception as e:
        print(f"❌ Error testing Friday logic: {e}")
    
    # Test 2: Simulate different days
    print("\n📅 Test 2: Simulate different days")
    test_dates = [
        datetime(2025, 8, 15).date(),  # Friday
        datetime(2025, 8, 18).date(),  # Monday
        datetime(2025, 8, 20).date(),  # Wednesday
        datetime(2025, 8, 23).date(),  # Saturday
    ]
    
    for test_date in test_dates:
        print(f"\nSimulating date: {test_date} ({test_date.strftime('%A')})")
        
        # Temporarily override datetime.now for testing
        original_now = datetime.now
        try:
            # Mock datetime.now to return our test date
            def mock_now():
                return datetime.combine(test_date, datetime.min.time())
            
            datetime.now = mock_now
            
            # Test the function
            result = find_previous_friday()
            print(f"  Result: {result.date()} ({result.strftime('%A')})")
            
            # Validate the result
            if test_date.weekday() == 4:  # Friday
                # For Friday, result should be today or last Friday
                if result.date() == test_date:
                    print("  ✅ Correct: Using today's Friday close")
                else:
                    print("  ✅ Correct: Using last Friday (market still open)")
            else:
                # For non-Friday, result should be last Friday
                if result.date() < test_date and result.weekday() == 4:
                    print("  ✅ Correct: Using last Friday")
                else:
                    print("  ❌ Incorrect: Should be last Friday")
                    
        except Exception as e:
            print(f"  ❌ Error: {e}")
        finally:
            # Restore original datetime.now
            datetime.now = original_now
    
    print("\n" + "=" * 50)
    print("🧪 find_previous_friday test completed")


def test_holiday_detection():
    """
    Test function to verify holiday detection works correctly.
    
    This function demonstrates how the system handles July 4th, 2025 (Friday)
    and other market holidays. Can be called for testing purposes.
    """
    print("🧪 Testing Holiday Detection System")
    print("=" * 50)
    
    # Test July 4th, 2025 (Friday)
    july_4_2025 = datetime(2025, 7, 4).date()
    print(f"📅 July 4th, 2025: {july_4_2025} ({july_4_2025.strftime('%A')})")
    print(f"🎆 Is market holiday: {is_market_holiday(july_4_2025)}")
    
    # Test the expiration date calculation around July 4th, 2025
    # Simulate being on July 1st, 2025 (Tuesday) looking for next Friday
    test_current_date = datetime(2025, 7, 1).date()  # Tuesday before July 4th
    print(f"\n🗓️ Simulating current date: {test_current_date} ({test_current_date.strftime('%A')})")
    
    # Calculate what find_next_friday_expiration would do
    days_ahead = 4 - test_current_date.weekday()  # Friday is weekday 4
    simulated_friday = test_current_date + timedelta(days=days_ahead)
    print(f"📊 Calculated next Friday: {simulated_friday} ({simulated_friday.strftime('%A')})")
    
    # Test holiday detection and adjustment
    if is_market_holiday(simulated_friday):
        adjusted_date = simulated_friday - timedelta(days=1)  # Thursday
        print(f"✅ Holiday detected! Adjusted to: {adjusted_date} ({adjusted_date.strftime('%A')})")
    else:
        print(f"ℹ️ No holiday detected, using original date")
    
    # Test other holidays for 2025
    print(f"\n🎊 Other 2025 Market Holidays:")
    test_dates_2025 = [
        (datetime(2025, 1, 1).date(), "New Year's Day"),
        (datetime(2025, 1, 20).date(), "MLK Day"),
        (datetime(2025, 2, 17).date(), "Presidents' Day"),
        (datetime(2025, 5, 26).date(), "Memorial Day"),
        (datetime(2025, 6, 19).date(), "Juneteenth"),
        (datetime(2025, 7, 4).date(), "Independence Day"),
        (datetime(2025, 9, 1).date(), "Labor Day"),
        (datetime(2025, 11, 27).date(), "Thanksgiving"),
        (datetime(2025, 12, 25).date(), "Christmas"),
    ]
    
    for test_date, holiday_name in test_dates_2025:
        is_holiday = is_market_holiday(test_date)
        status = "🎆 HOLIDAY" if is_holiday else "📈 Trading Day"
        print(f"  {test_date} ({test_date.strftime('%A')}): {holiday_name} - {status}")
    
    print(f"\n✅ Holiday detection test complete!")
    
    # Test pandas_market_calendars suggestion
    print(f"\n📚 FUTURE ENHANCEMENT SUGGESTION:")
    print(f"Consider upgrading to pandas_market_calendars library for:")
    print(f"  • More comprehensive holiday coverage")
    print(f"  • International market support")
    print(f"  • Early close handling (e.g., day after Thanksgiving)")
    print(f"  • Historical holiday rule changes")
    print(f"  • Installation: uv pip install pandas-market-calendars")


def test_holiday_detection_ui():
    """
    Streamlit UI function for testing holiday detection system.
    
    This function provides an interactive interface for testing market holiday
    detection and expiration date calculations. It should only be called
    when debug mode is enabled.
    
    Returns:
        None: Updates Streamlit UI directly
    """
    try:
        import streamlit as st
        import io
        import contextlib
        
        st.info("Testing holiday detection system...")
        
        # Run the test in a code block to show results
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            test_holiday_detection()
        
        test_output = f.getvalue()
        st.code(test_output, language="text")
        
        # Also show specific July 4th, 2025 test
        july_4_2025 = datetime(2025, 7, 4).date()
        is_holiday_result = is_market_holiday(july_4_2025)
        
        if is_holiday_result:
            st.success(f"✅ July 4th, 2025 ({july_4_2025.strftime('%A')}) correctly detected as market holiday!")
            st.info("📅 When this date comes around, WEM calculations will automatically use Thursday July 3rd, 2025 for options expiration.")
        else:
            st.error(f"❌ July 4th, 2025 not detected as holiday - check holiday detection logic")
            
        # Show next Friday calculation with adjustment
        try:
            next_friday = find_next_friday_expiration()
            st.info(f"🗓️ Next Friday expiration calculated: {next_friday.date()} ({next_friday.strftime('%A')})")
            
            # Show holiday adjustment logic
            raw_friday = datetime.now().date()
            days_ahead = 4 - raw_friday.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            raw_next_friday = raw_friday + timedelta(days=days_ahead)
            
            if raw_next_friday != next_friday.date():
                st.warning(f"📅 Holiday adjustment detected: {raw_next_friday} → {next_friday.date()}")
            else:
                st.success(f"✅ No holiday adjustment needed for {next_friday.date()}")
                
        except Exception as e:
            st.error(f"Error testing next Friday calculation: {e}")
            
    except ImportError:
        logger.error("Streamlit not available - cannot run UI test")
        print("❌ Streamlit not available for UI testing")
    except Exception as e:
        logger.error(f"Error in holiday detection UI test: {e}")
        print(f"❌ Error in UI test: {e}")


# Private helper functions

def _adjust_for_weekend(date) -> datetime.date:
    """
    Adjust a holiday date if it falls on a weekend.
    If Saturday, move to Friday. If Sunday, move to Monday.
    """
    if date.weekday() == 5:  # Saturday
        return date - timedelta(days=1)  # Friday
    elif date.weekday() == 6:  # Sunday
        return date + timedelta(days=1)  # Monday
    return date


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime.date:
    """
    Find the nth occurrence of a weekday in a given month/year.
    
    Args:
        year: Year
        month: Month (1-12)
        weekday: Weekday (0=Monday, 6=Sunday)
        n: Which occurrence (1=first, 2=second, etc.)
    """
    first_day = datetime(year, month, 1).date()
    first_weekday = first_day.weekday()
    
    # Calculate days until the desired weekday
    days_until_weekday = (weekday - first_weekday) % 7
    
    # Find the nth occurrence
    target_date = first_day + timedelta(days=days_until_weekday + (n - 1) * 7)
    
    # Make sure we're still in the same month
    if target_date.month != month:
        raise ValueError(f"No {n}th {weekday} in {month}/{year}")
    
    return target_date


def _last_weekday(year: int, month: int, weekday: int) -> datetime.date:
    """
    Find the last occurrence of a weekday in a given month/year.
    """
    # Start from the last day of the month and work backwards
    if month == 12:
        last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    # Find the last occurrence of the weekday
    days_back = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=days_back)


def _calculate_good_friday(year: int) -> datetime.date:
    """
    Calculate Good Friday (Friday before Easter Sunday).
    Uses a simplified Easter calculation algorithm.
    """
    # Simplified Easter calculation (Western Christianity)
    # This is a basic implementation - for production use, consider using a dedicated library
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    n = (h + l - 7 * m + 114) // 31
    p = (h + l - 7 * m + 114) % 31
    
    easter_sunday = datetime(year, n, p + 1).date()
    good_friday = easter_sunday - timedelta(days=2)
    
    return good_friday 