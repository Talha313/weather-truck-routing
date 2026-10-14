import { useEffect, useId, useRef, useState } from 'react'
import { api } from '../lib/api'
import type { Place } from '../types'

interface Props {
  label: string
  value: Place | string
  placeholder: string
  onChange: (value: Place | string) => void
}

/** Text input with Photon-backed suggestions. Holds a Place once one is picked, or the raw
 * text otherwise (the backend geocodes free text too). */
export default function PlaceInput({ label, value, placeholder, onChange }: Props) {
  const id = useId()
  const text = typeof value === 'string' ? value : value.label
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (typeof value !== 'string' || value.trim().length < 3) {
      setResults([])
      return
    }
    const timer = setTimeout(() => {
      abortRef.current?.abort()
      const ctrl = new AbortController()
      abortRef.current = ctrl
      api
        .geocode(value, ctrl.signal)
        .then((r) => {
          setResults(r)
          setActive(-1)
        })
        .catch(() => {})
    }, 250)
    return () => clearTimeout(timer)
  }, [value])

  const pick = (p: Place) => {
    onChange(p)
    setOpen(false)
  }

  return (
    <div className="relative">
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          value={text}
          placeholder={placeholder}
          autoComplete="off"
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls={`${id}-list`}
          onChange={(e) => {
            onChange(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (!open || !results.length) return
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setActive((a) => (a + 1) % results.length)
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setActive((a) => (a <= 0 ? results.length - 1 : a - 1))
            } else if (e.key === 'Enter' && active >= 0) {
              e.preventDefault()
              pick(results[active])
            } else if (e.key === 'Escape') setOpen(false)
          }}
          className="field-input pr-8"
        />
        {typeof value !== 'string' && (
          <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-teal-600" title="Location confirmed">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8.5l3 3 7-7" /></svg>
          </span>
        )}
      </div>
      {open && results.length > 0 && (
        <ul id={`${id}-list`} role="listbox" className="absolute z-[1000] mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {results.map((r, i) => (
            <li
              key={`${r.label}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault()
                pick(r)
              }}
              className={`cursor-pointer px-3 py-2 text-sm ${i === active ? 'bg-teal-50 text-teal-900' : 'text-slate-700 hover:bg-slate-50'}`}
            >
              {r.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
