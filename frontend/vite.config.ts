import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Vite owns the web frontend. Cargo/Tauri owns src-tauri and its target tree.
// Ignoring the native tree avoids Windows EBUSY watcher failures while Rust is
// compiling build-script executables under src-tauri/target.
export default defineConfig({
  plugins: [react()],
  server: {
    strictPort: true,
    watch: {
      ignored: ['**/src-tauri/**'],
    },
  },
})
