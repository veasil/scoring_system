import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// admin-web：生产托管在 /admin/，开发态 proxy 到后端 8080
export default defineConfig({
  plugins: [vue()],
  base: '/admin/',
  server: {
    port: 5174,
    proxy: {
      '/api': { target: 'http://localhost:8080', changeOrigin: true }
    }
  },
  build: { outDir: 'dist' }
})
