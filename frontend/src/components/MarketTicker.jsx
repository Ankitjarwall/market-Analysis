import { useEffect, useState } from 'react'
import axios from 'axios'
import { useMarketStore } from '../store/marketStore'
import MarketTooltip from './MarketTooltip'
import { getNow } from '../utils/timeSync'

const API = import.meta.env.VITE_API_URL || ''

// NSE instruments — open status comes from backend
const NSE_KEYS = new Set(['nifty', 'banknifty', 'india_vix'])

// Non-NSE market hours in UTC (weekdays only)
const MARKET_HOURS_UTC = {
  sp500:       [13, 30, 20, 0],
  nasdaq:      [13, 30, 20, 0],
  nikkei:      [0, 0, 6, 0],
  crude_brent: [22, 0, 21, 0],
  gold:        [22, 0, 21, 0],
  usd_inr:     [0, 0, 23, 59],
}

function isMarketOpen(key) {
  const now = getNow()
  const day = now.getUTCDay()
  if (day === 0 || day === 6) return false
  const hours = MARKET_HOURS_UTC[key]
  if (!hours) return false
  const [oh, om, ch, cm] = hours
  const nowMins = now.getUTCHours() * 60 + now.getUTCMinutes()
  const openMins = oh * 60 + om
  const closeMins = ch * 60 + cm
  if (openMins > closeMins) return nowMins >= openMins || nowMins <= closeMins
  return nowMins >= openMins && nowMins <= closeMins
}

const TICKER_ITEMS = [
  { key: 'nifty',       label: 'NIFTY',      prefix: '',  decimals: 2 },
  { key: 'banknifty',   label: 'BANK NIFTY', prefix: '',  decimals: 2 },
  { key: 'sp500',       label: 'S&P 500',    prefix: '',  decimals: 2 },
  { key: 'nasdaq',      label: 'NASDAQ',     prefix: '',  decimals: 2 },
  { key: 'nikkei',      label: 'NIKKEI',     prefix: '',  decimals: 2 },
  { key: 'crude_brent', label: 'BRENT',      prefix: '$', decimals: 2 },
  { key: 'gold',        label: 'GOLD',       prefix: '$', decimals: 1 },
  { key: 'usd_inr',     label: 'USD/INR',    prefix: '₹', decimals: 2 },
  { key: 'india_vix',   label: 'VIX',        prefix: '',  decimals: 2 },
]

function formatVal(val, prefix, decimals) {
  if (val == null || val === 0) return null
  return `${prefix}${Number(val).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`
}

export default function MarketTicker() {
  const data = useMarketStore(s => s.marketData)
  const prev = useMarketStore(s => s.previousData)
  const [openStates, setOpenStates] = useState({})
  const [nseOpen, setNseOpen] = useState(false)

  // Poll backend for NSE open status every 60s
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await axios.get(`${API}/api/market/status`)
        setNseOpen(res.data.is_nse_open)
      } catch {
        // fall back to client-side check
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

  // Update non-NSE open states every 30s
  useEffect(() => {
    function refresh() {
      const states = {}
      TICKER_ITEMS.forEach(({ key }) => {
        states[key] = NSE_KEYS.has(key) ? nseOpen : isMarketOpen(key)
      })
      setOpenStates(states)
    }
    refresh()
    const id = setInterval(refresh, 30_000)
    return () => clearInterval(id)
  }, [nseOpen])

  return (
    <div className="bg-[#1a1d26] border-b border-[#2a2d3a] overflow-hidden">
      <div className="overflow-x-auto scrollbar-hide">
        <div className="flex gap-0 px-2 py-0 whitespace-nowrap min-w-max">
          {TICKER_ITEMS.map(({ key, label, prefix, decimals }) => {
            const val = data?.[key]
            const prevVal = prev?.[key]
            const formatted = formatVal(val, prefix, decimals)
            let dir = 0
            if (val != null && prevVal != null && val !== prevVal) dir = val > prevVal ? 1 : -1
            const open = openStates[key]
            const valueColor = dir > 0 ? 'text-green-400' : dir < 0 ? 'text-red-400' : formatted ? 'text-white' : 'text-gray-600'
            const arrow = dir > 0 ? ' ▲' : dir < 0 ? ' ▼' : ''

            const chgPct = data?.[`${key}_chg_pct`]
            // Use real-time direction if available, else fall back to day-change direction
            const effectiveDir = dir !== 0 ? dir : (chgPct != null ? (chgPct > 0 ? 1 : chgPct < 0 ? -1 : 0) : 0)
            const effectiveColor = effectiveDir > 0 ? 'text-green-400' : effectiveDir < 0 ? 'text-red-400' : formatted ? 'text-white' : 'text-gray-600'
            const effectiveArrow = effectiveDir > 0 ? ' ▲' : effectiveDir < 0 ? ' ▼' : ''

            return (
              <MarketTooltip key={key} marketKey={key} currentPrice={val}>
                <div className="flex items-center gap-1.5 text-sm px-3 py-2 border-r border-[#2a2d3a] last:border-r-0 cursor-default hover:bg-[#1e2230] transition-colors">
                  {open ? (
                    <span className="relative flex h-2 w-2 shrink-0">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                    </span>
                  ) : (
                    <span className="h-2 w-2 rounded-full bg-gray-600 shrink-0" />
                  )}
                  <span className="text-gray-500 text-xs font-medium">{label}</span>
                  <span className={`font-mono font-bold text-sm transition-colors duration-300 ${effectiveColor}`}>
                    {formatted ? <>{formatted}<span className="text-xs">{effectiveArrow}</span></> : '—'}
                  </span>
                  {chgPct != null && (
                    <span className={`text-[10px] font-mono opacity-70 ${effectiveDir > 0 ? 'text-green-400' : effectiveDir < 0 ? 'text-red-400' : 'text-gray-500'}`}>
                      {chgPct > 0 ? '+' : ''}{chgPct.toFixed(2)}%
                    </span>
                  )}
                </div>
              </MarketTooltip>
            )
          })}
        </div>
      </div>
    </div>
  )
}
