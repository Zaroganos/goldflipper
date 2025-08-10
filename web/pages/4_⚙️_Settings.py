import streamlit as st
import sys
from pathlib import Path
import logging
import uuid
from datetime import datetime
from typing import Dict, Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from goldflipper.database.connection import get_db_connection
from sqlalchemy import text as sql_text

# Page configuration
st.set_page_config(page_title="Goldflipper Settings", page_icon="⚙️", layout="wide")
logger = logging.getLogger(__name__)

def _ensure_user_settings_table() -> None:
    """Ensure user_settings table exists in DuckDB."""
    try:
        with get_db_connection() as session:
            session.execute(
                sql_text(
                    """
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id VARCHAR PRIMARY KEY,
                        category VARCHAR NOT NULL,
                        key VARCHAR,
                        value VARCHAR,
                        last_modified TIMESTAMP
                    )
                    """
                )
            )
            # Best-effort: add unique constraint if not present (DuckDB lacks IF NOT EXISTS for constraints)
            try:
                session.execute(sql_text("CREATE UNIQUE INDEX IF NOT EXISTS uix_user_settings_cat_key ON user_settings(category, key)"))
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Failed to ensure user_settings table exists: {e}")

def _load_category(category: str) -> Dict[str, Any]:
    """Load a settings category from DuckDB and build nested dict."""
    try:
        with get_db_connection() as session:
            rows = session.execute(
                sql_text("SELECT key, value FROM user_settings WHERE category = :c"),
                {"c": category},
            ).fetchall()
        import json
        cfg: Dict[str, Any] = {}
        for key, raw in rows:
            val = raw
            if isinstance(raw, str):
                try:
                    val = json.loads(raw)
                except Exception:
                    low = raw.strip().lower()
                    if low in ("true", "false"):
                        val = (low == "true")
                    else:
                        try:
                            val = float(raw) if "." in raw else int(raw)
                        except Exception:
                            val = raw
            parts = key.split(".") if key else []
            if not parts:
                if isinstance(val, dict):
                    cfg.update(val)
                continue
            cursor = cfg
            for p in parts[:-1]:
                cursor = cursor.setdefault(p, {})
            cursor[parts[-1]] = val
        return cfg
    except Exception as e:
        logger.error(f"Failed to load category {category}: {e}")
        return {}

def _upsert(category: str, key: str, value: Any) -> tuple[bool, str | None]:
    """Upsert a single key into DuckDB using delete-then-insert.

    Returns (ok, error_message).
    """
    import json
    try:
        value_json = json.dumps(value)
        params = {
            "category": category,
            "key": key,
            "value": value_json,
            "ts": datetime.utcnow().isoformat(),
        }
        with get_db_connection() as session:
            # Delete any existing row, then insert fresh
            session.execute(
                sql_text(
                    'DELETE FROM user_settings WHERE category=:category AND "key"=:key'
                ),
                params,
            )
            params_with_id = {**params, "id": str(uuid.uuid4())}
            session.execute(
                sql_text(
                    'INSERT INTO user_settings (id, category, "key", "value", "last_modified") VALUES (:id, :category, :key, :value, :ts)'
                ),
                params_with_id,
            )
        return True, None
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        logger.error(f"Upsert failed for {category}.{key}: {msg}")
        return False, msg

