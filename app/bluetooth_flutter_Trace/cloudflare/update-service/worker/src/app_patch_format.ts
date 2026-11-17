export const APP_BSDIFF_FORMAT = "bsdiff-lzma-v1";
export const APP_BSDIFF_MIN_VERSION = 107;
export type AppDeltaFormat = "vcdiff" | typeof APP_BSDIFF_FORMAT;

export function preferredAppDeltaFormat(version: number, capabilities: string[]): AppDeltaFormat {
  return version >= APP_BSDIFF_MIN_VERSION && capabilities.includes(APP_BSDIFF_FORMAT)
    ? APP_BSDIFF_FORMAT : "vcdiff";
}

export function storedAppDeltaFormat(job: { input_json?: string; base_version_code: number }): AppDeltaFormat {
  const spec = job.input_json ? JSON.parse(job.input_json) as { patchFormat?: unknown } : {};
  if (spec.patchFormat == null || spec.patchFormat === "vcdiff") return "vcdiff";
  if (spec.patchFormat === APP_BSDIFF_FORMAT && job.base_version_code >= APP_BSDIFF_MIN_VERSION) return APP_BSDIFF_FORMAT;
  throw new Error("Unsupported stored App delta format");
}

export function clientSupportsAppDelta(format: AppDeltaFormat, version: number, capabilities: string[]): boolean {
  return format === APP_BSDIFF_FORMAT
    ? preferredAppDeltaFormat(version, capabilities) === APP_BSDIFF_FORMAT
    : version >= 41;
}
