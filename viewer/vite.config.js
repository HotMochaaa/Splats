import { defineConfig } from 'vite';

const crossOriginIsolation = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
};

export default defineConfig({
  server: {
    headers: crossOriginIsolation,
    watch: {
      ignored: ['**/*.ksplat', '**/*.ply', '**/*.db', '**/sparse/**']
    }
  },
  preview: { headers: crossOriginIsolation },
});
