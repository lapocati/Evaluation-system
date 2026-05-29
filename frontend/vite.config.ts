import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // 开发代理固定 8010；仅允许 VITE_API_PROXY_TARGET 显式覆盖（禁止误用 VITE_API_BASE_URL=:8000）
  const proxyOverride = env.VITE_API_PROXY_TARGET?.trim();
  const apiTarget =
    mode === 'development' && !proxyOverride
      ? 'http://127.0.0.1:8010'
      : proxyOverride || 'http://127.0.0.1:8010';

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': apiTarget,
      },
    },
  };
});
