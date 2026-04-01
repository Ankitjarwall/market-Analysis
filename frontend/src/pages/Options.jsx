import { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'
import { useAuthStore } from '../store/authStore'
import { useMarketStore } from '../store/marketStore'
import SignalCard from '../components/SignalCard'
import TradeCard from '../components/TradeCard'

const API = import.meta.env.VITE_API_URL || ''

const CAPITAL_MIN = 10_000
const CAPITAL_MAX = 10_000_000
const clamp = (v) => Math.max(CAPITAL_MIN, Math.min(CAPITAL_MAX, Math.round(Number(v) || 200_000)))

function GateRow({ label, desc, value, pass, reverse = false }) {
  const ok = reverse ? !pass : pass
  return (
    <div className={`flex items-center justify-between p-3 rounded-lg border ${ok ? 'bg-green-900/15 border-green-800/40' : 'bg-[#0f1117] border-[#2a2d3a]'}`}>
      <div>
        <div className="text-xs font-semibold text-gray-300">{label}</div>
        <div className="text-xs text-gray-600 mt-0.5">{desc}</div>
      </div>
      <div className="text-right shrink-0 ml-3">
        <div className={`text-sm font-mono font-bold ${ok ? 'text-green-400' : 'text-gray-500'}`}>
          {value ?? '—'}
        </div>
        <div className={`text-xs mt-0.5 ${ok ? 'text-green-500' : 'text-gray-600'}`}>
          {ok ? '✓ PASS' : '✗ FAIL'}
        </div>
      </div>
    </div>
  )
}

function HowToTradeGuide({ tradeMode }) {
  return (
    <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-4">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">How to Execute a Trade</div>
      <div className="space-y-2.5">
        {[
          { n: '1', title: 'Wait for a Signal', desc: 'When 3 of 4 market gates pass, the AI generates a BUY CALL or BUY PUT signal. Signals appear above.' },
          { n: '2', title: 'Check the Strike & Type', desc: 'The signal shows the option type (CE/PE), strike price, and the entry premium (LTP at signal time).' },
          { n: '3', title: tradeMode === 'auto' ? 'AUTO: Trade Logged Immediately' : 'MANUAL: Enter Your Price', desc: tradeMode === 'auto' ? 'In AUTO mode, the trade is recorded at the signal LTP automatically. Switch to MANUAL to enter your own price.' : 'Enter the premium you actually paid on your broker platform. The R:R will be recalculated for your entry price.' },
          { n: '4', title: 'Manage with T1/T2/SL', desc: 'Exit 75% of lots at Target 1, hold remaining for Target 2. Stop Loss is mandatory — exit immediately if hit.' },
          { n: '5', title: 'Log Exit', desc: 'After exiting on your broker, mark the trade as closed here to track P&L.' },
        ].map(step => (
          <div key={step.n} className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-blue-900/50 border border-blue-700/50 text-blue-300 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
              {step.n}
            </div>
            <div>
              <div className="text-xs font-semibold text-gray-300">{step.title}</div>
              <div className="text-xs text-gray-600 mt-0.5 leading-relaxed">{step.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function StatBox({ label, value, color = 'text-white', sub }) {
  return (
    <div className="bg-[#0f1117] rounded-lg p-3 text-center">
      <div className={`text-xl font-bold ${color}`}>{value ?? '—'}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
      {sub && <div className="text-xs text-gray-600">{sub}</div>}
    </div>
  )
}

export default function Options() {
  const { user } = useAuth()
  const updateUser = useAuthStore(s => s.updateUser)
  const activeSignals = useMarketStore(s => s.activeSignals)
  const openTrades = useMarketStore(s => s.openTrades)
  const marketData = useMarketStore(s => s.marketData)

  const [capital, setCapital] = useState(clamp(user?.capital))
  const [tradeMode, setTradeMode] = useState(user?.trade_mode || 'auto')
  const [tradeHistory, setTradeHistory] = useState([])
  const [predHistory, setPredHistory] = useState([])
  const [predAccuracy, setPredAccuracy] = useState(null)
  const [loading, setLoading] = useState(true)
  const [savingCapital, setSavingCapital] = useState(false)
  const [errors, setErrors] = useState({})
  const [showGuide, setShowGuide] = useState(false)

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    const results = await Promise.allSettled([
      axios.get(`${API}/api/trades/history?days=30`),
      axios.get(`${API}/api/trades/open`),
      axios.get(`${API}/api/signals/active`),
      axios.get(`${API}/api/trades/capital`),
      axios.get(`${API}/api/predictions/history?days=30`),
      axios.get(`${API}/api/predictions/accuracy?days=30`),
    ])
    const [tradesRes, openRes, signalsRes, settingsRes, predHistRes, predAccRes] = results
    const newErrors = {}

    if (tradesRes.status === 'fulfilled') setTradeHistory(tradesRes.value.data.trades || [])
    else newErrors.trades = 'Failed to load trade history'

    if (openRes.status === 'fulfilled') useMarketStore.getState().setOpenTrades(openRes.value.data.trades || [])
    if (signalsRes.status === 'fulfilled') useMarketStore.getState().setActiveSignals(signalsRes.value.data.signals || [])
    if (settingsRes.status === 'fulfilled') {
      if (settingsRes.value.data.trade_mode) setTradeMode(settingsRes.value.data.trade_mode)
      if (settingsRes.value.data.capital) setCapital(clamp(settingsRes.value.data.capital))
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
    } catch {
      setErrors(e => ({ ...e, capital: 'Failed to save capital' }))
    } finally {
      setSavingCapital(false)
    }
  }

  const switchMode = async (mode) => {
    try {
      await axios.put(`${API}/api/trades/mode`, { mode })
      setTradeMode(mode)
      updateUser({ trade_mode: mode })
    } catch {
      setErrors(e => ({ ...e, mode: 'Failed to switch mode' }))
    }
  }

  const niftySignal = activeSignals.find(s => s.underlying !== 'BANKNIFTY') || null
  const bnSignal = activeSignals.find(s => s.underlying === 'BANKNIFTY') || null

  const closedTrades = tradeHistory.filter(t => t.status === 'CLOSED')
  const winTrades = closedTrades.filter(t => (t.net_pnl || 0) > 0)
  const winRate = closedTrades.length ? Math.round((winTrades.length / closedTrades.length) * 100) : null
  const totalPnl = closedTrades.reduce((s, t) => s + (t.net_pnl || 0), 0)

  // Current market gate status
  const vix = marketData?.india_vix
  const nifty = marketData?.nifty
  const vwap = marketData?.vwap
  const fiiNet = marketData?.fii_net
  const pcr = marketData?.put_call_ratio
  const hasGateData = vix != null && nifty != null

  const callGates = [
    { label: 'VIX ≤ 28', desc: 'Volatility manageable for calls', value: vix?.toFixed(2), pass: vix != null && vix <= 28 },
    { label: 'Price > VWAP', desc: 'Nifty above intraday average', value: vwap ? `${nifty?.toFixed(0)} vs ${vwap?.toFixed(0)}` : nifty?.toFixed(0), pass: nifty != null && vwap != null && nifty > vwap },
    { label: 'FII Net Buying', desc: 'Foreign institutions buying', value: fiiNet != null ? `₹${fiiNet > 0 ? '+' : ''}${Math.abs(fiiNet).toFixed(0)}Cr` : null, pass: fiiNet != null && fiiNet > 0 },
    { label: 'PCR ≥ 0.50', desc: 'Not excessively bearish positioning', value: pcr?.toFixed(3), pass: pcr != null && pcr >= 0.5 },
  ]
  const putGates = [
    { label: 'VIX ≥ 15', desc: 'Enough fear for put premium', value: vix?.toFixed(2), pass: vix != null && vix >= 15 },
    { label: 'Price < VWAP', desc: 'Nifty below intraday average', value: vwap ? `${nifty?.toFixed(0)} vs ${vwap?.toFixed(0)}` : nifty?.toFixed(0), pass: nifty != null && vwap != null && nifty < vwap },
    { label: 'FII Net Selling', desc: 'Foreign institutions selling', value: fiiNet != null ? `₹${fiiNet > 0 ? '+' : ''}${Math.abs(fiiNet).toFixed(0)}Cr` : null, pass: fiiNet != null && fiiNet < 0 },
    { label: 'PCR ≤ 1.30', desc: 'Not excessively bullish positioning', value: pcr?.toFixed(3), pass: pcr != null && pcr <= 1.3 },
  ]

  const callGateCount = callGates.filter(g => g.pass).length
  const putGateCount = putGates.filter(g => g.pass).length

  return (
    <div className="p-4 lg:p-6 space-y-5 max-w-4xl mx-auto">
      {/* Page Title + Disclaimer */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold text-gray-200">Options Signal Board</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            AI-generated BUY CALL / BUY PUT signals for NIFTY 50 and BANK NIFTY · 4-gate system
          </p>
        </div>
        <button
          onClick={() => setShowGuide(g => !g)}
          className="px-3 py-1.5 text-xs rounded-lg border border-[#2a2d3a] text-gray-400 hover:text-gray-200 shrink-0"
        >
          {showGuide ? '✕ Close Guide' : '? How to Trade'}
        </button>
      </div>

      {showGuide && <HowToTradeGuide tradeMode={tradeMode} />}

      <div className="text-xs text-yellow-700 bg-yellow-900/15 border border-yellow-800/30 rounded-lg px-3 py-2">
        ⚠️ Technical analysis only. NOT SEBI-registered investment advice. Options carry significant risk of total capital loss.
      </div>

      {/* Live Gate Status */}
      {hasGateData && (
        <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Live Gate Status</div>
              <div className="text-xs text-gray-600 mt-0.5">Signal fires when 3+ gates pass. Checked every 10 min during market hours.</div>
            </div>
            <div className="flex gap-3 shrink-0">
              <div className="text-center">
                <div className={`text-lg font-bold ${callGateCount >= 3 ? 'text-green-400' : 'text-gray-600'}`}>{callGateCount}/4</div>
                <div className="text-[10px] text-gray-600">CALL</div>
              </div>
              <div className="text-center">
                <div className={`text-lg font-bold ${putGateCount >= 3 ? 'text-red-400' : 'text-gray-600'}`}>{putGateCount}/4</div>
                <div className="text-[10px] text-gray-600">PUT</div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div>
              <div className="text-[10px] text-green-600 font-semibold uppercase mb-1.5">CALL gates (bullish)</div>
              <div className="space-y-1.5">
                {callGates.map((g, i) => <GateRow key={i} {...g} />)}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-red-600 font-semibold uppercase mb-1.5">PUT gates (bearish)</div>
              <div className="space-y-1.5">
                {putGates.map((g, i) => <GateRow key={i} {...g} />)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Capital + Mode */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-4">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Your Trading Capital</div>
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <div className="text-xs text-gray-500 mb-1">Amount (₹)</div>
              <input
                type="number"
                className="w-full bg-[#0f1117] border border-[#2a2d3a] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-600"
                value={capital}
                min={10000} max={10000000} step={10000}
                onChange={e => setCapital(e.target.value)}
                onBlur={e => setCapital(clamp(e.target.value))}
              />
            </div>
            <button onClick={saveCapital} disabled={savingCapital}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors disabled:opacity-50">
              {savingCapital ? '...' : 'Save'}
            </button>
          </div>
          <div className="mt-2 text-sm font-semibold text-white">
            {capital >= 100000 ? `₹${(capital/100000).toFixed(2)}L` : `₹${Number(capital).toLocaleString('en-IN')}`}
          </div>
          <div className="text-xs text-gray-600 mt-0.5">Position sizing uses 2% risk rule per trade</div>
          {errors.capital && <p className="text-xs text-red-400 mt-1">{errors.capital}</p>}
        </div>

        <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-4">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Trade Mode</div>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => switchMode('auto')}
              className={`py-3 rounded-lg text-sm font-semibold border transition-all
                ${tradeMode === 'auto'
                  ? 'bg-green-600/20 border-green-500 text-green-300'
                  : 'border-[#2a2d3a] text-gray-500 hover:text-gray-300'}`}>
              ⚡ AUTO
            </button>
            <button onClick={() => switchMode('manual')}
              className={`py-3 rounded-lg text-sm font-semibold border transition-all
                ${tradeMode === 'manual'
                  ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                  : 'border-[#2a2d3a] text-gray-500 hover:text-gray-300'}`}>
              ✋ MANUAL
            </button>
          </div>
          <p className={`text-xs mt-2 leading-relaxed ${tradeMode === 'auto' ? 'text-green-700' : 'text-blue-700'}`}>
            {tradeMode === 'auto'
              ? 'Trades logged automatically at signal LTP. No confirmation needed.'
              : 'You enter your actual premium paid. R:R recalculated for your entry.'}
          </p>
        </div>
      </div>

      {/* Active Signals */}
      <div>
        <div className="flex items-baseline gap-2 mb-3">
          <h2 className="text-sm font-semibold text-gray-300">Active Signals</h2>
          <span className="text-xs text-gray-600">{activeSignals.length} active</span>
        </div>
        {loading ? (
          <div className="flex items-center justify-center h-28 text-gray-600 text-sm">Loading signals...</div>
        ) : !niftySignal && !bnSignal ? (
          <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-8 text-center">
            <div className="text-4xl mb-3">⏳</div>
            <div className="text-gray-400 text-sm font-medium">No active signals right now</div>
            <div className="text-gray-600 text-xs mt-2 max-w-xs mx-auto">
              Signals are generated when 3 of 4 gates pass simultaneously. The bot checks every 10 minutes during market hours (9:15 AM – 2:00 PM IST).
            </div>
            {hasGateData && (
              <div className="mt-3 flex justify-center gap-4">
                <span className={`text-xs ${callGateCount >= 3 ? 'text-green-400' : 'text-gray-600'}`}>
                  CALL: {callGateCount}/4 gates
                </span>
                <span className={`text-xs ${putGateCount >= 3 ? 'text-red-400' : 'text-gray-600'}`}>
                  PUT: {putGateCount}/4 gates
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {niftySignal && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs px-2 py-0.5 bg-blue-900/50 text-blue-300 border border-blue-800/40 rounded">NIFTY 50</span>
                  <span className="text-xs text-gray-600">Lot size: 25 · Check your broker for current expiry</span>
                </div>
                <SignalCard signal={niftySignal} tradeMode={tradeMode} capital={capital} />
              </div>
            )}
            {bnSignal && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs px-2 py-0.5 bg-purple-900/50 text-purple-300 border border-purple-800/40 rounded">BANK NIFTY</span>
                  <span className="text-xs text-gray-600">Lot size: 15 · Check your broker for current expiry</span>
                </div>
                <SignalCard signal={bnSignal} tradeMode={tradeMode} capital={capital} />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Open Trades */}
      {openTrades.length > 0 && (
        <div>
          <div className="flex items-baseline gap-2 mb-3">
            <h2 className="text-sm font-semibold text-gray-300">Open Positions</h2>
            <span className="text-xs text-gray-600">{openTrades.length} active trade{openTrades.length > 1 ? 's' : ''}</span>
          </div>
          <div className="space-y-3">
            {openTrades.map(trade => (
              <TradeCard
                key={trade.id}
                trade={trade}
                signal={activeSignals.find(s => s.id === trade.signal_id)}
                onExit={loadData}
              />
            ))}
          </div>
        </div>
      )}

      {/* Performance */}
      {!loading && closedTrades.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-gray-300 mb-3">30-Day Performance</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatBox label="Total Trades" value={closedTrades.length} />
            <StatBox label="Win Rate" value={winRate != null ? `${winRate}%` : '—'} color={winRate >= 50 ? 'text-green-400' : 'text-red-400'} />
            <StatBox label="Net P&L" value={totalPnl !== 0 ? `${totalPnl >= 0 ? '+' : ''}₹${Math.abs(totalPnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '₹0'} color={totalPnl >= 0 ? 'text-green-400' : 'text-red-400'} />
            <StatBox label="AI Accuracy" value={predAccuracy?.accuracy_pct != null ? `${predAccuracy.accuracy_pct}%` : '—'} color="text-blue-400" />
          </div>
        </div>
      )}

      {/* Trade Journal */}
      <div>
        <div className="flex items-baseline gap-2 mb-3">
          <h2 className="text-sm font-semibold text-gray-300">Trade Journal</h2>
          <span className="text-xs text-gray-600">Last 30 days</span>
        </div>
        {errors.trades && <p className="text-xs text-red-400 mb-2">{errors.trades}</p>}
        {!loading && tradeHistory.length === 0 ? (
          <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-6 text-center text-gray-600 text-sm">
            No closed trades yet
          </div>
        ) : (
          <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-500 border-b border-[#2a2d3a] bg-[#13151e]">
                    <th className="text-left px-4 py-2.5">Date</th>
                    <th className="text-left px-2 py-2.5">Index</th>
                    <th className="text-left px-2 py-2.5">Type</th>
                    <th className="text-right px-2 py-2.5">Mode</th>
                    <th className="text-right px-2 py-2.5">Lots</th>
                    <th className="text-right px-2 py-2.5">Entry ₹</th>
                    <th className="text-right px-2 py-2.5">Exit ₹</th>
                    <th className="text-right px-2 py-2.5">R:R</th>
                    <th className="text-right px-4 py-2.5">Net P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {tradeHistory.slice(0, 30).map(trade => (
                    <tr key={trade.id} className="border-b border-[#2a2d3a]/40 hover:bg-[#0f1117]/50">
                      <td className="px-4 py-2 text-gray-400">{trade.entry_time ? new Date(trade.entry_time).toLocaleDateString('en-IN', { day:'2-digit', month:'short' }) : '—'}</td>
                      <td className="px-2 py-2 text-gray-400 text-[10px]">{trade.signal?.underlying || '—'}</td>
                      <td className="px-2 py-2">
                        <span className={`text-[10px] font-bold ${trade.signal?.signal_type === 'BUY_CALL' ? 'text-green-400' : 'text-red-400'}`}>
                          {trade.signal?.signal_type === 'BUY_CALL' ? '▲ CALL' : '▼ PUT'}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-right">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${trade.trade_mode === 'auto' ? 'bg-green-900/40 text-green-400' : 'bg-blue-900/40 text-blue-400'}`}>
                          {trade.trade_mode}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-right text-gray-300">{trade.lots}</td>
                      <td className="px-2 py-2 text-right font-mono text-gray-300">₹{trade.entry_premium}</td>
                      <td className="px-2 py-2 text-right font-mono text-gray-400">{trade.exit_premium ? `₹${trade.exit_premium}` : '—'}</td>
                      <td className="px-2 py-2 text-right text-gray-400">{trade.rr_at_entry ? `1:${trade.rr_at_entry}` : '—'}</td>
                      <td className={`px-4 py-2 text-right font-mono font-semibold ${(trade.net_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {trade.net_pnl != null ? `${trade.net_pnl >= 0 ? '+' : ''}₹${Math.abs(trade.net_pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* AI Predictions */}
      <div className="border-t border-[#2a2d3a] pt-5">
        <div className="flex items-baseline gap-2 mb-3">
          <h2 className="text-sm font-semibold text-gray-300">AI Market Predictions</h2>
          <span className="text-xs text-gray-600">Claude-powered daily brief</span>
        </div>
        {predAccuracy && (
          <div className="grid grid-cols-4 gap-3 mb-4">
            <StatBox label="Accuracy" value={`${predAccuracy.accuracy_pct ?? '—'}%`} />
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
              {predHistory.slice(0, 15).map(p => (
                <div key={p.id} className="px-4 py-3 flex items-center justify-between hover:bg-[#0f1117]/50">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500 text-xs font-mono">{new Date(p.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</span>
                      <span className={`font-bold text-sm ${p.direction === 'UP' ? 'text-green-400' : p.direction === 'DOWN' ? 'text-red-400' : 'text-yellow-400'}`}>
                        {p.direction === 'UP' ? '↑' : p.direction === 'DOWN' ? '↓' : '→'} {p.direction}
                      </span>
                      <span className="text-gray-600 text-xs">{p.magnitude_low}–{p.magnitude_high}%</span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <div className="w-16 h-1 bg-[#0f1117] rounded-full">
                        <div className={`h-full rounded-full ${p.confidence >= 70 ? 'bg-green-500' : 'bg-yellow-500'}`} style={{ width: `${p.confidence}%` }} />
                      </div>
                      <span className="text-xs text-gray-600">{p.confidence}% conf</span>
                    </div>
                  </div>
                  <div className="text-right">
                    {p.was_correct !== null ? (
                      <span className={`text-lg font-bold ${p.was_correct ? 'text-green-400' : 'text-red-400'}`}>{p.was_correct ? '✓' : '✗'}</span>
                    ) : <span className="text-gray-600 text-xs">pending</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
