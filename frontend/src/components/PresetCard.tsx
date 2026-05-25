import type { Preset } from '../data/presets';

interface Props {
  preset: Preset;
  onClick: () => void;
}

export default function PresetCard({ preset, onClick }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-left rounded-xl border border-slate-200 bg-white hover:border-indigo-400 hover:shadow-md transition p-4 w-full"
    >
      <div className="font-semibold text-slate-800">{preset.title}</div>
      <div className="text-sm text-slate-500 mt-1">{preset.subtitle}</div>
      <div className="text-xs text-indigo-600 mt-3">点击填入任务指令 →</div>
    </button>
  );
}
