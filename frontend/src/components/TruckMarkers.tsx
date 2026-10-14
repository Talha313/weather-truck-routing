import L from 'leaflet'
import { Marker, Tooltip } from 'react-leaflet'
import { positionAtDrive } from '../lib/geo'
import type { RouteOption } from '../types'

const truckIcon = (letter: string, selected: boolean) =>
  L.divIcon({
    className: '',
    html: `<div class="truck-pin ${selected ? 'selected' : ''}">${letter}</div>`,
    iconSize: selected ? [28, 28] : [22, 22],
    iconAnchor: selected ? [14, 14] : [11, 11],
  })

const ICONS = new Map<string, L.DivIcon>()
const iconFor = (letter: string, selected: boolean) => {
  const key = `${letter}${selected}`
  if (!ICONS.has(key)) ICONS.set(key, truckIcon(letter, selected))
  return ICONS.get(key)!
}

interface Props {
  routes: RouteOption[]
  selectedId: string
  driveSeconds: Record<string, number>
}

/** Where each truck would be at the slider's time. */
export default function TruckMarkers({ routes, selectedId, driveSeconds }: Props) {
  return (
    <>
      {routes.map((r) => (
        <Marker
          key={`truck-${r.id}`}
          position={positionAtDrive(r.geometry, driveSeconds[r.id] ?? 0)}
          icon={iconFor(r.letter, r.id === selectedId)}
          zIndexOffset={r.id === selectedId ? 1000 : 500}
          interactive
        >
          <Tooltip direction="top" offset={[0, -12]}>
            Truck on {r.id} at the selected time
          </Tooltip>
        </Marker>
      ))}
    </>
  )
}
