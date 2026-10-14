import L from 'leaflet'
import { useEffect } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'
import type { HeatmapResponse, PlanResponse } from '../types'
import HeatmapLayer from './HeatmapLayer'
import MarkersLayer from './MarkersLayer'
import RouteLayers from './RouteLayers'
import TruckMarkers from './TruckMarkers'

function FitToPlan({ plan, focus }: { plan: PlanResponse | null; focus: [number, number] | null }) {
  const map = useMap()
  useEffect(() => {
    if (!plan) return
    const bounds = L.latLngBounds(plan.routes.flatMap((r) => r.geometry.map(([lat, lon]) => [lat, lon] as [number, number])))
    map.fitBounds(bounds, { padding: [40, 40] })
  }, [map, plan])
  useEffect(() => {
    if (focus) map.flyTo(focus, Math.max(map.getZoom(), 9), { duration: 0.8 })
  }, [map, focus])
  return null
}

interface Props {
  plan: PlanResponse | null
  heatmap: HeatmapResponse | null
  selectedId: string | null
  hour: number
  driveSeconds: Record<string, number>
  layers: { heatmap: boolean; checkpoints: boolean; trucks: boolean }
  focus: [number, number] | null
  onSelect: (id: string) => void
}

export default function MapView({ plan, heatmap, selectedId, hour, driveSeconds, layers, focus, onSelect }: Props) {
  const selected = plan?.routes.find((r) => r.id === selectedId)
  return (
    <MapContainer center={[39.5, -96]} zoom={4} maxZoom={16} preferCanvas zoomControl={false} className="h-full w-full">
      <TileLayer
        attribution='Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors · Weather: <a href="https://open-meteo.com/">Open-Meteo</a>'
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        maxZoom={16}
      />
      <LabelsPane />
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
        pane="labels"
        maxZoom={16}
      />
      <ZoomControlBottomRight />
      <FitToPlan plan={plan} focus={focus} />
      {heatmap && <HeatmapLayer data={heatmap} hour={hour} visible={layers.heatmap} />}
      {plan && selected && (
        <>
          <RouteLayers routes={plan.routes} selectedId={selected.id} showCheckpoints={layers.checkpoints} onSelect={onSelect} />
          <MarkersLayer origin={plan.origin} destination={plan.destination} selected={selected} />
          {layers.trucks && <TruckMarkers routes={plan.routes} selectedId={selected.id} driveSeconds={driveSeconds} />}
        </>
      )}
    </MapContainer>
  )
}

function ZoomControlBottomRight() {
  const map = useMap()
  useEffect(() => {
    const control = L.control.zoom({ position: 'topright' }).addTo(map)
    return () => {
      control.remove()
    }
  }, [map])
  return null
}

/** Place names drawn above the heatmap so cities stay readable. */
function LabelsPane() {
  const map = useMap()
  if (!map.getPane('labels')) {
    const pane = map.createPane('labels')
    pane.style.zIndex = '380'
    pane.style.pointerEvents = 'none'
  }
  return null
}
