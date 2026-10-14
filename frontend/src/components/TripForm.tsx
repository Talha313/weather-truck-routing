import { useState } from 'react'
import { toLocalInput } from '../lib/format'
import type { Place, PlanRequest } from '../types'
import PlaceInput from './PlaceInput'

const EXAMPLES: { label: string; origin: Place; destination: Place }[] = [
  {
    label: 'Chicago → Dallas',
    origin: { label: 'Chicago, Illinois, US', lat: 41.8755616, lon: -87.6244212 },
    destination: { label: 'Dallas, Texas, US', lat: 32.7762719, lon: -96.7968559 },
  },
  {
    label: 'Denver → Salt Lake City',
    origin: { label: 'Denver, Colorado, US', lat: 39.7392364, lon: -104.984862 },
    destination: { label: 'Salt Lake City, Utah, US', lat: 40.7596198, lon: -111.886797 },
  },
  {
    label: 'Seattle → Boise',
    origin: { label: 'Seattle, Washington, US', lat: 47.6038321, lon: -122.330062 },
    destination: { label: 'Boise, Idaho, US', lat: 43.6166163, lon: -116.200886 },
  },
]

function nextQuarterHour(): Date {
  const d = new Date()
  d.setMinutes(Math.ceil((d.getMinutes() + 1) / 15) * 15, 0, 0)
  return d
}

interface Props {
  loading: boolean
  onSubmit: (req: PlanRequest) => void
}

export default function TripForm({ loading, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | string>('')
  const [destination, setDestination] = useState<Place | string>('')
  const [departure, setDeparture] = useState(() => toLocalInput(nextQuarterHour()))
  const [load, setLoad] = useState('35000')
  const [interval, setCheckpointInterval] = useState<10 | 25 | 50>(25)
  const [includeHos, setIncludeHos] = useState(true)
  const [formError, setFormError] = useState<string | null>(null)

  const now = new Date()
  const maxDate = new Date(now.getTime() + 7 * 24 * 3600_000)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const loadLbs = Number(load)
    const dep = new Date(departure)
    if (!(typeof origin === 'string' ? origin.trim() : origin.label)) return setFormError('Enter an origin.')
    if (!(typeof destination === 'string' ? destination.trim() : destination.label)) return setFormError('Enter a destination.')
    if (Number.isNaN(dep.getTime())) return setFormError('Enter a valid departure date and time.')
    if (!Number.isFinite(loadLbs) || loadLbs < 0 || loadLbs > 120000) return setFormError('Load weight must be between 0 and 120,000 lb.')
    setFormError(null)
    onSubmit({
      origin,
      destination,
      departure_time: dep.toISOString(),
      load_weight_lbs: loadLbs,
      checkpoint_interval_miles: interval,
      include_hos: includeHos,
    })
  }

  return (
    <form onSubmit={submit} className="space-y-3.5" noValidate>
      <div className="flex flex-wrap gap-1.5">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            type="button"
            onClick={() => {
              setOrigin(ex.origin)
              setDestination(ex.destination)
            }}
            className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 hover:border-teal-300 hover:bg-teal-50 hover:text-teal-800"
          >
            {ex.label}
          </button>
        ))}
      </div>

      <PlaceInput label="Origin" value={origin} placeholder="City or address" onChange={setOrigin} />
      <PlaceInput label="Destination" value={destination} placeholder="City or address" onChange={setDestination} />

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="departure" className="field-label">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            value={departure}
            min={toLocalInput(new Date(now.getTime() - 6 * 3600_000))}
            max={toLocalInput(maxDate)}
            onChange={(e) => setDeparture(e.target.value)}
            className="field-input"
          />
        </div>
        <div>
          <label htmlFor="load" className="field-label">Load weight</label>
          <div className="relative">
            <input
              id="load"
              type="number"
              inputMode="numeric"
              min={0}
              max={120000}
              step={500}
              value={load}
              onChange={(e) => setLoad(e.target.value)}
              className="field-input pr-9"
            />
            <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-slate-400">lb</span>
          </div>
        </div>
      </div>

      <div>
        <span className="field-label">Weather checkpoint every</span>
        <div className="grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-1" role="radiogroup" aria-label="Checkpoint interval">
          {([10, 25, 50] as const).map((v) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={interval === v}
              onClick={() => setCheckpointInterval(v)}
              className={`rounded-md py-1.5 text-sm font-medium transition ${interval === v ? 'bg-white text-teal-800 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
            >
              {v} mi
            </button>
          ))}
        </div>
      </div>

      <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={includeHos} onChange={(e) => setIncludeHos(e.target.checked)} className="mt-0.5 accent-teal-700" />
        <span>
          Include required driver breaks in ETAs
          <span className="block text-xs text-slate-500">30-min break after 8 h, 10-h rest after 11 h of driving (FMCSA)</span>
        </span>
      </label>

      {formError && <p className="text-sm text-red-600" role="alert">{formError}</p>}

      <button
        type="submit"
        disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-800 disabled:cursor-wait disabled:opacity-70"
      >
        {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />}
        {loading ? 'Analyzing routes & weather…' : 'Find safest route'}
      </button>
    </form>
  )
}
