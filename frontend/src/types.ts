export interface Place {
  label: string
  lat: number
  lon: number
}

export interface PlanRequest {
  origin: Place | string
  destination: Place | string
  departure_time: string
  load_weight_lbs: number
  checkpoint_interval_miles: 10 | 25 | 50
  include_hos: boolean
}

export type LevelName = 'Low' | 'Moderate' | 'High' | 'Severe' | 'No Travel'

export interface CheckpointWeather {
  wind_mph: number
  gust_mph: number
  rain_in_hr: number
  snow_in_hr: number
  temp_f: number | null
  weather_code: number | null
}

export interface CheckpointRisk {
  level: number
  name: LevelName
  factor: 'wind' | 'rain' | 'snow' | 'none'
  wind: number
  rain: number
  snow: number
  load_rule: string | null
}

export interface Checkpoint {
  index: number
  mile: number
  lat: number
  lon: number
  covers: [number, number]
  eta: string
  elapsed_hours: number
  weather: CheckpointWeather | null
  risk: CheckpointRisk | null
}

export interface Stop {
  kind: 'break' | 'rest'
  mile: number
  position: [number, number]
  start_time: string
  duration_hours: number
}

/** [lat, lon, route mile, driving seconds] */
export type GeometryPoint = [number, number, number, number]

export interface RouteOption {
  id: string
  letter: string
  rank: number
  recommended: boolean
  via: string
  distance_miles: number
  drive_hours: number
  travel_hours: number
  arrival_time: string
  risk_miles: Record<LevelName, number>
  unknown_miles: number
  avg_risk: number
  max_level: number | null
  geometry: GeometryPoint[]
  stops: Stop[]
  checkpoints: Checkpoint[]
}

export interface PlanResponse {
  origin: Place
  destination: Place
  departure_time: string
  load_weight_lbs: number
  checkpoint_interval_miles: number
  include_hos: boolean
  provider: string
  recommendation: {
    route_id: string
    ranking: string[]
    reasons: string[]
    warning: string | null
  }
  routes: RouteOption[]
}

export interface HeatmapResponse {
  base_time: string
  frame_hours: number
  grid: { south: number; west: number; step: number; rows: number; cols: number }
  cells: [number, number][]
  scores: (number | null)[][]
}
