import { useEffect, useState } from 'react'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function Predictions() {
  const [history, setHistory] = useState([])
  const [accuracy, setAccuracy] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/api/predictions/history?days=30`),
      axios.get(`${API}/api/predictions/accuracy?days=30`),
    ]).then(([h, a]) => {
      setHistory(h.data.predictions || [])
      setAccuracy(a.data)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-4 text-gray-500">Loading...</div>

  return (
    <div className="p-4 space-y-4 max-w-2xl mx-auto">
      {/* Accuracy summary */}
      {accuracy && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-400 mb-3">30-Day Accuracy</h3>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <div className="text-2xl font-bold text-white">{accuracy.accuracy_pct ?? '—'}%</div>
              <div className="text-xs text-gray-500">Overall</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-green-400">{accuracy.correct ?? 0}</div>
              <div className="text-xs text-gray-500">Correct</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-red-400">{accuracy.incorrect ?? 0}</div>
              <div className="text-xs text-gray-500">Wrong</div>
            </div>
          </div>
        </div>
      )}

      {/* Prediction history */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">Prediction History</h3>
        {history.length === 0 ? (
          <div className="text-gray-600 text-sm text-center py-4">No predictions yet</div>
        ) : (
          <div className="space-y-2">
            {history.map(p => (
              <div key={p.id} className="flex items-center justify-between py-2 border-b border-[#2a2d3a]/50 last:border-0">
                <div>
                  <div className="text-sm">
                    {new Date(p.date).toLocaleDateString('en-IN')}
                    <span className={`ml-2 font-semibold
                      ${p.direction === 'UP' ? 'text-green-400' :
                        p.direction === 'DOWN' ? 'text-red-400' : 'text-yellow-400'}`}>
                      {p.direction}
                    </span>
                    <span className="text-gray-500 text-xs ml-1">
                      {p.magnitude_low}–{p.magnitude_high}%
                    </span>
                  </div>
                  <div className="text-xs text-gray-600">{p.confidence}% confidence</div>
                </div>
                <div className="text-right">
                  {p.was_correct !== null ? (
                    <span className={p.was_correct ? 'text-green-400 text-lg' : 'text-red-400 text-lg'}>
                      {p.was_correct ? '✓' : '✗'}
                    </span>
                  ) : (
                    <span className="text-gray-600 text-sm">—</span>
                  )}
                  {p.actual_direction && (
                    <div className="text-xs text-gray-500">actual: {p.actual_direction} ({p.actual_magnitude?.toFixed(1)}%)</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
