import { fmtDateTime } from '../lib/format'
import type { PlanResponse } from '../types'

export default function Recommendation({ plan }: { plan: PlanResponse }) {
  const rec = plan.recommendation
  const best = plan.routes.find((r) => r.id === rec.route_id)!
  return (
    <section className="rounded-xl border border-teal-200 bg-teal-50/70 p-3.5">
      <div className="text-xs font-semibold uppercase tracking-wide text-teal-700">Recommended</div>
      <div className="mt-0.5 text-lg font-semibold text-slate-900">
        {best.id} <span className="text-sm font-normal text-slate-600">via {best.via || 'local roads'}</span>
      </div>
      <div className="text-sm text-slate-600">Arrives {fmtDateTime(best.arrival_time)}</div>
      {rec.warning && (
        <p className="mt-2 rounded-lg border border-purple-200 bg-purple-50 px-2.5 py-2 text-sm font-medium text-purple-900" role="alert">
          {rec.warning}
        </p>
      )}
      <ul className="mt-2 space-y-1 text-sm text-slate-700">
        {rec.reasons.map((r) => (
          <li key={r} className="flex gap-2">
            <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-teal-600" />
            {r}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] leading-snug text-slate-500">
        Ranked by fewest Severe miles, then High miles, then average risk, then travel time. Any No Travel miles rank last.
      </p>
    </section>
  )
}
