import { useState } from 'react'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''

export default function SignalCard({ signal, tradeMode, capital }) {
  if (!signal) return null

  const ltp = signal.ltp_at_signal || 0
  const t1 = signal.target1 || 0
  const t2 = signal.target2 || 0
  const sl = signal.stop_loss || 0
  const t1Pct = ltp ? ((t1 - ltp) / ltp * 100).toFixed(1) : 0
  const t2Pct = ltp ? ((t2 - ltp) / ltp * 100).toFixed(1) : 0
  const slPct = ltp ? ((ltp - sl) / ltp * 100).toFixed(1) : 0
  const isCall = signal.signal_type === 'BUY_CALL'
  const rrOk = signal.rr_ratio >= 2
  const isBankNifty = signal.underlying === 'BANKNIFTY'
  const lotSize = isBankNifty ? 15 : 25

  return (
    <div className={`card border-l-4 ${isCall ? 'border-l-green-500' : 'border-l-red-500'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${isBankNifty ? 'bg-purple-900/60 text-purple-300 border border-purple-700/50' : 'bg-blue-900/60 text-blue-300 border border-blue-700/50'}`}>
            {isBankNifty ? 'BANK NIFTY' : 'NIFTY 50'}
          </span>
          <span className={`font-bold text-lg ${isCall ? 'text-green-400' : 'text-red-400'}`}>
            {isCall ? '📈 BUY CALL' : '📉 BUY PUT'}
          </span>
          <span className={`badge ${rrOk ? 'badge-green' : 'badge-red'}`}>
            R:R 1:{signal.rr_ratio?.toFixed(1)}
          </span>
        </div>
        <span className="badge badge-blue">{signal.confidence}% confident</span>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4 text-center">
        <div className="bg-[#0f1117] rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">STRIKE</div>
          <div className="font-bold text-white">{signal.strike} {signal.option_type}</div>
          <div className="text-xs text-gray-400">LTP ₹{ltp} · {lotSize}/lot</div>
        </div>
        <div className="bg-green-900/20 rounded-lg p-3 border border-green-800/40">
          <div className="text-xs text-gray-500 mb-1">T1 / T2</div>
          <div className="font-bold text-green-400">₹{t1}</div>
          <div className="text-xs text-green-600">+{t1Pct}% / +{t2Pct}%</div>
        </div>
        <div className="bg-red-900/20 rounded-lg p-3 border border-red-800/40">
          <div className="text-xs text-gray-500 mb-1">STOP LOSS</div>
          <div className="font-bold text-red-400">₹{sl}</div>
          <div className="text-xs text-red-600">-{slPct}%</div>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Confidence</span>
          <span>{signal.confidence}%</span>
        </div>
        <div className="h-1.5 bg-[#0f1117] rounded-full">
          <div
            className={`h-full rounded-full ${signal.confidence >= 70 ? 'bg-green-500' : signal.confidence >= 55 ? 'bg-yellow-500' : 'bg-red-500'}`}
            style={{ width: `${signal.confidence}%` }}
          />
        </div>
      </div>

      {/* Signal basis */}
      {signal.signal_basis?.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {signal.signal_basis.slice(0, 4).map((b, i) => (
            <span key={i} className="badge badge-gray">{b}</span>
          ))}
        </div>
      )}

      {tradeMode === 'auto' ? (
        <div className="text-sm text-green-400 bg-green-900/20 rounded-lg px-3 py-2 border border-green-800/30">
          ⚡ AUTO MODE — Trade logged at ₹{ltp}
        </div>
      ) : (
        <ManualEntryForm signalId={signal.id} ltp={ltp} />
      )}

      <p className="text-xs text-gray-600 mt-3 text-center">
        ⚠️ Technical analysis only. Not SEBI-registered advice.
      </p>
    </div>
  )
}

function ManualEntryForm({ signalId, ltp }) {
  const [premium, setPremium] = useState(ltp)
  const [lots, setLots] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)

  const submit = async () => {
    setSubmitting(true)
    try {
      const res = await axios.post(`${API}/api/signals/${signalId}/manual-entry`, {
        entry_premium: Number(premium),
        lots: Number(lots),
      })
      setResult(res.data)
    } catch (err) {
      setResult({ error: err.response?.data?.detail || 'Failed' })
    } finally {
      setSubmitting(false)
    }
  }

  if (result && !result.error) return (
    <div className="text-sm text-green-400 bg-green-900/20 rounded-lg px-3 py-2 border border-green-800/30">
      ✅ Trade logged — {result.message}
    </div>
  )

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Entry Premium ₹</label>
          <input type="number" className="input text-sm" value={premium} onChange={e => setPremium(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Lots</label>
          <input type="number" className="input text-sm" min={1} value={lots} onChange={e => setLots(e.target.value)} />
        </div>
      </div>
      {result?.error && <p className="text-red-400 text-xs">{result.error}</p>}
      <button onClick={submit} disabled={submitting} className="btn-primary w-full text-sm">
        {submitting ? 'Logging...' : 'Log Manual Trade'}
      </button>
    </div>
  )
}
