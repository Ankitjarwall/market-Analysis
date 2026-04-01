import axios from 'axios'
import { useState } from 'react'

const API = import.meta.env.VITE_API_URL || ''

const fmt = (n, decimals = 0) =>
  n != null ? Number(n).toLocaleString('en-IN', { maximumFractionDigits: decimals }) : '—'
const fmtRs = (n, decimals = 0) => n != null ? `₹${fmt(n, decimals)}` : '—'

export default function TradeCard({ trade, signal, onExit }) {
  const [exiting, setExiting] = useState(false)
  const [exitPremium, setExitPremium] = useState('')
  const [showExitForm, setShowExitForm] = useState(false)

  if (!trade) return null

  const isCall = signal?.signal_type === 'BUY_CALL'
  const isBankNifty = signal?.underlying === 'BANKNIFTY'
  const lotSize = isBankNifty ? 15 : 25
  const lots = trade.lots || 1

  const entryPremium = trade.entry_premium || 0
  const currentPremium = trade.current_premium || entryPremium
  const sl = signal?.stop_loss || 0
  const t1 = signal?.target1 || 0
  const t2 = signal?.target2 || 0

  const moneyDeployed = entryPremium * lots * lotSize
  const maxLoss = sl ? Math.abs(entryPremium - sl) * lots * lotSize : (trade.max_loss_calculated || 0)
  const t1Profit = t1 ? Math.abs(t1 - entryPremium) * lots * lotSize : (trade.target1_profit_calculated || 0)
  const t2Profit = t2 ? Math.abs(t2 - entryPremium) * lots * lotSize : (trade.target2_profit_calculated || 0)

  const unrealPnl = (currentPremium - entryPremium) * lots * lotSize * (isCall ? 1 : -1)
  const pnl = trade.net_pnl ?? (trade.status === 'OPEN' ? unrealPnl : 0)
  const isPnlPositive = pnl >= 0

  // T1 progress bar
  const targetForProgress = isCall ? t1 : sl ? 2 * entryPremium - t1 : 0
  const t1Progress = t1 && entryPremium && t1 !== entryPremium
    ? Math.min(100, Math.max(0,
        ((currentPremium - entryPremium) / (t1 - entryPremium)) * 100
      ))
    : 0

  const handleExit = async (reason, premium) => {
    setExiting(true)
    try {
      await axios.post(`${API}/api/trades/${trade.id}/exit`, {
        exit_premium: Number(premium || currentPremium),
        exit_reason: reason,
      })
      onExit?.()
    } catch (err) {
      alert(err.response?.data?.detail || 'Exit failed')
    } finally {
      setExiting(false)
      setShowExitForm(false)
    }
  }

  const entryTime = trade.entry_time
    ? new Date(trade.entry_time).toLocaleString('en-IN', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true,
      })
    : '—'

  return (
    <div className={`card border-l-4 ${isCall ? 'border-l-green-500' : 'border-l-red-500'}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`px-2 py-0.5 rounded text-xs font-bold ${isBankNifty ? 'bg-purple-900/60 text-purple-300' : 'bg-blue-900/60 text-blue-300'}`}>
              {isBankNifty ? 'BANK NIFTY' : 'NIFTY 50'}
            </span>
            <span className={`text-sm font-bold ${isCall ? 'text-green-400' : 'text-red-400'}`}>
              {isCall ? '▲ BUY CALL' : '▼ BUY PUT'}
            </span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${trade.trade_mode === 'auto' ? 'bg-green-900/40 text-green-400' : 'bg-blue-900/40 text-blue-400'}`}>
              {trade.trade_mode?.toUpperCase()}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">Entered {entryTime}</div>
        </div>
        <div className={`text-right ${isPnlPositive ? 'text-green-400' : 'text-red-400'}`}>
          <div className="text-lg font-bold">{isPnlPositive ? '+' : ''}{fmtRs(pnl)}</div>
          <div className="text-xs text-gray-500">{trade.status === 'OPEN' ? 'unrealised' : 'net P&L'}</div>
        </div>
      </div>

      {/* Core trade metrics */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="bg-[#0f1117] rounded-lg p-3 text-center">
          <div className="text-[10px] text-gray-500 mb-1">STRIKE</div>
          <div className="text-sm font-bold text-white font-mono">{signal?.strike ?? '—'} {signal?.option_type}</div>
          <div className="text-[10px] text-gray-500">{lots} lots × {lotSize}</div>
        </div>
        <div className="bg-[#0f1117] rounded-lg p-3 text-center">
          <div className="text-[10px] text-gray-500 mb-1">ENTRY</div>
          <div className="text-sm font-bold text-white font-mono">{fmtRs(entryPremium)}</div>
          <div className="text-[10px] text-gray-500">R:R 1:{trade.rr_at_entry?.toFixed(1) ?? '—'}</div>
        </div>
        <div className="bg-[#0f1117] rounded-lg p-3 text-center">
          <div className="text-[10px] text-gray-500 mb-1">CURRENT</div>
          <div className={`text-sm font-bold font-mono ${currentPremium > entryPremium ? 'text-green-400' : currentPremium < entryPremium ? 'text-red-400' : 'text-white'}`}>
            {fmtRs(currentPremium)}
          </div>
          {trade.t1_exit_done && <div className="text-[10px] text-green-500">T1 ✓</div>}
        </div>
      </div>

      {/* T1/T2/SL levels */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="bg-green-900/15 border border-green-900/30 rounded-lg p-2.5 text-center">
          <div className="text-[10px] text-green-600 mb-0.5">TARGET 1</div>
          <div className="text-sm font-bold text-green-400 font-mono">{fmtRs(t1)}</div>
          <div className="text-[10px] text-green-700">+{fmtRs(t1Profit)} exp.</div>
        </div>
        <div className="bg-blue-900/10 border border-blue-900/30 rounded-lg p-2.5 text-center">
          <div className="text-[10px] text-blue-600 mb-0.5">TARGET 2</div>
          <div className="text-sm font-bold text-blue-400 font-mono">{fmtRs(t2)}</div>
          <div className="text-[10px] text-blue-700">+{fmtRs(t2Profit)} exp.</div>
        </div>
        <div className="bg-red-900/15 border border-red-900/30 rounded-lg p-2.5 text-center">
          <div className="text-[10px] text-red-600 mb-0.5">STOP LOSS</div>
          <div className="text-sm font-bold text-red-400 font-mono">{fmtRs(sl)}</div>
          <div className="text-[10px] text-red-700">-{fmtRs(maxLoss)} max</div>
        </div>
      </div>

      {/* Money summary */}
      <div className="bg-[#0f1117] rounded-lg px-3 py-2 mb-4 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-[10px] text-gray-600">Deployed</div>
          <div className="text-xs font-semibold text-gray-300">{fmtRs(moneyDeployed)}</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-600">Max Loss</div>
          <div className="text-xs font-semibold text-red-400">−{fmtRs(maxLoss)}</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-600">T1 Profit</div>
          <div className="text-xs font-semibold text-green-400">+{fmtRs(t1Profit)}</div>
        </div>
      </div>

      {/* T1 progress bar */}
      {trade.status === 'OPEN' && !trade.t1_exit_done && t1 && (
        <div className="mb-4">
          <div className="flex justify-between text-[10px] text-gray-500 mb-1">
            <span>Entry {fmtRs(entryPremium)}</span>
            <span>{t1Progress.toFixed(0)}% to T1</span>
            <span>T1 {fmtRs(t1)}</span>
          </div>
          <div className="h-1.5 bg-[#0f1117] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${isCall ? 'bg-green-500' : 'bg-red-500'}`}
              style={{ width: `${Math.max(2, t1Progress)}%` }}
            />
          </div>
        </div>
      )}

      {/* T1 locked */}
      {trade.t1_exit_done && (
        <div className="bg-green-900/20 border border-green-900/30 rounded-lg px-3 py-2 mb-4">
          <span className="text-xs text-green-400 font-semibold">T1 locked: +{fmtRs(trade.t1_exit_profit)}</span>
          {trade.trailing_sl_after_t1 && (
            <span className="text-xs text-gray-500 ml-3">Trailing SL: {fmtRs(trade.trailing_sl_after_t1)}</span>
          )}
        </div>
      )}

      {/* Exit controls */}
      {trade.status === 'OPEN' && (
        <div className="space-y-2">
          <div className="flex gap-1.5 flex-wrap">
            <button onClick={() => handleExit('TARGET1', t1)} disabled={exiting}
              className="flex-1 text-xs bg-green-900/30 hover:bg-green-900/60 text-green-300 border border-green-800/50 px-2 py-1.5 rounded-lg transition-colors">
              Exit T1 ({fmtRs(t1)})
            </button>
            <button onClick={() => handleExit('TARGET2', t2)} disabled={exiting}
              className="flex-1 text-xs bg-blue-900/30 hover:bg-blue-900/60 text-blue-300 border border-blue-800/50 px-2 py-1.5 rounded-lg transition-colors">
              Exit T2 ({fmtRs(t2)})
            </button>
            <button onClick={() => handleExit('STOP_LOSS', sl)} disabled={exiting}
              className="flex-1 text-xs bg-red-900/30 hover:bg-red-900/60 text-red-300 border border-red-800/50 px-2 py-1.5 rounded-lg transition-colors">
              Hit SL ({fmtRs(sl)})
            </button>
          </div>
          <button onClick={() => setShowExitForm(f => !f)}
            className="w-full text-xs border border-[#2a2d3a] text-gray-500 hover:text-gray-300 py-1.5 rounded-lg transition-colors">
            Manual Exit at custom price
          </button>
          {showExitForm && (
            <div className="flex gap-2 mt-1">
              <input
                type="number"
                placeholder="Exit premium ₹"
                className="flex-1 bg-[#0f1117] border border-[#2a2d3a] rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-600"
                value={exitPremium}
                onChange={e => setExitPremium(e.target.value)}
              />
              <button
                onClick={() => handleExit('MANUAL', exitPremium)}
                disabled={!exitPremium || exiting}
                className="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg disabled:opacity-40"
              >
                {exiting ? '...' : 'Exit'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
