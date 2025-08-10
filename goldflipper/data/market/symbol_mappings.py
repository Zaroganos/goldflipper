"""
Provider-specific symbol translation mappings.

Some data providers use different root symbols for the same underlying.
This module centralizes those mappings and exposes a helper to translate
symbols before making provider calls.

Examples:
- yfinance uses "^VIX" for the CBOE Volatility Index, while others use "VIX".

Notes:
- MarketData.app indicates its underlying symbol for VIX is "VIX" (see their
  published index list). We therefore do not translate VIX for MarketData.app.
"""

from typing import Dict


PROVIDER_SYMBOL_ALIASES: Dict[str, Dict[str, str]] = {
    # Yahoo Finance differences
    "yfinance": {
        "VIX": "^VIX",
    },
    # MarketData.app uses VIX as-is per documentation
    "marketdataapp": {
        # No changes needed at the moment
    },
    # Alpaca mappings can be added as needed
    "alpaca": {
    },
}


def translate_symbol(provider_name: str, symbol: str) -> str:
    """Translate a symbol to the provider-specific alias if defined.

    Args:
        provider_name: provider key (e.g., 'yfinance', 'marketdataapp', 'alpaca')
        symbol: original symbol (case-insensitive)

    Returns:
        Translated symbol if mapping exists; otherwise the original symbol.
    """
    if not provider_name or not symbol:
        return symbol
    aliases = PROVIDER_SYMBOL_ALIASES.get(provider_name.lower(), {})
    return aliases.get(symbol.upper(), symbol)


