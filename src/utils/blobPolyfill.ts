/**
 * Pre-process GLB buffers to convert embedded textures to data URIs.
 *
 * React Native's BlobManager rejects ArrayBuffer in the Blob constructor,
 * but Three.js GLTFLoader uses `new Blob([bufferView])` to load embedded
 * textures. Instead of patching Blob globally (which breaks fetch),
 * we modify the GLB's JSON chunk to replace bufferView-based image
 * references with inline base64 data URIs before GLTFLoader parses it.
 */

/**
 * Convert a Uint8Array to a base64 string.
 */
function uint8ToBase64(data: Uint8Array): string {
  let binary = "";
  const chunkSize = 8192;
  for (let i = 0; i < data.length; i += chunkSize) {
    const end = Math.min(i + chunkSize, data.length);
    const chunk = data.subarray(i, end);
    for (let j = 0; j < chunk.length; j++) {
      binary += String.fromCharCode(chunk[j]);
    }
  }
  return btoa(binary);
}

interface GLTFImage {
  bufferView?: number;
  mimeType?: string;
  uri?: string;
  name?: string;
}

interface GLTFBufferView {
  buffer: number;
  byteOffset?: number;
  byteLength: number;
  byteStride?: number;
  target?: number;
}

interface GLTFJson {
  images?: GLTFImage[];
  bufferViews?: GLTFBufferView[];
  [key: string]: unknown;
}

/**
 * Pre-process a GLB ArrayBuffer: convert embedded images from bufferView
 * references to inline base64 data URIs. Returns a new GLB ArrayBuffer
 * that GLTFLoader can parse without needing Blob support.
 */
export function preprocessGLB(glbBuffer: ArrayBuffer): ArrayBuffer {
  const view = new DataView(glbBuffer);

  // Validate GLB header
  const magic = view.getUint32(0, true);
  if (magic !== 0x46546C67) {
    // Not a GLB file, return as-is
    return glbBuffer;
  }

  const version = view.getUint32(4, true);
  if (version !== 2) {
    return glbBuffer;
  }

  // Parse chunks
  let offset = 12; // after header

  // Chunk 0: JSON
  const jsonChunkLength = view.getUint32(offset, true);
  const jsonChunkType = view.getUint32(offset + 4, true);
  if (jsonChunkType !== 0x4E4F534A) {
    // Not JSON chunk
    return glbBuffer;
  }
  const jsonBytes = new Uint8Array(glbBuffer, offset + 8, jsonChunkLength);
  const jsonStr = new TextDecoder().decode(jsonBytes);
  const json: GLTFJson = JSON.parse(jsonStr);

  offset += 8 + jsonChunkLength;

  // Chunk 1: BIN (optional)
  let binChunk: Uint8Array | null = null;
  if (offset < glbBuffer.byteLength) {
    const binChunkLength = view.getUint32(offset, true);
    const binChunkType = view.getUint32(offset + 4, true);
    if (binChunkType === 0x004E4942) {
      binChunk = new Uint8Array(glbBuffer, offset + 8, binChunkLength);
    }
  }

  if (!json.images || !json.bufferViews || !binChunk) {
    // No embedded images to process
    return glbBuffer;
  }

  // Convert each embedded image to a data URI
  let modified = false;
  for (const image of json.images) {
    if (image.bufferView !== undefined && image.mimeType) {
      const bv = json.bufferViews[image.bufferView];
      const start = bv.byteOffset || 0;
      const imageData = binChunk.subarray(start, start + bv.byteLength);
      const base64 = uint8ToBase64(imageData);
      image.uri = `data:${image.mimeType};base64,${base64}`;
      delete image.bufferView;
      modified = true;
    }
  }

  if (!modified) {
    return glbBuffer;
  }

  // Reassemble GLB with modified JSON
  const newJsonStr = JSON.stringify(json);
  const newJsonBytes = new TextEncoder().encode(newJsonStr);
  // JSON chunk must be padded to 4-byte alignment with spaces (0x20)
  const jsonPadding = (4 - (newJsonBytes.length % 4)) % 4;
  const newJsonChunkLength = newJsonBytes.length + jsonPadding;

  // BIN chunk stays the same
  const binChunkLength = binChunk.length;
  const binPadding = (4 - (binChunkLength % 4)) % 4;
  const newBinChunkLength = binChunkLength + binPadding;

  const totalLength = 12 + 8 + newJsonChunkLength + 8 + newBinChunkLength;
  const result = new ArrayBuffer(totalLength);
  const resultView = new DataView(result);
  const resultBytes = new Uint8Array(result);

  // GLB header
  resultView.setUint32(0, 0x46546C67, true); // magic
  resultView.setUint32(4, 2, true); // version
  resultView.setUint32(8, totalLength, true); // length

  // JSON chunk
  let pos = 12;
  resultView.setUint32(pos, newJsonChunkLength, true);
  resultView.setUint32(pos + 4, 0x4E4F534A, true);
  resultBytes.set(newJsonBytes, pos + 8);
  // Pad with spaces
  for (let i = 0; i < jsonPadding; i++) {
    resultBytes[pos + 8 + newJsonBytes.length + i] = 0x20;
  }

  // BIN chunk
  pos = 12 + 8 + newJsonChunkLength;
  resultView.setUint32(pos, newBinChunkLength, true);
  resultView.setUint32(pos + 4, 0x004E4942, true);
  resultBytes.set(binChunk, pos + 8);
  // Pad with zeros
  for (let i = 0; i < binPadding; i++) {
    resultBytes[pos + 8 + binChunkLength + i] = 0;
  }

  console.log(
    `[blobPolyfill] Converted ${json.images.filter((img) => img.uri?.startsWith("data:")).length} embedded images to data URIs`
  );

  return result;
}
