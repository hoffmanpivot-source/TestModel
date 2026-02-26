/**
 * Polyfill Blob and URL.createObjectURL for React Native.
 *
 * React Native's BlobManager rejects ArrayBuffer in the Blob constructor,
 * but Three.js GLTFLoader uses `new Blob([bufferView])` to load embedded
 * textures from GLB files.
 *
 * This module patches the global Blob constructor (via Proxy) to intercept
 * ArrayBuffer-based blobs and store the raw data. URL.createObjectURL is
 * also patched to convert these fake blobs into base64 data URIs.
 *
 * Import BEFORE any Three.js imports:
 *   import "./utils/blobPolyfill";
 */

/**
 * Convert a Uint8Array to a base64 data URI string.
 */
function arrayBufferToDataURI(data: Uint8Array, mimeType: string): string {
  let binary = "";
  const chunkSize = 8192;
  for (let i = 0; i < data.length; i += chunkSize) {
    const end = Math.min(i + chunkSize, data.length);
    const chunk = data.subarray(i, end);
    for (let j = 0; j < chunk.length; j++) {
      binary += String.fromCharCode(chunk[j]);
    }
  }
  return `data:${mimeType};base64,${btoa(binary)}`;
}

const OriginalBlob = globalThis.Blob;

const BlobHandler: ProxyHandler<typeof Blob> = {
  construct(_target, args: [BlobPart[]?, BlobPropertyBag?]) {
    const [parts, options] = args;

    if (!parts) {
      return new OriginalBlob(undefined, options);
    }

    const hasArrayBuffer = parts.some(
      (p) => p instanceof ArrayBuffer || ArrayBuffer.isView(p)
    );

    if (!hasArrayBuffer) {
      return new OriginalBlob(parts, options);
    }

    // ArrayBuffer detected — create a fake blob with stored data
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

    // Return an object that URL.createObjectURL can recognize
    const fakeBlob = {
      __arrayBufferData: combined,
      __mimeType: options?.type || "application/octet-stream",
    };

    return fakeBlob as unknown as Blob;
  },

  // Forward static properties and instanceof checks
  get(target, prop) {
    if (prop === Symbol.hasInstance) {
      return (instance: unknown) =>
        instance instanceof OriginalBlob ||
        (instance !== null &&
          typeof instance === "object" &&
          "__arrayBufferData" in (instance as Record<string, unknown>));
    }
    return Reflect.get(target, prop);
  },
};

globalThis.Blob = new Proxy(OriginalBlob, BlobHandler) as unknown as typeof Blob;

// Patch URL.createObjectURL to handle our fake blobs
const origCreateObjectURL = URL.createObjectURL;
URL.createObjectURL = function (obj: unknown): string {
  const fakeBlob = obj as { __arrayBufferData?: Uint8Array; __mimeType?: string };
  if (fakeBlob && fakeBlob.__arrayBufferData) {
    return arrayBufferToDataURI(fakeBlob.__arrayBufferData, fakeBlob.__mimeType || "");
  }
  return origCreateObjectURL.call(URL, obj as Blob);
};

// Patch URL.revokeObjectURL to be a no-op for data URIs
const origRevokeObjectURL = URL.revokeObjectURL;
URL.revokeObjectURL = function (url: string): void {
  if (url && url.startsWith("data:")) {
    return;
  }
  return origRevokeObjectURL.call(URL, url);
};
