import { useEffect, useRef, useState } from 'react'
import { fmtDateTime } from '../lib/format'

interface Props {
  hour: number
  maxHour: number
  baseTime: Date
  departure: Date
  loading: boolean
  status: string
  onChange: (hour: number) => void
}

const HOURS_PER_SECOND = 3

export default function TimeSlider({ hour, maxHour, baseTime, departure, loading, status, onChange }: Props) {
  const [playing, setPlaying] = useState(false)
  const hourRef = useRef(hour)
  hourRef.current = hour

  useEffect(() => {
    if (!playing) return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      const next = hourRef.current + ((now - last) / 1000) * HOURS_PER_SECOND
      last = now
      if (next >= maxHour) {
        onChange(maxHour)
        setPlaying(false)
        return
      }
      onChange(next)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, maxHour, onChange])

  const at = new Date(baseTime.getTime() + hour * 3600_000)
  const sinceDeparture = (at.getTime() - departure.getTime()) / 3600_000

  const togglePlay = () => {
    if (!playing && hour >= maxHour) onChange(0)
    setPlaying((p) => !p)
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={togglePlay}
          aria-label={playing ? 'Pause' : 'Play forecast'}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-700 text-white hover:bg-teal-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2"
        >
          {playing ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><rect x="2" y="1" width="3.5" height="12" rx="1" /><rect x="8.5" y="1" width="3.5" height="12" rx="1" /></svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M3 1.5v11a.5.5 0 0 0 .76.43l9-5.5a.5.5 0 0 0 0-.86l-9-5.5A.5.5 0 0 0 3 1.5z" /></svg>
          )}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
            <span className="font-semibold text-slate-900">{fmtDateTime(at)}</span>
            <span className="tabular-nums text-slate-500">
              +{Math.floor(hour)} h forecast
              {Math.abs(sinceDeparture) >= 0.5 && ` · ${sinceDeparture >= 0 ? `${Math.round(sinceDeparture)} h after` : `${Math.round(-sinceDeparture)} h before`} departure`}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={maxHour}
            step={0.25}
            value={hour}
            onChange={(e) => {
              setPlaying(false)
              onChange(Number(e.target.value))
            }}
            className="time-slider mt-1 w-full"
            aria-label="Forecast hour"
          />
          <div className="flex justify-between text-[11px] tabular-nums text-slate-400">
            {[0, 12, 24, 36, 48].map((h) => <span key={h}>{h} h</span>)}
          </div>
        </div>
      </div>
      <div className="mt-1.5 truncate text-xs text-slate-600">
        {loading ? 'Loading corridor forecast…' : status}
      </div>
    </div>
  )
}
