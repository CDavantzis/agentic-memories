import { useMutation } from '@tanstack/react-query'
import { apiPost, getPersistedUserId } from '@/lib/api'
import { useEffect, useState } from 'react'

type StructuredResponse = Record<string, Array<{ id: string; content: string }>>

export function Structured() {
  const [userId, setUserId] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const m = useMutation({
    mutationFn: () => apiPost<StructuredResponse>('/v1/retrieve/structured', { user_id: userId, query }),
  })

  const categories = ['emotions','behaviors','personal','professional','habits','skills_tools','projects','relationships','learning_journal','other']

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Structured Retrieve</h1>
      <div className="flex gap-2 items-end">
        <div>
          <label className="text-sm text-neutral-600">query (optional)</label>
          <input className="border rounded px-2 py-1" value={query} onChange={e=>setQuery(e.target.value)} placeholder="" />
        </div>
        <button onClick={()=>m.mutate()} className="px-3 py-1 rounded bg-blue-600 text-white disabled:opacity-50" disabled={!userId || m.isPending}>Run</button>
        {m.isPending && <div className="text-sm text-neutral-600">Loading...</div>}
        {m.isError && <div className="text-sm text-red-600">{String(m.error)}</div>}
      </div>

      {m.data && (
        <div className="space-y-3">
          {categories.map(cat => (
            <details key={cat} open className="rounded border bg-white">
              <summary className="cursor-pointer px-3 py-2 font-medium">{cat} ({m.data[cat]?.length || 0})</summary>
              <div className="p-3 grid gap-2">
                {(m.data[cat] || []).map(item => (
                  <div key={item.id} className="rounded border bg-neutral-50 p-2">
                    <div className="text-sm">{item.content}</div>
                    <div className="text-xs text-neutral-600 mt-1">{item.id}</div>
                  </div>
                ))}
                {(!m.data[cat] || m.data[cat].length === 0) && <div className="text-sm text-neutral-600">No items.</div>}
              </div>
            </details>
          ))}
          <details>
            <summary className="cursor-pointer text-sm">raw</summary>
            <pre className="bg-neutral-50 border rounded p-2 text-xs overflow-auto">{JSON.stringify(m.data, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  )
}


