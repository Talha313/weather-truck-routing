import { fmtDateTime } from '../lib/format'
import { FACTOR_LABEL, LEVELS, levelColor } from '../lib/risk'
import type { Checkpoint } from '../types'

export default function CheckpointPopup({ routeId, checkpoint: cp }: { routeId: string; checkpoint: Checkpoint }) {
  const w = cp.weather
  const r = cp.risk
  return (
    <div className="min-w-[210px] text-[13px] leading-snug text-slate-700">
      <div className="mb-1 flex items-center justify-between gap-3">
        <span className="font-semibold text-slate-900">
          {routeId} · mile {Math.round(cp.mile)}
        </span>
        <span
          className="rounded px-1.5 py-0.5 text-[11px] font-semibold text-white"
          style={{ background: levelColor(r?.level) }}
        >
          {r?.name ?? 'No data'}
        </span>
      </div>
      <div className="mb-2 text-slate-500">ETA {fmtDateTime(cp.eta)}</div>
      {w ? (
        <table className="w-full">
          <tbody>
            <Row label="Wind" value={`${w.wind_mph} mph`} extra={`gusts ${w.gust_mph}`} level={r?.wind} />
            <Row label="Rain" value={`${w.rain_in_hr.toFixed(2)} in/hr`} level={r?.rain} />
            <Row label="Snow" value={`${w.snow_in_hr.toFixed(2)} in/hr`} level={r?.snow} />
            {w.temp_f != null && <Row label="Temp" value={`${w.temp_f}°F`} />}
          </tbody>
        </table>
      ) : (
        <div className="text-slate-500">No forecast available for this time.</div>
      )}
      {r && r.factor !== 'none' && (
        <div className="mt-2 border-t border-slate-200 pt-1.5 text-slate-600">
          Driven by <b>{FACTOR_LABEL[r.factor].toLowerCase()}</b>
          {r.load_rule && <> (load rule: {r.load_rule})</>}
        </div>
      )}
    </div>
  )
}

function Row({ label, value, extra, level }: { label: string; value: string; extra?: string; level?: number }) {
  return (
    <tr>
      <td className="py-0.5 pr-2 text-slate-500">{label}</td>
      <td className="py-0.5 font-medium text-slate-800">
        {value}
        {extra && <span className="ml-1 font-normal text-slate-400">{extra}</span>}
      </td>
      <td className="py-0.5 text-right">
        {level != null && (
          <span className="text-[11px] font-medium" style={{ color: LEVELS[level].color }}>
            {LEVELS[level].name}
          </span>
        )}
      </td>
    </tr>
  )
}
