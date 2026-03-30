import { useMarketStore } from '../store/marketStore'

const TICKER_ITEMS = [
  { key: 'nifty', label: 'NIFTY', prefix: '' },
  { key: 'banknifty', label: 'BANK NIFTY', prefix: '' },
  { key: 'sp500', label: 'S&P 500', prefix: '' },
  { key: 'nasdaq', label: 'NASDAQ', prefix: '' },
  { key: 'nikkei', label: 'NIKKEI', prefix: '' },
  { key: 'crude_brent', label: 'BRENT', prefix: '$' },
  { key: 'gold', label: 'GOLD', prefix: '$' },
  { key: 'usd_inr', label: 'USD/INR', prefix: '₹' },
  { key: 'india_vix', label: 'VIX', prefix: '' },
]

export default function MarketTicker() {
  const data = useMarketStore(s => s.marketData)

  return (
    <div className="bg-[#1a1d26] border-b border-[#2a2d3a] overflow-hidden">
      <div className="flex animate-none overflow-x-auto scrollbar-hide">
        <div className="flex gap-6 px-4 py-2 whitespace-nowrap min-w-max">
          {TICKER_ITEMS.map(({ key, label, prefix }) => {
            const val = data?.[key]
            return (
              <div key={key} className="flex items-center gap-1.5 text-sm">
                <span className="text-gray-500 text-xs">{label}</span>
                <span className={`font-mono font-semibold ${val ? 'text-white' : 'text-gray-600'}`}>
                  {val ? `${prefix}${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
