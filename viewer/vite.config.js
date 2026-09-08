import { defineConfig } from 'vite';

// mkkellogg/gaussian-splats-3d sorts splats in a Web Worker that uses
// SharedArrayBuffer on its default (fastest, best-tested) path. Browsers only
// expose SharedArrayBuffer when the document is cross-origin isolated, which
// requires these two response headers. Our assets are all same-origin, so
// COEP: require-corp is safe here.
const crossOriginIsolation = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
};

export default defineConfig({
  server: { headers: crossOriginIsolation },
  preview: { headers: crossOriginIsolation },
});
