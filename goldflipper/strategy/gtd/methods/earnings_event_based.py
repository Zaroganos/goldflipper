"""
Earnings/Event-Based GTD Method

Closes or shortens the position before known events (earnings, FOMC, etc.)
that could cause large, unpredictable price moves. This protects against
binary event risk.

Params:
    close_days_before (int): Days before the event to close. Default: 1
    event_types (list): Event types to watch for. Default: ["earnings", "fomc"]

Note: This method requires an event data source (upcoming_events in context).
      Currently a stub — the event calendar integration is a future enhancement.
"""

from datetime import timedelta

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("earnings_event_based")
class EarningsEventBasedMethod(DynamicGTDMethod):
    def get_name(self) -> str:
        return "earnings_event_based"

    def evaluate(self, context: GTDContext) -> GTDResult:
        close_days_before = context.method_params.get("close_days_before", 1)
        event_types = context.method_params.get("event_types", ["earnings", "fomc"])

        if not context.upcoming_events:
            return GTDResult(action=GTDAction.HOLD, reason="No upcoming events data available")

        symbol = context.play.get("symbol", "")

        for event in context.upcoming_events:
            event_type = event.get("type", "")
            event_symbol = event.get("symbol", "")
            event_date_str = event.get("date", "")

            # Filter by event type
            if event_type not in event_types:
                continue

            # Filter by symbol (earnings are symbol-specific; FOMC affects all)
            if event_type == "earnings" and event_symbol != symbol:
                continue

            # Parse event date
            from goldflipper.strategy.gtd.evaluator import GTDEvaluator

            event_date = GTDEvaluator._parse_date(event_date_str)
            if event_date is None:
                continue

            days_until = (event_date - context.current_date).days

            if days_until <= close_days_before:
                return GTDResult(
                    action=GTDAction.CLOSE_NOW,
                    reason=f"{event_type.upper()} event in {days_until} day(s) for {event_symbol or 'market'}, closing to avoid binary risk",
                    priority=30,
                    metadata={"event_type": event_type, "event_date": event_date_str},
                )

            # Set effective date to close before the event
            close_by = event_date - timedelta(days=close_days_before)
            return GTDResult(
                action=GTDAction.SHORTEN,
                recommended_date=close_by,
                reason=f"{event_type.upper()} on {event_date.strftime('%m/%d/%Y')}, will close by {close_by.strftime('%m/%d/%Y')}",
                priority=50,
                metadata={"event_type": event_type, "event_date": event_date_str},
            )

        return GTDResult(action=GTDAction.HOLD, reason="No relevant upcoming events found")

    def get_default_params(self):
        return {"close_days_before": 1, "event_types": ["earnings", "fomc"]}

    def get_param_schema(self):
        return {
            "close_days_before": {
                "type": "integer",
                "description": "Days before event to close the position",
                "default": 1,
                "min": 0,
                "max": 10,
            },
            "event_types": {
                "type": "array",
                "description": "Types of events to watch for",
                "default": ["earnings", "fomc"],
                "items": {"type": "string"},
            },
        }

    def validate_config(self, params):
        errors = []
        days = params.get("close_days_before")
        if days is not None and (not isinstance(days, int) or days < 0):
            errors.append("close_days_before must be a non-negative integer")
        return errors
