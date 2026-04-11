/**
 * ParametersPanel — sticky right-side panel showing every setting that drives
 * AUTO or MANUAL trade decisions. One glance tells the user exactly which
 * thresholds are active without scrolling into the AUTO Settings accordion.
 */

const PARAM_GROUPS = [
  {
    title: 'Scope',
    params: [
      {
        key: 'enable_nifty_auto',
        label: 'NIFTY Auto',
        fmt: (v) => (v ? 'ON' : 'OFF'),
        color: (v) => (v ? 'text-green-400' : 'text-gray-500'),
      },
      {
        key: 'enable_banknifty_auto',
        label: 'BankNifty Auto',
        fmt: (v) => (v ? 'ON' : 'OFF'),
        color: (v) => (v ? 'text-green-400' : 'text-gray-500'),
      },
      {
        key: 'max_daily_entries',
        label: 'Max Entries / Day',
        fmt: (v) => `${v}`,
        color: () => 'text-white',
      },
      {
        key: 'max_daily_losses',
        label: 'Max Losses / Day',
        fmt: (v) => `${v}`,
        color: () => 'text-red-300',
      },
      {
        key: 'daily_profit_target',
        label: 'Daily Target',
        fmt: (v) => `Rs${Number(v).toLocaleString('en-IN')}`,
        color: () => 'text-green-300',
      },
    ],
  },
  {
    title: 'Timing & Data',
    params: [
      {
        key: 'entry_start_minutes_after_open',
        label: 'Entry Start',
        fmt: (v) => `+${v} min after open`,
        color: () => 'text-white',
      },
      {
        key: 'entry_stop_minutes_before_close',
        label: 'Entry Stop',
        fmt: (v) => `-${v} min to close`,
        color: () => 'text-white',
      },
      {
        key: 'cooldown_after_sl_minutes',
        label: 'SL Cooldown',
        fmt: (v) => `${v} min`,
        color: () => 'text-yellow-300',
      },
      {
        key: 'min_fresh_signals',
        label: 'Min Fresh Signals',
        fmt: (v) => `${v} / 47`,
        color: () => 'text-white',
      },
      {
        key: 'min_fii_consecutive_days',
        label: 'Min FII Direction Days',
        fmt: (v) => `${v} day${v !== 1 ? 's' : ''}`,
        color: () => 'text-white',
      },
      {
        key: 'min_confidence',
        label: 'Min AI Confidence',
        fmt: (v) => `${v}%`,
        color: () => 'text-blue-300',
      },
    ],
  },
  {
    title: 'Risk & Sizing',
    params: [
      {
        key: 'max_risk_pct',
        label: 'Max Risk',
        fmt: (v) => `${v}% of capital`,
        color: () => 'text-red-300',
      },
      {
        key: 'max_deploy_pct',
        label: 'Max Deploy',
        fmt: (v) => `${v}% of capital`,
        color: () => 'text-orange-300',
      },
      {
        key: 'min_rr_ratio',
        label: 'Min R:R',
        fmt: (v) => `${v} : 1`,
        color: () => 'text-green-300',
      },
      {
        key: 'max_slippage_pct',
        label: 'Max Slippage',
        fmt: (v) => `${v}%`,
        color: () => 'text-yellow-300',
      },
    ],
  },
  {
    title: 'NIFTY Gates',
    isGates: true,
    params: [
      {
        key: 'nifty_put_min_vix',
        label: 'PUT — Min VIX',
        fmt: (v) => `\u2265 ${v}`,
        color: () => 'text-red-300',
      },
      {
        key: 'nifty_call_max_vix',
        label: 'CALL — Max VIX',
        fmt: (v) => `\u2264 ${v}`,
        color: () => 'text-green-300',
      },
      {
        key: 'nifty_put_pcr_max',
        label: 'PUT — Max PCR',
        fmt: (v) => `\u2264 ${v}`,
        color: () => 'text-red-300',
      },
      {
        key: 'nifty_call_pcr_min',
        label: 'CALL — Min PCR',
        fmt: (v) => `\u2265 ${v}`,
        color: () => 'text-green-300',
      },
    ],
  },
  {
    title: 'BANKNIFTY Gates',
    isGates: true,
    params: [
      {
        key: 'banknifty_put_min_vix',
        label: 'PUT — Min VIX',
        fmt: (v) => `\u2265 ${v}`,
        color: () => 'text-red-300',
      },
      {
        key: 'banknifty_call_max_vix',
        label: 'CALL — Max VIX',
        fmt: (v) => `\u2264 ${v}`,
        color: () => 'text-green-300',
      },
      {
        key: 'banknifty_put_pcr_max',
        label: 'PUT — Max PCR',
        fmt: (v) => `\u2264 ${v}`,
        color: () => 'text-red-300',
      },
      {
        key: 'banknifty_call_pcr_min',
        label: 'CALL — Min PCR',
        fmt: (v) => `\u2265 ${v}`,
        color: () => 'text-green-300',
      },
    ],
  },
]

