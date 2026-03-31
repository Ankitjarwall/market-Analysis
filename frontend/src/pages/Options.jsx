import { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'
import { useAuthStore } from '../store/authStore'
import { useMarketStore } from '../store/marketStore'
import SignalCard from '../components/SignalCard'
import TradeCard from '../components/TradeCard'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function Options() {
  const { user } = useAuth()
  const updateUser = useAuthStore(s => s.updateUser)
  const activeSignals = useMarketStore(s => s.activeSignals)
  const openTrades = useMarketStore(s => s.openTrades)

  const CAPITAL_MIN = 10_000        // ₹10,000 minimum
  const CAPITAL_MAX = 10_000_000   // ₹1 crore maximum
  const clampCapital = (v) => Math.max(CAPITAL_MIN, Math.min(CAPITAL_MAX, Math.round(Number(v) || 200_000)))
  const [capital, setCapital] = useState(clampCapital(user?.capital))
  const [tradeMode, setTradeMode] = useState(user?.trade_mode || 'auto')
  const [tradeHistory, setTradeHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [savingCapital, setSavingCapital] = useState(false)
  const [predHistory, setPredHistory] = useState([])
  const [predAccuracy, setPredAccuracy] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [tradesRes, openRes, signalsRes, settingsRes, predHistRes, predAccRes] = await Promise.all([
        axios.get(`${API}/api/trades/history?days=30`),
        axios.get(`${API}/api/trades/open`),
        axios.get(`${API}/api/signals/active`),
        axios.get(`${API}/api/trades/capital`),
        axios.get(`${API}/api/predictions/history?days=30`),
        axios.get(`${API}/api/predictions/accuracy?days=30`),
      ])
      setTradeHistory(tradesRes.data.trades || [])
      useMarketStore.getState().setOpenTrades(openRes.data.trades || [])
      useMarketStore.getState().setActiveSignals(signalsRes.data.signals || [])
      if (settingsRes.data.trade_mode) setTradeMode(settingsRes.data.trade_mode)
      if (settingsRes.data.capital) setCapital(clampCapital(settingsRes.data.capital))
      setPredHistory(predHistRes.data.predictions || [])
      setPredAccuracy(predAccRes.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const saveCapital = async () => {
    const clamped = clampCapital(capital)
    setCapital(clamped)
    setSavingCapital(true)
    try {
      await axios.put(`${API}/api/trades/capital`, { capital: clamped })
      updateUser({ capital: clamped })
    } catch (err) {
      alert('Failed to save capital')
    } finally {
      setSavingCapital(false)
    }
  }

  const switchMode = async (mode) => {
    try {
      await axios.put(`${API}/api/trades/mode`, { mode })
      setTradeMode(mode)
      updateUser({ trade_mode: mode })
    } catch (err) {
      alert('Failed to switch mode')
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-500">Loading...</div>
  )

  const niftySignal = activeSignals.find(s => s.underlying !== 'BANKNIFTY') || null
  const bnSignal = activeSignals.find(s => s.underlying === 'BANKNIFTY') || null

  return (
    <div className="p-4 space-y-4 max-w-2xl mx-auto">
      <p className="text-xs text-yellow-700 bg-yellow-900/20 border border-yellow-800/40 rounded-lg px-3 py-2">
        ⚠️ Technical analysis signals for educational/tracking purposes only. NOT SEBI-registered investment advice.
        Options trading carries significant risk.
      </p>

      {/* Capital + Mode */}
      <div className="card space-y-3">
        <div>
          <label className="text-sm text-gray-400 mb-1 block">
            Your Capital (₹)
            <span className="text-gray-600 font-normal ml-2">
              {capital >= 100000
                ? `₹${(capital / 100000).toFixed(capital % 100000 === 0 ? 0 : 1)} lakh`
                : `₹${Number(capital).toLocaleString('en-IN')}`}
            </span>
          </label>
          <div className="flex gap-2">
            <input
              type="number"
              className="input"
              value={capital}
              min={10000}
              max={10000000}
              step={10000}
              onChange={e => setCapital(e.target.value)}
              onBlur={e => setCapital(clampCapital(e.target.value))}
            />
            <button onClick={saveCapital} disabled={savingCapital} className="btn-primary shrink-0">
              {savingCapital ? '...' : 'Save'}
            </button>
          </div>
          <p className="text-xs text-gray-600 mt-1">Min ₹10,000 · Max ₹1,00,00,000</p>
        </div>

        <div>
          <label className="text-sm text-gray-400 mb-2 block">Trade Mode</label>
          <div className="flex gap-2">
            <button
              onClick={() => switchMode('auto')}
              className={`flex-1 py-2 rounded-lg text-sm font-semibold border transition-colors
                ${tradeMode === 'auto'
                  ? 'bg-green-600 border-green-500 text-white'
                  : 'border-[#2a2d3a] text-gray-400 hover:border-gray-500'}`}
            >
              ⚡ AUTO
            </button>
            <button
              onClick={() => switchMode('manual')}
              className={`flex-1 py-2 rounded-lg text-sm font-semibold border transition-colors
                ${tradeMode === 'manual'
                  ? 'bg-blue-600 border-blue-500 text-white'
                  : 'border-[#2a2d3a] text-gray-400 hover:border-gray-500'}`}
            >
              ✋ MANUAL
            </button>
          </div>
          {tradeMode === 'auto' && (
            <p className="text-xs text-green-600 mt-1">Auto mode: signals are logged immediately without confirmation.</p>
          )}
        </div>
      </div>

      {/* Active signals — split by underlying */}
      {!niftySignal && !bnSignal ? (
        <div>
          <h3 className="text-sm font-semibold text-gray-400 mb-2">Active Signals</h3>
          <div className="card text-center text-gray-600 py-8">
            No active signals right now.<br/>
            <span className="text-xs">Nifty checked :00/:10/... · Bank Nifty checked :05/:15/...</span>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {niftySignal && (
            <div>
              <h3 className="text-sm font-semibold text-gray-400 mb-2">
                <span className="inline-block px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded text-xs mr-2">NIFTY 50</span>
                Active Signal
              </h3>
              <SignalCard signal={niftySignal} tradeMode={tradeMode} capital={capital} />
            </div>
          )}
          {bnSignal && (
            <div>
              <h3 className="text-sm font-semibold text-gray-400 mb-2">
                <span className="inline-block px-2 py-0.5 bg-purple-900/50 text-purple-300 rounded text-xs mr-2">BANK NIFTY</span>
                Active Signal
              </h3>
              <SignalCard signal={bnSignal} tradeMode={tradeMode} capital={capital} />
            </div>
          )}
        </div>
      )}

      {/* Open trades */}
      {openTrades.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-400 mb-2">Open Trades</h3>
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

      {/* Trade history */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 mb-2">Trade Journal (Last 30 Days)</h3>
        {tradeHistory.length === 0 ? (
          <div className="card text-center text-gray-600 py-6 text-sm">No closed trades yet</div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-[#2a2d3a]">
                  <th className="text-left py-2">Entry</th>
                  <th className="text-right">Mode</th>
                  <th className="text-right">Lots</th>
                  <th className="text-right">Entry ₹</th>
                  <th className="text-right">Exit ₹</th>
                  <th className="text-right">Net P&L</th>
                  <th className="text-right">%</th>
                </tr>
              </thead>
              <tbody>
                {tradeHistory.slice(0, 20).map(trade => (
                  <tr key={trade.id} className="border-b border-[#2a2d3a]/50 hover:bg-[#0f1117]/50">
                    <td className="py-1.5 text-gray-400">
                      {trade.entry_time ? new Date(trade.entry_time).toLocaleDateString('en-IN') : '—'}
                    </td>
                    <td className="text-right">
                      <span className={`badge ${trade.trade_mode === 'auto' ? 'badge-green' : 'badge-blue'}`}>
                        {trade.trade_mode}
                      </span>
                    </td>
                    <td className="text-right">{trade.lots}</td>
                    <td className="text-right font-mono">₹{trade.entry_premium}</td>
                    <td className="text-right font-mono">{trade.exit_premium ? `₹${trade.exit_premium}` : '—'}</td>
                    <td className={`text-right font-mono font-semibold ${(trade.net_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {trade.net_pnl != null ? `${trade.net_pnl >= 0 ? '+' : ''}₹${trade.net_pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—'}
                    </td>
                    <td className={`text-right ${(trade.net_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {trade.net_pnl_pct != null ? `${trade.net_pnl_pct >= 0 ? '+' : ''}${trade.net_pnl_pct.toFixed(2)}%` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Predictions section (merged from /predictions) ── */}
      <div className="border-t border-[#2a2d3a] pt-4">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">🔮 AI Predictions</h2>

        {predAccuracy && (
          <div className="card mb-3">
            <h3 className="text-xs font-semibold text-gray-400 mb-3">30-Day Accuracy</h3>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <div className="text-2xl font-bold text-white">{predAccuracy.accuracy_pct ?? '—'}%</div>
                <div className="text-xs text-gray-500">Overall</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-400">{predAccuracy.correct ?? 0}</div>
                <div className="text-xs text-gray-500">Correct</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-red-400">{predAccuracy.incorrect ?? 0}</div>
                <div className="text-xs text-gray-500">Wrong</div>
              </div>
            </div>
          </div>
        )}

        <div className="card">
          <h3 className="text-xs font-semibold text-gray-400 mb-3">Prediction History</h3>
          {predHistory.length === 0 ? (
            <div className="text-gray-600 text-sm text-center py-4">No predictions yet</div>
          ) : (
            <div className="space-y-2">
              {predHistory.slice(0, 15).map(p => (
                <div key={p.id} className="flex items-center justify-between py-2 border-b border-[#2a2d3a]/50 last:border-0">
                  <div>
                    <div className="text-sm">
                      {new Date(p.date).toLocaleDateString('en-IN')}
                      <span className={`ml-2 font-semibold
                        ${p.direction === 'UP' ? 'text-green-400' :
                          p.direction === 'DOWN' ? 'text-red-400' : 'text-yellow-400'}`}>
                        {p.direction}
                      </span>
                      <span className="text-gray-500 text-xs ml-1">
                        {p.magnitude_low}–{p.magnitude_high}%
                      </span>
                    </div>
                    <div className="text-xs text-gray-600">{p.confidence}% confidence</div>
                  </div>
                  <div className="text-right">
                    {p.was_correct !== null ? (
                      <span className={p.was_correct ? 'text-green-400 text-lg' : 'text-red-400 text-lg'}>
                        {p.was_correct ? '✓' : '✗'}
                      </span>
                    ) : (
                      <span className="text-gray-600 text-sm">—</span>
                    )}
                    {p.actual_direction && (
                      <div className="text-xs text-gray-500">actual: {p.actual_direction} ({p.actual_magnitude?.toFixed(1)}%)</div>
                    )}
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
