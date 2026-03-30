import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { useMarketStore } from '../store/marketStore'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export function useWebSocket() {
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const token = useAuthStore(s => s.token)
  const store = useMarketStore()

  const connect = useCallback(() => {
    if (!token) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(`${WS_URL}/ws/market?token=${token}`)
    wsRef.current = ws

    ws.onopen = () => {
      store.setWsConnected(true)
      store.setWsError(null)
      store.addActivity('WebSocket connected')
      // Start pinging
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'PING' }))
        } else {
          clearInterval(ping)
        }
      }, 20000)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        handleEvent(msg, store)
      } catch (_) {}
    }

    ws.onerror = (err) => {
      store.setWsError('Connection error')
    }

    ws.onclose = () => {
      store.setWsConnected(false)
      // Reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000)
    }
  }, [token])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected: store.wsConnected }
}

function handleEvent(msg, store) {
  switch (msg.type) {
    case 'PRICE_UPDATE':
      store.setMarketData(msg.data || {})
      break
    case 'SIGNAL_GENERATED':
      store.setActiveSignals(prev => [msg.signal, ...prev].slice(0, 10))
      store.addActivity(`🎯 Signal: ${msg.signal?.signal_type} ${msg.signal?.strike} ${msg.signal?.option_type}`, 'SIGNAL')
      break
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
    default:
      break
  }
}
