"""Order management tools — place, cancel, status, history, preview."""

from typing import Optional

from goldflipper.mcp_server.server import mcp
from goldflipper.mcp_server.context import ctx


@mcp.tool
def get_order_status(order_id: str) -> dict:
    """Get the current status of an order by its Alpaca order ID.

    Args:
        order_id: The Alpaca order ID (UUID string).

    Returns:
        Dict with order details including status, symbol, qty, type, and timestamps.
    """
    try:
        client = ctx.alpaca_client
        order = client.get_order_by_id(order_id)
    except Exception as e:
        return {"error": f"Failed to get order: {e}"}

    return {
        "order_id": str(order.id),
        "client_order_id": str(order.client_order_id),
        "symbol": str(order.symbol),
        "side": str(order.side),
        "type": str(order.type),
        "qty": str(order.qty),
        "filled_qty": str(order.filled_qty),
        "filled_avg_price": str(order.filled_avg_price) if order.filled_avg_price else None,
        "limit_price": str(order.limit_price) if order.limit_price else None,
        "status": str(order.status),
        "time_in_force": str(order.time_in_force),
        "created_at": str(order.created_at) if order.created_at else None,
        "filled_at": str(order.filled_at) if order.filled_at else None,
    }


@mcp.tool
def get_order_history(limit: int = 20, status: Optional[str] = None, symbol: Optional[str] = None) -> dict:
    """Get recent order history from Alpaca.

    Args:
        limit: Maximum number of orders to return (default 20, max 500).
        status: Optional filter: 'open', 'closed', 'all' (default: 'all').
        symbol: Optional symbol filter (e.g., 'AAPL250117C00150000').

    Returns:
        Dict with list of order summaries.
    """
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    limit = min(max(1, limit), 500)

    status_map = {
        "open": QueryOrderStatus.OPEN,
        "closed": QueryOrderStatus.CLOSED,
        "all": QueryOrderStatus.ALL,
    }
    query_status = status_map.get((status or "all").lower(), QueryOrderStatus.ALL)

    try:
        client = ctx.alpaca_client
        request_params = GetOrdersRequest(status=query_status, limit=limit)
        if symbol:
            request_params.symbols = [symbol.upper()]
        orders = client.get_orders(request_params)
    except Exception as e:
        return {"error": f"Failed to get orders: {e}"}

    order_list = []
    for o in orders:
        order_list.append({
            "order_id": str(o.id),
            "symbol": str(o.symbol),
            "side": str(o.side),
            "type": str(o.type),
            "qty": str(o.qty),
            "filled_qty": str(o.filled_qty),
            "status": str(o.status),
            "created_at": str(o.created_at) if o.created_at else None,
        })

    return {"count": len(order_list), "orders": order_list}


@mcp.tool
def preview_order(
    symbol: str,
    trade_type: str,
    strike_price: float,
    expiration_date: str,
    contracts: int,
    action: str = "BTO",
    order_type: str = "limit at bid",
) -> dict:
    """Preview what an order would look like without placing it.

    Resolves the option contract, gets current quotes, and shows the order
    parameters that would be used.

    Args:
        symbol: Stock ticker (e.g., 'AAPL').
        trade_type: 'CALL' or 'PUT'.
        strike_price: Option strike price.
        expiration_date: Option expiration in MM/DD/YYYY format.
        contracts: Number of contracts.
        action: Order action: 'BTO', 'STC', 'STO', 'BTC'.
        order_type: Order type: market, limit at bid, limit at ask, limit at mid, limit at last.

    Returns:
        Dict with resolved contract symbol, current quotes, and estimated order details.
    """
    from goldflipper.strategy.shared.order_executor import OrderExecutor, determine_limit_price

    trade_type = trade_type.upper()
    if trade_type not in ("CALL", "PUT"):
        return {"error": "trade_type must be 'CALL' or 'PUT'"}

    action = action.upper()
    if action not in ("BTO", "STC", "STO", "BTC"):
        return {"error": "action must be one of: BTO, STC, STO, BTC"}

    # Build a minimal play dict for contract resolution
    play = {
        "symbol": symbol.upper(),
        "trade_type": trade_type,
        "strike_price": strike_price,
        "expiration_date": expiration_date,
    }

    executor = OrderExecutor(client=ctx.alpaca_client, market_data=ctx.market_data)

    try:
        contract = executor.get_option_contract(play)
    except Exception as e:
        return {"error": f"Failed to resolve option contract: {e}"}

    if contract is None:
        return {"error": f"No option contract found for {symbol} {trade_type} {strike_price} exp {expiration_date}"}

    contract_symbol = str(contract.symbol)

    # Get current quote
    quote = ctx.market_data.get_option_quote(contract_symbol)
    if quote is None:
        quote = {}

    # Determine price
    limit_price, price_source = determine_limit_price(order_type, quote, quote.get("last", 0.0), "entry")

    estimated_cost = None
    if limit_price and contracts:
        estimated_cost = round(limit_price * contracts * 100, 2)

    return {
        "preview": True,
        "contract_symbol": contract_symbol,
        "action": action,
        "order_type": order_type,
        "contracts": contracts,
        "quote": {
            "bid": quote.get("bid"),
            "ask": quote.get("ask"),
            "last": quote.get("last"),
            "mid": quote.get("mid"),
        },
        "limit_price": round(limit_price, 2) if limit_price else None,
        "price_source": price_source,
        "estimated_cost": estimated_cost,
        "message": "This is a preview only. Use trade_place_order to execute.",
    }


