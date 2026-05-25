import type { ParseResult } from '../types';

export async function parseInstruction(
  instruction: string,
  apiKey: string,
): Promise<ParseResult> {
  const res = await fetch('/api/parse_instruction', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction, api_key: apiKey }),
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    const msg =
      typeof detail === 'object' && detail !== null
        ? JSON.stringify(detail)
        : String(detail);
    throw new Error(`HTTP ${res.status}：${msg}`);
  }
  return (await res.json()) as ParseResult;
}
