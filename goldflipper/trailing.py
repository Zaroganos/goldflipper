import logging
from datetime import datetime
from typing import Optional, Dict, Any
from Goldflipper.config.config import config


def _get_trade_type(play: Dict[str, Any]) -> str:
    return (play.get('trade_type') or '').upper()


def trailing_tp_enabled(play: Dict[str, Any]) -> bool:
    if not config.get('trailing', 'enabled', default=False):
        return False
    tp = play.get('take_profit') or {}
    cfg = tp.get('trailing_config') or {}
    # Fall back to config default if play doesn't specify
    enabled = cfg.get('enabled')
    if enabled is None:
        enabled = config.get('trailing', 'take_profit', 'default_enabled', default=False)
    return bool(enabled)


def trailing_sl_enabled(play: Dict[str, Any]) -> bool:
    if not config.get('trailing', 'enabled', default=False):
        return False
    sl = play.get('stop_loss') or {}
    cfg = sl.get('trailing_config') or {}
    enabled = cfg.get('enabled')
    if enabled is None:
        enabled = config.get('trailing', 'stop_loss', 'default_enabled', default=False)
    return bool(enabled)


def has_trailing_enabled(play: Dict[str, Any]) -> bool:
    return trailing_tp_enabled(play) or trailing_sl_enabled(play)


def _init_trail_state(section: Dict[str, Any]) -> Dict[str, Any]:
    state = section.get('trail_state')
    if state is None:
        state = {
            'current_trail_level': None,
            'highest_favorable_price': None,
            'last_update_timestamp': None,
            # both TP and SL may use these flags; harmless if unused
            'trail_activated': False,
            'breakeven_activated': False,
        }
        section['trail_state'] = state
    if 'trail_history' not in section:
        section['trail_history'] = []
    return state


def _update_peak_price(play: Dict[str, Any], current_stock_price: Optional[float]) -> None:
    if current_stock_price is None:
        return
    trade_type = _get_trade_type(play)

    for key in ['take_profit', 'stop_loss']:
        sec = play.get(key) or {}
        state = _init_trail_state(sec)
        peak = state.get('highest_favorable_price')
        if peak is None:
            state['highest_favorable_price'] = current_stock_price
        else:
            if trade_type == 'CALL':
                if current_stock_price > peak:
                    state['highest_favorable_price'] = current_stock_price
            elif trade_type == 'PUT':
                if current_stock_price < peak:
                    state['highest_favorable_price'] = current_stock_price


def _activation_met(play: Dict[str, Any], section_name: str, current_stock_price: Optional[float]) -> bool:
    if current_stock_price is None:
        return False
    section = play.get(section_name) or {}
    cfg = section.get('trailing_config') or {}
    if not cfg.get('enabled'):
        return False
    # fallback to config defaults
    if section_name == 'take_profit':
        threshold = cfg.get('activation_threshold_pct')
        if threshold in (None, 0):
            threshold = config.get('trailing', 'take_profit', 'activation_threshold_pct', default=0)
    else:
        threshold = cfg.get('activation_threshold_pct')
        if threshold in (None, 0):
            threshold = config.get('trailing', 'stop_loss', 'activation_threshold_pct', default=0)
    if threshold in (None, 0):
        return True
    entry_price = (play.get('entry_point') or {}).get('entry_stock_price')
    if not entry_price:
        return True  # if missing, don't block activation
    trade_type = _get_trade_type(play)
    move_pct = (current_stock_price - entry_price) / entry_price * 100.0
    if trade_type == 'CALL':
        return move_pct >= float(threshold)
    else:  # PUT
        return (-move_pct) >= float(threshold)


def _calc_percentage_trail(trade_type: str, peak_price: float, pct: float) -> float:
    if trade_type == 'CALL':
        return peak_price * (1.0 - pct / 100.0)
    else:  # PUT
        return peak_price * (1.0 + pct / 100.0)


def _calc_fixed_trail(trade_type: str, peak_price: float, amt: float) -> float:
    if trade_type == 'CALL':
        return peak_price - amt
    else:
        return peak_price + amt


def _compute_trail_level(play: Dict[str, Any], section_name: str) -> Optional[float]:
    section = play.get(section_name) or {}
    cfg = section.get('trailing_config') or {}
    state = _init_trail_state(section)
    peak = state.get('highest_favorable_price')
    if not cfg.get('enabled') or peak is None:
        return None
    trade_type = _get_trade_type(play)
    # Merge with defaults from config
    defaults = config.get('trailing', 'take_profit' if section_name == 'take_profit' else 'stop_loss', default={}) or {}
    trail_type = (cfg.get('trail_type') or defaults.get('trail_type') or 'percentage').lower()
    try:
        if trail_type == 'percentage':
            pct = float(cfg.get('trail_distance_pct') or defaults.get('trail_distance_pct') or 0)
            if pct <= 0:
                return None
            return _calc_percentage_trail(trade_type, float(peak), pct)
        elif trail_type in ('fixed', 'fixed_amount'):
            amt = float(cfg.get('trail_distance_fixed') or defaults.get('trail_distance_fixed') or 0)
            if amt <= 0:
                return None
            return _calc_fixed_trail(trade_type, float(peak), amt)
        else:
            # ATR or unsupported; to be implemented later
            return None
    except Exception as e:
        logging.warning(f"Error computing trail level for {section_name}: {e}")
        return None


def _append_history(section: Dict[str, Any], kind: str, old_level: Optional[float], new_level: float) -> None:
    history = section.get('trail_history')
    if history is None:
        history = []
        section['trail_history'] = history
    history.append({
        'timestamp': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        'trail_type': kind,
        'old_level': old_level,
        'new_level': new_level,
        'reason': 'recalc'
    })


def update_trailing_levels(play: Dict[str, Any], current_stock_price: Optional[float], current_premium: Optional[float]) -> bool:
    """
    Update trailing state for TP/SL without changing system behavior.
    Safe to call every monitoring cycle. Does nothing unless trailing is enabled.
    Returns True if any trail level ratcheted (changed), else False.
    """
    changed: bool = False
    try:
        if not has_trailing_enabled(play):
            return False

        # Track peak favorable stock price
        _update_peak_price(play, current_stock_price)

        # Update TP trail level
        if trailing_tp_enabled(play) and _activation_met(play, 'take_profit', current_stock_price):
            tp = play.get('take_profit') or {}
            tp_state = _init_trail_state(tp)
            new_level = _compute_trail_level(play, 'take_profit')
            if new_level is not None:
                old_level = tp_state.get('current_trail_level')
                # Only ratchet in favorable direction (never loosen)
                if old_level is None or (new_level > old_level if _get_trade_type(play) == 'CALL' else new_level < old_level):
                    tp_state['current_trail_level'] = new_level
                    tp_state['last_update_timestamp'] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
                    tp_state['trail_activated'] = True
                    _append_history(tp, 'TP', old_level, new_level)
                    changed = True

        # Update SL trail level
        if trailing_sl_enabled(play) and _activation_met(play, 'stop_loss', current_stock_price):
            sl = play.get('stop_loss') or {}
            sl_state = _init_trail_state(sl)
            new_level = _compute_trail_level(play, 'stop_loss')
            if new_level is not None:
                old_level = sl_state.get('current_trail_level')
                if old_level is None or (new_level > old_level if _get_trade_type(play) == 'CALL' else new_level < old_level):
                    sl_state['current_trail_level'] = new_level
                    sl_state['last_update_timestamp'] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
                    _append_history(sl, 'SL', old_level, new_level)
                    changed = True

    except Exception as e:
        logging.warning(f"Trailing update failed: {e}")
        return changed
    return changed