@mcp.tool
def trade_place_order(
    symbol: str,
    trade_type: str,
    strike_price: float,
    expiration_date: str,
    contracts: int,
    action: str = "BTO",
    order_type: str = "limit at bid",
    confirm: bool = False,
) -> dict:
    """Place a trading order through Alpaca.

    This is a Tier 3 operation. With confirm=False (default), returns a preview.
    With confirm=True, submits the order to Alpaca.

    Args:
        symbol: Stock ticker (e.g., 'AAPL').
        trade_type: 'CALL' or 'PUT'.
        strike_price: Option strike price.
        expiration_date: Option expiration in MM/DD/YYYY format.
        contracts: Number of contracts.
        action: Order action: 'BTO', 'STC', 'STO', 'BTC'.
        order_type: Order type: market, limit at bid, limit at ask, limit at mid, limit at last.
        confirm: Set to True to actually place the order. Default False returns a preview.

    Returns:
        Preview of the order (confirm=False) or order result (confirm=True).
    """
    from goldflipper.strategy.shared.order_executor import OrderExecutor
    from goldflipper.strategy.base import OrderAction

    trade_type = trade_type.upper()
    if trade_type not in ("CALL", "PUT"):
        return {"error": "trade_type must be 'CALL' or 'PUT'"}

    action = action.upper()
    action_map = {
        "BTO": OrderAction.BUY_TO_OPEN,
        "STC": OrderAction.SELL_TO_CLOSE,
        "STO": OrderAction.SELL_TO_OPEN,
        "BTC": OrderAction.BUY_TO_CLOSE,
    }
    if action not in action_map:
        return {"error": "action must be one of: BTO, STC, STO, BTC"}

    order_action = action_map[action]

    # Build play dict for contract resolution
    play = {
        "symbol": symbol.upper(),
        "trade_type": trade_type,
        "strike_price": strike_price,
        "expiration_date": expiration_date,
    }

    executor = OrderExecutor(client=ctx.alpaca_client, market_data=ctx.market_data)

    try:
        contract = executor.get_option_contract(play)
    except Exception as e:
        return {"error": f"Failed to resolve option contract: {e}"}

    if contract is None:
        return {"error": f"No option contract found for {symbol} {trade_type} {strike_price} exp {expiration_date}"}

    contract_symbol = str(contract.symbol)

    # Get current quote for pricing
    quote = ctx.market_data.get_option_quote(contract_symbol) or {}

    if not confirm:
        from goldflipper.strategy.shared.order_executor import determine_limit_price

        limit_price, price_source = determine_limit_price(order_type, quote, quote.get("last", 0.0), "entry")
        return {
            "preview": True,
            "contract_symbol": contract_symbol,
            "action": action,
            "order_type": order_type,
            "contracts": contracts,
            "limit_price": round(limit_price, 2) if limit_price else None,
            "price_source": price_source,
            "quote": {"bid": quote.get("bid"), "ask": quote.get("ask"), "last": quote.get("last")},
            "message": "Set confirm=True to execute this order.",
        }

    # Execute the order
    try:
        is_entry = order_action.is_buy() if action in ("BTO", "STO") else not order_action.is_buy()

        if action in ("BTO", "STO"):
            order_req, is_limit = executor.create_entry_order(
                contract_symbol, contracts, order_type, quote, action=order_action
            )
        else:
            fallback_price = quote.get("last", 0.0)
            order_req, is_limit = executor.create_exit_order(
                contract_symbol, contracts, order_type, quote, fallback_price, action=order_action
            )

        if order_req is None:
            # Market exit — use close_position
            result = executor.close_position_market(contract_symbol, contracts)
            return {
                "order_placed": True,
                "method": "close_position_market",
                "contract_symbol": contract_symbol,
                "contracts": contracts,
            }

        order = ctx.alpaca_client.submit_order(order_req)

        return {
            "order_placed": True,
            "order_id": str(order.id),
            "symbol": str(order.symbol),
            "side": str(order.side),
            "type": str(order.type),
            "qty": str(order.qty),
            "limit_price": str(order.limit_price) if order.limit_price else None,
            "status": str(order.status),
        }
    except Exception as e:
        return {"error": f"Order placement failed: {e}"}


