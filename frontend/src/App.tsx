import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Legend, { type Layers } from './components/Legend'
import MapView from './components/MapView'
import Recommendation from './components/Recommendation'
import RouteCard from './components/RouteCard'
import TimeSlider from './components/TimeSlider'
import TripForm from './components/TripForm'
import { api, ApiError } from './lib/api'
import { fmtHours, fmtMiles } from './lib/format'
import { mileAtDrive } from './lib/geo'
import { clockToDrive } from './lib/hos'
import type { Checkpoint, HeatmapResponse, PlanRequest, PlanResponse, RouteOption } from './types'

const MAX_HOUR = 48

function floorHour(iso: string): Date {
  const d = new Date(iso)
  d.setUTCMinutes(0, 0, 0)
  return d
}

/** What the selected truck is doing at a given clock time (seconds since departure). */
function truckStatus(route: RouteOption, elapsedS: number, includeHos: boolean): string {
  if (elapsedS <= 0) return `${route.id}: departs in ${fmtHours(-elapsedS / 3600)}`
  if (elapsedS >= route.travel_hours * 3600) return `${route.id}: arrived at destination`
  const drive = clockToDrive(elapsedS, includeHos)
  const moving = clockToDrive(elapsedS + 60, includeHos) > drive
  const mile = mileAtDrive(route.geometry, drive)
  return `${route.id}: ${moving ? 'driving' : 'on a required break / rest'} at mile ${Math.round(mile)} of ${fmtMiles(route.distance_miles)}`
}

