import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: [
      { find: '@', replacement: fileURLToPath(new URL('./src', import.meta.url)) },
      {
        find: /^@xmov\/avatar\/agent$/,
        replacement: fileURLToPath(
          new URL('./node_modules/@xmov/avatar/dist/agent/index.cjs', import.meta.url),
        ),
      },
      {
        find: /^@xmov\/avatar$/,
        replacement: fileURLToPath(
          new URL('./node_modules/@xmov/avatar/dist/index.cjs', import.meta.url),
        ),
      },
    ],
  },
  optimizeDeps: {
    include: ['@xmov/avatar', '@xmov/avatar/agent'],
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
