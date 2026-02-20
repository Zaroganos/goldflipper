"""Analytics and trade logging tools — summary stats, trade log queries, export."""

from typing import Any

from goldflipper.mcp_server.server import mcp


def _get_logger():
    """Get a PlayLogger instance."""
    from goldflipper.trade_logging.trade_logger import PlayLogger

    return PlayLogger(save_to_desktop=False, enable_backfill=False)


@mcp.tool
def get_trade_summary(strategy: str | None = None) -> dict:
    """Get summary statistics from the trade log.

    Args:
        strategy: Optional strategy name to filter by (e.g., 'option_swings').
                  None or 'All' returns stats for all strategies.

    Returns:
        Dict with total trades, winning trades, win rate, and total P&L.
    """
    try:
        logger = _get_logger()
        stats_df = logger._create_summary_stats(strategy_filter=strategy)
    except FileNotFoundError:
        return {"error": "Trade log file not found. Run import_closed_plays first."}
    except Exception as e:
        return {"error": f"Failed to calculate summary: {e}"}

    row = stats_df.iloc[0]
    result = {
        "total_trades": int(row["total_trades"]),
        "winning_trades": int(row["winning_trades"]),
        "losing_trades": int(row["total_trades"]) - int(row["winning_trades"]),
        "win_rate_pct": round(float(row["win_rate"]), 2),
        "total_pl": round(float(row["total_pl"]), 2),
    }
    if strategy and strategy != "All":
        result["strategy_filter"] = strategy
    return result


@mcp.tool
def get_trade_log(limit: int = 50, strategy: str | None = None, symbol: str | None = None) -> dict:
    """Read recent entries from the trade log CSV.

    Args:
        limit: Maximum number of trades to return (default 50).
        strategy: Optional strategy filter.
        symbol: Optional symbol filter.

    Returns:
        Dict with list of trade entries and count.
    """
    import pandas as pd

    try:
        logger = _get_logger()
        df = pd.read_csv(logger.csv_path)
    except FileNotFoundError:
        return {"error": "Trade log file not found."}
    except Exception as e:
        return {"error": f"Failed to read trade log: {e}"}

    # Apply filters
    if strategy and strategy != "All" and "strategy" in df.columns:
        df = df.loc[df["strategy"] == strategy]
    if symbol and "symbol" in df.columns:
        df = df.loc[df["symbol"] == symbol.upper()]

    # Take the most recent entries
    df = df.tail(limit)

    trades = []
    for _, row in df.iterrows():
        trade = {}
        for col in df.columns:
            val = row[col]
            try:
                is_null = bool(pd.isna(val))
            except Exception:
                is_null = False
            if is_null:
                trade[col] = None
            else:
                trade[col] = val
        trades.append(trade)

    return {"count": len(trades), "total_in_log": len(df), "trades": trades}


@mcp.tool
def list_logged_strategies() -> dict:
    """List all unique strategy names found in the trade log.

    Returns:
        Dict with list of strategy names.
    """
    try:
        logger = _get_logger()
        strategies = logger.get_unique_strategies()
    except Exception as e:
        return {"error": f"Failed to read strategies from log: {e}"}

    return {"strategies": strategies, "count": len(strategies)}


@mcp.tool
def refresh_trade_log(mode: str = "closed", confirm: bool = False) -> dict:
    """Re-import play files into the trade log CSV.

    This rebuilds the trade log from play JSON files on disk.

    Args:
        mode: 'closed' to import only closed/expired plays (default),
              'all' to import from all status folders.
        confirm: Set to True to actually run. Default False returns a preview.

    Returns:
        Preview or result of the import.
    """
    if mode not in ("closed", "all"):
        return {"error": "mode must be 'closed' or 'all'"}

    if not confirm:
        return {
            "preview": True,
            "mode": mode,
            "message": f"Would rebuild trade log from {'closed/expired' if mode == 'closed' else 'all'} play files. "
            "This resets the current trade log. Set confirm=True to execute.",
        }

    try:
        logger = _get_logger()
        if mode == "all":
            count = logger.import_all_plays()
        else:
            count = logger.import_closed_plays()
    except Exception as e:
        return {"error": f"Import failed: {e}"}

    return {"imported": count, "mode": mode}


@mcp.tool
def export_trade_log(format: str = "both") -> dict:
    """Export the trade log to CSV and/or Excel files.

    Args:
        format: Export format: 'csv', 'excel', or 'both' (default).

    Returns:
        Dict with paths to the exported files.
    """
    if format not in ("csv", "excel", "both"):
        return {"error": "format must be 'csv', 'excel', or 'both'"}

    try:
        logger = _get_logger()
        result: dict[str, Any] = logger.export_to_spreadsheet(format=format, save_to_desktop=False)
    except Exception as e:
        return {"error": f"Export failed: {e}"}

    return {
        "exported": True,
        "format": format,
        "export_dir": result.get("export_dir"),
        "csv_file": result.get("csv_file"),
        "excel_file": result.get("excel_file"),
    }
