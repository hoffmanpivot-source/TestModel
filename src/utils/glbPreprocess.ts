/**
 * Strip embedded textures from GLB files for React Native compatibility.
 *
 * React Native's BlobManager rejects ArrayBuffer in the Blob constructor,
 * causing THREE.GLTFLoader errors when loading embedded textures.
 * This preprocessor removes embedded image references from the GLB JSON
 * so GLTFLoader never attempts to create Blobs. Materials retain their
 * base colors; only texture maps are removed.
 */

interface GLTFImage {
  bufferView?: number;
  mimeType?: string;
  uri?: string;
  name?: string;
}

interface GLTFTexture {
  source?: number;
  sampler?: number;
  name?: string;
}

interface GLTFMaterialTexInfo {
  index?: number;
  texCoord?: number;
}

interface GLTFMaterial {
  pbrMetallicRoughness?: {
    baseColorTexture?: GLTFMaterialTexInfo;
    metallicRoughnessTexture?: GLTFMaterialTexInfo;
    [key: string]: unknown;
  };
  normalTexture?: GLTFMaterialTexInfo;
  occlusionTexture?: GLTFMaterialTexInfo;
  emissiveTexture?: GLTFMaterialTexInfo;
  [key: string]: unknown;
}

interface GLTFJson {
  images?: GLTFImage[];
  textures?: GLTFTexture[];
  materials?: GLTFMaterial[];
  bufferViews?: unknown[];
  [key: string]: unknown;
}

/**
 * Strip embedded images from a GLB ArrayBuffer.
 * Returns a new GLB with the image/texture references removed.
 * Materials keep base colors but lose texture maps.
 */
export function stripEmbeddedTextures(glbBuffer: ArrayBuffer): ArrayBuffer {
  const view = new DataView(glbBuffer);

  // Validate GLB header
  const magic = view.getUint32(0, true);
  if (magic !== 0x46546C67) return glbBuffer;
  if (view.getUint32(4, true) !== 2) return glbBuffer;

  // Parse JSON chunk
  let offset = 12;
  const jsonChunkLength = view.getUint32(offset, true);
  const jsonChunkType = view.getUint32(offset + 4, true);
  if (jsonChunkType !== 0x4E4F534A) return glbBuffer;

  const jsonBytes = new Uint8Array(glbBuffer, offset + 8, jsonChunkLength);
  const json: GLTFJson = JSON.parse(new TextDecoder().decode(jsonBytes));
  offset += 8 + jsonChunkLength;

  // Find BIN chunk
  let binChunk: Uint8Array | null = null;
  let binChunkOrigLength = 0;
  if (offset < glbBuffer.byteLength) {
    binChunkOrigLength = view.getUint32(offset, true);
    if (view.getUint32(offset + 4, true) === 0x004E4942) {
      binChunk = new Uint8Array(glbBuffer, offset + 8, binChunkOrigLength);
    }
  }

  if (!json.images || json.images.length === 0) return glbBuffer;

  // Find which images are embedded (have bufferView, not uri)
  const embeddedImageIndices = new Set<number>();
  json.images.forEach((img, i) => {
    if (img.bufferView !== undefined && !img.uri) {
      embeddedImageIndices.add(i);
    }
  });

  if (embeddedImageIndices.size === 0) return glbBuffer;

  // Find which textures reference embedded images
  const embeddedTextureIndices = new Set<number>();
  if (json.textures) {
    json.textures.forEach((tex, i) => {
      if (tex.source !== undefined && embeddedImageIndices.has(tex.source)) {
        embeddedTextureIndices.add(i);
      }
    });
  }

  // Remove texture references from materials
  if (json.materials) {
    for (const mat of json.materials) {
      if (mat.pbrMetallicRoughness?.baseColorTexture?.index !== undefined &&
          embeddedTextureIndices.has(mat.pbrMetallicRoughness.baseColorTexture.index)) {
        delete mat.pbrMetallicRoughness.baseColorTexture;
      }
      if (mat.pbrMetallicRoughness?.metallicRoughnessTexture?.index !== undefined &&
          embeddedTextureIndices.has(mat.pbrMetallicRoughness.metallicRoughnessTexture.index)) {
        delete mat.pbrMetallicRoughness.metallicRoughnessTexture;
      }
      if (mat.normalTexture?.index !== undefined &&
          embeddedTextureIndices.has(mat.normalTexture.index)) {
        delete mat.normalTexture;
      }
      if (mat.occlusionTexture?.index !== undefined &&
          embeddedTextureIndices.has(mat.occlusionTexture.index)) {
        delete mat.occlusionTexture;
      }
      if (mat.emissiveTexture?.index !== undefined &&
          embeddedTextureIndices.has(mat.emissiveTexture.index)) {
        delete mat.emissiveTexture;
      }
    }
  }

  // Remove embedded images (replace with empty placeholders to preserve indices)
  for (const i of embeddedImageIndices) {
    json.images![i] = { name: `stripped_${i}` };
  }

  console.log(
    `[glbPreprocess] Stripped ${embeddedImageIndices.size} embedded textures`
  );

  // Reassemble GLB with modified (smaller) JSON
  const newJsonStr = JSON.stringify(json);
  const newJsonBytes = new TextEncoder().encode(newJsonStr);
  const jsonPadding = (4 - (newJsonBytes.length % 4)) % 4;
  const newJsonChunkLength = newJsonBytes.length + jsonPadding;

  if (!binChunk) {
    // No BIN chunk — just write header + JSON
    const totalLength = 12 + 8 + newJsonChunkLength;
    const result = new ArrayBuffer(totalLength);
    const rv = new DataView(result);
    const rb = new Uint8Array(result);
    rv.setUint32(0, 0x46546C67, true);
    rv.setUint32(4, 2, true);
    rv.setUint32(8, totalLength, true);
    rv.setUint32(12, newJsonChunkLength, true);
    rv.setUint32(16, 0x4E4F534A, true);
    rb.set(newJsonBytes, 20);
    for (let i = 0; i < jsonPadding; i++) rb[20 + newJsonBytes.length + i] = 0x20;
    return result;
  }

  // With BIN chunk
  const binPadding = (4 - (binChunk.length % 4)) % 4;
  const newBinChunkLength = binChunk.length + binPadding;
  const totalLength = 12 + 8 + newJsonChunkLength + 8 + newBinChunkLength;

  const result = new ArrayBuffer(totalLength);
  const rv = new DataView(result);
  const rb = new Uint8Array(result);

  // Header
  rv.setUint32(0, 0x46546C67, true);
  rv.setUint32(4, 2, true);
  rv.setUint32(8, totalLength, true);

  // JSON chunk
  let pos = 12;
  rv.setUint32(pos, newJsonChunkLength, true);
  rv.setUint32(pos + 4, 0x4E4F534A, true);
  rb.set(newJsonBytes, pos + 8);
  for (let i = 0; i < jsonPadding; i++) rb[pos + 8 + newJsonBytes.length + i] = 0x20;

  // BIN chunk (unchanged)
  pos = 12 + 8 + newJsonChunkLength;
  rv.setUint32(pos, newBinChunkLength, true);
  rv.setUint32(pos + 4, 0x004E4942, true);
  rb.set(binChunk, pos + 8);
  for (let i = 0; i < binPadding; i++) rb[pos + 8 + binChunk.length + i] = 0;

  return result;
}
