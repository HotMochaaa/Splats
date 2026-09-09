// Convert a Gaussian-splat .ply to mkkellogg's compressed .ksplat for fast web
// loading.  Usage: node convert-ksplat.mjs <in.ply> <out.ksplat> [compression 0|1|2] [shDeg]
// mkkellogg touches a few browser globals during parsing; stub them for Node.
globalThis.window = globalThis;
globalThis.self = globalThis;
globalThis.document = globalThis.document || { createElement: () => ({}), createElementNS: () => ({}) };

import * as GS from '@mkkellogg/gaussian-splats-3d';
import fs from 'fs';

const [inPath, outPath, compArg, shArg] = process.argv.slice(2);
if (!inPath || !outPath) {
  console.error('usage: node convert-ksplat.mjs <in.ply> <out.ksplat> [comp 0|1|2] [shDeg]');
  process.exit(1);
}
const compressionLevel = compArg !== undefined ? parseInt(compArg, 10) : 1;
const shDegree = shArg !== undefined ? parseInt(shArg, 10) : 0;

const buf = fs.readFileSync(inPath);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);

console.log(`[convert] ${inPath} (${(buf.length / 1e6).toFixed(1)} MB) -> ksplat`
  + ` comp=${compressionLevel} sh=${shDegree}`);

const minimumAlpha = 5;
const optimize = true;
const splatBuffer = await GS.PlyLoader.loadFromFileData(
  ab, minimumAlpha, compressionLevel, optimize, shDegree,
);

const out = splatBuffer.bufferData ? splatBuffer.bufferData : splatBuffer.getBufferData?.();
if (!out) { console.error('could not get ksplat buffer from SplatBuffer'); process.exit(2); }
fs.writeFileSync(outPath, Buffer.from(out));
const outSize = fs.statSync(outPath).size;
console.log(`[convert] wrote ${outPath} (${(outSize / 1e6).toFixed(1)} MB), `
  + `splats=${splatBuffer.getSplatCount ? splatBuffer.getSplatCount() : '?'}`);
