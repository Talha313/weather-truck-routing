import L from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { HeatRaster } from '../lib/heatRaster'
import type { HeatmapResponse } from '../types'

/** L.ImageOverlay that displays a live <canvas> instead of loading an image URL, so each
 * frame is a plain canvas redraw: no image decoding, no flicker. Leaflet still handles
 * positioning and zoom animation. */
const CanvasOverlay = L.ImageOverlay.extend({
  _initImage(this: L.ImageOverlay & Record<string, unknown>) {
    const el = this._url as unknown as HTMLCanvasElement
    this._image = el
    L.DomUtil.addClass(el, 'leaflet-image-layer')
    if (this._zoomAnimated) L.DomUtil.addClass(el, 'leaflet-zoom-animated')
  },
}) as unknown as new (canvas: HTMLCanvasElement, bounds: L.LatLngBoundsExpression, options?: L.ImageOverlayOptions) => L.ImageOverlay

interface Props {
  data: HeatmapResponse
  hour: number
  visible: boolean
}

export default function HeatmapLayer({ data, hour, visible }: Props) {
  const map = useMap()
  const raster = useMemo(() => new HeatRaster(data), [data])
  const layerRef = useRef<L.ImageOverlay | null>(null)

  useEffect(() => {
    if (!map.getPane('heat')) {
      const pane = map.createPane('heat')
      pane.style.zIndex = '350' // above tiles, below routes and markers
      pane.style.pointerEvents = 'none'
    }
    const layer = new CanvasOverlay(raster.canvas, raster.bounds, { pane: 'heat', interactive: false })
    layerRef.current = layer
    return () => {
      layer.remove()
      layerRef.current = null
    }
  }, [map, raster])

  useEffect(() => {
    const layer = layerRef.current
    if (!layer) return
    if (visible) layer.addTo(map)
    else layer.remove()
  }, [map, raster, visible])

  useEffect(() => {
    if (visible) raster.draw(hour)
  }, [raster, hour, visible])

  return null
}
