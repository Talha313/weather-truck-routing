import type { LevelName } from '../types'

export const LEVELS: { name: LevelName; color: string; text: string }[] = [
  { name: 'Low', color: '#16a34a', text: '#ffffff' },
  { name: 'Moderate', color: '#ca8a04', text: '#ffffff' },
  { name: 'High', color: '#ea580c', text: '#ffffff' },
  { name: 'Severe', color: '#dc2626', text: '#ffffff' },
  { name: 'No Travel', color: '#7e22ce', text: '#ffffff' },
]

export const UNKNOWN_COLOR = '#94a3b8'

export function levelColor(level: number | null | undefined): string {
  return level == null ? UNKNOWN_COLOR : LEVELS[level].color
}

/** Heatmap color ramp: [score, r, g, b, alpha]. Low risk stays faint so hazards stand out. */
const RAMP: [number, number, number, number, number][] = [
  [0, 34, 197, 94, 0.1],
  [1, 234, 179, 8, 0.42],
  [2, 249, 115, 22, 0.55],
  [3, 220, 38, 38, 0.65],
  [4, 126, 34, 206, 0.72],
]

/** 256-entry RGBA lookup for scores 0..4, built once. */
export const HEAT_LUT: Uint8ClampedArray = (() => {
  const lut = new Uint8ClampedArray(256 * 4)
  for (let i = 0; i < 256; i++) {
    const s = (i / 255) * 4
    const k = Math.min(Math.floor(s), 3)
    const f = s - k
    const [, r0, g0, b0, a0] = RAMP[k]
    const [, r1, g1, b1, a1] = RAMP[k + 1]
    lut[i * 4] = r0 + (r1 - r0) * f
    lut[i * 4 + 1] = g0 + (g1 - g0) * f
    lut[i * 4 + 2] = b0 + (b1 - b0) * f
    lut[i * 4 + 3] = 255 * (a0 + (a1 - a0) * f)
  }
  return lut
})()

export const FACTOR_LABEL = { wind: 'Wind', rain: 'Rain', snow: 'Snow', none: '—' } as const
