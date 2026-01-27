import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5001,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        // Handle WebSocket proxy errors gracefully
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            // Silently handle ECONNABORTED and ECONNRESET errors
            // These occur when WebSocket connections are closed abruptly
            if (err.code === 'ECONNABORTED' || err.code === 'ECONNRESET' || err.code === 'EPIPE') {
              return;
            }
            console.error('[WS Proxy Error]', err.message);
          });
        },
      },
      '/npl-time': {
        target: 'https://www.nplindia.in',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/npl-time/, '/cgi-bin/ntp_client'),
        secure: true,
      }
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './vitest.setup.js',
    css: true,
  }
})
