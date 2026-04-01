import { useState, useRef, useEffect } from 'react'
import { useMarketStore } from '../store/marketStore'

// ── Static market metadata ─────────────────────────────────────────────────────
export const MARKET_META = {
  nifty: { label: 'NIFTY 50', exchange: 'NSE', country: '🇮🇳 India', hoursIST: '9:15 AM – 3:30 PM', tz: 'IST', currency: '₹', decimals: 2 },
  banknifty: { label: 'BANK NIFTY', exchange: 'NSE', country: '🇮🇳 India', hoursIST: '9:15 AM – 3:30 PM', tz: 'IST', currency: '₹', decimals: 2 },
  india_vix: { label: 'INDIA VIX', exchange: 'NSE', country: '🇮🇳 India', hoursIST: '9:15 AM – 3:30 PM', tz: 'IST', currency: '', decimals: 2, note: 'Volatility index — higher = more fear' },
  sensex: { label: 'SENSEX', exchange: 'BSE', country: '🇮🇳 India', hoursIST: '9:15 AM – 3:30 PM', tz: 'IST', currency: '₹', decimals: 2, note: 'BSE top 30 companies' },
  nifty_midcap: { label: 'NIFTY MIDCAP', exchange: 'NSE', country: '🇮🇳 India', hoursIST: '9:15 AM – 3:30 PM', tz: 'IST', currency: '₹', decimals: 2 },
  nifty_it: { label: 'NIFTY IT', exchange: 'NSE', country: '🇮🇳 India', hoursIST: '9:15 AM – 3:30 PM', tz: 'IST', currency: '₹', decimals: 2, note: 'Top IT sector stocks' },
  nifty_pharma: { label: 'NIFTY PHARMA', exchange: 'NSE', country: '🇮🇳 India', hoursIST: '9:15 AM – 3:30 PM', tz: 'IST', currency: '₹', decimals: 2 },
  sp500: { label: 'S&P 500', exchange: 'NYSE', country: '🇺🇸 USA', hoursIST: '7:00 PM – 1:30 AM', tz: 'EST', hoursLocal: '9:30 AM – 4:00 PM EST', currency: '$', decimals: 2, note: 'US top 500 companies — key global signal' },
  nasdaq: { label: 'NASDAQ', exchange: 'NASDAQ', country: '🇺🇸 USA', hoursIST: '7:00 PM – 1:30 AM', tz: 'EST', hoursLocal: '9:30 AM – 4:00 PM EST', currency: '$', decimals: 2, note: 'Tech-heavy US index' },
  nikkei: { label: 'NIKKEI 225', exchange: 'TSE', country: '🇯🇵 Japan', hoursIST: '5:30 AM – 12:00 PM', tz: 'JST', hoursLocal: '9:00 AM – 3:30 PM JST', currency: '¥', decimals: 0 },
  hangseng: { label: 'HANG SENG', exchange: 'HKEX', country: '🇭🇰 Hong Kong', hoursIST: '6:45 AM – 1:30 PM', tz: 'HKT', hoursLocal: '9:15 AM – 4:00 PM HKT', currency: 'HK$', decimals: 0 },
  shanghai: { label: 'SHANGHAI', exchange: 'SSE', country: '🇨🇳 China', hoursIST: '6:30 AM – 11:30 AM', tz: 'CST', hoursLocal: '9:30 AM – 3:00 PM CST', currency: '¥', decimals: 2 },
  ftse: { label: 'FTSE 100', exchange: 'LSE', country: '🇬🇧 UK', hoursIST: '1:30 PM – 10:00 PM', tz: 'GMT', hoursLocal: '8:00 AM – 4:30 PM GMT', currency: '£', decimals: 2 },
  dax: { label: 'DAX', exchange: 'XETRA', country: '🇩🇪 Germany', hoursIST: '1:00 PM – 10:30 PM', tz: 'CET', hoursLocal: '9:00 AM – 5:30 PM CET', currency: '€', decimals: 2 },
  gold: { label: 'GOLD', exchange: 'COMEX', country: '🌍 Global', hoursIST: '12:30 AM – 11:00 PM', tz: 'ET', hoursLocal: '6:00 PM – 5:15 PM ET', currency: '$', decimals: 1, note: 'Safe haven — rises on uncertainty' },
  crude_brent: { label: 'BRENT CRUDE', exchange: 'ICE', country: '🌍 Global', hoursIST: '6:00 AM – 11:00 PM', tz: 'GMT', hoursLocal: '24x5', currency: '$', decimals: 2, note: 'International oil benchmark' },
  crude_wti: { label: 'WTI CRUDE', exchange: 'NYMEX', country: '🇺🇸 USA', hoursIST: '6:00 AM – 11:00 PM', tz: 'ET', hoursLocal: '24x5', currency: '$', decimals: 2, note: 'US domestic oil benchmark' },
  silver: { label: 'SILVER', exchange: 'COMEX', country: '🌍 Global', hoursIST: '12:30 AM – 11:00 PM', tz: 'ET', hoursLocal: '6:00 PM – 5:15 PM ET', currency: '$', decimals: 3 },
  natural_gas: { label: 'NAT GAS', exchange: 'NYMEX', country: '🌍 Global', hoursIST: '6:00 AM – 11:00 PM', tz: 'ET', hoursLocal: '24x5', currency: '$', decimals: 3 },
  copper: { label: 'COPPER', exchange: 'COMEX', country: '🌍 Global', hoursIST: '6:00 AM – 11:00 PM', tz: 'ET', hoursLocal: '24x5', currency: '$', decimals: 3, note: 'Industrial demand indicator' },
  usd_inr: { label: 'USD / INR', exchange: 'NSE Forex', country: '🇮🇳 India', hoursIST: '9:00 AM – 5:00 PM', tz: 'IST', currency: '₹', decimals: 2, note: 'Higher = Rupee weaker = bearish for India' },
  dxy: { label: 'US DOLLAR INDEX', exchange: 'ICE', country: '🇺🇸 USA', hoursIST: '24x5', tz: 'ET', currency: '', decimals: 3, note: 'Dollar strength vs basket of 6 currencies' },
  usd_jpy: { label: 'USD / JPY', exchange: 'FOREX', country: '🇯🇵 Japan', hoursIST: '24x5', tz: 'JST', currency: '¥', decimals: 2, note: 'Yen carry trade indicator' },
  us_10y: { label: 'US 10Y YIELD', exchange: 'UST', country: '🇺🇸 USA', hoursIST: '7:00 PM – 2:30 AM', tz: 'EST', currency: '', decimals: 2, note: 'Higher yield = tighter global liquidity' },
  us_vix: { label: 'CBOE VIX', exchange: 'CBOE', country: '🇺🇸 USA', hoursIST: '7:00 PM – 1:30 AM', tz: 'EST', currency: '', decimals: 2, note: 'US fear gauge. >30 = extreme fear' },
}

