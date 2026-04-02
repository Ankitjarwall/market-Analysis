/**
 * AutoStatusPanel — shows daily auto-trading progress toward the ₹50,000 target.
 *
 * Data sources (in priority order):
 *   1. WebSocket AUTO_STATUS_UPDATE events (real-time, pushed on every trade event)
 *   2. GET /api/trades/auto-status poll (every 30 s, also fired on mount)
 *
 * Only rendered when the user's trade_mode === 'auto'.
 */

import { useEffect, useRef } from 'react'
import axios from 'axios'
import { useMarketStore } from '../store/marketStore'
import { useAuthStore } from '../store/authStore'

const API = import.meta.env.VITE_API_URL || ''

export default function AutoStatusPanel() {
  const user      = useAuthStore(s => s.user)
  const status    = useMarketStore(s => s.autoStatus)
  const setStatus = useMarketStore(s => s.setAutoStatus)
  const pollRef   = useRef(null)

  // Only active for auto-mode users
  const isAuto = user?.trade_mode === 'auto'

  useEffect(() => {
    if (!isAuto) return

    const fetch = async () => {
      try {
        const res = await axios.get(`${API}/api/trades/auto-status`)
        setStatus(res.data)
      } catch (_) {}
    }

    fetch()
    pollRef.current = setInterval(fetch, 30_000)
    return () => clearInterval(pollRef.current)
  }, [isAuto, setStatus])

  if (!isAuto || !status) return null

  const { daily_pnl = 0, daily_target = 50000, loss_count = 0, max_losses = 3, waiting_reason, status: state } = status
  const progressPct  = Math.min(100, Math.round((daily_pnl / daily_target) * 100))
  const isHalted     = state === 'HALTED'
  const isTargetMet  = state === 'TARGET_MET'
  const isActive     = state === 'ACTIVE'

  const barColor = isHalted
    ? 'bg-red-500'
    : isTargetMet
      ? 'bg-green-500'
      : progressPct >= 60
        ? 'bg-blue-400'
        : 'bg-blue-500'

  const pnlColor = daily_pnl > 0 ? 'text-green-400' : daily_pnl < 0 ? 'text-red-400' : 'text-gray-300'

  return (
    <div className={`rounded-lg border px-4 py-3 ${
      isHalted    ? 'border-red-500/50 bg-red-950/30' :
      isTargetMet ? 'border-green-500/50 bg-green-950/30' :
                    'border-[#2a2d3a] bg-[#1a1d26]'
    }`}>
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Auto Trading</span>
          {isActive && (
            <span className="flex items-center gap-1 text-xs text-blue-400">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500" />
              </span>
              ACTIVE
            </span>
          )}
          {isHalted && (
            <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-red-900/60 text-red-300">
              HALTED
            </span>
          )}
          {isTargetMet && (
            <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-green-900/60 text-green-300">
              TARGET MET
            </span>
          )}
        </div>

        {/* Loss counter */}
        <div className="flex items-center gap-1">
          {[...Array(max_losses)].map((_, i) => (
            <span
              key={i}
              className={`w-2.5 h-2.5 rounded-full border ${
                i < loss_count
                  ? 'bg-red-500 border-red-400'
                  : 'bg-[#2a2d3a] border-gray-600'
              }`}
              title={i < loss_count ? 'Loss' : 'Slot'}
            />
          ))}
          <span className={`ml-1 text-xs font-mono ${loss_count > 0 ? 'text-red-400' : 'text-gray-500'}`}>
            {loss_count}/{max_losses} losses
          </span>
        </div>
      </div>

      {/* Daily P&L progress bar */}
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500">Daily P&L</span>
          <div className="flex items-baseline gap-1">
            <span className={`text-sm font-mono font-bold ${pnlColor}`}>
              {daily_pnl >= 0 ? '+' : ''}₹{Math.abs(daily_pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </span>
            <span className="text-xs text-gray-600">/ ₹{daily_target.toLocaleString('en-IN')}</span>
          </div>
        </div>
        <div className="w-full h-1.5 bg-[#2a2d3a] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${barColor}`}
            style={{ width: `${Math.max(0, progressPct)}%` }}
          />
        </div>
        <div className="flex justify-between mt-0.5">
          <span className="text-xs text-gray-600">0</span>
          <span className={`text-xs font-mono ${progressPct >= 100 ? 'text-green-400' : 'text-gray-600'}`}>
            {progressPct}% of target
          </span>
        </div>
      </div>

      {/* Waiting reason */}
      {waiting_reason && (
        <div className={`flex items-start gap-1.5 text-xs mt-1 ${
          isHalted    ? 'text-red-300' :
          isTargetMet ? 'text-green-300' :
                        'text-gray-400'
        }`}>
          <span className="mt-0.5 shrink-0">
            {isHalted ? '🛑' : isTargetMet ? '🎯' : '⏳'}
          </span>
          <span>{waiting_reason}</span>
        </div>
      )}
    </div>
  )
}
