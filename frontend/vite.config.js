import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// En desarrollo Vite reenvia /api al backend, asi el navegador ve un solo origen.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const api = env.VITE_API_DESTINO || 'http://localhost:8000'
  return {
    plugins: [react()],
    server: {
      port: Number(env.VITE_PUERTO || 3000),
      proxy: { '/api': { target: api, changeOrigin: true } },
    },
  }
})
