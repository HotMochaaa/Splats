globalThis.window = globalThis;
globalThis.self = globalThis;
globalThis.document = globalThis.document || { createElement: () => ({}), createElementNS: () => ({}) };

import * as GS from '@mkkellogg/gaussian-splats-3d';
import fs from 'fs';

const [inPath, outPath, compArg, shArg, minAlphaArg] = process.argv.slice(2);
if (!inPath || !outPath) {
  console.error('usage: node convert-ksplat.mjs <in.ply> <out.ksplat> [comp 0|1|2] [shDeg] [minAlpha]');
  process.exit(1);
}
const compressionLevel = compArg !== undefined ? parseInt(compArg, 10) : 1;
const shDegree = shArg !== undefined ? parseInt(shArg, 10) : 1;
const minimumAlpha = minAlphaArg !== undefined ? parseInt(minAlphaArg, 10) : 15;
const optimize = true;
const fileBuf = fs.readFileSync(inPath);
const ab = fileBuf.buffer.slice(fileBuf.byteOffset, fileBuf.byteOffset + fileBuf.byteLength);
const splatBuffer = await GS.PlyLoader.loadFromFileData(
  ab, minimumAlpha, compressionLevel, optimize, shDegree,
);

const out = splatBuffer.bufferData ? splatBuffer.bufferData : splatBuffer.getBufferData?.();
if (!out) { console.error('could not get ksplat buffer from SplatBuffer'); process.exit(2); }
fs.writeFileSync(outPath, Buffer.from(out));
const outSize = fs.statSync(outPath).size;
console.log(`[convert] wrote ${outPath} (${(outSize / 1e6).toFixed(1)} MB), `
  + `splats=${splatBuffer.getSplatCount ? splatBuffer.getSplatCount() : '?'}`);
