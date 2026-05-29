import type { ParseResult } from '../types';

export async function parseInstruction(
  instruction: string,
  apiKey: string,
): Promise<ParseResult> {
  const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/parse_instruction`, {
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
    // #region agent log
    fetch('http://localhost:7492/ingest/018f9570-af31-4316-8237-a31d49daba47', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '7be968' },
      body: JSON.stringify({
        sessionId: '7be968',
        hypothesisId: 'H1',
        location: 'parse.ts:parseInstruction',
        message: 'parse_http_error',
        data: { status: res.status, msg: msg.slice(0, 400), keyLen: apiKey.length },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
    throw new Error(`HTTP ${res.status}：${msg}`);
  }
  return (await res.json()) as ParseResult;
}
