// Shared IST time sync — fetches real time from the backend, then all
// callers use getNow() for an offset-corrected Date.
export let offsetMs = 0

export function getNow() {
  return new Date(Date.now() + offsetMs)
}

export async function syncIST() {
  const API = import.meta.env.VITE_API_URL || ''
  try {
    const before = Date.now()
    const res = await fetch(`${API}/api/system/time`)
    if (!res.ok) throw new Error('non-200')
    const json = await res.json()
    // json.unix is seconds; correct for half the round-trip
    offsetMs = json.unix * 1000 + (Date.now() - before) / 2 - Date.now()
  } catch {
    offsetMs = 0  // fall back to system time
  }
}
