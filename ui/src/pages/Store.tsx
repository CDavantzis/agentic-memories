import { useMutation } from '@tanstack/react-query'
import { apiPost, getPersistedUserId } from '@/lib/api'
import { useEffect, useState } from 'react'

type StoreResponse = {
  memories_created: number
  ids: string[]
  summary?: string
  duplicates_avoided?: number
  updates_made?: number
  existing_memories_checked?: number
}

type Turn = { role: 'user' | 'assistant'; content: string }

export function Store() {
  const [userId, setUserId] = useState('')
  const [turns, setTurns] = useState<Turn[]>([{ role: 'user', content: '' }])

  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const m = useMutation({
    mutationFn: () => apiPost<StoreResponse>('/v1/store', { user_id: userId, history: turns }),
  })

  function updateTurn(idx: number, key: 'role' | 'content', value: string) {
    setTurns(t => t.map((it, i) => i === idx ? { ...it, [key]: value } as Turn : it))
  }
  function addTurn(role: Turn['role']) { setTurns(t => [...t, { role, content: '' }]) }
  function removeTurn(idx: number) { setTurns(t => t.filter((_, i) => i !== idx)) }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Store Transcript</h1>

      <div className="space-y-2">
        {turns.map((turn, idx) => (
          <div key={idx} className="rounded border bg-white p-3 space-y-2">
            <div className="flex items-center gap-2">
              <select className="border rounded px-2 py-1" value={turn.role} onChange={e=>updateTurn(idx,'role', e.target.value)}>
                <option value="user">user</option>
                <option value="assistant">assistant</option>
              </select>
              <button className="ml-auto text-sm text-red-600" onClick={()=>removeTurn(idx)}>remove</button>
            </div>
            <textarea className="w-full border rounded px-2 py-1" rows={3} value={turn.content} onChange={e=>updateTurn(idx,'content', e.target.value)} placeholder="Type message..." />
          </div>
        ))}
        <div className="flex gap-2">
          <button onClick={()=>addTurn('user')} className="px-3 py-1 rounded border">+ user turn</button>
          <button onClick={()=>addTurn('assistant')} className="px-3 py-1 rounded border">+ assistant turn</button>
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={()=>m.mutate()} className="px-3 py-1 rounded bg-blue-600 text-white disabled:opacity-50" disabled={!userId || m.isPending}>Submit</button>
        {m.isPending && <div className="text-sm text-neutral-600">Submitting...</div>}
        {m.isError && <div className="text-sm text-red-600">{String(m.error)}</div>}
      </div>

      {m.data && (
        <div className="rounded border bg-white p-3 space-y-2">
          <div className="text-sm">memories_created: <b>{m.data.memories_created}</b></div>
          <div className="flex flex-wrap gap-2 text-xs">
            {m.data.duplicates_avoided !== undefined && <span className="px-2 py-1 rounded bg-neutral-100 border">duplicates_avoided {m.data.duplicates_avoided}</span>}
            {m.data.updates_made !== undefined && <span className="px-2 py-1 rounded bg-neutral-100 border">updates_made {m.data.updates_made}</span>}
            {m.data.existing_memories_checked !== undefined && <span className="px-2 py-1 rounded bg-neutral-100 border">existing_checked {m.data.existing_memories_checked}</span>}
          </div>
          {m.data.summary && <div className="text-sm text-neutral-700">{m.data.summary}</div>}
          <details>
            <summary className="cursor-pointer text-sm">raw</summary>
            <pre className="bg-neutral-50 border rounded p-2 text-xs overflow-auto">{JSON.stringify(m.data, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  )
}


