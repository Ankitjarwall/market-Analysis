import { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'
import { useAuthStore } from '../store/authStore'
import { useMarketStore } from '../store/marketStore'
import SignalCard from '../components/SignalCard'
import TradeCard from '../components/TradeCard'
import AutoSettingsPanel from '../components/AutoSettingsPanel'
import AutoStatusPanel from '../components/AutoStatusPanel'
import ParametersPanel from '../components/ParametersPanel'
import { FALLBACK_AUTO_SETTINGS, RISK_PRESETS } from '../lib/autoSettingsDefaults'

// ── Shared SVG helpers ────────────────────────────────────────────────────────
function Chevron({ open, className = '' }) {
  return (
    <svg
      className={`w-4 h-4 transition-transform duration-200 ${open ? '' : '-rotate-90'} ${className}`}
      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  )
}

function GearIcon({ className = '' }) {
  return (
    <svg className={`w-4 h-4 ${className}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 011.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 01-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 01-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.505-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.108-1.204l-.526-.738a1.125 1.125 0 01.12-1.45l.773-.773a1.125 1.125 0 011.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  )
}

// ── Collapsible section wrapper ───────────────────────────────────────────────
function Section({ id, title, badge, open, onToggle, children, noPad = false }) {
  return (
    <div>
      <button
        className="w-full flex items-center justify-between mb-3 group"
        onClick={() => onToggle(id)}
      >
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-gray-300 group-hover:text-gray-200 transition-colors">{title}</span>
          {badge && <span className="text-xs text-gray-600">{badge}</span>}
        </div>
        <Chevron open={open} className="text-gray-600 group-hover:text-gray-400" />
      </button>
      {open && <div className={noPad ? '' : ''}>{children}</div>}
    </div>
  )
}

const API = import.meta.env.VITE_API_URL || ''
const CAPITAL_MIN = 10_000
const CAPITAL_MAX = 10_000_000
const clamp = (v) => Math.max(CAPITAL_MIN, Math.min(CAPITAL_MAX, Math.round(Number(v) || 200_000)))

function GateRow({ label, desc, value, pass, noData = false, noDataReason }) {
  if (noData) {
    return (
      <div className="flex items-center justify-between p-3 rounded-lg border bg-[#0f1117] border-[#2a2d3a] opacity-50">
        <div>
          <div className="text-xs font-semibold text-gray-500">{label}</div>
          <div className="text-xs text-gray-700 mt-0.5">{noDataReason || desc}</div>
        </div>
        <div className="text-right shrink-0 ml-3">
          <div className="text-sm font-mono font-bold text-gray-700">--</div>
          <div className="text-xs mt-0.5 text-gray-700">Unavailable</div>
        </div>
      </div>
    )
  }

  return (
    <div className={`flex items-center justify-between p-3 rounded-lg border ${pass ? 'bg-green-900/15 border-green-800/40' : 'bg-red-900/10 border-red-900/30'}`}>
      <div>
        <div className="text-xs font-semibold text-gray-300">{label}</div>
        <div className="text-xs text-gray-600 mt-0.5">{desc}</div>
      </div>
      <div className="text-right shrink-0 ml-3">
        <div className={`text-sm font-mono font-bold ${pass ? 'text-green-400' : 'text-red-400'}`}>
          {value ?? '--'}
        </div>
        <div className={`text-xs mt-0.5 ${pass ? 'text-green-500' : 'text-red-500'}`}>
          {pass ? 'PASS' : 'FAIL'}
        </div>
      </div>
    </div>
  )
}

function StatBox({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-[#0f1117] rounded-lg p-3 text-center">
      <div className={`text-xl font-bold ${color}`}>{value ?? '--'}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </div>
  )
}

function MarketRadar({ nifty, banknifty, callGateCount, putGateCount }) {
  if (!nifty) return null

  const niftyAtm = Math.round(nifty / 50) * 50
  const bnAtm = banknifty ? Math.round(banknifty / 100) * 100 : null
  const hasBullBias = callGateCount > putGateCount && callGateCount >= 2
  const hasBearBias = putGateCount > callGateCount && putGateCount >= 2
  const bias = hasBullBias ? 'BULLISH BIAS' : hasBearBias ? 'BEARISH BIAS' : 'NEUTRAL'
  const biasColor = hasBullBias ? 'text-green-400' : hasBearBias ? 'text-red-400' : 'text-yellow-400'

  return (
    <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Market Radar</div>
          <div className={`text-base font-bold mt-0.5 ${biasColor}`}>{bias}</div>
          <div className="text-xs text-gray-600 mt-0.5">Live view using your current NIFTY AUTO thresholds</div>
        </div>
        <div className="flex gap-5 text-right">
          <div>
            <div className="text-[10px] text-gray-600 mb-0.5">NIFTY ATM</div>
            <div className="text-xl font-bold font-mono text-white">{niftyAtm}</div>
            <div className="text-[10px] text-gray-600">Rs{nifty?.toFixed(0)}</div>
          </div>
          {bnAtm && (
            <div>
              <div className="text-[10px] text-gray-600 mb-0.5">BANKNIFTY ATM</div>
              <div className="text-xl font-bold font-mono text-white">{bnAtm}</div>
              <div className="text-[10px] text-gray-600">Rs{banknifty?.toFixed(0)}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Options() {
  const { user } = useAuth()
  const updateUser = useAuthStore((s) => s.updateUser)
  const activeSignals = useMarketStore((s) => s.activeSignals)
  const openTrades = useMarketStore((s) => s.openTrades)
  const marketData = useMarketStore((s) => s.marketData)

  const [capital, setCapital] = useState(clamp(user?.capital))
  const [tradeMode, setTradeMode] = useState(user?.trade_mode || 'auto')
  const [tradeHistory, setTradeHistory] = useState([])
  const [predHistory, setPredHistory] = useState([])
  const [predAccuracy, setPredAccuracy] = useState(null)
  const [loading, setLoading] = useState(true)
  const [savingCapital, setSavingCapital] = useState(false)
  const [savingAutoSettings, setSavingAutoSettings] = useState(false)
  const [autoSettings, setAutoSettings] = useState(FALLBACK_AUTO_SETTINGS)
  const [savedAutoSettings, setSavedAutoSettings] = useState(FALLBACK_AUTO_SETTINGS)
  const [defaultAutoSettings, setDefaultAutoSettings] = useState(FALLBACK_AUTO_SETTINGS)
  const [errors, setErrors] = useState({})

  // ── UI state ────────────────────────────────────────────────────────────────
  const [showAutoSettings, setShowAutoSettings] = useState(false)
  const [activePreset, setActivePreset] = useState('moderate')
  const [openSections, setOpenSections] = useState({
    gates: true, signals: true, positions: true, perf: true, journal: true, predictions: false,
  })

  const toggleSection = (key) => setOpenSections((s) => ({ ...s, [key]: !s[key] }))

  const applyPreset = (presetKey) => {
    setActivePreset(presetKey)
    const presetValues = RISK_PRESETS[presetKey]?.values || {}
    setAutoSettings((prev) => ({ ...prev, ...presetValues }))
  }

  useEffect(() => {
    loadData()
    const id = setInterval(async () => {
      try {
        const [sigRes, openRes, histRes] = await Promise.all([
          axios.get(`${API}/api/signals/active`),
          axios.get(`${API}/api/trades/open`),
          axios.get(`${API}/api/trades/history?days=30`),
        ])
        if (sigRes.data?.signals) useMarketStore.getState().setActiveSignals(sigRes.data.signals)
        if (openRes.data?.trades) useMarketStore.getState().setOpenTrades(openRes.data.trades)
        if (histRes.data?.trades) setTradeHistory(histRes.data.trades)
      } catch (_) {}
    }, 30_000)
    return () => clearInterval(id)
  }, [])

  const loadData = async () => {
    setLoading(true)
    const results = await Promise.allSettled([
      axios.get(`${API}/api/trades/history?days=30`),
      axios.get(`${API}/api/trades/open`),
      axios.get(`${API}/api/signals/active`),
      axios.get(`${API}/api/trades/capital`),
      axios.get(`${API}/api/trades/auto-settings`),
      axios.get(`${API}/api/predictions/history?days=30`),
      axios.get(`${API}/api/predictions/accuracy?days=30`),
    ])

    const [tradesRes, openRes, signalsRes, settingsRes, autoSettingsRes, predHistRes, predAccRes] = results
    const newErrors = {}

    if (tradesRes.status === 'fulfilled') setTradeHistory(tradesRes.value.data.trades || [])
    else newErrors.trades = 'Failed to load trade history'

    if (openRes.status === 'fulfilled') useMarketStore.getState().setOpenTrades(openRes.value.data.trades || [])
    if (signalsRes.status === 'fulfilled') useMarketStore.getState().setActiveSignals(signalsRes.value.data.signals || [])

    if (settingsRes.status === 'fulfilled') {
      if (settingsRes.value.data.trade_mode) setTradeMode(settingsRes.value.data.trade_mode)
      if (settingsRes.value.data.capital) setCapital(clamp(settingsRes.value.data.capital))
    }

    if (autoSettingsRes.status === 'fulfilled') {
      const defaults = autoSettingsRes.value.data.defaults || FALLBACK_AUTO_SETTINGS
      const effective = autoSettingsRes.value.data.effective || defaults
      setDefaultAutoSettings(defaults)
      setAutoSettings(effective)
      setSavedAutoSettings(effective)
      updateUser({ auto_settings: effective })
    } else {
      newErrors.autoSettings = 'Failed to load AUTO settings'
    }

    if (predHistRes.status === 'fulfilled') setPredHistory(predHistRes.value.data.predictions || [])
    if (predAccRes.status === 'fulfilled') setPredAccuracy(predAccRes.value.data)

    setErrors(newErrors)
    setLoading(false)
  }

  const saveCapital = async () => {
    const clamped = clamp(capital)
    setCapital(clamped)
    setSavingCapital(true)
    try {
      await axios.put(`${API}/api/trades/capital`, { capital: clamped })
      updateUser({ capital: clamped })
      setErrors((e) => ({ ...e, capital: null }))
    } catch {
      setErrors((e) => ({ ...e, capital: 'Failed to save capital' }))
    } finally {
      setSavingCapital(false)
    }
  }

  const switchMode = async (mode) => {
    try {
      await axios.put(`${API}/api/trades/mode`, { mode })
      setTradeMode(mode)
      updateUser({ trade_mode: mode })
      setErrors((e) => ({ ...e, mode: null }))
    } catch {
      setErrors((e) => ({ ...e, mode: 'Failed to switch mode' }))
    }
  }

  const updateAutoSetting = (key, rawValue, type) => {
    const value = type === 'boolean' ? rawValue : rawValue === '' ? '' : Number(rawValue)
    setAutoSettings((current) => ({ ...current, [key]: value }))
  }

  const saveAutoSettings = async () => {
    setSavingAutoSettings(true)
    try {
      const res = await axios.put(`${API}/api/trades/auto-settings`, { settings: autoSettings })
      const defaults = res.data.defaults || FALLBACK_AUTO_SETTINGS
      const effective = res.data.effective || defaults
      setDefaultAutoSettings(defaults)
      setAutoSettings(effective)
      setSavedAutoSettings(effective)
      updateUser({ auto_settings: effective })
      setErrors((e) => ({ ...e, autoSettings: null }))
    } catch (err) {
      setErrors((e) => ({ ...e, autoSettings: err.response?.data?.detail || 'Failed to save AUTO settings' }))
    } finally {
      setSavingAutoSettings(false)
    }
  }

  const resetAutoSettings = () => {
    setAutoSettings(defaultAutoSettings)
    setErrors((e) => ({ ...e, autoSettings: null }))
  }

  const effectiveAutoSettings = autoSettings || FALLBACK_AUTO_SETTINGS
  const settingsDirty = JSON.stringify(autoSettings) !== JSON.stringify(savedAutoSettings)

  const niftySignal = activeSignals.find((s) => s.underlying !== 'BANKNIFTY') || null
  const bnSignal = activeSignals.find((s) => s.underlying === 'BANKNIFTY') || null
  const closedTrades = tradeHistory.filter((t) => t.status === 'CLOSED')
  const winTrades = closedTrades.filter((t) => (t.net_pnl || 0) > 0)
  const winRate = closedTrades.length ? Math.round((winTrades.length / closedTrades.length) * 100) : null
  const totalPnl = closedTrades.reduce((sum, t) => sum + (t.net_pnl || 0), 0)

  const vix = marketData?.india_vix
  const nifty = marketData?.nifty
  const banknifty = marketData?.banknifty
  const vwap = marketData?.vwap
  const fiiNet = marketData?.fii_net
  const pcr = marketData?.put_call_ratio
  const hasGateData = vix != null && nifty != null
  const fiiDisplay = fiiNet != null ? `Rs${fiiNet > 0 ? '+' : ''}${Math.abs(fiiNet).toFixed(0)}Cr` : null

  const callGates = [
    { label: `VIX <= ${effectiveAutoSettings.nifty_call_max_vix}`, desc: 'Volatility must stay below your CALL ceiling', value: vix?.toFixed(2), pass: vix <= effectiveAutoSettings.nifty_call_max_vix, noData: vix == null },
    { label: 'Price > VWAP', desc: 'NIFTY must stay above VWAP', value: vwap ? `${nifty?.toFixed(0)} vs ${vwap?.toFixed(0)}` : null, pass: nifty > vwap, noData: nifty == null || vwap == null },
    { label: 'FII Net Buying', desc: `Needs ${effectiveAutoSettings.min_fii_consecutive_days}+ directional buy day(s)`, value: fiiDisplay, pass: fiiNet > 0, noData: fiiNet == null },
    { label: `PCR >= ${effectiveAutoSettings.nifty_call_pcr_min}`, desc: 'PCR must stay above your CALL floor', value: pcr?.toFixed(3), pass: pcr >= effectiveAutoSettings.nifty_call_pcr_min, noData: pcr == null, noDataReason: 'NSE option chain unavailable' },
  ]

  const putGates = [
    { label: `VIX >= ${effectiveAutoSettings.nifty_put_min_vix}`, desc: 'Volatility must stay above your PUT minimum', value: vix?.toFixed(2), pass: vix >= effectiveAutoSettings.nifty_put_min_vix, noData: vix == null },
    { label: 'Price < VWAP', desc: 'NIFTY must stay below VWAP', value: vwap ? `${nifty?.toFixed(0)} vs ${vwap?.toFixed(0)}` : null, pass: nifty < vwap, noData: nifty == null || vwap == null },
    { label: 'FII Net Selling', desc: `Needs ${effectiveAutoSettings.min_fii_consecutive_days}+ directional sell day(s)`, value: fiiDisplay, pass: fiiNet < 0, noData: fiiNet == null },
    { label: `PCR <= ${effectiveAutoSettings.nifty_put_pcr_max}`, desc: 'PCR must stay below your PUT ceiling', value: pcr?.toFixed(3), pass: pcr <= effectiveAutoSettings.nifty_put_pcr_max, noData: pcr == null, noDataReason: 'NSE option chain unavailable' },
  ]

  const callGateCount = callGates.filter((g) => !g.noData && g.pass).length
  const putGateCount = putGates.filter((g) => !g.noData && g.pass).length

  return (
    <div className="p-4 lg:p-6">
      <div className="max-w-screen-2xl mx-auto">

        {/* Page title */}
        <div className="flex items-start justify-between gap-3 mb-5">
          <div>
            <h1 className="text-lg font-bold text-gray-200">Options Signal Board</h1>
            <p className="text-xs text-gray-500 mt-0.5">AI-generated BUY CALL and BUY PUT signals with live AUTO controls.</p>
          </div>
          {/* AUTO Settings toggle — gear icon */}
          <button
            onClick={() => setShowAutoSettings((v) => !v)}
            title="AUTO Settings"
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold border transition-all shrink-0 ${
              showAutoSettings
                ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                : 'border-[#2a2d3a] text-gray-500 hover:text-gray-300 hover:border-[#3a3d4a]'
            }`}
          >
            <GearIcon className={showAutoSettings ? 'text-blue-300' : ''} />
            <span className="hidden sm:inline">AUTO Settings</span>
            <Chevron open={showAutoSettings} className={showAutoSettings ? 'text-blue-400' : 'text-gray-600'} />
          </button>
        </div>

        {/* Two-column layout: main content left, parameters panel right */}
        <div className="flex flex-col xl:flex-row gap-5 items-start">

          {/* ── LEFT COLUMN — main content ── */}
          <div className="flex-1 min-w-0 space-y-5">

            <MarketRadar nifty={nifty} banknifty={banknifty} callGateCount={callGateCount} putGateCount={putGateCount} />

            {hasGateData && (
              <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl overflow-hidden">
                {/* Collapsible gate header */}
                <button
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#0f1117]/50 transition-colors group"
                  onClick={() => toggleSection('gates')}
                >
                  <div>
                    <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider text-left">Live Gate Status</div>
                    <div className="text-xs text-gray-600 mt-0.5 text-left">NIFTY AUTO thresholds — {callGateCount}/4 CALL &nbsp;·&nbsp; {putGateCount}/4 PUT</div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="flex gap-3">
                      <div className="text-center">
                        <div className={`text-lg font-bold ${callGateCount >= 3 ? 'text-green-400' : 'text-gray-600'}`}>{callGateCount}/4</div>
                        <div className="text-[10px] text-gray-600">CALL</div>
                      </div>
                      <div className="text-center">
                        <div className={`text-lg font-bold ${putGateCount >= 3 ? 'text-red-400' : 'text-gray-600'}`}>{putGateCount}/4</div>
                        <div className="text-[10px] text-gray-600">PUT</div>
                      </div>
                    </div>
                    <Chevron open={openSections.gates} className="text-gray-600 group-hover:text-gray-400" />
                  </div>
                </button>
                {openSections.gates && (
                  <div className="px-4 pb-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      <div>
                        <div className="text-[10px] text-green-600 font-semibold uppercase mb-1.5">CALL gates</div>
                        <div className="space-y-1.5">{callGates.map((g, i) => <GateRow key={i} {...g} />)}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-red-600 font-semibold uppercase mb-1.5">PUT gates</div>
                        <div className="space-y-1.5">{putGates.map((g, i) => <GateRow key={i} {...g} />)}</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-4">
                <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Your Trading Capital</div>
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <div className="text-xs text-gray-500 mb-1">Amount (Rs)</div>
                    <input
                      type="number"
                      className="w-full bg-[#0f1117] border border-[#2a2d3a] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-600"
                      value={capital}
                      min={10000}
                      max={10000000}
                      step={10000}
                      onChange={(e) => setCapital(e.target.value)}
                      onBlur={(e) => setCapital(clamp(e.target.value))}
                    />
                  </div>
                  <button onClick={saveCapital} disabled={savingCapital} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors disabled:opacity-50">
                    {savingCapital ? '...' : 'Save'}
                  </button>
                </div>
                <div className="mt-2 text-sm font-semibold text-white">
                  {capital >= 100000 ? `Rs${(capital / 100000).toFixed(2)}L` : `Rs${Number(capital).toLocaleString('en-IN')}`}
                </div>
                <div className="text-xs text-gray-600 mt-0.5">AUTO sizing uses your saved risk and deployment settings.</div>
                {errors.capital && <p className="text-xs text-red-400 mt-1">{errors.capital}</p>}
              </div>

              <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-4">
                <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Trade Mode</div>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => switchMode('auto')} className={`py-3 rounded-lg text-sm font-semibold border transition-all ${tradeMode === 'auto' ? 'bg-green-600/20 border-green-500 text-green-300' : 'border-[#2a2d3a] text-gray-500 hover:text-gray-300'}`}>
                    AUTO
                  </button>
                  <button onClick={() => switchMode('manual')} className={`py-3 rounded-lg text-sm font-semibold border transition-all ${tradeMode === 'manual' ? 'bg-blue-600/20 border-blue-500 text-blue-300' : 'border-[#2a2d3a] text-gray-500 hover:text-gray-300'}`}>
                    MANUAL
                  </button>
                </div>
                <p className={`text-xs mt-2 leading-relaxed ${tradeMode === 'auto' ? 'text-green-700' : 'text-blue-700'}`}>
                  {tradeMode === 'auto'
                    ? 'AUTO opens only when the live signal also passes your saved AUTO settings.'
                    : 'MANUAL shows the signal and lets you log your broker entry manually.'}
                </p>
                {errors.mode && <p className="text-xs text-red-400 mt-1">{errors.mode}</p>}
              </div>
            </div>

            {/* AUTO Settings — only visible when gear icon is clicked */}
            {showAutoSettings && (
              <AutoSettingsPanel
                settings={autoSettings}
                defaults={defaultAutoSettings}
                dirty={settingsDirty}
                saving={savingAutoSettings}
                error={errors.autoSettings}
                activePreset={activePreset}
                onChange={updateAutoSetting}
                onSave={saveAutoSettings}
                onReset={resetAutoSettings}
                onApplyPreset={applyPreset}
              />
            )}

            {/* Active Signals — collapsible */}
            <Section
              id="signals"
              title="Active Signals"
              badge={`${activeSignals.length} active`}
              open={openSections.signals}
              onToggle={toggleSection}
            >
              {loading ? (
                <div className="flex items-center justify-center h-28 text-gray-600 text-sm">Loading signals...</div>
              ) : !niftySignal && !bnSignal ? (
                <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-5 text-sm text-gray-500">No active signal</div>
              ) : (
                <div className="space-y-4">
                  {niftySignal && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs px-2 py-0.5 bg-blue-900/50 text-blue-300 border border-blue-800/40 rounded">NIFTY 50</span>
                        <span className="text-xs text-gray-500">Lot size: 25</span>
                      </div>
                      <SignalCard signal={niftySignal} tradeMode={tradeMode} capital={capital} />
                    </div>
                  )}
                  {bnSignal && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs px-2 py-0.5 bg-purple-900/50 text-purple-300 border border-purple-800/40 rounded">BANKNIFTY</span>
                        <span className="text-xs text-gray-500">Lot size: 15</span>
                      </div>
                      <SignalCard signal={bnSignal} tradeMode={tradeMode} capital={capital} />
                    </div>
                  )}
                </div>
              )}
            </Section>

            {/* Open Positions — collapsible, only shown when trades exist */}
            {openTrades.length > 0 && (
              <Section
                id="positions"
                title="Open Positions"
                badge={`${openTrades.length} active trade${openTrades.length > 1 ? 's' : ''}`}
                open={openSections.positions}
                onToggle={toggleSection}
              >
                <div className="space-y-3">
                  {openTrades.map((trade) => (
                    <TradeCard key={trade.id} trade={trade} signal={activeSignals.find((s) => s.id === trade.signal_id)} onExit={loadData} />
                  ))}
                </div>
              </Section>
            )}

            {/* 30-Day Performance — collapsible */}
            {!loading && closedTrades.length > 0 && (
              <Section
                id="perf"
                title="30-Day Performance"
                badge={`${closedTrades.length} closed trades`}
                open={openSections.perf}
                onToggle={toggleSection}
              >
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatBox label="Total Trades" value={closedTrades.length} />
                  <StatBox label="Win Rate" value={winRate != null ? `${winRate}%` : '--'} color={winRate >= 50 ? 'text-green-400' : 'text-red-400'} />
                  <StatBox label="Net P&L" value={totalPnl !== 0 ? `${totalPnl >= 0 ? '+' : ''}Rs${Math.abs(totalPnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : 'Rs0'} color={totalPnl >= 0 ? 'text-green-400' : 'text-red-400'} />
                  <StatBox label="AI Accuracy" value={predAccuracy?.accuracy_pct != null ? `${predAccuracy.accuracy_pct}%` : '--'} color="text-blue-400" />
                </div>
              </Section>
            )}

            {/* Trade Journal — collapsible */}
            <Section
              id="journal"
              title="Trade Journal"
              badge={`Last 30 days · ${tradeHistory.length} trade${tradeHistory.length !== 1 ? 's' : ''}`}
              open={openSections.journal}
              onToggle={toggleSection}
            >
              {errors.trades && <p className="text-xs text-red-400 mb-2">{errors.trades}</p>}
              {!loading && tradeHistory.length === 0 ? (
                <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-6 text-center text-gray-500 text-sm">No trades yet</div>
              ) : (
                <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-gray-500 border-b border-[#2a2d3a] bg-[#13151e]">
                          <th className="text-left px-3 py-2.5">Date / Time</th>
                          <th className="text-left px-2 py-2.5">Strike</th>
                          <th className="text-left px-2 py-2.5">Type</th>
                          <th className="text-right px-2 py-2.5">Lots</th>
                          <th className="text-right px-2 py-2.5">Entry</th>
                          <th className="text-right px-2 py-2.5">SL</th>
                          <th className="text-right px-2 py-2.5">T1</th>
                          <th className="text-right px-2 py-2.5">T2</th>
                          <th className="text-right px-2 py-2.5">Deployed</th>
                          <th className="text-right px-2 py-2.5">Max Loss</th>
                          <th className="text-right px-2 py-2.5">Exit</th>
                          <th className="text-right px-3 py-2.5">Net P&L</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tradeHistory.slice(0, 30).map((trade) => {
                          const sig = trade.signal || {}
                          const isCall = sig.signal_type === 'BUY_CALL'
                          const isBN = sig.underlying === 'BANKNIFTY'
                          const lotSize = isBN ? 15 : 25
                          const deployed = trade.premium_total || (trade.entry_premium * trade.lots * lotSize)
                          const isOpen = trade.status === 'OPEN' || trade.status === 'PARTIAL'
                          return (
                            <tr key={trade.id} className={`border-b border-[#2a2d3a]/40 hover:bg-[#0f1117]/50 ${isOpen ? 'bg-blue-950/10' : ''}`}>
                              <td className="px-3 py-2">
                                <div className="text-gray-300">{trade.entry_time ? new Date(trade.entry_time).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '--'}</div>
                                <div className="text-gray-600 text-[10px]">{trade.entry_time ? new Date(trade.entry_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }) : ''}</div>
                              </td>
                              <td className="px-2 py-2"><div className="font-mono text-gray-200 font-semibold">{sig.strike ?? '--'} {sig.option_type}</div></td>
                              <td className="px-2 py-2">
                                <div className={`text-[10px] font-bold ${isCall ? 'text-green-400' : 'text-red-400'}`}>{isCall ? 'CALL' : 'PUT'}</div>
                                <span className={`px-1 py-0.5 rounded text-[10px] ${trade.trade_mode === 'auto' ? 'bg-green-900/40 text-green-400' : 'bg-blue-900/40 text-blue-400'}`}>{trade.trade_mode}</span>
                              </td>
                              <td className="px-2 py-2 text-right text-gray-300">{trade.lots} x {lotSize}</td>
                              <td className="px-2 py-2 text-right font-mono text-gray-200 font-semibold">Rs{trade.entry_premium}</td>
                              <td className="px-2 py-2 text-right font-mono text-red-400">Rs{sig.stop_loss ?? '--'}</td>
                              <td className="px-2 py-2 text-right font-mono text-green-400">Rs{sig.target1 ?? '--'}</td>
                              <td className="px-2 py-2 text-right font-mono text-blue-400">Rs{sig.target2 ?? '--'}</td>
                              <td className="px-2 py-2 text-right font-mono text-gray-400">Rs{deployed ? Number(deployed).toLocaleString('en-IN', { maximumFractionDigits: 0 }) : '--'}</td>
                              <td className="px-2 py-2 text-right font-mono text-red-400/70">-Rs{trade.max_loss_calculated ? Number(trade.max_loss_calculated).toLocaleString('en-IN', { maximumFractionDigits: 0 }) : '--'}</td>
                              <td className="px-2 py-2 text-right font-mono">{isOpen ? 'OPEN' : trade.exit_premium ? `Rs${trade.exit_premium}` : '--'}</td>
                              <td className={`px-3 py-2 text-right font-mono font-semibold ${isOpen ? 'text-blue-400' : (trade.net_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{isOpen ? 'live' : trade.net_pnl != null ? `${trade.net_pnl >= 0 ? '+' : ''}Rs${Math.abs(trade.net_pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '--'}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </Section>

            {/* AI Predictions — collapsible */}
            <div className="border-t border-[#2a2d3a] pt-5">
              <Section
                id="predictions"
                title="AI Market Predictions"
                badge="Claude-powered daily brief"
                open={openSections.predictions}
                onToggle={toggleSection}
              >
              {predAccuracy && (
                <div className="grid grid-cols-4 gap-3 mb-4">
                  <StatBox label="Accuracy" value={`${predAccuracy.accuracy_pct ?? '--'}%`} />
                  <StatBox label="Correct" value={predAccuracy.correct ?? 0} color="text-green-400" />
                  <StatBox label="Incorrect" value={predAccuracy.incorrect ?? 0} color="text-red-400" />
                  <StatBox label="Pending" value={predAccuracy.pending ?? 0} color="text-yellow-400" />
                </div>
              )}
              <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl overflow-hidden">
                {predHistory.length === 0 ? (
                  <div className="p-6 text-center text-gray-600 text-sm">No predictions yet</div>
                ) : (
                  <div className="divide-y divide-[#2a2d3a]/50">
                    {predHistory.slice(0, 15).map((p) => (
                      <div key={p.id} className="px-4 py-3 flex items-center justify-between hover:bg-[#0f1117]/50">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-gray-500 text-xs font-mono">{new Date(p.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</span>
                            <span className={`font-bold text-sm ${p.direction === 'UP' ? 'text-green-400' : p.direction === 'DOWN' ? 'text-red-400' : 'text-yellow-400'}`}>{p.direction}</span>
                            <span className="text-gray-600 text-xs">{p.magnitude_low} to {p.magnitude_high}%</span>
                          </div>
                        </div>
                        <div className="text-right">
                          {p.was_correct !== null ? <span className={`text-sm font-bold ${p.was_correct ? 'text-green-400' : 'text-red-400'}`}>{p.was_correct ? 'OK' : 'MISS'}</span> : <span className="text-gray-600 text-xs">pending</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              </Section>
            </div>{/* end border-t wrapper */}

          </div>
          {/* ── END LEFT COLUMN ── */}

          {/* ── RIGHT COLUMN — live status + parameters ── */}
          <div className="w-full xl:w-72 shrink-0 space-y-4 xl:sticky xl:top-4">
            <AutoStatusPanel />
            <ParametersPanel
              settings={effectiveAutoSettings}
              tradeMode={tradeMode}
              capital={capital}
            />
          </div>
          {/* ── END RIGHT COLUMN ── */}

        </div>
      </div>
    </div>
  )
}
