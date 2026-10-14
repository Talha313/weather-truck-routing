import { memo, useMemo } from 'react'
import { CircleMarker, Polyline, Popup, Tooltip } from 'react-leaflet'
import { levelColor } from '../lib/risk'
import type { RouteOption } from '../types'
import CheckpointPopup from './CheckpointPopup'

/** Split the route into runs of equal risk level using each checkpoint's mile coverage. */
function riskSegments(route: RouteOption): { level: number | null; positions: [number, number][] }[] {
  const cps = route.checkpoints
  const segs: { level: number | null; positions: [number, number][] }[] = []
  let k = 0
  for (const [lat, lon, mile] of route.geometry) {
    while (k < cps.length - 1 && mile > cps[k].covers[1]) k++
    const level = cps[k].risk?.level ?? null
    const last = segs[segs.length - 1]
    if (last && last.level === level) last.positions.push([lat, lon])
    else {
      // Start the new run at the previous point so runs join without gaps.
      const prev = last ? last.positions[last.positions.length - 1] : null
      segs.push({ level, positions: prev ? [prev, [lat, lon]] : [[lat, lon]] })
    }
  }
  return segs
}

interface Props {
  routes: RouteOption[]
  selectedId: string
  showCheckpoints: boolean
  onSelect: (id: string) => void
}

function RouteLayers({ routes, selectedId, showCheckpoints, onSelect }: Props) {
  const selected = routes.find((r) => r.id === selectedId)!
  const segments = useMemo(() => riskSegments(selected), [selected])
  const others = routes.filter((r) => r.id !== selectedId)

  return (
    <>
      {others.map((r) => (
        <Polyline
          key={`line-${r.id}`}
          positions={r.geometry.map(([lat, lon]) => [lat, lon] as [number, number])}
          pathOptions={{ color: '#475569', weight: 5, opacity: 0.55, dashArray: '8 7' }}
          eventHandlers={{ click: () => onSelect(r.id) }}
        >
          <Tooltip sticky>
            {r.id} · click to select
          </Tooltip>
        </Polyline>
      ))}

      <Polyline
        key={`casing-${selected.id}`}
        positions={selected.geometry.map(([lat, lon]) => [lat, lon] as [number, number])}
        pathOptions={{ color: '#0f172a', weight: 9, opacity: 0.85 }}
        interactive={false}
      />
      {segments.map((s, i) => (
        <Polyline
          key={`seg-${selected.id}-${i}`}
          positions={s.positions}
          pathOptions={{ color: levelColor(s.level), weight: 5, opacity: 1 }}
          interactive={false}
        />
      ))}

      {showCheckpoints &&
        [...others, selected].map((r) =>
          r.checkpoints.map((cp) => {
            const isSel = r.id === selectedId
            return (
              <CircleMarker
                key={`cp-${r.id}-${cp.index}`}
                center={[cp.lat, cp.lon]}
                radius={isSel ? 6 : 4}
                pathOptions={{
                  color: isSel ? '#ffffff' : '#334155',
                  weight: isSel ? 2 : 1,
                  fillColor: levelColor(cp.risk?.level),
                  fillOpacity: isSel ? 1 : 0.75,
                }}
              >
                <Popup>
                  <CheckpointPopup routeId={r.id} checkpoint={cp} />
                </Popup>
              </CircleMarker>
            )
          }),
        )}
    </>
  )
}

export default memo(RouteLayers)
