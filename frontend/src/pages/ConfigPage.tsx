import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PresetCard from '../components/PresetCard';
import { parseInstruction } from '../api/parse';
import { PRESETS } from '../data/presets';
import { useAppStore } from '../store/useAppStore';

const REQUIRED_FIELDS: Array<{ key: string; pattern: RegExp }> = [
  { key: 'Role', pattern: /(^|\n)\s*#+\s*Role\b/i },
  { key: 'Task', pattern: /(^|\n)\s*#+\s*Task\b/i },
  { key: 'Opening Line', pattern: /(^|\n)\s*#+\s*Opening\s*Line\b/i },
  { key: 'Constraints', pattern: /(^|\n)\s*#+\s*Constraints\b/i },
];

const KEY_PATTERN = /^sk-[A-Za-z0-9]{20,}$/;
const FIXED_MODEL = 'deepseek-chat';

export default function ConfigPage() {
  const navigate = useNavigate();
  const {
    instruction,
    agentKey,
    evaluatorKey,
    setInstruction,
    setAgentKey,
    setEvaluatorKey,
    setParseResult,
  } = useAppStore();

  const [showSchema, setShowSchema] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const missingFields = useMemo(
    () => REQUIRED_FIELDS.filter((f) => !f.pattern.test(instruction)).map((f) => f.key),
    [instruction],
  );

  const agentKeyValid = KEY_PATTERN.test(agentKey);
  const evaluatorKeyValid = KEY_PATTERN.test(evaluatorKey);
  const canSubmit =
    missingFields.length === 0 &&
    agentKeyValid &&
    evaluatorKeyValid &&
    instruction.trim().length > 0 &&
    !loading;

  const handleParse = async () => {
    if (!canSubmit) return;
    setError(null);
    setLoading(true);
    try {
      const result = await parseInstruction(instruction);
      setParseResult(result);
      navigate('/branches');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-800">ConvoMatrix·复杂指令下的多轮对话评测系统</h1>
        <p className="text-sm text-slate-500 mt-1">
          配置任务指令与模型 Key，启动评测
        </p>
      </header>

      <section>
        <div className="text-sm font-medium text-slate-700 mb-2">预置指令</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {PRESETS.map((p) => (
            <PresetCard key={p.id} preset={p} onClick={() => setInstruction(p.content)} />
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-slate-700">任务指令</label>
          <button
            type="button"
            onClick={() => setShowSchema((s) => !s)}
            className="text-xs text-indigo-600 hover:underline"
          >
            {showSchema ? '收起' : '展开'} 结构规范
          </button>
        </div>
        {showSchema && (
          <div className="text-xs text-slate-600 bg-slate-100 border border-slate-200 rounded-lg p-3 mb-2 space-y-2">
            <div>
              <span className="font-semibold text-red-600">必需字段：</span>
              <code className="ml-1">#Role / #Task / #Opening Line / #Constraints</code>
            </div>
            <div>
              <span className="font-semibold text-slate-600">可选字段：</span>
              <code className="ml-1">
                #Call Flow / #Knowledge Points / 其他自定义字段（LLM 自动归类）
              </code>
            </div>
          </div>
        )}
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          rows={14}
          placeholder="自由输入符合结构规范的任务指令，或点击上方预置卡片快速填入。"
          className={`w-full font-mono text-sm rounded-lg border p-3 focus:outline-none focus:ring-1 ${
            instruction.length > 0 && missingFields.length > 0
              ? 'border-red-400 focus:border-red-500 focus:ring-red-500'
              : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500'
          }`}
        />
        {instruction.length > 0 && missingFields.length > 0 && (
          <div className="text-xs text-red-600 mt-1">
            缺失必需字段：{missingFields.map((f) => `#${f}`).join('、')}
          </div>
        )}
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ModelKeyBox
          label="被测模型（数字人）"
          keyValue={agentKey}
          keyValid={agentKeyValid}
          onKeyChange={setAgentKey}
        />
        <ModelKeyBox
          label="评测 & 模拟器模型"
          keyValue={evaluatorKey}
          keyValid={evaluatorKeyValid}
          onKeyChange={setEvaluatorKey}
        />
      </section>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm p-3 whitespace-pre-wrap">
          {error}
        </div>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleParse}
          disabled={!canSubmit}
          className="px-5 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition"
        >
          {loading ? '解析中…' : '解析指令 →'}
        </button>
      </div>
    </div>
  );
}

function ModelKeyBox(props: {
  label: string;
  keyValue: string;
  keyValid: boolean;
  onKeyChange: (v: string) => void;
}) {
  const hasInput = props.keyValue.length > 0;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
      <div className="font-medium text-slate-700">{props.label}</div>
      <div>
        <div className="text-xs text-slate-500 mb-1">模型选择</div>
        <div className="rounded-md bg-slate-100 border border-slate-200 px-3 py-2 text-sm text-slate-600">
          {FIXED_MODEL}
        </div>
      </div>
      <div>
        <div className="text-xs text-slate-500 mb-1">API Key</div>
        <input
          type="password"
          value={props.keyValue}
          readOnly
          disabled
          placeholder="sk-xxxxxxxxxxxxxxxx"
          className={`w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 ${
            hasInput && !props.keyValid
              ? 'border-red-400 focus:ring-red-500'
              : 'border-slate-300 focus:ring-indigo-500 focus:border-indigo-500'
          }`}
        />
        {hasInput && !props.keyValid && (
          <div className="text-xs text-red-600 mt-1">Key 格式应形如 sk-xxxx……</div>
        )}
      </div>
    </div>
  );
}