def main():
    st.title("Goldflipper Settings (DB-only)")

    tabs = st.tabs(["Market Data", "Logging", "System"])  # Trading can be added later

    # Market Data
    with tabs[0]:
        st.header("Market Data Providers")

        md = _load_category("market_data_providers")
        defaults = {
            "primary_provider": "marketdataapp",
            "expiration_provider": "yfinance",
            "providers": {
                "marketdataapp": {"enabled": True, "api_key": ""},
                "yfinance": {"enabled": False},
                "alpaca": {"enabled": False, "use_websocket": False},
            },
            "fallback": {"enabled": True, "order": ["marketdataapp", "yfinance", "alpaca"], "max_attempts": 3},
        }

        def get(path: str, default=None):
            cursor = md
            for p in path.split("."):
                if isinstance(cursor, dict) and p in cursor:
                    cursor = cursor[p]
                else:
                    return default
            return cursor

        col1, col2 = st.columns(2)
        with col1:
            primary_provider = st.selectbox(
                "Primary Provider",
                ["marketdataapp", "yfinance", "alpaca"],
                index=["marketdataapp", "yfinance", "alpaca"].index(
                    get("primary_provider", defaults["primary_provider"])
                ),
            )
        with col2:
            expiration_provider = st.selectbox(
                "Expiration Provider",
                ["yfinance", "marketdataapp", "alpaca"],
                index=["yfinance", "marketdataapp", "alpaca"].index(
                    get("expiration_provider", defaults["expiration_provider"]) 
                ),
            )

        st.subheader("Providers")
        mda = get("providers.marketdataapp", defaults["providers"]["marketdataapp"]) or {}
        with st.expander("MarketData.app", expanded=True):
            mda_enabled = st.checkbox("Enabled", value=bool(mda.get("enabled", True)), key="mda_enabled")
            mda_api = st.text_input("API Key", value=str(mda.get("api_key", "")), type="password")

        yf = get("providers.yfinance", defaults["providers"]["yfinance"]) or {}
        with st.expander("yfinance", expanded=False):
            yf_enabled = st.checkbox("Enabled", value=bool(yf.get("enabled", False)), key="yf_enabled")
            st.caption("No API key required.")

        ap = get("providers.alpaca", defaults["providers"]["alpaca"]) or {}
        with st.expander("Alpaca (market data)", expanded=False):
            ap_enabled = st.checkbox("Enabled", value=bool(ap.get("enabled", False)), key="alpaca_enabled")
            ap_ws = st.checkbox("Use WebSocket (experimental)", value=bool(ap.get("use_websocket", False)), key="alpaca_ws")
            st.caption("Trading keys configured elsewhere. This toggles market data usage only.")

        st.subheader("Fallback")
        fb = get("fallback", defaults["fallback"]) or {}
        fb_enabled = st.checkbox("Enable Fallback", value=bool(fb.get("enabled", True)), key="fallback_enabled")
        fb_order = st.multiselect(
            "Fallback Order",
            options=["marketdataapp", "yfinance", "alpaca"],
            default=[p for p in (fb.get("order") or defaults["fallback"]["order"]) if p in ["marketdataapp", "yfinance", "alpaca"]],
            help="Order in which providers are tried if the primary fails"
        )
        fb_max = st.number_input("Max Attempts", min_value=1, max_value=5, value=int(fb.get("max_attempts", 3)))

        col_s, col_t = st.columns(2)
        with col_s:
            if st.button("Save Market Data Settings", type="primary"):
                _ensure_user_settings_table()
                ok = True
                failures = []
                for k, v in [
                    ("primary_provider", primary_provider),
                    ("expiration_provider", expiration_provider),
                    ("providers.marketdataapp.enabled", bool(mda_enabled)),
                    ("providers.marketdataapp.api_key", str(mda_api or "")),
                    ("providers.yfinance.enabled", bool(yf_enabled)),
                    ("providers.alpaca.enabled", bool(ap_enabled)),
                    ("providers.alpaca.use_websocket", bool(ap_ws)),
                    ("fallback.enabled", bool(fb_enabled)),
                    ("fallback.order", fb_order),
                    ("fallback.max_attempts", int(fb_max)),
                ]:
                    result_ok, err = _upsert("market_data_providers", k, v)
                    if not result_ok:
                        ok = False
                        failures.append(f"{k}: {err}")
                if ok:
                    st.success("Saved to database.")
                else:
                    st.error("One or more settings failed to save:")
                    if failures:
                        st.code("\n".join(failures))

        with col_t:
            if st.button("Apply & Test Market Data"):
                # Clear cached resources in other pages upon rerun
                try:
                    st.cache_resource.clear()
                except Exception:
                    pass
                try:
                    import importlib, sys as _sys
                    # Hot-reload market data modules to pick up recent edits
                    for _mod in [
                        'goldflipper.data.market.cache',
                        'goldflipper.data.market.providers.marketdataapp_provider',
                        'goldflipper.data.market.providers.alpaca_provider',
                        'goldflipper.data.market.providers.yfinance_provider',
                        'goldflipper.data.market.manager',
                    ]:
                        if _mod in _sys.modules:
                            importlib.reload(_sys.modules[_mod])
                    from goldflipper.data.market.manager import MarketDataManager
                    mgr = MarketDataManager()
                    price = mgr.get_stock_price("SPY", regular_hours_only=True)
                    if price is not None:
                        st.success(f"Market data OK. SPY last: {price:.2f}")
                    else:
                        st.warning("Market data call returned no price. Check provider/API key.")
                except Exception as e:
                    st.error(f"Test failed: {e}")

    # Logging (placeholder: DB-only UI to be designed later)
    with tabs[1]:
        st.header("Logging Settings")
        st.info("Logging settings editor (DB-only) will be added in a future update.")

    # System settings (placeholder)
    with tabs[2]:
        st.header("System Settings")
        st.info("System settings editor will be added here, including DB directory selection.")

if __name__ == "__main__":
    main() 