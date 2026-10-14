import L from 'leaflet'
import { memo } from 'react'
import { Marker, Tooltip } from 'react-leaflet'
import { fmtDateTime, fmtHours } from '../lib/format'
import type { Place, RouteOption } from '../types'

const endpointIcon = (label: string, bg: string) =>
  L.divIcon({
    className: '',
    html: `<div class="endpoint-pin" style="background:${bg}">${label}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })

const START = endpointIcon('S', '#0f766e')
const END = endpointIcon('E', '#0f172a')
const STOP = {
  break: L.divIcon({ className: '', html: '<div class="stop-pin">30m</div>', iconSize: [34, 18], iconAnchor: [17, 9] }),
  rest: L.divIcon({ className: '', html: '<div class="stop-pin rest">10h</div>', iconSize: [34, 18], iconAnchor: [17, 9] }),
}

interface Props {
  origin: Place
  destination: Place
  selected: RouteOption
}

function MarkersLayer({ origin, destination, selected }: Props) {
  return (
    <>
      <Marker position={[origin.lat, origin.lon]} icon={START}>
        <Tooltip direction="top" offset={[0, -12]}>Start: {origin.label}</Tooltip>
      </Marker>
      <Marker position={[destination.lat, destination.lon]} icon={END}>
        <Tooltip direction="top" offset={[0, -12]}>End: {destination.label}</Tooltip>
      </Marker>
      {selected.stops.map((s, i) => (
        <Marker key={`${selected.id}-stop-${i}`} position={s.position} icon={STOP[s.kind]}>
          <Tooltip direction="top" offset={[0, -8]}>
            {s.kind === 'rest' ? '10-hour rest' : '30-minute break'} at mile {Math.round(s.mile)}
            <br />
            {fmtDateTime(s.start_time)} · {fmtHours(s.duration_hours)}
          </Tooltip>
        </Marker>
      ))}
    </>
  )
}

export default memo(MarkersLayer)
