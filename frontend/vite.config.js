import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,       // listen on 0.0.0.0 so phone/tablet can connect
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5000'
    }
  }
})
