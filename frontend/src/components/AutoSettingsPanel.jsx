import { useState } from 'react'
import { RISK_PRESETS } from '../lib/autoSettingsDefaults'

// ── Preset colour maps ────────────────────────────────────────────────────────
const PRESET_STYLES = {
  safe: {
    active:   'bg-blue-600/25 border-blue-500   text-blue-200',
    inactive: 'bg-[#0f1117]   border-[#2a2d3a]  text-gray-400 hover:border-blue-800 hover:text-blue-300',
    badge:    'bg-blue-900/40 text-blue-300',
    dot:      'bg-blue-400',
  },
  moderate: {
    active:   'bg-yellow-600/20 border-yellow-500   text-yellow-200',
    inactive: 'bg-[#0f1117]     border-[#2a2d3a]    text-gray-400 hover:border-yellow-800 hover:text-yellow-300',
    badge:    'bg-yellow-900/40 text-yellow-300',
    dot:      'bg-yellow-400',
  },
  risk: {
    active:   'bg-red-600/20 border-red-500   text-red-200',
    inactive: 'bg-[#0f1117]   border-[#2a2d3a]  text-gray-400 hover:border-red-800 hover:text-red-300',
    badge:    'bg-red-900/40 text-red-300',
    dot:      'bg-red-400',
  },
}

// ── Setting groups ────────────────────────────────────────────────────────────
const GROUPS = [
  {
    id: 'scope',
    title: 'AUTO Scope',
    description: 'What AUTO is allowed to trade and how many entries it can take in a day.',
    fields: [
      { key: 'enable_nifty_auto',     label: 'Enable NIFTY AUTO',        type: 'boolean' },
      { key: 'enable_banknifty_auto', label: 'Enable BANKNIFTY AUTO',     type: 'boolean' },
      { key: 'max_daily_entries',     label: 'Max Daily Entries',         type: 'number', step: 1 },
      { key: 'max_daily_losses',      label: 'Max Daily Losses',          type: 'number', step: 1 },
      { key: 'daily_profit_target',   label: 'Daily Profit Target (Rs)',  type: 'number', step: 1000 },
    ],
  },
  {
    id: 'timing',
    title: 'Timing & Data',
    description: 'AUTO will skip signals outside these windows or below these data-quality floors.',
    fields: [
      { key: 'entry_start_minutes_after_open',   label: 'Start Min After Open',    type: 'number', step: 1 },
      { key: 'entry_stop_minutes_before_close',  label: 'Stop Min Before Close',   type: 'number', step: 1 },
      { key: 'cooldown_after_sl_minutes',        label: 'Cooldown After SL (min)', type: 'number', step: 1 },
      { key: 'min_fresh_signals',                label: 'Min Fresh Signals',       type: 'number', step: 1 },
      { key: 'min_fii_consecutive_days',         label: 'Min FII Direction Days',  type: 'number', step: 1 },
      { key: 'min_confidence',                   label: 'Min AI Confidence',       type: 'number', step: 1 },
    ],
  },
  {
    id: 'risk',
    title: 'Risk & Execution',
    description: 'These settings drive AUTO sizing and slippage acceptance immediately.',
    fields: [
      { key: 'max_risk_pct',    label: 'Max Risk %',     type: 'number', step: 0.1 },
      { key: 'max_deploy_pct',  label: 'Max Deploy %',   type: 'number', step: 0.5 },
      { key: 'min_rr_ratio',    label: 'Min R:R',        type: 'number', step: 0.1 },
      { key: 'max_slippage_pct',label: 'Max Slippage %', type: 'number', step: 0.1 },
    ],
  },
  {
    id: 'nifty_gates',
    title: 'NIFTY Gates',
    description: 'Thresholds AUTO uses before accepting a NIFTY CALL or PUT signal.',
    fields: [
      { key: 'nifty_put_min_vix',   label: 'PUT Min VIX',   type: 'number', step: 0.1 },
      { key: 'nifty_call_max_vix',  label: 'CALL Max VIX',  type: 'number', step: 0.1 },
      { key: 'nifty_put_pcr_max',   label: 'PUT Max PCR',   type: 'number', step: 0.01 },
      { key: 'nifty_call_pcr_min',  label: 'CALL Min PCR',  type: 'number', step: 0.01 },
    ],
  },
  {
    id: 'bn_gates',
    title: 'BANKNIFTY Gates',
    description: 'Thresholds AUTO uses before accepting a BANKNIFTY CALL or PUT signal.',
    fields: [
      { key: 'banknifty_put_min_vix',  label: 'PUT Min VIX',  type: 'number', step: 0.1 },
      { key: 'banknifty_call_max_vix', label: 'CALL Max VIX', type: 'number', step: 0.1 },
      { key: 'banknifty_put_pcr_max',  label: 'PUT Max PCR',  type: 'number', step: 0.01 },
      { key: 'banknifty_call_pcr_min', label: 'CALL Min PCR', type: 'number', step: 0.01 },
    ],
  },
]

