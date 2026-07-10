type LogLevel = "info" | "warn" | "error";

const runtimeLogSink = globalThis["console"];

export function writeLog(
  level: LogLevel,
  event: string,
  fields: Record<string, unknown>
): void {
  const line = JSON.stringify({ level, event, ...fields });
  if (level === "error") {
    runtimeLogSink["error"](line);
    return;
  }
  runtimeLogSink["log"](line);
}
