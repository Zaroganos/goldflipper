import logging
from datetime import datetime, timezone, time
from typing import Optional, Dict, Any
from goldflipper.config.config import config


def _get_trade_type(play: Dict[str, Any]) -> str:
    return (play.get('trade_type') or '').upper()


def trailing_tp_enabled(play: Dict[str, Any]) -> bool:
    if not config.get('trailing', 'enabled', default=False):
        return False
    # Per-play override: enable only if play sets trailing_config.enabled True OR trailing column provided
    tp = play.get('take_profit') or {}
    cfg = tp.get('trailing_config') or {}
    # Allow activation_threshold override from play
    if 'trailing_activation_pct' in tp:
        cfg['enabled'] = True
        tp['trailing_config'] = cfg
    enabled = cfg.get('enabled')
    return bool(enabled)


def trailing_sl_enabled(play: Dict[str, Any]) -> bool:
    if not config.get('trailing', 'enabled', default=False):
        return False
    # For now, SL trailing is stubbed - allow config to enable later
    sl = play.get('stop_loss') or {}
    cfg = sl.get('trailing_config') or {}
    enabled = cfg.get('enabled')
    if enabled is None:
        enabled = False
    return bool(enabled)


def has_trailing_enabled(play: Dict[str, Any]) -> bool:
    return trailing_tp_enabled(play) or trailing_sl_enabled(play)


def _init_trail_state(section: Dict[str, Any]) -> Dict[str, Any]:
    state = section.get('trail_state')
    if state is None:
        state = {
            # Legacy field, not used in new design but kept for compatibility/logging
            'current_trail_level': None,
            # High-water-marks
            'highest_favorable_stock': None,
            'highest_favorable_premium': None,
            # Activation and timestamps
            'trail_activated': False,
            'activation_timestamp': None,
            'last_update_timestamp': None,
            # TP1/TP2 state (premium-centric; stock optional)
            'tp1': {
                'basis': None,                 # profit_capture | distance_from_current
                'current_capture_pct': None,   # used if basis=profit_capture
                'distance_below_pct': None,    # used if basis=distance_from_current
                'level_premium': None,
                'level_stock': None,
                'last_set_timestamp': None,
            },
            'tp2': {
                'basis': None,                 # profit_capture | distance_from_current
                'start_at_original_tp': True,
                'distance_above_pct': None,    # used if basis=distance_from_current
                'capture_pct': None,           # used if basis=profit_capture
                'level_premium': None,
                'level_stock': None,
                'last_set_timestamp': None,
                'moved_from_original': False,
            },
            # Original TP anchors (for monotonic max rule)
            'original_tp_premium': None,
            'original_tp_stock': None,
            # Ratcheting markers
            'last_ratchet_premium': None,
            'last_ratchet_date': None,
            # Backwards compatibility flags
            'breakeven_activated': False,
        }
        section['trail_state'] = state
    if 'trail_history' not in section:
        section['trail_history'] = []
    return state


def _update_high_water_marks(play: Dict[str, Any], current_stock_price: Optional[float], current_premium: Optional[float]) -> None:
    trade_type = _get_trade_type(play)
    for key in ['take_profit', 'stop_loss']:
        sec = play.get(key) or {}
        state = _init_trail_state(sec)
        # Stock high-water
        if current_stock_price is not None:
            peak_stock = state.get('highest_favorable_stock')
            if peak_stock is None:
                state['highest_favorable_stock'] = current_stock_price
            else:
                if trade_type == 'CALL':
                    if current_stock_price > peak_stock:
                        state['highest_favorable_stock'] = current_stock_price
                elif trade_type == 'PUT':
                    if current_stock_price < peak_stock:
                        state['highest_favorable_stock'] = current_stock_price
        # Premium high-water
        if current_premium is not None:
            peak_prem = state.get('highest_favorable_premium')
            if peak_prem is None:
                state['highest_favorable_premium'] = current_premium
            else:
                if trade_type in ('CALL', 'PUT'):
                    if current_premium > peak_prem:
                        state['highest_favorable_premium'] = current_premium


