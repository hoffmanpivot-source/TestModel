const fs = require('fs');
const buf = fs.readFileSync('assets/models/makehuman_base.glb');
let offset = 12;
let jsonChunk, binChunk;
while (offset < buf.length) {
  const chunkLen = buf.readUInt32LE(offset);
  const chunkType = buf.readUInt32LE(offset + 4);
  const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
  if (chunkType === 0x4E4F534A) jsonChunk = JSON.parse(chunkData.toString());
  else if (chunkType === 0x004E4942) binChunk = chunkData;
  offset += 8 + chunkLen;
}
const accessors = jsonChunk.accessors;
const bufferViews = jsonChunk.bufferViews;
let converted = 0;
for (let i = 0; i < accessors.length; i++) {
  const acc = accessors[i];
  if (!acc.sparse) continue;
  const count = acc.count;
  const type = acc.type;
  const elemSize = type === 'VEC3' ? 3 : type === 'VEC2' ? 2 : type === 'SCALAR' ? 1 : 4;
  const bytesPerElem = elemSize * 4;
  const dense = Buffer.alloc(count * bytesPerElem, 0);
  if (acc.bufferView !== undefined) {
    const bv = bufferViews[acc.bufferView];
    const srcOff = (bv.byteOffset || 0) + (acc.byteOffset || 0);
    binChunk.copy(dense, 0, srcOff, srcOff + count * bytesPerElem);
  }
  const sparse = acc.sparse;
  const idxBv = bufferViews[sparse.indices.bufferView];
  const valBv = bufferViews[sparse.values.bufferView];
  const idxOff = (idxBv.byteOffset || 0) + (sparse.indices.byteOffset || 0);
  const valOff = (valBv.byteOffset || 0) + (sparse.values.byteOffset || 0);
  const idxCompType = sparse.indices.componentType;
  for (let j = 0; j < sparse.count; j++) {
    let idx;
    if (idxCompType === 5123) idx = binChunk.readUInt16LE(idxOff + j * 2);
    else if (idxCompType === 5125) idx = binChunk.readUInt32LE(idxOff + j * 4);
    else idx = binChunk.readUInt8(idxOff + j);
    for (let k = 0; k < elemSize; k++) {
      const val = binChunk.readFloatLE(valOff + j * bytesPerElem + k * 4);
      dense.writeFloatLE(val, idx * bytesPerElem + k * 4);
    }
  }
  const newBvIndex = bufferViews.length;
  bufferViews.push({ buffer: 0, byteOffset: binChunk.length, byteLength: dense.length });
  binChunk = Buffer.concat([binChunk, dense]);
  acc.bufferView = newBvIndex;
  acc.byteOffset = 0;
  delete acc.sparse;
  converted++;
}
jsonChunk.buffers[0].byteLength = binChunk.length;
const jsonStr = JSON.stringify(jsonChunk);
const jsonBuf = Buffer.from(jsonStr);
const jsonPad = (4 - (jsonBuf.length % 4)) % 4;
const paddedJson = Buffer.concat([jsonBuf, Buffer.alloc(jsonPad, 0x20)]);
const binPad = (4 - (binChunk.length % 4)) % 4;
const paddedBin = Buffer.concat([binChunk, Buffer.alloc(binPad, 0)]);
const totalLen = 12 + 8 + paddedJson.length + 8 + paddedBin.length;
const out = Buffer.alloc(totalLen);
out.writeUInt32LE(0x46546C67, 0);
out.writeUInt32LE(2, 4);
out.writeUInt32LE(totalLen, 8);
out.writeUInt32LE(paddedJson.length, 12);
out.writeUInt32LE(0x4E4F534A, 16);
paddedJson.copy(out, 20);
let o = 20 + paddedJson.length;
out.writeUInt32LE(paddedBin.length, o);
out.writeUInt32LE(0x004E4942, o + 4);
paddedBin.copy(out, o + 8);
fs.writeFileSync('assets/models/makehuman_base_dense.glb', out);
console.log('Converted ' + converted + ' sparse -> dense, size: ' + (out.length / (1024*1024)).toFixed(1) + ' MB');
