import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.HARNESS_API_URL || 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
    watch: process.env.HARNESS_POLL === '1' ? { usePolling: true } : undefined,
  },
});
