import { useEffect } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useMarketStore } from '../store/marketStore'
import MarketTicker from '../components/MarketTicker'
import HealWarning from '../components/HealWarning'

const KEY_METRICS = [
  { key: 'india_vix', label: 'India VIX', fmt: (v) => v?.toFixed(2) },
  { key: 'put_call_ratio', label: 'PCR', fmt: (v) => v?.toFixed(3) },
  { key: 'fii_net', label: 'FII (₹Cr)', fmt: (v) => v ? (v > 0 ? '+' : '') + v?.toLocaleString('en-IN', { maximumFractionDigits: 0 }) : null },
  { key: 'nifty_pe', label: 'Nifty PE', fmt: (v) => v?.toFixed(2) },
  { key: 'usd_inr', label: 'USD/INR', fmt: (v) => v?.toFixed(2) },
  { key: 'us_10y', label: 'US 10Y', fmt: (v) => v ? v?.toFixed(2) + '%' : null },
]

export default function Dashboard() {
  const { connected } = useWebSocket()
  const data = useMarketStore(s => s.marketData)
  const prediction = useMarketStore(s => s.todayPrediction)
  const activityLog = useMarketStore(s => s.activityLog)
  const lastUpdated = useMarketStore(s => s.lastUpdated)

  return (
    <div className="flex flex-col h-full">
      <MarketTicker />

      <div className="flex-1 overflow-auto p-4 space-y-4">
        <HealWarning />

        {/* Top stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Nifty live */}
          <div className="card col-span-2 lg:col-span-1">
            <div className="text-xs text-gray-500 mb-1">NIFTY 50</div>
            <div className="text-3xl font-bold font-mono">
              {data?.nifty ? Number(data.nifty).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—'}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-xs ${connected ? 'text-green-400' : 'text-gray-500'}`}>
                ● {connected ? 'LIVE' : 'Connecting...'}
              </span>
              {lastUpdated && (
                <span className="text-xs text-gray-600">
                  {lastUpdated.toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>

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
            <div className={`text-lg font-bold font-mono
              ${(data?.india_vix || 0) > 20 ? 'text-red-400' : (data?.india_vix || 0) > 15 ? 'text-yellow-400' : 'text-green-400'}`}>
              {data?.india_vix?.toFixed(2) || '—'}
            </div>
            <div className="text-xs text-gray-500">
              {(data?.india_vix || 0) > 20 ? 'High Volatility' : (data?.india_vix || 0) > 15 ? 'Moderate' : 'Low'}
            </div>
          </div>
        </div>

        {/* Key metrics grid */}
        <div className="grid grid-cols-3 lg:grid-cols-6 gap-2">
          {KEY_METRICS.map(({ key, label, fmt }) => (
            <div key={key} className="bg-[#1a1d26] rounded-lg border border-[#2a2d3a] px-3 py-2">
              <div className="text-xs text-gray-500 mb-0.5">{label}</div>
              <div className="text-sm font-mono font-semibold">
                {data?.[key] != null ? fmt(data[key]) ?? '—' : '—'}
              </div>
            </div>
          ))}
        </div>

        {/* Data freshness */}
        {data?.fresh_signals_count != null && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className={`w-2 h-2 rounded-full
              ${data.fresh_signals_count >= 40 ? 'bg-green-500' : data.fresh_signals_count >= 30 ? 'bg-yellow-500' : 'bg-red-500'}`} />
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
