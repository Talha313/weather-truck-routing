/** Inverse of the backend's HOS timing: clock seconds since departure → driving seconds done.
 * One shift cycle = 8 h drive, 0.5 h break, 3 h drive, 10 h rest (21.5 h). */
const H = 3600

export function clockToDrive(elapsedS: number, includeHos: boolean): number {
  if (elapsedS <= 0) return 0
  if (!includeHos) return elapsedS
  const cycle = 21.5 * H
  const k = Math.floor(elapsedS / cycle)
  const r = elapsedS - k * cycle
  let drive = k * 11 * H
  if (r < 8 * H) drive += r
  else if (r < 8.5 * H) drive += 8 * H
  else if (r < 11.5 * H) drive += 8 * H + (r - 8.5 * H)
  else drive += 11 * H
  return drive
}
