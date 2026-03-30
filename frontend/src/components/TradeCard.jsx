import axios from 'axios'
import { useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function TradeCard({ trade, signal, onExit }) {
  const [exiting, setExiting] = useState(false)

  if (!trade) return null

  const pnl = trade.unrealised_pnl ?? 0
  const pnlPct = trade.capital_at_entry ? (pnl / trade.capital_at_entry * 100).toFixed(2) : 0
  const isProfit = pnl >= 0

  const handleExit = async (reason) => {
    const exitPremium = trade.current_premium || trade.entry_premium
    setExiting(true)
    try {
      await axios.post(`${API}/api/trades/${trade.id}/exit`, {
        exit_premium: exitPremium,
        exit_reason: reason,
      })
      onExit?.()
    } catch (err) {
      alert(err.response?.data?.detail || 'Exit failed')
    } finally {
      setExiting(false)
    }
  }

  const t1Progress = signal
    ? Math.min(100, Math.max(0,
        ((trade.current_premium || trade.entry_premium) - trade.entry_premium) /
        (signal.target1 - trade.entry_premium) * 100
      ))
    : 0

  return (
    <div className="card border border-yellow-800/40">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="font-semibold">
            {signal?.strike} {signal?.option_type} — {trade.lots} lots
          </div>
          <div className="text-xs text-gray-500">
            Entry ₹{trade.entry_premium} · R:R 1:{trade.rr_at_entry?.toFixed(1)}
          </div>
        </div>
        <div className={`text-right ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
          <div className="font-bold text-lg">{isProfit ? '+' : ''}₹{pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
          <div className="text-xs">{isProfit ? '+' : ''}{pnlPct}%</div>
        </div>
      </div>

      {/* Current premium */}
      {trade.current_premium && (
        <div className="text-sm text-gray-400 mb-3">
          Current: <span className="text-white font-mono">₹{trade.current_premium}</span>
          {trade.t1_exit_done && <span className="badge badge-green ml-2">T1 ✓</span>}
        </div>
      )}

      {/* Progress bar to T1 */}
      {signal && !trade.t1_exit_done && (
        <div className="mb-3">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Entry ₹{trade.entry_premium}</span>
            <span>T1 ₹{signal.target1}</span>
          </div>
          <div className="h-2 bg-[#0f1117] rounded-full">
            <div
              className="h-full bg-green-500 rounded-full transition-all"
              style={{ width: `${Math.max(2, t1Progress)}%` }}
            />
          </div>
        </div>
      )}

      {/* Partial exit info */}
      {trade.t1_exit_done && (
        <div className="bg-green-900/20 rounded-lg px-3 py-2 mb-3 text-sm">
          <span className="text-green-400">T1 locked: +₹{trade.t1_exit_profit?.toLocaleString('en-IN')}</span>
          <span className="text-gray-400"> · Trailing SL: ₹{trade.trailing_sl_after_t1}</span>
        </div>
      )}

      {/* Exit buttons */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => handleExit('TARGET1')}
          disabled={exiting}
          className="text-xs bg-green-900/40 hover:bg-green-900/70 text-green-300 border border-green-800/50 px-3 py-1.5 rounded-lg transition-colors"
        >
          Exit at T1
        </button>
        <button
          onClick={() => handleExit('TARGET2')}
          disabled={exiting}
          className="text-xs bg-blue-900/40 hover:bg-blue-900/70 text-blue-300 border border-blue-800/50 px-3 py-1.5 rounded-lg transition-colors"
        >
          Exit at T2
        </button>
        <button
          onClick={() => handleExit('STOP_LOSS')}
          disabled={exiting}
          className="text-xs bg-red-900/40 hover:bg-red-900/70 text-red-300 border border-red-800/50 px-3 py-1.5 rounded-lg transition-colors"
        >
          Exit at SL
        </button>
        <button
          onClick={() => handleExit('MANUAL')}
          disabled={exiting}
          className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 px-3 py-1.5 rounded-lg transition-colors"
        >
          Manual Exit
        </button>
      </div>
    </div>
  )
}
