/**
 * Polyfill: Allow creating Blob from ArrayBuffer in React Native.
 *
 * React Native's BlobManager explicitly rejects ArrayBuffer/ArrayBufferView
 * in the Blob constructor. Three.js's GLTFLoader needs this to load embedded
 * textures from GLB files. This polyfill intercepts those calls and stores
 * the raw data, then URL.createObjectURL converts it to a base64 data URI
 * that React Native's image pipeline can handle.
 *
 * Import this file BEFORE any Three.js imports:
 *   import "./utils/blobPolyfill";
 */

const OrigBlob = globalThis.Blob;

// Store for ArrayBuffer-based fake blobs
const fakeBlobStore = new Map<
  string,
  { data: Uint8Array; type: string }
>();
let fakeBlobId = 0;

// Wrapper that handles ArrayBuffer (which RN rejects)
function PatchedBlob(
  this: Record<string, unknown>,
  parts?: BlobPart[],
  options?: BlobPropertyBag
) {
  if (!parts) {
    return new OrigBlob(parts, options);
  }

  const hasArrayBuffer = parts.some(
    (p) => p instanceof ArrayBuffer || ArrayBuffer.isView(p)
  );

  if (!hasArrayBuffer) {
    return new OrigBlob(parts, options);
  }

  // Combine all ArrayBuffer parts into a single Uint8Array
  let totalLen = 0;
  for (const p of parts) {
    if (p instanceof ArrayBuffer) totalLen += p.byteLength;
    else if (ArrayBuffer.isView(p)) totalLen += p.byteLength;
  }

  const combined = new Uint8Array(totalLen);
  let offset = 0;
  for (const p of parts) {
    if (p instanceof ArrayBuffer) {
      combined.set(new Uint8Array(p), offset);
      offset += p.byteLength;
    } else if (ArrayBuffer.isView(p)) {
      combined.set(
        new Uint8Array(p.buffer, p.byteOffset, p.byteLength),
        offset
      );
      offset += p.byteLength;
    }
  }

  // Store data and return a fake blob object
  const id = `__fake_blob_${fakeBlobId++}`;
  fakeBlobStore.set(id, {
    data: combined,
    type: options?.type || "application/octet-stream",
  });

  this.__fakeBlobId = id;
  return this;
}

// Preserve prototype chain
PatchedBlob.prototype = OrigBlob.prototype;
(globalThis as Record<string, unknown>).Blob = PatchedBlob;

// Patch URL.createObjectURL to handle our fake blobs
const origCreateObjectURL = URL.createObjectURL;
URL.createObjectURL = function (obj: unknown): string {
  const blobObj = obj as Record<string, unknown>;
  if (blobObj && typeof blobObj.__fakeBlobId === "string") {
    const entry = fakeBlobStore.get(blobObj.__fakeBlobId);
    if (entry) {
      fakeBlobStore.delete(blobObj.__fakeBlobId);

      // Convert to base64 data URI
      const { data, type } = entry;
      let binary = "";
      // Process in chunks to avoid call stack overflow for large textures
      const chunkSize = 8192;
      for (let i = 0; i < data.length; i += chunkSize) {
        const chunk = data.subarray(i, Math.min(i + chunkSize, data.length));
        for (let j = 0; j < chunk.length; j++) {
          binary += String.fromCharCode(chunk[j]);
        }
      }
      const base64 = btoa(binary);
      return `data:${type};base64,${base64}`;
    }
  }

  return origCreateObjectURL.call(URL, obj as Blob);
};

// Patch URL.revokeObjectURL to be a no-op for data URIs
const origRevokeObjectURL = URL.revokeObjectURL;
URL.revokeObjectURL = function (url: string): void {
  if (url && url.startsWith("data:")) {
    return; // No-op for data URIs
  }
  return origRevokeObjectURL.call(URL, url);
};