// ── Tooltip content ────────────────────────────────────────────────────────────
function TooltipContent({ marketKey, currentPrice }) {
  const data = useMarketStore(s => s.marketData)
  const meta = MARKET_META[marketKey]
  if (!meta) return null

  const { currency, decimals, label, exchange, country, hoursIST, hoursLocal, tz, note } = meta

  const prevClose  = data?.[`${marketKey}_prev_close`]
  const todayOpen  = data?.[`${marketKey}_today_open`]
  const todayHigh  = data?.[`${marketKey}_today_high`]
  const todayLow   = data?.[`${marketKey}_today_low`]
  const chgPct     = currentPrice && prevClose ? ((currentPrice - prevClose) / prevClose) * 100 : null
  const chgAbs     = currentPrice && prevClose ? currentPrice - prevClose : null

  return (
    <div className="w-64 bg-[#0f1117] border border-[#2a2d3a] rounded-xl shadow-2xl p-3 text-xs z-50">
      {/* Header */}
      <div className="flex items-center justify-between mb-2 pb-2 border-b border-[#2a2d3a]">
        <div>
          <div className="font-bold text-gray-200 text-sm">{label}</div>
          <div className="text-gray-500">{country} · {exchange}</div>
        </div>
        {chgPct != null && (
          <div className={`text-right`}>
            <div className={`text-sm font-bold font-mono ${chgPct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {chgPct >= 0 ? '+' : ''}{chgPct.toFixed(2)}%
            </div>
            {chgAbs != null && (
              <div className={`text-xs font-mono ${chgAbs >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {chgAbs >= 0 ? '+' : ''}{currency}{Math.abs(chgAbs).toLocaleString('en-IN', { maximumFractionDigits: decimals })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Price grid */}
      <div className="space-y-1 mb-2">
        <div className="grid grid-cols-2 gap-x-2 gap-y-1">
          <div className="flex justify-between col-span-2">
            <span className="text-gray-500">Current</span>
            <span className={`font-mono font-bold ${chgPct != null ? (chgPct >= 0 ? 'text-green-400' : 'text-red-400') : 'text-white'}`}>
              {currentPrice != null ? `${currency}${Number(currentPrice).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}` : '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Prev Close</span>
            <span className="font-mono text-gray-300">{prevClose != null ? `${currency}${Number(prevClose).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}` : '—'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Today Open</span>
            <span className="font-mono text-gray-300">{todayOpen != null ? `${currency}${Number(todayOpen).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}` : '—'}</span>
          </div>
          {todayHigh != null && (
            <div className="flex justify-between">
              <span className="text-gray-500">Day High</span>
              <span className="font-mono text-green-400">{currency}{Number(todayHigh).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}</span>
            </div>
          )}
          {todayLow != null && (
            <div className="flex justify-between">
              <span className="text-gray-500">Day Low</span>
              <span className="font-mono text-red-400">{currency}{Number(todayLow).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}</span>
            </div>
          )}
        </div>
      </div>

      {/* Note if any */}
      {note && (
        <div className="py-1.5 border-t border-[#2a2d3a] text-gray-500 italic">{note}</div>
      )}

      {/* Trading hours */}
      <div className="pt-1.5 border-t border-[#2a2d3a]">
        <div className="flex justify-between">
          <span className="text-gray-600">Hours (IST)</span>
          <span className="text-gray-400">{hoursIST}</span>
        </div>
        {hoursLocal && (
          <div className="flex justify-between mt-0.5">
            <span className="text-gray-600">{tz}</span>
            <span className="text-gray-500">{hoursLocal}</span>
          </div>
        )}
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