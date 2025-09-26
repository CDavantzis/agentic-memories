import { Outlet, Link, useLocation } from 'react-router-dom'
import { getPersistedUserId } from '@/lib/api'
import { useEffect, useState } from 'react'
import { DevConsole } from '@/components/DevConsole'

export function AppLayout() {
  const location = useLocation()
  const [userId, setUserId] = useState('')
  useEffect(() => { setUserId(getPersistedUserId()) }, [location])

  function onChangeUserId(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value
    setUserId(v)
    const url = new URL(window.location.href)
    url.searchParams.set('user_id', v)
    localStorage.setItem('user_id', v)
    window.history.replaceState({}, '', url.toString())
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-4">
          <div className="font-semibold">Agentic Memories</div>
          <nav className="flex items-center gap-3 text-sm">
            <Link className="hover:underline" to="/health">Health</Link>
            <Link className="hover:underline" to="/retrieve">Retrieve</Link>
            <Link className="hover:underline" to="/store">Store</Link>
            <Link className="hover:underline" to="/structured">Structured</Link>
            <Link className="hover:underline" to="/browser">Browser</Link>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <label className="text-sm text-neutral-600">user_id</label>
            <input
              className="border rounded px-2 py-1 text-sm"
              value={userId}
              onChange={onChangeUserId}
              placeholder="test_user_22"
            />
          </div>
        </div>
      </header>
      <main className="flex-1">
        <div className="max-w-6xl mx-auto p-4">
          <Outlet />
        </div>
      </main>
      <DevConsole />
    </div>
  )
}


