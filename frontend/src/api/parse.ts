import type { ParseResult } from '../types';
import { apiBaseUrl } from '../lib/apiBase';

export async function parseInstruction(instruction: string): Promise<ParseResult> {
  const apiBase = apiBaseUrl();
  // #region agent log
  fetch('http://127.0.0.1:7492/ingest/018f9570-af31-4316-8237-a31d49daba47', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': 'bdd1ec' },
    body: JSON.stringify({
      sessionId: 'bdd1ec',
      hypothesisId: 'H5',
      location: 'parse.ts:parseInstruction',
      message: 'parse_request',
      data: {
        apiBase: apiBase || '(relative)',
        usesServerKey: true,
      },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion
  const res = await fetch(`${apiBase}/api/parse_instruction`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction, api_key: '' }),
  });
  // #region agent log
  fetch('http://127.0.0.1:7456/ingest/a0e45155-c3fd-453e-878d-00c592c80c43', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '69f08c' },
    body: JSON.stringify({
      sessionId: '69f08c',
      hypothesisId: 'H2',
      location: 'parse.ts:afterFetch',
      message: 'parse_response_meta',
      data: {
        ok: res.ok,
        status: res.status,
        contentType: res.headers.get('content-type'),
        apiBase: apiBase ?? null,
        apiBaseMissing: apiBase == null || apiBase === '',
      },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion
  if (!res.ok) {
    const bodyText = await res.text();
    let detail: unknown = bodyText;
    try {
      detail = bodyText ? JSON.parse(bodyText) : null;
    } catch {
      /* 非 JSON 响应，保留 bodyText */
    }
    // #region agent log
    fetch('http://127.0.0.1:7456/ingest/a0e45155-c3fd-453e-878d-00c592c80c43', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '69f08c' },
      body: JSON.stringify({
        sessionId: '69f08c',
        hypothesisId: 'H1',
        location: 'parse.ts:errorBodyRead',
        message: 'error_body_read_once',
        data: {
          status: res.status,
          bodyLen: bodyText.length,
          detailType: typeof detail,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
    const msg =
      typeof detail === 'object' && detail !== null
        ? JSON.stringify(detail)
        : String(detail);
    // #region agent log
    fetch('http://127.0.0.1:7456/ingest/a0e45155-c3fd-453e-878d-00c592c80c43', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '69f08c' },
      body: JSON.stringify({
        sessionId: '69f08c',
        hypothesisId: 'H3',
        location: 'parse.ts:parseInstruction',
        message: 'parse_http_error',
        data: { status: res.status, msg: msg.slice(0, 400) },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
    throw new Error(`HTTP ${res.status}：${msg}`);
  }
  return (await res.json()) as ParseResult;
}