// ── Preset key highlights per group ──────────────────────────────────────────
const PRESET_KEYS = new Set([
  'max_risk_pct', 'max_deploy_pct', 'min_rr_ratio', 'max_slippage_pct',
  'max_daily_entries', 'max_daily_losses', 'daily_profit_target',
  'cooldown_after_sl_minutes', 'min_confidence', 'min_fresh_signals',
  'min_fii_consecutive_days', 'entry_start_minutes_after_open', 'entry_stop_minutes_before_close',
])

function fmtDefault(value) {
  if (typeof value === 'boolean') return value ? 'On' : 'Off'
  if (typeof value === 'number') return Number.isInteger(value) ? `${value}` : value.toFixed(2)
  return `${value ?? ''}`
}

function Chevron({ open }) {
  return (
    <svg
      className={`w-3.5 h-3.5 text-gray-500 transition-transform duration-200 ${open ? '' : '-rotate-90'}`}
      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  )
}

function SettingField({ field, value, defaultValue, activePreset, onChange }) {
  const changed = value !== defaultValue
  const isPresetControlled = PRESET_KEYS.has(field.key)

  if (field.type === 'boolean') {
    return (
      <div className="rounded-lg border border-[#2a2d3a] bg-[#0f1117] p-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-xs font-semibold text-gray-300">{field.label}</div>
            <div className="text-[10px] text-gray-600">Default: {fmtDefault(defaultValue)}</div>
          </div>
          <button
            type="button"
            onClick={() => onChange(field.key, !value, field.type)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${value
              ? 'bg-green-600/20 border-green-500 text-green-300'
              : 'bg-[#161922] border-[#2a2d3a] text-gray-400 hover:text-gray-200'}`}
          >
            {value ? 'Enabled' : 'Disabled'}
          </button>
        </div>
        {changed && <div className="text-[10px] text-amber-400">Custom override active</div>}
      </div>
    )
  }

  return (
    <label className={`rounded-lg border bg-[#0f1117] p-3 block transition-colors ${
      isPresetControlled && activePreset
        ? `border-${PRESET_STYLES[activePreset]?.dot === 'bg-blue-400' ? 'blue' : PRESET_STYLES[activePreset]?.dot === 'bg-yellow-400' ? 'yellow' : 'red'}-900/50`
        : 'border-[#2a2d3a]'
    }`}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs font-semibold text-gray-300">{field.label}</span>
        {changed && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/30 text-amber-300">Custom</span>}
      </div>
      <input
        type="number"
        step={field.step || 'any'}
        value={value ?? ''}
        onChange={(e) => onChange(field.key, e.target.value, field.type)}
        className="w-full bg-[#161922] border border-[#2a2d3a] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-600"
      />
      <div className="text-[10px] text-gray-600 mt-2">Default: {fmtDefault(defaultValue)}</div>
    </label>
  )
}

function GroupCard({ group, settings, defaults, activePreset, onChange, openGroups, toggleGroup }) {
  const open = openGroups[group.id] !== false
  return (
    <div className="rounded-xl border border-[#2a2d3a] bg-[#13151e] overflow-hidden">
      {/* Group header — clickable */}
      <button
        type="button"
        onClick={() => toggleGroup(group.id)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#0f1117]/60 transition-colors"
      >
        <div className="text-sm font-semibold text-gray-200">{group.title}</div>
        <Chevron open={open} />
      </button>
      {open && (
        <div className="px-4 pb-4">
          <div className="text-xs text-gray-600 mb-3 leading-relaxed">{group.description}</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {group.fields.map((field) => (
              <SettingField
                key={field.key}
                field={field}
                value={settings[field.key]}
                defaultValue={defaults[field.key]}
                activePreset={activePreset}
                onChange={onChange}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function AutoSettingsPanel({
  settings,
  defaults,
  dirty,
  saving,
  error,
  activePreset,
  onChange,
  onSave,
  onReset,
  onApplyPreset,
}) {
  // Each settings group can be independently collapsed
  const [openGroups, setOpenGroups] = useState({ scope: true, timing: true, risk: true, nifty_gates: false, bn_gates: false })
  const toggleGroup = (id) => setOpenGroups((s) => ({ ...s, [id]: !s[id] }))

  if (!settings || !defaults) return null

  return (
    <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-4 space-y-4">

      {/* ── Panel header ── */}
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">AUTO Settings</div>
          <div className="text-xs text-gray-600 mt-1 max-w-2xl">
            Defaults stay active unless you override them. Saved changes apply to AUTO immediately.
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={onReset}
            className="px-3 py-2 rounded-lg border border-[#2a2d3a] text-xs text-gray-400 hover:text-gray-200 transition-colors"
          >
            Reset to Defaults
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={!dirty || saving}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition-colors"
          >
            {saving ? 'Saving...' : dirty ? 'Save Live Settings' : 'Saved'}
          </button>
        </div>
      </div>

      {/* ── Risk preset bar ── */}
      <div>
        <div className="text-[10px] text-gray-600 uppercase tracking-wider mb-2">Quick Risk Profile</div>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(RISK_PRESETS).map(([key, preset]) => {
            const style = PRESET_STYLES[key]
            const isActive = activePreset === key
            return (
              <button
                key={key}
                type="button"
                onClick={() => onApplyPreset(key)}
                className={`relative rounded-xl border px-3 py-2.5 text-left transition-all ${isActive ? style.active : style.inactive}`}
              >
                {isActive && (
                  <span className={`absolute top-2 right-2 w-1.5 h-1.5 rounded-full ${style.dot}`} />
                )}
                <div className="text-xs font-bold leading-tight">{preset.label}</div>
                <div className="text-[10px] opacity-70 mt-0.5 leading-tight">{preset.subtitle}</div>
                {isActive && (
                  <div className={`mt-1.5 text-[9px] font-semibold px-1.5 py-0.5 rounded inline-block ${style.badge}`}>
                    ACTIVE
                  </div>
                )}
              </button>
            )
          })}
        </div>
        {activePreset && (
          <div className="mt-2 text-[10px] text-gray-600 leading-relaxed">
            {activePreset === 'safe' && 'Safe: 1% risk, 10% deploy, R:R 2.5 — 1 trade/day, 2-day FII streak required, 65% confidence floor.'}
            {activePreset === 'moderate' && 'Moderate: 2% risk, 20% deploy, R:R 2.0 — 2 trades/day, standard gates, 55% confidence floor.'}
            {activePreset === 'risk' && 'Risk: 4% risk, 40% deploy, R:R 1.5 — 3 trades/day, relaxed gates, 50% confidence floor. Trade carefully.'}
          </div>
        )}
      </div>

      {error && <div className="text-xs text-red-400 bg-red-900/15 border border-red-900/30 rounded-lg px-3 py-2">{error}</div>}

      {/* ── Settings groups ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {GROUPS.map((group) => (
          <GroupCard
            key={group.id}
            group={group}
            settings={settings}
            defaults={defaults}
            activePreset={activePreset}
            onChange={onChange}
            openGroups={openGroups}
            toggleGroup={toggleGroup}
          />
        ))}
      </div>
    </div>
  )
}