function ParamRow({ label, value, valueColor }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-[#2a2d3a]/40 last:border-0 gap-2">
      <span className="text-[11px] text-gray-500 leading-tight">{label}</span>
      <span className={`text-[11px] font-mono font-semibold shrink-0 ${valueColor || 'text-white'}`}>
        {value}
      </span>
    </div>
  )
}

export default function ParametersPanel({ settings, tradeMode, capital }) {
  if (!settings) return null

  const isAuto = tradeMode === 'auto'

  return (
    <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl overflow-hidden">

      {/* Header */}
      <div className="px-4 py-3 bg-[#13151e] border-b border-[#2a2d3a] flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Parameters In Use
          </div>
          <div className="text-[10px] text-gray-600 mt-0.5">
            {isAuto ? 'Effective AUTO settings' : 'MANUAL — no auto execution'}
          </div>
        </div>
        <span
          className={`px-2 py-1 rounded text-[10px] font-bold border ${
            isAuto
              ? 'bg-green-900/30 text-green-300 border-green-800/40'
              : 'bg-blue-900/30 text-blue-300 border-blue-800/40'
          }`}
        >
          {isAuto ? 'AUTO' : 'MANUAL'}
        </span>
      </div>

      {/* Capital row — always shown */}
      <div className="px-4 py-2.5 border-b border-[#2a2d3a] flex items-center justify-between">
        <span className="text-[11px] text-gray-500">Capital at Risk</span>
        <span className="text-[11px] font-mono font-semibold text-white">
          Rs{Number(capital).toLocaleString('en-IN')}
        </span>
      </div>

      {!isAuto ? (
        /* MANUAL mode placeholder */
        <div className="px-4 py-6 text-center space-y-2">
          <div className="text-xs text-gray-500 leading-relaxed">
            MANUAL mode active.<br />
            Signals are shown, but no orders<br />
            are placed automatically.
          </div>
          <div className="text-[10px] text-gray-600 leading-relaxed">
            Log your broker entry on each signal card.<br />
            Switch to AUTO to enable automated entry.
          </div>
        </div>
      ) : (
        /* AUTO mode — all parameter groups */
        <div>
          {PARAM_GROUPS.map((group) => (
            <div key={group.title} className="border-b border-[#2a2d3a] last:border-0">
              <div className="px-4 pt-3 pb-1">
                <div
                  className={`text-[10px] font-semibold uppercase tracking-wider mb-1 ${
                    group.isGates ? 'text-blue-700' : 'text-gray-600'
                  }`}
                >
                  {group.title}
                </div>
                {group.params.map((p) => {
                  const val = settings[p.key]
                  if (val === undefined || val === null) return null
                  return (
                    <ParamRow
                      key={p.key}
                      label={p.label}
                      value={p.fmt(val)}
                      valueColor={p.color(val)}
                    />
                  )
                })}
              </div>
            </div>
          ))}

          {/* Footer note */}
          <div className="px-4 py-2.5 bg-[#13151e]">
            <div className="text-[10px] text-gray-700 leading-relaxed">
              Edit any value in AUTO Settings above and click Save Live Settings to apply instantly.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
