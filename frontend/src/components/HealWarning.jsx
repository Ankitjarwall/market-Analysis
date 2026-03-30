import { useMarketStore } from '../store/marketStore'

export default function HealWarning() {
  const warnings = useMarketStore(s => s.healWarnings)
  const dismiss = useMarketStore(s => s.dismissHealWarning)

  if (warnings.length === 0) return null

  return (
    <div className="space-y-2 mb-4">
      {warnings.map(w => (
        <div
          key={w.id}
          className={`flex items-start justify-between gap-3 px-4 py-3 rounded-lg border text-sm
            ${w.severity === 4
              ? 'bg-red-900/40 border-red-700 text-red-200'
              : 'bg-yellow-900/30 border-yellow-700 text-yellow-200'
            }`}
        >
          <div className="flex items-start gap-2">
            <span>{w.severity === 4 ? '🚨' : '⚠️'}</span>
            <div>
              <div className="font-semibold">
                {w.severity === 4 ? 'CRITICAL — Manual Required' : 'Self-Heal Warning'}
              </div>
              <div className="text-xs opacity-80 mt-0.5">{w.message}</div>
            </div>
          </div>
          <button
            onClick={() => dismiss(w.id)}
            className="text-xs opacity-60 hover:opacity-100 mt-0.5 shrink-0"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
