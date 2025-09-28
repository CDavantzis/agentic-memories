import { devLog } from '@/lib/devlog'

// Derive API base: prefer env; else LAN -> host:8080, public -> same origin
const envBase = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined
function isLanHost(hostname: string): boolean {
  if (!hostname) return false
  if (hostname === 'localhost' || hostname === '127.0.0.1') return true
  // 192.168.x.x
  if (/^192\.168\.(\d{1,3})\.(\d{1,3})$/.test(hostname)) return true
  // 10.x.x.x
  if (/^10\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.test(hostname)) return true
  // 172.16.0.0 – 172.31.255.255
  if (/^172\.(1[6-9]|2[0-9]|3[0-1])\.(\d{1,3})\.(\d{1,3})$/.test(hostname)) return true
  return false
}

export const API_BASE = (envBase && envBase.trim() !== '')
  ? envBase
  : (() => {
      const loc = window.location
      if (isLanHost(loc.hostname)) {
        return `${loc.protocol}//${loc.hostname}:8080`
      }
      // On public hosts behind a proxy (e.g., Cloudflare), use same-origin with /api path
      return `${loc.origin}/api`
    })()

// Safe ID generator: crypto.randomUUID if available; fallback to getRandomValues; else Math.random
function createId(): string {
  try {
    if (typeof crypto !== 'undefined') {
      if (typeof (crypto as any).randomUUID === 'function') return (crypto as any).randomUUID()
      if (typeof crypto.getRandomValues === 'function') {
        const bytes = new Uint8Array(16)
        crypto.getRandomValues(bytes)
        // RFC4122 v4
        bytes[6] = (bytes[6] & 0x0f) | 0x40
        bytes[8] = (bytes[8] & 0x3f) | 0x80
        const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0'))
        return `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-${hex[4]}${hex[5]}-${hex[6]}${hex[7]}-${hex[8]}${hex[9]}-${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`
      }
    }
  } catch {}
  return `${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  const start = performance.now()
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })
  const durationMs = performance.now() - start
  if (!res.ok) {
    const text = await res.text()
    devLog.log({ id: createId(), ts: Date.now(), method: 'GET', url, status: res.status, durationMs, responseBytes: text.length })
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  const json = await res.json()
  const body = JSON.stringify(json)
  devLog.log({ id: createId(), ts: Date.now(), method: 'GET', url, status: res.status, durationMs, responseBytes: body.length })
  return json
}

export async function apiPost<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  const payload = JSON.stringify(body)
  const start = performance.now()
  const res = await fetch(url, {
    method: 'POST',
    body: payload,
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })
  const durationMs = performance.now() - start
  if (!res.ok) {
    const text = await res.text()
    devLog.log({ id: createId(), ts: Date.now(), method: 'POST', url, status: res.status, durationMs, requestBytes: payload.length, responseBytes: text.length })
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  const json = await res.json()
  const bodyStr = JSON.stringify(json)
  devLog.log({ id: createId(), ts: Date.now(), method: 'POST', url, status: res.status, durationMs, requestBytes: payload.length, responseBytes: bodyStr.length })
  return json
}

export function getPersistedUserId(): string {
  const url = new URL(window.location.href)
  const userIdFromUrl = url.searchParams.get('user_id')
  const stored = localStorage.getItem('user_id')
  const userId = userIdFromUrl || stored || 'test_user_22'
  if (userId !== stored) localStorage.setItem('user_id', userId)
  if (userIdFromUrl !== userId) {
    url.searchParams.set('user_id', userId)
    window.history.replaceState({}, '', url.toString())
  }
  return userId
}


