export type DevEvent = {
  id: string
  ts: number
  method: string
  url: string
  status: number
  durationMs: number
  requestBytes?: number
  responseBytes?: number
}

type Subscriber = (events: DevEvent[]) => void

class DevLogger {
  private _events: DevEvent[] = []
  private _subs: Set<Subscriber> = new Set()

  get events(): DevEvent[] { return this._events }

  subscribe(fn: Subscriber): () => void {
    this._subs.add(fn)
    fn(this._events)
    return () => { this._subs.delete(fn) }
  }

  log(e: DevEvent) {
    this._events = [e, ...this._events].slice(0, 200)
    for (const fn of this._subs) fn(this._events)
  }
}

export const devLog = new DevLogger()


