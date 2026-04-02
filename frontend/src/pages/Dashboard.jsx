import { useEffect, useState } from 'react'
import axios from 'axios'
import { useMarketStore } from '../store/marketStore'
import MarketTicker from '../components/MarketTicker'
import HealWarning from '../components/HealWarning'
import AutoStatusPanel from '../components/AutoStatusPanel'
import MarketTooltip from '../components/MarketTooltip'
import { getNow } from '../utils/timeSync'

const API = import.meta.env.VITE_API_URL || ''

// ── helpers ──────────────────────────────────────────────────────────────────

function useDelta(cur, prev) {
  if (cur == null || prev == null || cur === prev) return 0
  return cur > prev ? 1 : -1
}

function dirColor(dir, hasValue) {
  if (!hasValue) return 'text-gray-600'
  return dir > 0 ? 'text-green-400' : dir < 0 ? 'text-red-400' : 'text-gray-200'
}

function PriceDisplay({ value, prevValue, chgPct, prefix = '', decimals = 2, size = 'xl' }) {
  const rtDir  = useDelta(value, prevValue)
  const dayDir = chgPct != null ? (chgPct > 0 ? 1 : chgPct < 0 ? -1 : 0) : 0
  const dir    = rtDir !== 0 ? rtDir : dayDir
  const color  = dirColor(dir, value != null)
  const arrow  = dir > 0 ? ' ▲' : dir < 0 ? ' ▼' : ''
  const sizeClass = size === '3xl' ? 'text-3xl' : size === '2xl' ? 'text-2xl' : 'text-xl'

  return (
    <span className={`font-bold font-mono ${sizeClass} ${color} transition-colors duration-300`}>
      {value != null
        ? `${prefix}${Number(value).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
        : '—'}
      {arrow && <span className="text-sm">{arrow}</span>}
      {chgPct != null && (
        <span className="ml-1 text-xs font-normal opacity-70">
          ({chgPct > 0 ? '+' : ''}{chgPct.toFixed(2)}%)
        </span>
      )}
    </span>
  )
}

function MiniMetric({ label, value, dir }) {
  return (
    <div className="bg-[#1a1d26] rounded-lg border border-[#2a2d3a] px-3 py-2">
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <div className={`text-sm font-mono font-semibold ${dirColor(dir, value != null)} transition-colors duration-300`}>
        {value ?? '—'}
        {dir !== 0 && value != null && (
          <span className="text-xs ml-0.5">{dir > 0 ? ' ▲' : ' ▼'}</span>
        )}
      </div>
    </div>
  )
}

function CompactPrice({ label, value, prev, chgPct, prefix = '', decimals = 2 }) {
  const rtDir  = useDelta(value, prev)
  const dayDir = chgPct != null ? (chgPct > 0 ? 1 : chgPct < 0 ? -1 : 0) : 0
  const dir    = rtDir !== 0 ? rtDir : dayDir
  return (
    <div className="bg-[#1a1d26] rounded-lg border border-[#2a2d3a] px-3 py-2">
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <div className={`text-sm font-mono font-semibold ${dirColor(dir, value != null)}`}>
        {value != null
          ? `${prefix}${Number(value).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
          : '—'}
        {dir !== 0 && value != null && <span className="text-xs ml-0.5">{dir > 0 ? '▲' : '▼'}</span>}
      </div>
      {chgPct != null && (
        <div className={`text-xs opacity-60 ${dir > 0 ? 'text-green-400' : dir < 0 ? 'text-red-400' : 'text-gray-400'}`}>
          {chgPct > 0 ? '+' : ''}{chgPct.toFixed(2)}%
        </div>
      )}
    </div>
  )
}

function SkeletonCard({ className = '' }) {
  return (
    <div className={`card animate-pulse ${className}`}>
      <div className="h-3 bg-gray-700 rounded w-16 mb-2" />
      <div className="h-7 bg-gray-700 rounded w-28 mb-1" />
      <div className="h-2 bg-gray-700 rounded w-12" />
    </div>
  )
}

// ── Section header ────────────────────────────────────────────────────────────
function SectionHeader({ title }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{title}</span>
      <div className="flex-1 h-px bg-[#2a2d3a]" />
    </div>
  )
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const connected    = useMarketStore(s => s.wsConnected)
  const data         = useMarketStore(s => s.marketData)
  const prev         = useMarketStore(s => s.previousData)
  const prediction   = useMarketStore(s => s.todayPrediction)
  const activityLog  = useMarketStore(s => s.activityLog)
  const lastUpdated  = useMarketStore(s => s.lastUpdated)
  const activeSignals = useMarketStore(s => s.activeSignals)

  const niftySignal = activeSignals?.find(s => s.underlying !== 'BANKNIFTY') || null
  const bnSignal    = activeSignals?.find(s => s.underlying === 'BANKNIFTY') || null

  const [nseOpen, setNseOpen] = useState(false)
  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await axios.get(`${API}/api/market/status`)
        setNseOpen(res.data.is_nse_open)
      } catch {
        const now = getNow()
        const day = now.getUTCDay()
        const mins = now.getUTCHours() * 60 + now.getUTCMinutes()
        setNseOpen(day >= 1 && day <= 5 && mins >= 225 && mins <= 600)
      }
    }
    fetch()
    const id = setInterval(fetch, 60_000)
    return () => clearInterval(id)
  }, [])

  const hasData = data?.nifty != null || data?.sp500 != null
  const total   = data?.total_signals ?? 47
  const fresh   = data?.fresh_signals_count ?? 0
  const freshPct = Math.round((fresh / total) * 100)

  if (!hasData && !connected) {
    return (
      <div className="flex flex-col h-full">
        <MarketTicker />
        <div className="flex-1 overflow-auto p-4 space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <SkeletonCard className="col-span-2 lg:col-span-1" />
            <SkeletonCard className="col-span-2 lg:col-span-1" />
            <SkeletonCard />
            <SkeletonCard />
          </div>
          <div className="text-center text-gray-600 text-sm py-8">
            Connecting to live feed...
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <MarketTicker />

      <div className="flex-1 overflow-auto p-4 space-y-4">
        <HealWarning />
        <AutoStatusPanel />

        {/* ── Hero row: Nifty + BankNifty + Prediction + FII/DII ── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">

          {/* Nifty 50 */}
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
              <PriceDisplay value={data?.nifty} prevValue={prev?.nifty} chgPct={data?.nifty_chg_pct} size="3xl" />
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs ${connected && nseOpen ? 'text-green-400' : connected ? 'text-gray-500' : 'text-gray-600'}`}>
                  {!connected ? 'Reconnecting...' : nseOpen
                    ? <span className="flex items-center gap-1"><span className="relative flex h-1.5 w-1.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" /><span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" /></span>LIVE</span>
                    : 'Market Closed'}
                </span>
                {lastUpdated && (
                  <span className="text-xs text-gray-600">{lastUpdated.toLocaleTimeString()}</span>
                )}
              </div>
            </div>
          </MarketTooltip>

          {/* Bank Nifty */}
          <MarketTooltip marketKey="banknifty" currentPrice={data?.banknifty}>
            <div className="card col-span-2 lg:col-span-1 cursor-default">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-gray-500">BANK NIFTY</span>
                {bnSignal && (
                  <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${bnSignal.signal_type === 'BUY_CALL' ? 'bg-green-900/60 text-green-300' : 'bg-red-900/60 text-red-300'}`}>
                    {bnSignal.signal_type === 'BUY_CALL' ? '▲ CALL' : '▼ PUT'}
                  </span>
                )}
              </div>
              <PriceDisplay value={data?.banknifty} prevValue={prev?.banknifty} chgPct={data?.banknifty_chg_pct} size="2xl" />
              <div className="text-xs text-gray-500 mt-1">
                {data?.banknifty_vwap ? `VWAP ₹${Number(data.banknifty_vwap).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : ''}
              </div>
            </div>
          </MarketTooltip>

          {/* Today's Prediction */}
          {prediction ? (
            <div className={`card border-l-4 ${prediction.direction === 'UP' ? 'border-l-green-500' : prediction.direction === 'DOWN' ? 'border-l-red-500' : 'border-l-yellow-500'}`}>
              <div className="text-xs text-gray-500 mb-1">TODAY'S PREDICTION</div>
              <div className={`text-xl font-bold ${prediction.direction === 'UP' ? 'text-green-400' : prediction.direction === 'DOWN' ? 'text-red-400' : 'text-yellow-400'}`}>
                {prediction.direction} {prediction.magnitude_low}–{prediction.magnitude_high}%
              </div>
              <div className="text-xs text-gray-400 mt-1">Confidence: {prediction.confidence}%</div>
            </div>
          ) : (
            <div className="card text-gray-600 text-sm flex flex-col items-center justify-center min-h-[80px]">
              <div className="text-xs text-gray-500 mb-1">TODAY'S PREDICTION</div>
              <div className="text-gray-600 text-sm">No prediction yet</div>
            </div>
          )}

          {/* FII + DII */}
          <div className="card">
            <div className="text-xs text-gray-500 mb-2">INSTITUTIONAL FLOWS</div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">FII</span>
                <span className={`text-sm font-mono font-bold ${data?.fii_net == null ? 'text-gray-600' : data.fii_net > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {data?.fii_net != null
                    ? `${data.fii_net > 0 ? '+' : ''}₹${Math.abs(data.fii_net).toLocaleString('en-IN', { maximumFractionDigits: 0 })}Cr`
                    : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">DII</span>
                <span className={`text-sm font-mono font-bold ${data?.dii_net == null ? 'text-gray-600' : data.dii_net > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {data?.dii_net != null
                    ? `${data.dii_net > 0 ? '+' : ''}₹${Math.abs(data.dii_net).toLocaleString('en-IN', { maximumFractionDigits: 0 })}Cr`
                    : '—'}
                </span>
              </div>
              {(data?.fii_net != null || data?.dii_net != null) && (
                <div className="text-xs text-gray-500 pt-0.5 border-t border-[#2a2d3a]">
                  Net: {((data?.fii_net ?? 0) + (data?.dii_net ?? 0)) > 0 ? 'Buying' : 'Selling'}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Key market metrics ── */}
        <div>
          <SectionHeader title="Market Metrics" />
          <div className="grid grid-cols-3 lg:grid-cols-6 gap-2">
            {[
              { label: 'India VIX',  key: 'india_vix',           fmt: v => v?.toFixed(2) },
              { label: 'PCR',        key: 'put_call_ratio',       fmt: v => v?.toFixed(3) },
              { label: 'Nifty PE',   key: 'nifty_pe',             fmt: v => v?.toFixed(2) },
              { label: 'Nifty PB',   key: 'nifty_pb',             fmt: v => v?.toFixed(2) },
              { label: 'Div Yield',  key: 'nifty_dividend_yield', fmt: v => v ? v.toFixed(2) + '%' : null },
              { label: 'A/D Ratio',  key: 'advance_decline_ratio',fmt: v => v?.toFixed(2) },
            ].map(({ label, key, fmt }) => {
              const cur     = data?.[key]
              const pre     = prev?.[key]
              const chgPct  = data?.[`${key}_chg_pct`]
              const rtDir   = useDelta(cur, pre)
              const dayDir  = chgPct != null ? (chgPct > 0 ? 1 : chgPct < 0 ? -1 : 0) : 0
              const dir     = rtDir !== 0 ? rtDir : dayDir
              const formatted = cur != null ? fmt(cur) : null
              return (
                <MiniMetric key={key} label={label} value={formatted} dir={dir} />
              )
            })}
          </div>
        </div>

        {/* ── Forex & rates ── */}
        <div>
          <SectionHeader title="Forex & Rates" />
          <div className="grid grid-cols-3 lg:grid-cols-5 gap-2">
            <MarketTooltip marketKey="usd_inr" currentPrice={data?.usd_inr}>
              <CompactPrice label="USD / INR"  key="usd_inr" value={data?.usd_inr}  prev={prev?.usd_inr}  chgPct={data?.usd_inr_chg_pct}  prefix="₹" decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="dxy" currentPrice={data?.dxy}>
              <CompactPrice label="DXY"        key="dxy"     value={data?.dxy}       prev={prev?.dxy}       chgPct={data?.dxy_chg_pct}       decimals={3} />
            </MarketTooltip>
            <MarketTooltip marketKey="usd_jpy" currentPrice={data?.usd_jpy}>
              <CompactPrice label="USD / JPY"  key="usd_jpy" value={data?.usd_jpy}  prev={prev?.usd_jpy}  chgPct={data?.usd_jpy_chg_pct}  decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="us_10y" currentPrice={data?.us_10y}>
              <CompactPrice label="US 10Y"     key="us_10y"  value={data?.us_10y}   prev={prev?.us_10y}   chgPct={data?.us_10y_chg_pct}   decimals={2} prefix="" />
            </MarketTooltip>
            <MarketTooltip marketKey="us_vix" currentPrice={data?.us_vix}>
              <CompactPrice label="US VIX"     key="us_vix"  value={data?.us_vix}   prev={prev?.us_vix}   chgPct={data?.us_vix_chg_pct}   decimals={2} />
            </MarketTooltip>
          </div>
        </div>

        {/* ── Indian sectoral indices ── */}
        <div>
          <SectionHeader title="Indian Markets" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
            <MarketTooltip marketKey="sensex" currentPrice={data?.sensex}>
              <CompactPrice label="SENSEX"      key="sensex"       value={data?.sensex}       prev={prev?.sensex}       chgPct={data?.sensex_chg_pct}       decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="nifty_midcap" currentPrice={data?.nifty_midcap}>
              <CompactPrice label="NIFTY MIDCAP" key="nifty_midcap" value={data?.nifty_midcap} prev={prev?.nifty_midcap} chgPct={data?.nifty_midcap_chg_pct} decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="nifty_it" currentPrice={data?.nifty_it}>
              <CompactPrice label="NIFTY IT"     key="nifty_it"     value={data?.nifty_it}     prev={prev?.nifty_it}     chgPct={data?.nifty_it_chg_pct}     decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="nifty_pharma" currentPrice={data?.nifty_pharma}>
              <CompactPrice label="NIFTY PHARMA" key="nifty_pharma" value={data?.nifty_pharma} prev={prev?.nifty_pharma} chgPct={data?.nifty_pharma_chg_pct} decimals={2} />
            </MarketTooltip>
          </div>
        </div>

        {/* ── Global indices ── */}
        <div>
          <SectionHeader title="Global Indices" />
          <div className="grid grid-cols-3 lg:grid-cols-7 gap-2">
            <MarketTooltip marketKey="sp500" currentPrice={data?.sp500}>
              <CompactPrice label="S&P 500"  key="sp500"    value={data?.sp500}    prev={prev?.sp500}    chgPct={data?.sp500_chg_pct}    decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="nasdaq" currentPrice={data?.nasdaq}>
              <CompactPrice label="NASDAQ"   key="nasdaq"   value={data?.nasdaq}   prev={prev?.nasdaq}   chgPct={data?.nasdaq_chg_pct}   decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="nikkei" currentPrice={data?.nikkei}>
              <CompactPrice label="NIKKEI"   key="nikkei"   value={data?.nikkei}   prev={prev?.nikkei}   chgPct={data?.nikkei_chg_pct}   decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="hangseng" currentPrice={data?.hangseng}>
              <CompactPrice label="HANG SENG" key="hangseng" value={data?.hangseng} prev={prev?.hangseng} chgPct={data?.hangseng_chg_pct} decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="shanghai" currentPrice={data?.shanghai}>
              <CompactPrice label="SHANGHAI" key="shanghai"  value={data?.shanghai} prev={prev?.shanghai} chgPct={data?.shanghai_chg_pct} decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="ftse" currentPrice={data?.ftse}>
              <CompactPrice label="FTSE 100" key="ftse"     value={data?.ftse}     prev={prev?.ftse}     chgPct={data?.ftse_chg_pct}     decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="dax" currentPrice={data?.dax}>
              <CompactPrice label="DAX"      key="dax"      value={data?.dax}      prev={prev?.dax}      chgPct={data?.dax_chg_pct}      decimals={2} />
            </MarketTooltip>
          </div>
        </div>

        {/* ── Commodities ── */}
        <div>
          <SectionHeader title="Commodities" />
          <div className="grid grid-cols-3 lg:grid-cols-6 gap-2">
            <MarketTooltip marketKey="gold" currentPrice={data?.gold}>
              <CompactPrice label="GOLD"       key="gold"         value={data?.gold}         prev={prev?.gold}         chgPct={data?.gold_chg_pct}         prefix="$" decimals={1} />
            </MarketTooltip>
            <MarketTooltip marketKey="crude_brent" currentPrice={data?.crude_brent}>
              <CompactPrice label="BRENT"      key="crude_brent"  value={data?.crude_brent}  prev={prev?.crude_brent}  chgPct={data?.crude_brent_chg_pct}  prefix="$" decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="crude_wti" currentPrice={data?.crude_wti}>
              <CompactPrice label="WTI"        key="crude_wti"    value={data?.crude_wti}    prev={prev?.crude_wti}    chgPct={data?.crude_wti_chg_pct}    prefix="$" decimals={2} />
            </MarketTooltip>
            <MarketTooltip marketKey="silver" currentPrice={data?.silver}>
              <CompactPrice label="SILVER"     key="silver"       value={data?.silver}       prev={prev?.silver}       chgPct={data?.silver_chg_pct}       prefix="$" decimals={3} />
            </MarketTooltip>
            <MarketTooltip marketKey="natural_gas" currentPrice={data?.natural_gas}>
              <CompactPrice label="NAT GAS"    key="natural_gas"  value={data?.natural_gas}  prev={prev?.natural_gas}  chgPct={data?.natural_gas_chg_pct}  prefix="$" decimals={3} />
            </MarketTooltip>
            <MarketTooltip marketKey="copper" currentPrice={data?.copper}>
              <CompactPrice label="COPPER"     key="copper"       value={data?.copper}       prev={prev?.copper}       chgPct={data?.copper_chg_pct}       prefix="$" decimals={3} />
            </MarketTooltip>
          </div>
        </div>

        {/* ── Signal freshness bar ── */}
        {fresh > 0 && (
          <div className="bg-[#1a1d26] rounded-lg border border-[#2a2d3a] px-4 py-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400 font-medium">Signal Freshness</span>
              <span className={`text-xs font-mono font-bold ${freshPct >= 85 ? 'text-green-400' : freshPct >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
                {fresh}/{total} signals ({freshPct}%)
              </span>
            </div>
            <div className="w-full h-1.5 bg-[#2a2d3a] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${freshPct >= 85 ? 'bg-green-500' : freshPct >= 60 ? 'bg-yellow-500' : 'bg-red-500'}`}
                style={{ width: `${freshPct}%` }}
              />
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-500">
              {[
                { label: 'Prices',    keys: ['nifty','banknifty','sp500','gold','usd_inr'] },
                { label: 'NSE Data',  keys: ['fii_net','nifty_pe','put_call_ratio','advance_decline_ratio'] },
                { label: 'Sectoral',  keys: ['nifty_midcap','nifty_it','nifty_pharma','sensex'] },
                { label: 'Change %',  keys: ['nifty_chg_pct','sp500_chg_pct','gold_chg_pct'] },
              ].map(({ label, keys }) => {
                const count = keys.filter(k => data?.[k] != null).length
                const ok = count === keys.length
                return (
                  <span key={label} className={`flex items-center gap-1 ${ok ? 'text-green-500' : 'text-gray-500'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-green-500' : 'bg-gray-600'}`} />
                    {label} ({count}/{keys.length})
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {/* ── Bot activity feed ── */}
        <div className="card">
          <div className="text-sm font-semibold mb-3 text-gray-300 flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-gray-600'}`} />
            Bot Activity Feed
          </div>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {activityLog.length === 0 ? (
              <div className="text-gray-600 text-sm">Waiting for bot activity...</div>
            ) : (
              activityLog.slice(0, 30).map(log => (
                <div key={log.id} className="flex items-start gap-2 text-xs">
                  <span className="text-gray-600 font-mono shrink-0 tabular-nums">
                    {new Date(log.ts).toLocaleTimeString()}
                  </span>
                  <span className={
                    log.level === 'SIGNAL' ? 'text-yellow-300' :
                    log.level === 'TRADE' || log.level === 'T1' || log.level === 'T2' ? 'text-green-300' :
                    log.level === 'SL'   ? 'text-red-300' :
                    log.level === 'WARN' ? 'text-orange-300' :
                    'text-gray-400'
                  }>{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* ── News ── */}
        {data?.news?.length > 0 && (
          <div className="card">
            <div className="text-sm font-semibold mb-3 text-gray-300">Market News</div>
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {data.news.slice(0, 8).map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-xs border-b border-[#2a2d3a] pb-2 last:border-0 last:pb-0">
                  <div className="flex-1 min-w-0">
                    <div className="text-gray-300 line-clamp-2 leading-relaxed">{item.title}</div>
                    <div className="text-gray-600 mt-0.5 flex items-center gap-2">
                      <span>{item.source}</span>
                      {item.published_at && (
                        <span>{new Date(item.published_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
