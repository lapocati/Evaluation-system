import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts';
import type { DimensionKey, Report } from '../types';

const DIM_LABEL: Record<DimensionKey | 'efficiency', string> = {
  task_completion: '任务完成',
  instruction_following: '指令遵循',
  naturalness: '自然度',
  branch_handling: '分支处理',
  efficiency: '效率',
};

interface Props {
  report: Report;
}

export default function ScoreRadar({ report }: Props) {
  const data = (Object.keys(DIM_LABEL) as Array<keyof typeof DIM_LABEL>).map((key) => {
    let score: number | null;
    if (key === 'efficiency') {
      score = report.efficiency.score;
    } else {
      score = report.dimensions[key]?.score ?? null;
    }
    return {
      dimension: DIM_LABEL[key],
      score: score === null ? 0 : Math.round(score * 100),
      hasScore: score !== null,
    };
  });

  return (
    <div className="w-full h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="75%">
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fill: '#475569', fontSize: 12 }}
          />
          <PolarRadiusAxis
            domain={[0, 100]}
            tickCount={5}
            tick={{ fill: '#94a3b8', fontSize: 10 }}
            stroke="#cbd5e1"
          />
          <Radar
            dataKey="score"
            stroke="#4f46e5"
            fill="#6366f1"
            fillOpacity={0.35}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
