export class CliError extends Error { code: string; exitCode: number; requestId?: string; }
export function projectRoot(): string;
export function outputPath(root: string, value: string): string;
export function writeOutput(root: string, value: string, bytes: string | Uint8Array): Promise<void>;
