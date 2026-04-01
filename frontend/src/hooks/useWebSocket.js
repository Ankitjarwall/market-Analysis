import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { useMarketStore } from '../store/marketStore'

// Use relative WebSocket URL so nginx proxies it — avoids hardcoded port issues
const WS_URL = import.meta.env.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

/** Decode JWT payload without verifying signature — for client-side expiry check only. */
function _isTokenExpired(token) {
  try {
    const [, payload] = token.split('.')
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
    return decoded.exp != null && decoded.exp * 1000 < Date.now()
  } catch {
    return true  // treat unparseable token as expired
  }
}

export function useWebSocket() {
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const pingTimer = useRef(null)
  const didOpenRef = useRef(false)  // track whether onopen ever fired
  const token = useAuthStore(s => s.token)
  const store = useMarketStore()

  const connect = useCallback(() => {
    if (!token) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    // Proactively check token expiry — avoids hitting the server with a dead token
    if (_isTokenExpired(token)) {
      console.warn('[WS] Token expired before connect — logging out')
      store.setWsError('Session expired — please log in again')
      useAuthStore.getState().logout()
      return
    }

    didOpenRef.current = false
    const ws = new WebSocket(`${WS_URL}/ws/market?token=${token}`)
    wsRef.current = ws

    ws.onopen = () => {
      didOpenRef.current = true
      store.setWsConnected(true)
      store.setWsError(null)
      store.addActivity('WebSocket connected')
      console.log('[WS] Connected to', `${WS_URL}/ws/market`)
      // Start pinging — clear any previous interval first
      clearInterval(pingTimer.current)
      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'PING' }))
        } else {
          clearInterval(pingTimer.current)
        }
      }, 20000)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        // Console debug: log every incoming WS message type + key fields
        if (msg.type === 'PRICE_UPDATE') {
          const d = msg.data || {}
          console.log('[WS] PRICE_UPDATE', {
            nifty: d.nifty, banknifty: d.banknifty,
            sp500: d.sp500, gold: d.gold, usd_inr: d.usd_inr,
            india_vix: d.india_vix, us_vix: d.us_vix,
            fresh: d.fresh_signals_count, ts: msg.ts,
          })
        } else if (msg.type === 'CONNECTED') {
          console.log('[WS] Server handshake:', msg.message)
        } else if (msg.type === 'PONG') {
          // silent
        } else {
          console.log('[WS]', msg.type, msg)
        }

        handleEvent(msg, store)
      } catch (_) {}
    }

    ws.onerror = (err) => {
      console.warn('[WS] Error:', err)
      store.setWsError('Connection error')
    }

    ws.onclose = (event) => {
      clearInterval(pingTimer.current)
      store.setWsConnected(false)
      console.log('[WS] Closed — code:', event.code, 'reason:', event.reason, 'wasOpen:', didOpenRef.current)

      if (!didOpenRef.current) {
        // Server rejected the connection (token expired/invalid) — force logout
        console.warn('[WS] Connection rejected before handshake — session expired, logging out')
        store.setWsError('Session expired — please log in again')
        useAuthStore.getState().logout()
        return  // do NOT reconnect with a dead token
      }

      // Normal disconnect — reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000)
    }
  }, [token])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      clearInterval(pingTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected: store.wsConnected }
}

function handleEvent(msg, store) {
  switch (msg.type) {
    case 'PRICE_UPDATE': {
      const d = msg.data || {}
      store.setMarketData(d)
      // Patch live option premiums into active signals if available
      if (d.active_signal_premiums) {
        const sigs = store.activeSignals || []
        const patched = sigs.map(s => {
          const live = d.active_signal_premiums[String(s.id)]
          return live != null ? { ...s, current_premium: live } : s
        })
        store.setActiveSignals(patched)
      }
      break
    }
    case 'SIGNAL_GENERATED': {
      const current = store.activeSignals || []
      store.setActiveSignals([msg.signal, ...current].slice(0, 10))
      store.addActivity(`🎯 Signal: ${msg.signal?.signal_type} ${msg.signal?.strike} ${msg.signal?.option_type}`, 'SIGNAL')
      break
    }
    case 'TRADE_OPENED':
      store.addActivity(msg.payload?.message || 'Trade opened', 'TRADE')
      break
    case 'TRADE_ALERT_T1':
      store.addActivity(msg.payload?.message || 'T1 hit!', 'T1')
      break
    case 'TRADE_ALERT_T2':
      store.addActivity(msg.payload?.message || 'T2 hit!', 'T2')
      break
    case 'TRADE_ALERT_SL':
      store.addActivity(msg.payload?.message || 'SL hit', 'SL')
      break
    case 'BOT_ACTIVITY':
      store.addActivity(msg.message, msg.level || 'INFO')
      break
    case 'HEAL_WARNING':
      store.addHealWarning(msg.warning || {})
      store.addActivity(`⚠️ Heal: ${msg.warning?.message}`, 'WARN')
      break
    case 'PNL_UPDATE':
      store.updateTradePnl(msg.payload?.trade_id, msg.payload?.unrealised_pnl, msg.payload?.current_premium)
      break
    case 'LOG_ENTRY':
      if (msg.entry) store.addSystemLog(msg.entry)
      break
    default:
      break
  }
}
