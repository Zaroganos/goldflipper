"""Portfolio and account query tools — positions, account info, active account."""

from typing import Any, cast

from goldflipper.mcp_server.context import ctx
from goldflipper.mcp_server.server import mcp


@mcp.tool
def get_portfolio_positions() -> dict:
    """Get all current positions from the active Alpaca account.

    Returns:
        Dict with account name and list of position summaries including
        symbol, quantity, market value, unrealized P&L, and current price.
    """
    from goldflipper.config.config import get_active_account_name

    try:
        client: Any = ctx.alpaca_client
        positions = cast(list[Any], client.get_all_positions())
    except Exception as e:
        return {"error": f"Failed to get positions: {e}"}

    pos_list = []
    for pos in positions:
        pos_list.append(
            {
                "symbol": str(pos.symbol),
                "qty": str(pos.qty),
                "side": str(pos.side),
                "market_value": str(pos.market_value),
                "current_price": str(pos.current_price),
                "avg_entry_price": str(pos.avg_entry_price),
                "unrealized_pl": str(pos.unrealized_pl),
                "unrealized_plpc": str(pos.unrealized_plpc),
                "asset_class": str(pos.asset_class),
            }
        )

    return {
        "account": get_active_account_name(),
        "position_count": len(pos_list),
        "positions": pos_list,
    }


@mcp.tool
def get_account_info() -> dict:
    """Get account information from the active Alpaca account.

    Returns:
        Dict with account balance, buying power, equity, and trading status.
    """
    from goldflipper.config.config import get_active_account_name

    try:
        client: Any = ctx.alpaca_client
        account = client.get_account()
    except Exception as e:
        return {"error": f"Failed to get account info: {e}"}

    return {
        "account_name": get_active_account_name(),
        "account_number": str(account.account_number),
        "status": str(account.status),
        "cash": str(account.cash),
        "buying_power": str(account.buying_power),
        "portfolio_value": str(account.portfolio_value),
        "equity": str(account.equity),
        "last_equity": str(account.last_equity),
        "long_market_value": str(account.long_market_value),
        "short_market_value": str(account.short_market_value),
        "pattern_day_trader": bool(account.pattern_day_trader),
        "trading_blocked": bool(account.trading_blocked),
        "transfers_blocked": bool(account.transfers_blocked),
        "account_blocked": bool(account.account_blocked),
    }


@mcp.tool
def get_active_account() -> dict:
    """Get the name and details of the currently active Alpaca trading account.

    Returns:
        Dict with account name, nickname, and whether it's a paper account.
    """
    from goldflipper.config.config import get_account_nickname, get_active_account_name

    account_name = get_active_account_name()
    nickname = get_account_nickname(account_name)

    return {
        "account_name": account_name,
        "nickname": nickname,
        "is_paper": "paper" in account_name.lower(),
    }
