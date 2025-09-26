import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/lib/api'

type Health = { status: string }

export function Health() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<Health>('/health'),
    staleTime: 30_000,
  })

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-semibold">API Health</h1>
      {isLoading && <div>Loading...</div>}
      {isError && <div className="text-red-600 text-sm">{String(error)}</div>}
      {data && (
        <div className="rounded border bg-white p-3">
          <div className="text-sm">status: <span className="font-mono">{data.status}</span></div>
        </div>
      )}
    </div>
  )
}


