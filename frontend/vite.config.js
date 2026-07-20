// 文件名: frontend/vite.config.js
// 功能: Vite 构建配置 + 开发代理 + 路径别名
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/chat': 'http://localhost:8765',
      '/rag': 'http://localhost:8765',
      '/tools': 'http://localhost:8765',
      '/files': 'http://localhost:8765',
      '/download': 'http://localhost:8765',
      '/health': 'http://localhost:8765',
      '/conversations': 'http://localhost:8765',
    }
  }
})