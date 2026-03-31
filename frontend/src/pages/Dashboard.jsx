import { useEffect, useState } from 'react'
import axios from 'axios'
import { useWebSocket } from '../hooks/useWebSocket'
import { useMarketStore } from '../store/marketStore'
import MarketTicker from '../components/MarketTicker'
import HealWarning from '../components/HealWarning'
import MarketTooltip from '../components/MarketTooltip'
import { getNow } from '../utils/timeSync'

const KEY_METRICS = [
  { key: 'india_vix',     label: 'India VIX',  fmt: (v) => v?.toFixed(2) },
  { key: 'put_call_ratio',label: 'PCR',         fmt: (v) => v?.toFixed(3) },
  { key: 'fii_net',       label: 'FII (₹Cr)',  fmt: (v) => v ? (v > 0 ? '+' : '') + v?.toLocaleString('en-IN', { maximumFractionDigits: 0 }) : null },
  { key: 'nifty_pe',      label: 'Nifty PE',   fmt: (v) => v?.toFixed(2) },
  { key: 'usd_inr',       label: 'USD/INR',    fmt: (v) => v?.toFixed(2) },
  { key: 'us_10y',        label: 'US 10Y',     fmt: (v) => v ? v?.toFixed(2) + '%' : null },
]

function useDelta(current, previous) {
  if (current == null || previous == null || current === previous) return 0
  return current > previous ? 1 : -1
}