def _activation_met(play: Dict[str, Any], current_stock_price: Optional[float], current_premium: Optional[float]) -> bool:
    """Delayed activation: trigger when absolute gain since entry reaches threshold.
    Consider whichever TP basis is enabled (premium or stock price)."""
    if not trailing_tp_enabled(play):
        return False
    # Per-play override wins; fallback to global default
    tp = play.get('take_profit') or {}
    per_play_threshold = tp.get('trailing_activation_pct')
    threshold = float(per_play_threshold if per_play_threshold not in (None, '') else config.get('trailing', 'activation_threshold_pct', default=0) or 0)
    if threshold <= 0:
        return True
    trade_type = _get_trade_type(play)
    entry = play.get('entry_point') or {}
    # Check premium-based TP
    premium_tp_enabled = (play.get('take_profit') or {}).get('premium_pct') not in (None, 0)
    stock_tp_enabled = (play.get('take_profit') or {}).get('stock_price_pct') not in (None, 0) or (play.get('take_profit') or {}).get('stock_price') not in (None, 0)
    activated_by_premium = False
    activated_by_stock = False
    entry_prem = entry.get('entry_premium')
    if premium_tp_enabled and current_premium is not None and entry_prem:
        prem_gain_pct = (current_premium - float(entry_prem)) / float(entry_prem) * 100.0
        activated_by_premium = prem_gain_pct >= threshold
    entry_stock = entry.get('entry_stock_price')
    if stock_tp_enabled and current_stock_price is not None and entry_stock:
        move_pct = (float(current_stock_price) - float(entry_stock)) / float(entry_stock) * 100.0
        if trade_type == 'CALL':
            activated_by_stock = move_pct >= threshold
        else:
            activated_by_stock = (-move_pct) >= threshold
    # If neither specific TP type is configured, fall back to either source if available
    return activated_by_premium or activated_by_stock


def _calc_floor_from_current_premium(current_premium: float, distance_below_pct: float) -> float:
    return float(current_premium) * (1.0 - float(distance_below_pct) / 100.0)


def _calc_ceiling_from_current_premium(current_premium: float, distance_above_pct: float) -> float:
    return float(current_premium) * (1.0 + float(distance_above_pct) / 100.0)


def _get_trailing_config_defaults() -> Dict[str, Any]:
    return {
        'update_mode': (config.get('trailing', 'update_mode', default='eod') or 'eod').lower(),
        'update_frequency_seconds': float(config.get('trailing', 'update_frequency_seconds', default=30) or 30),
        'tp1': {
            'basis': (config.get('trailing', 'tp1', 'basis', default='profit_capture') or 'profit_capture').lower(),
            'start_capture_pct': float(config.get('trailing', 'tp1', 'start_capture_pct', default=10.0) or 10.0),
            'start_distance_below_pct': float(config.get('trailing', 'tp1', 'start_distance_below_pct', default=30.0) or 30.0),
            'min_gap_below_current_pct': float(config.get('trailing', 'tp1', 'min_gap_below_current_pct', default=20.0) or 20.0),
            'ratcheting': {
                'enabled': bool(config.get('trailing', 'tp1', 'ratcheting', 'enabled', default=True)),
                'min_rise_since_last_pct': float(config.get('trailing', 'tp1', 'ratcheting', 'min_rise_since_last_pct', default=30.0) or 30.0),
                'ratchet_factor': float(config.get('trailing', 'tp1', 'ratcheting', 'ratchet_factor', default=1.0) or 1.0),
            }
        },
        'tp2': {
            'basis': (config.get('trailing', 'tp2', 'basis', default='distance_from_current') or 'distance_from_current').lower(),
            'start_at_original_tp': bool(config.get('trailing', 'tp2', 'start_at_original_tp', default=True)),
            'distance_above_pct': float(config.get('trailing', 'tp2', 'distance_above_pct', default=20.0) or 20.0),
            'capture_pct': float(config.get('trailing', 'tp2', 'capture_pct', default=0.0) or 0.0),
        }
    }


def _append_history(section: Dict[str, Any], kind: str, old_level: Optional[float], new_level: float, reason: str = 'recalc') -> None:
    history = section.get('trail_history')
    if history is None:
        history = []
        section['trail_history'] = history
    history.append({
        'timestamp': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        'trail_type': kind,
        'old_level': old_level,
        'new_level': new_level,
        'reason': reason,
    })


def _is_end_of_day_now() -> bool:
    try:
        end_str = config.get('market_hours', 'regular_hours', 'end', default='16:16') or '16:16'
        hh, mm = [int(x) for x in end_str.split(':')]
        end_t = time(hh, mm)
    except Exception:
        end_t = time(16, 16)
    now = datetime.now().astimezone() if datetime.now().tzinfo else datetime.now()
    return now.time() >= end_t


