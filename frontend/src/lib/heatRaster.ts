import type { HeatmapResponse } from '../types'
import { HEAT_LUT } from './risk'

/** Output pixels per grid cell; the browser upsamples the canvas further when zoomed in. */
const SCALE = 8

const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))
const invMercY = (y: number) => (360 / Math.PI) * Math.atan(Math.exp(y)) - 90

/**
 * Renders the corridor risk field for any (fractional) forecast hour into a canvas.
 *
 * - Time: scores are blended linearly between the two surrounding hourly frames, so
 *   playback is continuous instead of stepping once per hour.
 * - Space: bilinear interpolation between cell centres. Cells outside the corridor have
 *   no value; their interpolation weight becomes transparency, which feathers the edge.
 * - Projection: rows are laid out in Web Mercator so the image lines up with the map.
 */
export class HeatRaster {
  readonly canvas: HTMLCanvasElement
  readonly bounds: [[number, number], [number, number]]
  private readonly ctx: CanvasRenderingContext2D
  private readonly image: ImageData
  private readonly rows: number
  private readonly cols: number
  private readonly frames: Float32Array[] // per hour, rows*cols, NaN = outside corridor
  private readonly field: Float32Array
  private readonly rowIdx: Int32Array
  private readonly rowFrac: Float32Array
  private readonly colIdx: Int32Array
  private readonly colFrac: Float32Array

  constructor(data: HeatmapResponse) {
    const { south, west, step, rows, cols } = data.grid
    this.rows = rows
    this.cols = cols
    const north = south + rows * step
    const east = west + cols * step
    this.bounds = [[south, west], [north, east]]

    this.frames = Array.from({ length: data.frame_hours + 1 }, () => new Float32Array(rows * cols).fill(NaN))
    data.cells.forEach(([r, c], i) => {
      data.scores[i].forEach((score, h) => {
        if (score != null) this.frames[h][r * cols + c] = score
      })
    })
    this.field = new Float32Array(rows * cols)

    const width = cols * SCALE
    const height = rows * SCALE
    this.canvas = document.createElement('canvas')
    this.canvas.width = width
    this.canvas.height = height
    this.ctx = this.canvas.getContext('2d')!
    this.image = this.ctx.createImageData(width, height)

    // Precompute which grid cells each output pixel row/column samples from.
    const yN = mercY(north)
    const yS = mercY(south)
    this.rowIdx = new Int32Array(height)
    this.rowFrac = new Float32Array(height)
    for (let py = 0; py < height; py++) {
      const lat = invMercY(yN + ((py + 0.5) / height) * (yS - yN))
      const g = (lat - south) / step - 0.5 // grid row space, cell centres at integers
      this.rowIdx[py] = Math.floor(g)
      this.rowFrac[py] = g - Math.floor(g)
    }
    this.colIdx = new Int32Array(width)
    this.colFrac = new Float32Array(width)
    for (let px = 0; px < width; px++) {
      const g = (px + 0.5) / SCALE - 0.5
      this.colIdx[px] = Math.floor(g)
      this.colFrac[px] = g - Math.floor(g)
    }
  }

  get maxHour(): number {
    return this.frames.length - 1
  }

  draw(hour: number): void {
    const h = Math.max(0, Math.min(hour, this.maxHour))
    const h0 = Math.floor(h)
    const h1 = Math.min(h0 + 1, this.maxHour)
    const t = h - h0
    const a = this.frames[h0]
    const b = this.frames[h1]
    const field = this.field
    for (let i = 0; i < field.length; i++) {
      const va = a[i]
      const vb = b[i]
      field[i] = va !== va ? vb : vb !== vb ? va : va + (vb - va) * t // NaN-aware blend
    }

    const { rows, cols, image } = this
    const px = image.data
    const width = this.canvas.width
    const height = this.canvas.height
    let o = 0
    for (let y = 0; y < height; y++) {
      // Row is flipped: canvas top is north, grid row 0 is south.
      const r0 = this.rowIdx[height - 1 - y]
      const fr = this.rowFrac[height - 1 - y]
      for (let x = 0; x < width; x++) {
        const c0 = this.colIdx[x]
        const fc = this.colFrac[x]
        let sumW = 0
        let sumV = 0
        for (let dr = 0; dr < 2; dr++) {
          const r = r0 + dr
          if (r < 0 || r >= rows) continue
          const wr = dr ? fr : 1 - fr
          for (let dc = 0; dc < 2; dc++) {
            const c = c0 + dc
            if (c < 0 || c >= cols) continue
            const v = field[r * cols + c]
            if (v !== v) continue
            const w = wr * (dc ? fc : 1 - fc)
            sumW += w
            sumV += v * w
          }
        }
        if (sumW < 1e-3) {
          px[o + 3] = 0
        } else {
          const score = sumV / sumW
          const li = Math.min(255, Math.max(0, Math.round((score / 4) * 255))) * 4
          const edge = sumW >= 0.6 ? 1 : sumW / 0.6 // feather the corridor boundary
          px[o] = HEAT_LUT[li]
          px[o + 1] = HEAT_LUT[li + 1]
          px[o + 2] = HEAT_LUT[li + 2]
          px[o + 3] = HEAT_LUT[li + 3] * edge * edge * (3 - 2 * edge)
        }
        o += 4
      }
    }
    this.ctx.putImageData(image, 0, 0)
  }
}
