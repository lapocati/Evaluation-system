/**
 * 开发模式直连 8010（已配置 CORS）。
 * 不用 Vite 代理：frontend/.env 曾把 VITE_API_BASE_URL 指到 :8000，代理会打到陈旧后端并出现 Bearer  502。
 */
export function apiBaseUrl(): string {
  if (import.meta.env.DEV) {
    return 'http://127.0.0.1:8010';
  }
  return import.meta.env.VITE_API_BASE_URL ?? '';
}