def _today_date_str() -> str:
    return datetime.utcnow().date().isoformat()


def _init_on_activation(play: Dict[str, Any], current_stock_price: Optional[float], current_premium: Optional[float]) -> None:
    tp = play.get('take_profit') or {}
    state = _init_trail_state(tp)
    if state.get('trail_activated'):
        return
    defaults = _get_trailing_config_defaults()

    # Record original TPs for ceiling floor anchors
    state['original_tp_premium'] = (tp.get('TP_option_prem') if tp.get('TP_option_prem') else None)
    state['original_tp_stock'] = (tp.get('TP_stock_price_target') if tp.get('TP_stock_price_target') else tp.get('stock_price'))

    # Initialize TP1
    tp1 = state['tp1']
    tp1['basis'] = defaults['tp1']['basis']
    if tp1['basis'] == 'profit_capture':
        tp1['current_capture_pct'] = defaults['tp1']['start_capture_pct']
        entry_prem = (play.get('entry_point') or {}).get('entry_premium')
        if entry_prem:
            tp1_level = float(entry_prem) * (1.0 + float(tp1['current_capture_pct']) / 100.0)
            tp1['level_premium'] = tp1_level
    else:
        tp1['distance_below_pct'] = defaults['tp1']['start_distance_below_pct']
        if current_premium is not None:
            tp1['level_premium'] = _calc_floor_from_current_premium(current_premium, tp1['distance_below_pct'])
    tp1['last_set_timestamp'] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'

    # Initialize TP2
    tp2 = state['tp2']
    tp2['basis'] = defaults['tp2']['basis']
    tp2['start_at_original_tp'] = defaults['tp2']['start_at_original_tp']
    tp2['distance_above_pct'] = defaults['tp2']['distance_above_pct']
    tp2['capture_pct'] = defaults['tp2']['capture_pct']
    # Initially set to original TP where possible
    if tp2['start_at_original_tp']:
        tp2['level_premium'] = state['original_tp_premium']
        tp2['level_stock'] = state['original_tp_stock']
        tp2['moved_from_original'] = False
    else:
        # Place immediately at trailing ceiling
        if tp2['basis'] == 'distance_from_current' and current_premium is not None:
            tp2['level_premium'] = _calc_ceiling_from_current_premium(current_premium, tp2['distance_above_pct'])
        elif tp2['basis'] == 'profit_capture':
            entry_prem = (play.get('entry_point') or {}).get('entry_premium')
            if entry_prem and tp2['capture_pct']:
                tp2['level_premium'] = float(entry_prem) * (1.0 + float(tp2['capture_pct']) / 100.0)
        tp2['moved_from_original'] = True
    tp2['last_set_timestamp'] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'

    # Activate and set ratchet marker
    state['trail_activated'] = True
    state['activation_timestamp'] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    state['last_ratchet_premium'] = current_premium
    state['last_ratchet_date'] = _today_date_str()


