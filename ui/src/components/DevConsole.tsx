import { useEffect, useState } from 'react'
import { devLog, DevEvent } from '@/lib/devlog'

export function DevConsole() {
  const [events, setEvents] = useState<DevEvent[]>(devLog.events)
  useEffect(() => devLog.subscribe(setEvents), [])

  return (
    <div className="fixed bottom-3 right-3 w-[520px] max-w-[95vw] rounded border bg-white shadow-lg">
      <details open>
        <summary className="cursor-pointer px-3 py-2 font-medium">Developer Console ({events.length})</summary>
        <div className="p-3 max-h-[50vh] overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-neutral-600">
                <th className="pr-2">time</th>
                <th className="pr-2">method</th>
                <th className="pr-2">status</th>
                <th className="pr-2">ms</th>
                <th>url</th>
              </tr>
            </thead>
            <tbody>
              {events.map(e => (
                <tr key={e.id} className="border-t">
                  <td className="pr-2 whitespace-nowrap">{new Date(e.ts).toLocaleTimeString()}</td>
                  <td className="pr-2">{e.method}</td>
                  <td className="pr-2">{e.status}</td>
                  <td className="pr-2">{Math.round(e.durationMs)}</td>
                  <td className="truncate max-w-[280px]" title={e.url}>{e.url}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}


