import { LEVELS } from '../lib/risk'

export type Layers = { heatmap: boolean; checkpoints: boolean; trucks: boolean }

interface Props {
  layers: Layers
  onToggle: (key: keyof Layers) => void
}

export default function Legend({ layers, onToggle }: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white/95 p-3 text-xs shadow-lg backdrop-blur">
      <div className="mb-1.5 font-semibold text-slate-800">Risk level</div>
      <ul className="space-y-1">
        {LEVELS.map((l) => (
          <li key={l.name} className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ background: l.color }} />
            <span className="text-slate-600">{l.name}</span>
          </li>
        ))}
      </ul>
      <div className="mt-2.5 space-y-1 border-t border-slate-200 pt-2">
        {(
          [
            ['heatmap', 'Weather heatmap'],
            ['checkpoints', 'Checkpoints'],
            ['trucks', 'Truck positions'],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex cursor-pointer items-center gap-2 text-slate-700">
            <input type="checkbox" checked={layers[key]} onChange={() => onToggle(key)} className="accent-teal-700" />
            {label}
          </label>
        ))}
      </div>
    </div>
  )
}