def update_trailing_levels(play: Dict[str, Any], current_stock_price: Optional[float], current_premium: Optional[float]) -> bool:
    """
    Update trailing TP1/TP2 levels according to simplified rules.
    - Activation by absolute gain threshold (premium or stock movement)
    - TP2 starts at original TP, then moves to trailing ceiling (never below original TP)
    - TP1 acts as floor; basis can be profit-capture (default) or distance-from-current
    - EOD ratcheting for TP1 (profit-capture): only increases; respects min-gap below current
    Returns True if any level changed.
    """
    changed: bool = False
    try:
        if not trailing_tp_enabled(play):
            return False

        # Track high-water-marks
        _update_high_water_marks(play, current_stock_price, current_premium)

        # Activation
        if _activation_met(play, current_stock_price, current_premium):
            _init_on_activation(play, current_stock_price, current_premium)
        else:
            return False

        tp = play.get('take_profit') or {}
        state = _init_trail_state(tp)
        defaults = _get_trailing_config_defaults()
        update_mode = defaults['update_mode']

        # Update TP2 according to cadence
        tp2 = state['tp2']
        orig_tp_prem = state.get('original_tp_premium')
        if current_premium is not None:
            if tp2['basis'] == 'distance_from_current':
                candidate = _calc_ceiling_from_current_premium(current_premium, tp2['distance_above_pct'])
            else:  # profit_capture
                entry_prem = (play.get('entry_point') or {}).get('entry_premium')
                candidate = None
                if entry_prem and tp2.get('capture_pct'):
                    candidate = float(entry_prem) * (1.0 + float(tp2['capture_pct']) / 100.0)
            # Apply cadence: if EOD, only move from original after EOD; if cycle, move immediately
            should_move = (update_mode == 'cycle') or (update_mode == 'eod' and _is_end_of_day_now())
            if candidate is not None and should_move:
                new_level = candidate
                if orig_tp_prem is not None:
                    new_level = max(float(orig_tp_prem), float(candidate))
                old_level = tp2.get('level_premium')
                if old_level is None or float(new_level) > float(old_level):
                    tp2['level_premium'] = float(new_level)
                    tp2['last_set_timestamp'] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
                    tp2['moved_from_original'] = True
                    _append_history(tp, 'TP2', old_level, float(new_level), reason='ceiling_update')
                    changed = True

        # Update TP1 according to basis
        tp1 = state['tp1']
        if current_premium is not None:
            if tp1['basis'] == 'distance_from_current':
                candidate = _calc_floor_from_current_premium(current_premium, tp1['distance_below_pct'])
                old_level = tp1.get('level_premium')
                if old_level is None or float(candidate) > float(old_level):
                    tp1['level_premium'] = float(candidate)
                    tp1['last_set_timestamp'] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
                    _append_history(tp, 'TP1', old_level, float(candidate), reason='floor_update')
                    changed = True
            else:
                # profit_capture basis updates only via EOD ratcheting
                pass

        # EOD ratcheting for TP1 (profit_capture)
        if tp1['basis'] == 'profit_capture' and defaults['tp1']['ratcheting']['enabled'] and current_premium is not None:
            if (defaults['update_mode'] == 'eod' and _is_end_of_day_now()) or (defaults['update_mode'] == 'cycle' and _is_end_of_day_now()):
                last_ratchet_date = state.get('last_ratchet_date')
                today_str = _today_date_str()
                if last_ratchet_date != today_str and state.get('last_ratchet_premium'):
                    prev = float(state['last_ratchet_premium'])
                    rise_pct = (float(current_premium) - prev) / prev * 100.0
                    if rise_pct >= defaults['tp1']['ratcheting']['min_rise_since_last_pct']:
                        # Compute new capture percent
                        start_c = float(defaults['tp1']['start_capture_pct'])
                        factor = float(defaults['tp1']['ratcheting']['ratchet_factor'])
                        current_c = float(tp1.get('current_capture_pct') or start_c)
                        proposed_c = max(current_c, start_c + factor * rise_pct)
                        entry_prem = (play.get('entry_point') or {}).get('entry_premium')
                        if entry_prem:
                            candidate = float(entry_prem) * (1.0 + proposed_c / 100.0)
                            # Enforce min-gap: keep TP1 at least X% below current premium; if violation, keep unchanged
                            min_gap = defaults['tp1']['min_gap_below_current_pct']
                            max_allowed = float(current_premium) * (1.0 - float(min_gap) / 100.0)
                            old_level = tp1.get('level_premium')
                            if candidate <= max_allowed and (old_level is None or candidate > float(old_level)):
                                tp1['level_premium'] = float(candidate)
                                tp1['current_capture_pct'] = float(proposed_c)
                                tp1['last_set_timestamp'] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
                                _append_history(tp, 'TP1', old_level, float(candidate), reason='ratchet')
                                changed = True
                        # Update ratchet markers regardless of whether we moved (we tried)
                        state['last_ratchet_premium'] = float(current_premium)
                        state['last_ratchet_date'] = today_str

        # Update legacy current_trail_level for backward-compatible logs (use TP1 floor if present)
        legacy_tp = state.get('tp1', {}).get('level_premium')
        if legacy_tp is not None:
            state['current_trail_level'] = float(legacy_tp)
        state['last_update_timestamp'] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'

        return changed
    except Exception as e:
        logging.warning(f"Trailing update failed: {e}")
        return changed


def get_trailing_tp_levels(play: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Return current TP1/TP2 premium levels if available."""
    tp = play.get('take_profit') or {}
    state = _init_trail_state(tp)
    return {
        'tp1_premium': state.get('tp1', {}).get('level_premium'),
        'tp2_premium': state.get('tp2', {}).get('level_premium'),
    }

