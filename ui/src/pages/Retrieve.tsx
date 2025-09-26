import { useQuery } from '@tanstack/react-query'
import { apiGet, getPersistedUserId } from '@/lib/api'
import { useEffect, useMemo, useState } from 'react'

type RetrieveResult = {
  results: Array<{
    id: string
    content: string
    layer: string
    type: string
    score: number
    metadata?: Record<string, unknown>
  }>
  pagination?: { limit: number; offset: number; total?: number }
}

export function Retrieve() {
  const [userId, setUserId] = useState('')
  const [query, setQuery] = useState('')
  const [layer, setLayer] = useState('')
  const [type, setType] = useState('')
  const [limit, setLimit] = useState(10)
  const [offset, setOffset] = useState(0)

  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const url = useMemo(() => {
    const params = new URLSearchParams()
    params.set('user_id', userId)
    if (query) params.set('query', query)
    if (layer) params.set('layer', layer)
    if (type) params.set('type', type)
    params.set('limit', String(limit))
    params.set('offset', String(offset))
    return `/v1/retrieve?${params.toString()}`
  }, [userId, query, layer, type, limit, offset])

  const { data, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['retrieve', url],
    queryFn: () => apiGet<RetrieveResult>(url),
    enabled: !!userId,
  })

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Retrieve</h1>
      <div className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end">
        <div className="md:col-span-2">
          <label className="text-sm text-neutral-600">query (optional)</label>
          <input className="w-full border rounded px-2 py-1" value={query} onChange={e=>setQuery(e.target.value)} placeholder="" />
        </div>
        <div>
          <label className="text-sm text-neutral-600">layer</label>
          <input className="w-full border rounded px-2 py-1" value={layer} onChange={e=>setLayer(e.target.value)} placeholder="semantic" />
        </div>
        <div>
          <label className="text-sm text-neutral-600">type</label>
          <input className="w-full border rounded px-2 py-1" value={type} onChange={e=>setType(e.target.value)} placeholder="explicit" />
        </div>
        <div>
          <label className="text-sm text-neutral-600">limit</label>
          <input type="number" className="w-full border rounded px-2 py-1" value={limit} onChange={e=>setLimit(parseInt(e.target.value||'10'))} />
        </div>
        <div>
          <label className="text-sm text-neutral-600">offset</label>
          <input type="number" className="w-full border rounded px-2 py-1" value={offset} onChange={e=>setOffset(parseInt(e.target.value||'0'))} />
        </div>
        <div className="md:col-span-6 flex gap-2">
          <button onClick={()=>refetch()} className="px-3 py-1 rounded bg-blue-600 text-white disabled:opacity-50" disabled={!userId || isFetching}>Run</button>
          <div className="text-sm text-neutral-600">{isFetching ? 'Loading...' : ''}</div>
        </div>
      </div>

      {isError && <div className="text-red-600 text-sm">{String(error)}</div>}

      {data && (
        <div className="space-y-2">
          <div className="text-sm text-neutral-600">{data.results.length} results</div>
          <div className="grid gap-2">
            {data.results.map(r => (
              <div key={r.id} className="rounded border bg-white p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">{r.content}</div>
                  <div className="text-xs text-neutral-600">score {r.score.toFixed(2)}</div>
                </div>
                <div className="text-xs text-neutral-600 mt-1">{r.layer} · {r.type}</div>
                {r.metadata && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-sm">metadata</summary>
                    <pre className="bg-neutral-50 border rounded p-2 text-xs overflow-auto">{JSON.stringify(r.metadata, null, 2)}</pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


