import type { HeatmapResponse, Place, PlanRequest, PlanResponse } from '../types'

const BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

export class ApiError extends Error {}

function describe(body: unknown): string {
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>
    if (typeof b.error === 'string') return b.error
    // DRF validation errors: { field: ["message"] }
    return Object.entries(b)
      .map(([field, msgs]) => `${field.replace(/_/g, ' ')}: ${Array.isArray(msgs) ? msgs.join(' ') : String(msgs)}`)
      .join(' · ')
  }
  return 'Unexpected server response'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running?')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(describe(body))
  return body as T
}

export const api = {
  geocode: (q: string, signal?: AbortSignal) =>
    request<{ results: Place[] }>(`/api/geocode/?q=${encodeURIComponent(q)}`, { signal }).then((r) => r.results),
  plan: (body: PlanRequest) => request<PlanResponse>('/api/plan/', { method: 'POST', body: JSON.stringify(body) }),
  heatmap: (body: Omit<PlanRequest, 'checkpoint_interval_miles' | 'include_hos'>) =>
    request<HeatmapResponse>('/api/heatmap/', { method: 'POST', body: JSON.stringify(body) }),
}
