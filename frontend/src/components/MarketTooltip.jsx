import { useState, useRef, useEffect } from 'react'
import { useMarketStore } from '../store/marketStore'

// ── Static market metadata ─────────────────────────────────────────────────────
export const MARKET_META = {
  nifty: {
    label: 'NIFTY 50',
    exchange: 'NSE',
    country: '🇮🇳 India',
    hoursIST: '9:15 AM – 3:30 PM IST',
    hoursLocal: '9:15 AM – 3:30 PM',
    tz: 'IST',
    currency: '₹',
    decimals: 2,
  },
  banknifty: {
    label: 'BANK NIFTY',
    exchange: 'NSE',
    country: '🇮🇳 India',
    hoursIST: '9:15 AM – 3:30 PM IST',
    hoursLocal: '9:15 AM – 3:30 PM',
    tz: 'IST',
    currency: '₹',
    decimals: 2,
  },
  india_vix: {
    label: 'INDIA VIX',
    exchange: 'NSE',
    country: '🇮🇳 India',
    hoursIST: '9:15 AM – 3:30 PM IST',
    hoursLocal: '9:15 AM – 3:30 PM',
    tz: 'IST',
    currency: '',
    decimals: 2,
  },
  sp500: {
    label: 'S&P 500',
    exchange: 'NYSE',
    country: '🇺🇸 USA',
    hoursIST: '7:00 PM – 1:30 AM IST',
    hoursLocal: '9:30 AM – 4:00 PM EST',
    tz: 'EST',
    currency: '$',
    decimals: 2,
  },
  nasdaq: {
    label: 'NASDAQ',
    exchange: 'NASDAQ',
    country: '🇺🇸 USA',
    hoursIST: '7:00 PM – 1:30 AM IST',
    hoursLocal: '9:30 AM – 4:00 PM EST',
    tz: 'EST',
    currency: '$',
    decimals: 2,
  },
  nikkei: {
    label: 'NIKKEI 225',
    exchange: 'TSE',
    country: '🇯🇵 Japan',
    hoursIST: '5:30 AM – 12:00 PM IST',
    hoursLocal: '9:00 AM – 3:30 PM JST',
    tz: 'JST',
    currency: '¥',
    decimals: 0,
  },
  crude_brent: {
    label: 'BRENT CRUDE',
    exchange: 'ICE',
    country: '🌍 Global',
    hoursIST: '6:00 AM – 11:00 PM IST',
    hoursLocal: '12:30 AM – 5:00 PM GMT',
    tz: 'GMT',
    currency: '$',
    decimals: 2,
  },
  gold: {
    label: 'GOLD',
    exchange: 'COMEX',
    country: '🌍 Global',
    hoursIST: '12:30 AM – 11:00 PM IST',
    hoursLocal: '6:00 PM – 5:15 PM ET (next day)',
    tz: 'ET',
    currency: '$',
    decimals: 1,
  },
  usd_inr: {
    label: 'USD / INR',
    exchange: 'NSE Forex',
    country: '🇮🇳 India',
    hoursIST: '9:00 AM – 5:00 PM IST',
    hoursLocal: '9:00 AM – 5:00 PM',
    tz: 'IST',
    currency: '₹',
    decimals: 2,
  },
  us_vix: {
    label: 'CBOE VIX',
    exchange: 'CBOE',
    country: '🇺🇸 USA',
    hoursIST: '7:00 PM – 1:30 AM IST',
    hoursLocal: '9:30 AM – 4:15 PM EST',
    tz: 'EST',
    currency: '',
    decimals: 2,
  },
}

function fmt(val, decimals, currency = '') {
  if (val == null) return '—'
  return `${currency}${Number(val).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`
}

function changePct(current, prevClose) {
  if (!current || !prevClose) return null
  return ((current - prevClose) / prevClose) * 100
}

// ── Tooltip content ────────────────────────────────────────────────────────────
function TooltipContent({ marketKey, currentPrice }) {
  const data = useMarketStore(s => s.marketData)
  const meta = MARKET_META[marketKey]
  if (!meta) return null

  const { currency, decimals, label, exchange, country, hoursIST, hoursLocal, tz } = meta

  const prevClose  = data?.[`${marketKey}_prev_close`]
  const prevOpen   = data?.[`${marketKey}_prev_open`]
  const todayOpen  = data?.[`${marketKey}_today_open`]
  const pct        = changePct(currentPrice, prevClose)

  return (
    <div className="w-64 bg-[#0f1117] border border-[#2a2d3a] rounded-xl shadow-2xl p-3 text-xs z-50">
      {/* Header */}
      <div className="flex items-center justify-between mb-2 pb-2 border-b border-[#2a2d3a]">
        <div>
          <div className="font-bold text-gray-200 text-sm">{label}</div>
          <div className="text-gray-500">{country} · {exchange}</div>
        </div>
        {pct != null && (
          <div className={`text-sm font-bold font-mono ${pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
          </div>
        )}
      </div>

      {/* OHLC */}
      <div className="space-y-1.5 mb-2">
        <div className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">Price Data</div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          <div className="flex justify-between">
            <span className="text-gray-500">Today Open</span>
            <span className="font-mono text-gray-200">{fmt(todayOpen, decimals, currency)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Current</span>
            <span className={`font-mono font-semibold ${pct != null ? (pct >= 0 ? 'text-green-400' : 'text-red-400') : 'text-white'}`}>
              {fmt(currentPrice, decimals, currency)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Prev Open</span>
            <span className="font-mono text-gray-400">{fmt(prevOpen, decimals, currency)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Prev Close</span>
            <span className="font-mono text-gray-400">{fmt(prevClose, decimals, currency)}</span>
          </div>
        </div>
      </div>

      {/* Trading hours */}
      <div className="pt-2 border-t border-[#2a2d3a] space-y-0.5">
        <div className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">Trading Hours</div>
        <div className="flex justify-between">
          <span className="text-gray-500">IST</span>
          <span className="text-gray-300">{hoursIST.replace(' IST', '')}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">{tz}</span>
          <span className="text-gray-400">{hoursLocal}</span>
        </div>
      </div>
    </div>
  )
}

// ── Wrapper that adds hover tooltip to any child ───────────────────────────────
export default function MarketTooltip({ marketKey, currentPrice, children }) {
  const [visible, setVisible] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const wrapRef = useRef(null)
  const tipRef = useRef(null)

  function handleMouseEnter(e) {
    setVisible(true)
    reposition(e.currentTarget)
  }

  function handleMouseLeave() {
    setVisible(false)
  }

  function reposition(el) {
    if (!el) return
    const rect = el.getBoundingClientRect()
    // Default: below element, aligned left
    let top = rect.bottom + 6
    let left = rect.left

    // Viewport overflow guard
    const vpW = window.innerWidth
    const tipW = 256 // w-64
    if (left + tipW > vpW - 8) left = vpW - tipW - 8

    // Flip above if below would go off screen
    const tipH = 220
    if (top + tipH > window.innerHeight - 8) {
      top = rect.top - tipH - 6
    }

    setPos({ top, left })
  }

  return (
    <div
      ref={wrapRef}
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {visible && (
        <div
          ref={tipRef}
          style={{ position: 'fixed', top: pos.top, left: pos.left, zIndex: 9999 }}
        >
          <TooltipContent marketKey={marketKey} currentPrice={currentPrice} />
        </div>
      )}
    </div>
  )
}