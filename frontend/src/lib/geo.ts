import type { GeometryPoint } from '../types'

/** Binary search for the segment containing `value` in column `col` (monotonic). */
function locate(points: GeometryPoint[], col: 2 | 3, value: number): [number, number] {
  const n = points.length
  if (value <= points[0][col]) return [0, 0]
  if (value >= points[n - 1][col]) return [n - 2, 1]
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (points[mid][col] <= value) lo = mid
    else hi = mid
  }
  const span = points[hi][col] - points[lo][col]
  return [lo, span > 0 ? (value - points[lo][col]) / span : 0]
}

export function positionAtDrive(points: GeometryPoint[], driveS: number): [number, number] {
  const [i, f] = locate(points, 3, driveS)
  const a = points[i]
  const b = points[i + 1]
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
}


export function mileAtDrive(points: GeometryPoint[], driveS: number): number {
  const [i, f] = locate(points, 3, driveS)
  return points[i][2] + (points[i + 1][2] - points[i][2]) * f
}
