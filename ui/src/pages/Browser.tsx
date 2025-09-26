import { useQuery } from '@tanstack/react-query'
import { apiGet, getPersistedUserId } from '@/lib/api'
import { useEffect, useMemo, useState } from 'react'

type RetrieveResult = {
  results: Array<{
    id: string
    content: string
    layer: string
    type: string
    score?: number
    metadata?: Record<string, unknown>
  }>
  pagination?: { limit: number; offset: number; total?: number }
}

export function Browser() {
  const [userId, setUserId] = useState('')
  const [layer, setLayer] = useState('')
  const [type, setType] = useState('')
  const [limit, setLimit] = useState(20)
  const [offset, setOffset] = useState(0)

  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const url = useMemo(() => {
    const params = new URLSearchParams()
    params.set('user_id', userId)
    // empty query -> all memories
    if (layer) params.set('layer', layer)
    if (type) params.set('type', type)
    params.set('limit', String(limit))
    params.set('offset', String(offset))
    return `/v1/retrieve?${params.toString()}`
  }, [userId, layer, type, limit, offset])

  const { data, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['browser', url],
    queryFn: () => apiGet<RetrieveResult>(url),
    enabled: !!userId,
  })

  function copy(text: string) { navigator.clipboard?.writeText(text).catch(() => {}) }
  function exportJson() { if (!data) return; const blob = new Blob([JSON.stringify(data.results, null, 2)], { type: 'application/json' }); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `memories_${userId}.json`; a.click(); }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Memory Browser</h1>
      <div className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end">
        <div>
          <label className="text-sm text-neutral-600">layer</label>
          <input className="w-full border rounded px-2 py-1" value={layer} onChange={e=>setLayer(e.target.value)} placeholder="" />
        </div>
        <div>
          <label className="text-sm text-neutral-600">type</label>
          <input className="w-full border rounded px-2 py-1" value={type} onChange={e=>setType(e.target.value)} placeholder="" />
        </div>
        <div>
          <label className="text-sm text-neutral-600">limit</label>
          <input type="number" className="w-full border rounded px-2 py-1" value={limit} onChange={e=>setLimit(parseInt(e.target.value||'20'))} />
        </div>
        <div>
          <label className="text-sm text-neutral-600">offset</label>
          <input type="number" className="w-full border rounded px-2 py-1" value={offset} onChange={e=>setOffset(parseInt(e.target.value||'0'))} />
        </div>
        <div className="md:col-span-2 flex gap-2">
          <button onClick={()=>refetch()} className="px-3 py-1 rounded bg-blue-600 text-white disabled:opacity-50" disabled={!userId || isFetching}>Refresh</button>
          <button onClick={exportJson} className="px-3 py-1 rounded border bg-white">Export JSON</button>
        </div>
      </div>

      {isError && <div className="text-red-600 text-sm">{String(error)}</div>}

      {data && (
        <div className="grid gap-2">
          {data.results.map(r => (
            <div key={r.id} className="rounded border bg-white p-3">
              <div className="flex items-center gap-3">
                <div className="font-medium flex-1">{r.content}</div>
                <button className="text-xs text-blue-700" onClick={()=>copy(r.id)}>copy id</button>
              </div>
              <div className="text-xs text-neutral-600 mt-1">{r.layer} · {r.type}</div>
              <details className="mt-2">
                <summary className="cursor-pointer text-sm">raw</summary>
                <pre className="bg-neutral-50 border rounded p-2 text-xs overflow-auto">{JSON.stringify(r, null, 2)}</pre>
              </details>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