@mcp.tool
def trade_cancel_order(order_id: str, confirm: bool = False) -> dict:
    """Cancel an open order.

    This is a Tier 3 operation. With confirm=False (default), returns a preview.
    With confirm=True, cancels the order.

    Args:
        order_id: The Alpaca order ID to cancel.
        confirm: Set to True to actually cancel. Default False returns a preview.

    Returns:
        Preview or confirmation of cancellation.
    """
    # First get the order to show what we're cancelling
    try:
        client = ctx.alpaca_client
        order = client.get_order_by_id(order_id)
    except Exception as e:
        return {"error": f"Failed to find order: {e}"}

    if not confirm:
        return {
            "preview": True,
            "order_id": str(order.id),
            "symbol": str(order.symbol),
            "side": str(order.side),
            "qty": str(order.qty),
            "status": str(order.status),
            "message": "Set confirm=True to cancel this order.",
        }

    try:
        client.cancel_order_by_id(order_id)
    except Exception as e:
        return {"error": f"Cancel failed: {e}"}

    return {"order_id": order_id, "cancelled": True, "symbol": str(order.symbol)}


@mcp.tool
def trade_close_position(symbol: str, qty: Optional[int] = None, confirm: bool = False) -> dict:
    """Close an open position (partial or full).

    This is a Tier 3 operation. With confirm=False (default), returns a preview.
    With confirm=True, closes the position.

    Args:
        symbol: The position symbol (stock or option contract symbol).
        qty: Number of shares/contracts to close. None = close entire position.
        confirm: Set to True to actually close. Default False returns a preview.

    Returns:
        Preview or confirmation of position closure.
    """
    try:
        client = ctx.alpaca_client
        # Get the position first
        position = client.get_open_position(symbol.upper())
    except Exception as e:
        return {"error": f"No open position found for {symbol}: {e}"}

    close_qty = qty or int(float(str(position.qty)))

    if not confirm:
        return {
            "preview": True,
            "symbol": str(position.symbol),
            "current_qty": str(position.qty),
            "close_qty": close_qty,
            "side": str(position.side),
            "market_value": str(position.market_value),
            "unrealized_pl": str(position.unrealized_pl),
            "message": "Set confirm=True to close this position.",
        }

    try:
        from alpaca.trading.requests import ClosePositionRequest

        result = client.close_position(
            symbol_or_asset_id=symbol.upper(),
            close_options=ClosePositionRequest(qty=str(close_qty)),
        )

        return {
            "closed": True,
            "symbol": symbol.upper(),
            "qty_closed": close_qty,
            "order_id": str(result.id) if hasattr(result, "id") else None,
        }
    except Exception as e:
        return {"error": f"Close position failed: {e}"}
