import { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'
import { useMarketStore } from '../store/marketStore'
import SignalCard from '../components/SignalCard'
import TradeCard from '../components/TradeCard'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function Options() {
  const { user } = useAuth()
  const activeSignals = useMarketStore(s => s.activeSignals)
  const openTrades = useMarketStore(s => s.openTrades)

  const [capital, setCapital] = useState(user?.capital || 200000)
  const [tradeMode, setTradeMode] = useState(user?.trade_mode || 'auto')
  const [tradeHistory, setTradeHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [savingCapital, setSavingCapital] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [tradesRes, openRes, signalsRes] = await Promise.all([
        axios.get(`${API}/api/trades/history?days=30`),
        axios.get(`${API}/api/trades/open`),
        axios.get(`${API}/api/signals/active`),
      ])
      setTradeHistory(tradesRes.data.trades || [])
      useMarketStore.getState().setOpenTrades(openRes.data.trades || [])
      useMarketStore.getState().setActiveSignals(signalsRes.data.signals || [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const saveCapital = async () => {
    setSavingCapital(true)
    try {
      await axios.put(`${API}/api/trades/capital`, { capital: Number(capital) })
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
    } catch (err) {
      alert('Failed to switch mode')
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-500">Loading...</div>
  )

  const latestSignal = activeSignals[0] || null

  return (
    <div className="p-4 space-y-4 max-w-2xl mx-auto">
      <p className="text-xs text-yellow-700 bg-yellow-900/20 border border-yellow-800/40 rounded-lg px-3 py-2">
        ⚠️ Technical analysis signals for educational/tracking purposes only. NOT SEBI-registered investment advice.
        Options trading carries significant risk.
      </p>

      {/* Capital + Mode */}
      <div className="card space-y-3">
        <div>
          <label className="text-sm text-gray-400 mb-1 block">Your Capital (₹)</label>
          <div className="flex gap-2">
            <input
              type="number"
              className="input"
              value={capital}
              onChange={e => setCapital(e.target.value)}
            />
            <button onClick={saveCapital} disabled={savingCapital} className="btn-primary shrink-0">
              {savingCapital ? '...' : 'Save'}
            </button>
          </div>
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

      {/* Active signal */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 mb-2">Active Signal</h3>
        {latestSignal ? (
          <SignalCard signal={latestSignal} tradeMode={tradeMode} capital={capital} />
        ) : (
          <div className="card text-center text-gray-600 py-8">
            No active signals right now.<br/>
            <span className="text-xs">Bot checks every 5 minutes during market hours.</span>
          </div>
        )}
      </div>

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
    </div>
  )
}
