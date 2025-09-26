import { devLog } from '@/lib/devlog'
export const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL || ''

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
    devLog.log({ id: crypto.randomUUID(), ts: Date.now(), method: 'GET', url, status: res.status, durationMs, responseBytes: text.length })
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  const json = await res.json()
  const body = JSON.stringify(json)
  devLog.log({ id: crypto.randomUUID(), ts: Date.now(), method: 'GET', url, status: res.status, durationMs, responseBytes: body.length })
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
    devLog.log({ id: crypto.randomUUID(), ts: Date.now(), method: 'POST', url, status: res.status, durationMs, requestBytes: payload.length, responseBytes: text.length })
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  const json = await res.json()
  const bodyStr = JSON.stringify(json)
  devLog.log({ id: crypto.randomUUID(), ts: Date.now(), method: 'POST', url, status: res.status, durationMs, requestBytes: payload.length, responseBytes: bodyStr.length })
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