function PriceDisplay({ value, prevValue, prefix = '', decimals = 2, size = 'xl' }) {
  const dir = useDelta(value, prevValue)
  const color = dir > 0 ? 'text-green-400' : dir < 0 ? 'text-red-400' : 'text-white'
  const arrow = dir > 0 ? ' ▲' : dir < 0 ? ' ▼' : ''
  const sizeClass = size === '3xl' ? 'text-3xl' : size === '2xl' ? 'text-2xl' : 'text-xl'

  return (
    <span className={`font-bold font-mono ${sizeClass} ${color} transition-colors duration-300`}>
      {value != null
        ? `${prefix}${Number(value).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
        : '—'}
      {arrow && <span className="text-sm">{arrow}</span>}
    </span>
  )
}

export default function Dashboard() {
  const { connected } = useWebSocket()
  const data = useMarketStore(s => s.marketData)
  const prev = useMarketStore(s => s.previousData)
  const prediction = useMarketStore(s => s.todayPrediction)
  const activityLog = useMarketStore(s => s.activityLog)
  const lastUpdated = useMarketStore(s => s.lastUpdated)
  const activeSignals = useMarketStore(s => s.activeSignals)
  const niftySignal = activeSignals?.find(s => s.underlying !== 'BANKNIFTY') || null
  const bnSignal = activeSignals?.find(s => s.underlying === 'BANKNIFTY') || null

  const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  // Check if NSE is currently open — source from backend (server IST time, no timezone bugs)
  const [nseOpen, setNseOpen] = useState(false)
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await axios.get(`${API}/api/market/status`)
        setNseOpen(res.data.is_nse_open)
      } catch {
        // fallback: client-side UTC check
        const now = getNow()
        const day = now.getUTCDay()
        const mins = now.getUTCHours() * 60 + now.getUTCMinutes()
        setNseOpen(day >= 1 && day <= 5 && mins >= 225 && mins <= 600)
      }
    }
    fetchStatus()
    const id = setInterval(fetchStatus, 60_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="flex flex-col h-full">
      <MarketTicker />

      <div className="flex-1 overflow-auto p-4 space-y-4">
        <HealWarning />

        {/* Top stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">

          {/* Nifty live */}
          <MarketTooltip marketKey="nifty" currentPrice={data?.nifty}>
            <div className="card col-span-2 lg:col-span-1 cursor-default">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">NIFTY 50</span>
                  {niftySignal && (
                    <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${niftySignal.signal_type === 'BUY_CALL' ? 'bg-green-900/60 text-green-300' : 'bg-red-900/60 text-red-300'}`}>
                      {niftySignal.signal_type === 'BUY_CALL' ? '▲ CALL' : '▼ PUT'}
                    </span>
                  )}
                </div>
                {nseOpen && (
                  <span className="flex items-center gap-1 text-xs text-green-400">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                    </span>
                    NSE OPEN
                  </span>
                )}
              </div>
              <PriceDisplay value={data?.nifty} prevValue={prev?.nifty} size="3xl" />
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs ${connected && nseOpen ? 'text-green-400' : connected ? 'text-gray-500' : 'text-gray-600'}`}>
                  {!connected ? 'Connecting...' : nseOpen ? (
                    <span className="flex items-center gap-1">
                      <span className="relative flex h-1.5 w-1.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
                      </span>
                      LIVE
                    </span>
                  ) : 'Market Closed'}
                </span>
                {lastUpdated && (
                  <span className="text-xs text-gray-600">
                    {lastUpdated.toLocaleTimeString()}
                  </span>
                )}
              </div>
            </div>
          </MarketTooltip>

          {/* Today's prediction */}
          {prediction ? (
            <div className={`card col-span-2 lg:col-span-1 border-l-4
              ${prediction.direction === 'UP' ? 'border-l-green-500' :
                prediction.direction === 'DOWN' ? 'border-l-red-500' : 'border-l-yellow-500'}`}>
              <div className="text-xs text-gray-500 mb-1">TODAY'S PREDICTION</div>
              <div className={`text-xl font-bold
                ${prediction.direction === 'UP' ? 'text-green-400' :
                  prediction.direction === 'DOWN' ? 'text-red-400' : 'text-yellow-400'}`}>
                {prediction.direction} {prediction.magnitude_low}–{prediction.magnitude_high}%
              </div>
              <div className="text-xs text-gray-400 mt-1">Confidence: {prediction.confidence}%</div>
            </div>
          ) : (
            <div className="card col-span-2 lg:col-span-1 text-gray-600 text-sm flex items-center justify-center">
              No prediction yet
            </div>
          )}

          {/* FII flow */}
          <div className="card">
            <div className="text-xs text-gray-500 mb-1">FII FLOW</div>
            <div className={`text-lg font-bold font-mono
              ${(data?.fii_net || 0) > 0 ? 'text-green-400' : 'text-red-400'}`}>
              {data?.fii_net
                ? `${data.fii_net > 0 ? '+' : ''}₹${Math.abs(data.fii_net).toLocaleString('en-IN', { maximumFractionDigits: 0 })}Cr`
                : '—'}
            </div>
            <div className="text-xs text-gray-500">{(data?.fii_net || 0) > 0 ? 'Buying' : 'Selling'}</div>
          </div>

          {/* India VIX */}
          <div className="card">
            <div className="text-xs text-gray-500 mb-1">INDIA VIX</div>
            <div className="flex items-center gap-2">
              <PriceDisplay value={data?.india_vix} prevValue={prev?.india_vix} size="xl" decimals={2} />
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {(data?.india_vix || 0) > 20 ? '🔴 High Volatility' :
               (data?.india_vix || 0) > 15 ? '🟡 Moderate' : '🟢 Low'}
            </div>
          </div>
        </div>

        {/* Key metrics grid */}
        <div className="grid grid-cols-3 lg:grid-cols-6 gap-2">
          {KEY_METRICS.map(({ key, label, fmt }) => {
            const cur = data?.[key]
            const pre = prev?.[key]
            const dir = useDelta(cur, pre)
            const valueColor = dir > 0 ? 'text-green-400' : dir < 0 ? 'text-red-400' : 'text-gray-200'
            const arrow = dir > 0 ? ' ▲' : dir < 0 ? ' ▼' : ''
            const formatted = cur != null ? fmt(cur) : null

            return (
              <div key={key} className="bg-[#1a1d26] rounded-lg border border-[#2a2d3a] px-3 py-2">
                <div className="text-xs text-gray-500 mb-0.5">{label}</div>
                <div className={`text-sm font-mono font-semibold ${valueColor} transition-colors duration-300`}>
                  {formatted ?? '—'}
                  {arrow && <span className="text-xs">{arrow}</span>}
                </div>
              </div>
            )
          })}
        </div>

        {/* Live market prices row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {/* Bank Nifty — rendered separately to show signal badge */}
          <MarketTooltip marketKey="banknifty" currentPrice={data?.banknifty}>
            <div className="bg-[#1a1d26] rounded-lg border border-[#2a2d3a] px-3 py-2 cursor-default">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs text-gray-500">BANK NIFTY</span>
                {bnSignal && (
                  <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${bnSignal.signal_type === 'BUY_CALL' ? 'bg-green-900/60 text-green-300' : 'bg-red-900/60 text-red-300'}`}>
                    {bnSignal.signal_type === 'BUY_CALL' ? '▲ CALL' : '▼ PUT'}
                  </span>
                )}
              </div>
              <PriceDisplay value={data?.banknifty} prevValue={prev?.banknifty} size="xl" decimals={2} />
            </div>
          </MarketTooltip>

          {[
            { key: 'gold',        label: 'GOLD',        prefix: '$', decimals: 1 },
            { key: 'crude_brent', label: 'BRENT CRUDE', prefix: '$', decimals: 2 },
            { key: 'usd_inr',     label: 'USD / INR',   prefix: '₹', decimals: 2 },
          ].map(({ key, label, prefix = '', decimals }) => (
            <MarketTooltip key={key} marketKey={key} currentPrice={data?.[key]}>
              <div className="bg-[#1a1d26] rounded-lg border border-[#2a2d3a] px-3 py-2 cursor-default">
                <div className="text-xs text-gray-500 mb-0.5">{label}</div>
                <PriceDisplay value={data?.[key]} prevValue={prev?.[key]} prefix={prefix} size="xl" decimals={decimals} />
              </div>
            </MarketTooltip>
          ))}
        </div>

        {/* Data freshness */}
        {data?.fresh_signals_count != null && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className={`w-2 h-2 rounded-full
              ${data.fresh_signals_count >= 40 ? 'bg-green-500' :
                data.fresh_signals_count >= 30 ? 'bg-yellow-500' : 'bg-red-500'}`} />
            {data.fresh_signals_count}/47 signals fresh
          </div>
        )}

        {/* Bot activity feed */}
        <div className="card">
          <div className="text-sm font-semibold mb-3 text-gray-300">🤖 Bot Activity Feed</div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {activityLog.length === 0 ? (
              <div className="text-gray-600 text-sm">Waiting for bot activity...</div>
            ) : (
              activityLog.slice(0, 30).map(log => (
                <div key={log.id} className="flex items-start gap-2 text-xs">
                  <span className="text-gray-600 font-mono shrink-0">
                    {new Date(log.ts).toLocaleTimeString()}
                  </span>
                  <span className={
                    log.level === 'SIGNAL' ? 'text-yellow-300' :
                    log.level === 'TRADE' || log.level === 'T1' || log.level === 'T2' ? 'text-green-300' :
                    log.level === 'SL' ? 'text-red-300' :
                    log.level === 'WARN' ? 'text-orange-300' :
                    'text-gray-400'
                  }>
                    {log.message}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