export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [heatLoading, setHeatLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [heatError, setHeatError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hour, setHour] = useState(0)
  const [layers, setLayers] = useState<Layers>({ heatmap: true, checkpoints: true, trucks: true })
  const [focus, setFocus] = useState<[number, number] | null>(null)
  const requestId = useRef(0)

  const submit = useCallback(async (req: PlanRequest) => {
    const id = ++requestId.current
    setLoading(true)
    setError(null)
    setHeatError(null)
    setHeatmap(null)
    try {
      const result = await api.plan(req)
      if (id !== requestId.current) return
      setPlan(result)
      setSelectedId(result.recommendation.route_id)
      setHour(0)
      setLoading(false)
      // The heatmap needs ~250 more forecasts, so load it after the routes are on screen.
      setHeatLoading(true)
      try {
        const heat = await api.heatmap({
          origin: result.origin,
          destination: result.destination,
          departure_time: req.departure_time,
          load_weight_lbs: req.load_weight_lbs,
        })
        if (id === requestId.current) setHeatmap(heat)
      } catch (e) {
        if (id === requestId.current) setHeatError(e instanceof ApiError ? e.message : 'Could not load the heatmap.')
      } finally {
        if (id === requestId.current) setHeatLoading(false)
      }
    } catch (e) {
      if (id !== requestId.current) return
      setError(e instanceof ApiError ? e.message : 'Something went wrong.')
      setLoading(false)
    }
  }, [])

  const departure = useMemo(() => (plan ? new Date(plan.departure_time) : null), [plan])
  const baseTime = useMemo(
    () => (heatmap ? new Date(heatmap.base_time) : plan ? floorHour(plan.departure_time) : null),
    [heatmap, plan],
  )

  // Seconds of driving done by each truck at the slider time.
  const driveSeconds = useMemo(() => {
    if (!plan || !baseTime || !departure) return {}
    const elapsed = (baseTime.getTime() + hour * 3600_000 - departure.getTime()) / 1000
    return Object.fromEntries(plan.routes.map((r) => [r.id, clockToDrive(Math.min(elapsed, r.travel_hours * 3600), plan.include_hos)]))
  }, [plan, baseTime, departure, hour])

  const selected = plan?.routes.find((r) => r.id === selectedId) ?? null
  const status = useMemo(() => {
    if (!plan || !selected || !baseTime || !departure) return ''
    const elapsed = (baseTime.getTime() + hour * 3600_000 - departure.getTime()) / 1000
    return truckStatus(selected, elapsed, plan.include_hos)
  }, [plan, selected, baseTime, departure, hour])

  const focusCheckpoint = useCallback((cp: Checkpoint) => setFocus([cp.lat, cp.lon]), [])
  const toggleLayer = useCallback((key: keyof Layers) => setLayers((l) => ({ ...l, [key]: !l[key] })), [])

  useEffect(() => {
    if (plan) document.title = `${plan.origin.label.split(',')[0]} → ${plan.destination.label.split(',')[0]} · Weather-Aware Truck Routing`
  }, [plan])

  return (
    <div className="flex h-full flex-col md:flex-row">
      <aside className="flex w-full shrink-0 flex-col border-slate-200 bg-slate-50 md:h-full md:w-[400px] md:border-r">
        <header className="border-b border-slate-200 bg-white px-4 py-3.5">
          <div className="flex items-center gap-2.5">
            <img src="/truck.svg" alt="" className="h-7 w-7" />
            <div>
              <h1 className="text-[15px] font-semibold leading-tight text-slate-900">Weather-Aware Truck Routing</h1>
              <p className="text-xs text-slate-500">Safest route by weather, load and travel time</p>
            </div>
          </div>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <TripForm loading={loading} onSubmit={submit} />
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
              {error}
            </div>
          )}
          {plan && (
            <>
              <Recommendation plan={plan} />
              <div className="space-y-2.5">
                {[...plan.routes]
                  .sort((a, b) => a.rank - b.rank)
                  .map((r) => (
                    <RouteCard
                      key={r.id}
                      route={r}
                      selected={r.id === selectedId}
                      onSelect={() => setSelectedId(r.id)}
                      onFocusCheckpoint={focusCheckpoint}
                    />
                  ))}
              </div>
              <p className="pb-2 text-[11px] leading-snug text-slate-400">
                Routing: {plan.provider === 'valhalla' ? 'Valhalla (truck profile)' : 'OSRM'} · Weather: Open-Meteo hourly forecast, sampled at each
                checkpoint’s ETA · Each checkpoint stands for the route miles nearest to it.
              </p>
            </>
          )}
        </div>
      </aside>

      <main className="relative h-[75vh] min-h-[420px] flex-1 md:h-full">
        <MapView
          plan={plan}
          heatmap={heatmap}
          selectedId={selectedId}
          hour={hour}
          driveSeconds={driveSeconds}
          layers={layers}
          focus={focus}
          onSelect={setSelectedId}
        />
        {!plan && !loading && (
          <div className="pointer-events-none absolute inset-x-0 top-4 z-[500] mx-auto w-fit max-w-[90%] rounded-full bg-white/95 px-4 py-2 text-sm text-slate-600 shadow">
            Enter a trip to compare three routes
          </div>
        )}
        {loading && (
          <div className="absolute inset-0 z-[600] flex items-center justify-center bg-white/40 backdrop-blur-[1px]">
            <div className="flex items-center gap-3 rounded-xl bg-white px-4 py-3 text-sm text-slate-700 shadow-lg">
              <span className="h-5 w-5 animate-spin rounded-full border-2 border-teal-200 border-t-teal-700" />
              Finding 3 truck routes and checking the forecast at every checkpoint…
            </div>
          </div>
        )}
        {plan && (
          <div className="absolute right-3 top-24 z-[500] hidden sm:block">
            <Legend layers={layers} onToggle={toggleLayer} />
          </div>
        )}
        {plan && baseTime && departure && (
          <div className="absolute inset-x-3 bottom-9 z-[500] mx-auto max-w-2xl sm:bottom-5">
            {heatError && (
              <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-900">
                Heatmap unavailable: {heatError}
              </div>
            )}
            <TimeSlider
              hour={hour}
              maxHour={MAX_HOUR}
              baseTime={baseTime}
              departure={departure}
              loading={heatLoading}
              status={status}
              onChange={setHour}
            />
          </div>
        )}
      </main>
    </div>
  )
}
