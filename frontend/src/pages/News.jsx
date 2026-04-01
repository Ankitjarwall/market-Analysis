import { useEffect, useState } from 'react'
import { useMarketStore } from '../store/marketStore'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''

const SENTIMENT_CONFIG = {
  'Bullish': { color: 'text-green-400', bg: 'bg-green-900/30 border-green-800/40' },
  'Somewhat-Bullish': { color: 'text-green-500', bg: 'bg-green-900/20 border-green-800/30' },
  'Neutral': { color: 'text-gray-400', bg: 'bg-gray-800/30 border-gray-700/40' },
  'Somewhat-Bearish': { color: 'text-red-500', bg: 'bg-red-900/20 border-red-800/30' },
  'Bearish': { color: 'text-red-400', bg: 'bg-red-900/30 border-red-800/40' },
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
}

export default function News() {
  const marketData = useMarketStore(s => s.marketData)
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(false)
  const [lastRefresh, setLastRefresh] = useState(null)

  const allNews = marketData?.news || []

  const newsapiItems = allNews.filter(n => n.source !== 'AlphaVantage' && !n.sentiment)
  const avItems = allNews.filter(n => n.sentiment)

  const filtered = filter === 'newsapi' ? newsapiItems
    : filter === 'alphavantage' ? avItems
    : filter === 'bullish' ? avItems.filter(n => n.sentiment?.toLowerCase().includes('bullish'))
    : filter === 'bearish' ? avItems.filter(n => n.sentiment?.toLowerCase().includes('bearish'))
    : allNews

  const refresh = async () => {
    setLoading(true)
    try {
      await axios.get(`${API}/api/system/test-feeds`)
      setLastRefresh(new Date())
    } catch {}
    setLoading(false)
  }

  return (
    <div className="p-4 lg:p-6 max-w-4xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-200">Market News</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            {allNews.length} articles · NewsAPI + AlphaVantage
            {lastRefresh && ` · refreshed ${timeAgo(lastRefresh.toISOString())}`}
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="px-3 py-1.5 text-xs rounded-lg bg-blue-600/20 border border-blue-700/50 text-blue-300 hover:bg-blue-600/40 transition-colors disabled:opacity-50"
        >
          {loading ? '⟳ Refreshing...' : '⟳ Refresh'}
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 flex-wrap">
        {[
          { id: 'all', label: `All (${allNews.length})` },
          { id: 'newsapi', label: `NewsAPI (${newsapiItems.length})` },
          { id: 'alphavantage', label: `AlphaVantage (${avItems.length})` },
          { id: 'bullish', label: 'Bullish' },
          { id: 'bearish', label: 'Bearish' },
        ].map(f => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`px-3 py-1 text-xs rounded-lg border transition-colors
              ${filter === f.id
                ? 'border-blue-600 bg-blue-900/30 text-blue-300'
                : 'border-[#2a2d3a] text-gray-500 hover:text-gray-300'}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* News list */}
      {allNews.length === 0 ? (
        <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-8 text-center">
          <div className="text-gray-600 text-sm">No news loaded yet</div>
          <div className="text-gray-700 text-xs mt-1">News refreshes automatically every 45 seconds</div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-6 text-center text-gray-600 text-sm">
          No articles match this filter
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((item, i) => {
            const sentCfg = item.sentiment ? (SENTIMENT_CONFIG[item.sentiment] || SENTIMENT_CONFIG.Neutral) : null
            return (
              <div
                key={i}
                className={`bg-[#1a1d26] border rounded-xl p-4 hover:border-[#3a3d4a] transition-colors ${sentCfg ? sentCfg.bg : 'border-[#2a2d3a]'}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-200 leading-relaxed font-medium">
                      {item.url ? (
                        <a href={item.url} target="_blank" rel="noopener noreferrer"
                           className="hover:text-blue-400 transition-colors">
                          {item.title}
                        </a>
                      ) : item.title}
                    </div>
                    {item.description && (
                      <div className="text-xs text-gray-500 mt-1 line-clamp-2 leading-relaxed">
                        {item.description}
                      </div>
                    )}
                    <div className="flex items-center gap-3 mt-2">
                      <span className="text-xs text-gray-600 font-medium">{item.source}</span>
                      <span className="text-xs text-gray-700">{timeAgo(item.published_at)}</span>
                      {item.sentiment && sentCfg && (
                        <span className={`text-xs font-semibold ${sentCfg.color}`}>
                          {item.sentiment}
                        </span>
                      )}
                    </div>
                  </div>
                  {item.sentiment && sentCfg && (
                    <div className={`shrink-0 text-lg ${sentCfg.color}`}>
                      {item.sentiment?.includes('Bullish') ? '📈' : item.sentiment?.includes('Bearish') ? '📉' : '➖'}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* AlphaVantage notice if empty */}
      {avItems.length === 0 && (
        <div className="bg-[#1a1d26] border border-yellow-900/40 rounded-xl p-3 text-xs text-yellow-600">
          AlphaVantage NEWS_SENTIMENT requires a Premium API plan ($50+/month). Only NewsAPI articles shown.
        </div>
      )}
    </div>
  )
}
