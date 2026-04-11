export const FALLBACK_AUTO_SETTINGS = {
  enable_nifty_auto: true,
  enable_banknifty_auto: true,
  entry_start_minutes_after_open: 30,
  entry_stop_minutes_before_close: 60,
  cooldown_after_sl_minutes: 60,
  max_daily_entries: 2,
  max_daily_losses: 3,
  daily_profit_target: 50000,
  max_risk_pct: 2,
  max_deploy_pct: 20,
  max_slippage_pct: 3,
  min_rr_ratio: 2,
  min_confidence: 55,
  min_fresh_signals: 40,
  min_fii_consecutive_days: 1,
  nifty_put_min_vix: 15,
  nifty_call_max_vix: 28,
  nifty_put_pcr_max: 1.3,
  nifty_call_pcr_min: 0.5,
  banknifty_put_min_vix: 17,
  banknifty_call_max_vix: 35,
  banknifty_put_pcr_max: 1.3,
  banknifty_call_pcr_min: 0.5,
}

/**
 * RISK_PRESETS — three named trading profiles that set risk/timing/quality
 * parameters in one click. Gate thresholds (VIX, PCR) are preserved as-is.
 *
 * Safe      — capital protection first, very small position sizes
 * Moderate  — balanced defaults, the recommended starting point
 * Risk      — aggressive sizing for experienced traders
 */
export const RISK_PRESETS = {
  safe: {
    label: 'Safe',
    subtitle: 'Capital protection first',
    color: 'blue',
    values: {
      max_risk_pct: 1,
      max_deploy_pct: 10,
      min_rr_ratio: 2.5,
      max_slippage_pct: 2,
      max_daily_entries: 1,
      max_daily_losses: 1,
      daily_profit_target: 15000,
      cooldown_after_sl_minutes: 120,
      min_confidence: 65,
      min_fresh_signals: 42,
      min_fii_consecutive_days: 2,
      entry_start_minutes_after_open: 45,
      entry_stop_minutes_before_close: 90,
    },
  },
  moderate: {
    label: 'Moderate',
    subtitle: 'Balanced growth',
    color: 'yellow',
    values: {
      max_risk_pct: 2,
      max_deploy_pct: 20,
      min_rr_ratio: 2,
      max_slippage_pct: 3,
      max_daily_entries: 2,
      max_daily_losses: 2,
      daily_profit_target: 50000,
      cooldown_after_sl_minutes: 60,
      min_confidence: 55,
      min_fresh_signals: 40,
      min_fii_consecutive_days: 1,
      entry_start_minutes_after_open: 30,
      entry_stop_minutes_before_close: 60,
    },
  },
  risk: {
    label: 'Risk',
    subtitle: 'Higher stakes, higher reward',
    color: 'red',
    values: {
      max_risk_pct: 4,
      max_deploy_pct: 40,
      min_rr_ratio: 1.5,
      max_slippage_pct: 5,
      max_daily_entries: 3,
      max_daily_losses: 3,
      daily_profit_target: 100000,
      cooldown_after_sl_minutes: 30,
      min_confidence: 50,
      min_fresh_signals: 35,
      min_fii_consecutive_days: 1,
      entry_start_minutes_after_open: 20,
      entry_stop_minutes_before_close: 45,
    },
  },
}