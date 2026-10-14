import { fmtDateTime, fmtHours, fmtMiles, fmtTime } from '../lib/format'
import { FACTOR_LABEL, LEVELS, levelColor, UNKNOWN_COLOR } from '../lib/risk'
import type { Checkpoint, RouteOption } from '../types'

interface Props {
  route: RouteOption
  selected: boolean
  onSelect: () => void
  onFocusCheckpoint: (cp: Checkpoint) => void
}

export function RiskBar({ route }: { route: RouteOption }) {
  const total = route.distance_miles || 1
  return (
    <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100" aria-hidden>
      {route.checkpoints.map((cp) => (
        <div
          key={cp.index}
          style={{ width: `${((cp.covers[1] - cp.covers[0]) / total) * 100}%`, background: levelColor(cp.risk?.level) }}
        />
      ))}
    </div>
  )
}

export default function RouteCard({ route, selected, onSelect, onFocusCheckpoint }: Props) {
  const rm = route.risk_miles
  return (
    <div
      className={`rounded-xl border bg-white transition ${selected ? 'border-teal-600 shadow-md ring-1 ring-teal-600' : 'border-slate-200 hover:border-slate-300'}`}
    >
      <button type="button" onClick={onSelect} className="w-full p-3.5 text-left" aria-pressed={selected}>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold text-slate-900">{route.id}</span>
              {route.recommended && (
                <span className="rounded-full bg-teal-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-teal-800">
                  Recommended
                </span>
              )}
            </div>
            <div className="truncate text-xs text-slate-500" title={route.via}>
              via {route.via || 'local roads'}
            </div>
          </div>
          <span className="shrink-0 rounded-md bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">#{route.rank}</span>
        </div>

        <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
          <Stat label="Distance" value={fmtMiles(route.distance_miles)} />
          <Stat label="Driving" value={fmtHours(route.drive_hours)} />
          <Stat label="Arrive" value={fmtTime(route.arrival_time)} title={`${fmtDateTime(route.arrival_time)} · total ${fmtHours(route.travel_hours)} incl. stops`} />
        </dl>

        <div className="mt-3">
          <RiskBar route={route} />
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
            {(['No Travel', 'Severe', 'High', 'Moderate'] as const).map((name) =>
              rm[name] > 0 ? (
                <span key={name} className="flex items-center gap-1 text-slate-600">
                  <span className="h-2 w-2 rounded-full" style={{ background: LEVELS.find((l) => l.name === name)!.color }} />
                  {name} <b className="font-semibold text-slate-800">{fmtMiles(rm[name])}</b>
                </span>
              ) : null,
            )}
            {rm['No Travel'] + rm.Severe + rm.High + rm.Moderate === 0 && (
              <span className="text-slate-600">All checkpoints Low risk</span>
            )}
            {route.unknown_miles > 0 && (
              <span className="flex items-center gap-1 text-slate-500">
                <span className="h-2 w-2 rounded-full" style={{ background: UNKNOWN_COLOR }} />
                no data {fmtMiles(route.unknown_miles)}
              </span>
            )}
            <span className="ml-auto text-slate-500">avg risk {route.avg_risk.toFixed(2)}</span>
          </div>
        </div>
      </button>

      {selected && (
        <div className="border-t border-slate-100 px-3.5 pb-3 pt-2">
          <div className="mb-1.5 flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-700">{route.checkpoints.length} checkpoints</span>
            <span className="text-slate-400">Click one to zoom to it</span>
          </div>
          <div className="max-h-72 overflow-auto rounded-lg border border-slate-100">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-2 py-1.5 font-medium">Mile</th>
                  <th className="px-2 py-1.5 font-medium">ETA</th>
                  <th className="px-2 py-1.5 font-medium">Wind</th>
                  <th className="px-2 py-1.5 font-medium">Precip</th>
                  <th className="px-2 py-1.5 font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {route.checkpoints.map((cp) => (
                  <tr
                    key={cp.index}
                    onClick={() => onFocusCheckpoint(cp)}
                    className="cursor-pointer border-t border-slate-100 tabular-nums hover:bg-teal-50/60"
                  >
                    <td className="px-2 py-1 text-slate-700">{Math.round(cp.mile)}</td>
                    <td className="whitespace-nowrap px-2 py-1 text-slate-600">{fmtTime(cp.eta)}</td>
                    <td className="px-2 py-1 text-slate-600">{cp.weather ? Math.round(cp.weather.wind_mph) : '–'}</td>
                    <td className="px-2 py-1 text-slate-600">{precip(cp)}</td>
                    <td className="px-2 py-1">
                      <span
                        className="inline-block rounded px-1.5 py-px text-[10.5px] font-semibold text-white"
                        style={{ background: levelColor(cp.risk?.level) }}
                        title={cp.risk && cp.risk.factor !== 'none' ? `${FACTOR_LABEL[cp.risk.factor]}${cp.risk.load_rule ? ` · ${cp.risk.load_rule}` : ''}` : undefined}
                      >
                        {cp.risk?.name ?? 'n/a'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function precip(cp: Checkpoint): string {
  const w = cp.weather
  if (!w) return '–'
  if (w.snow_in_hr >= 0.01) return `${w.snow_in_hr.toFixed(2)}″ snow`
  if (w.rain_in_hr >= 0.01) return `${w.rain_in_hr.toFixed(2)}″ rain`
  return 'none'
}

function Stat({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div title={title}>
      <dt className="text-slate-400">{label}</dt>
      <dd className="font-semibold text-slate-800">{value}</dd>
    </div>
  )
}
