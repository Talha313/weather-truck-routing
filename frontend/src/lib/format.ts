const timeFmt = new Intl.DateTimeFormat(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
})

export const fmtTime = (iso: string | Date) => timeFmt.format(new Date(iso))
export const fmtDateTime = (iso: string | Date) => dateTimeFmt.format(new Date(iso))

export function fmtHours(hours: number): string {
  const total = Math.round(hours * 60)
  const h = Math.floor(total / 60)
  const m = total % 60
  return h ? `${h} h ${m.toString().padStart(2, '0')} min` : `${m} min`
}

export const fmtMiles = (mi: number) => `${Math.round(mi).toLocaleString()} mi`

/** Value for <input type="datetime-local"> in the browser's local time. */
export function toLocalInput(d: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
