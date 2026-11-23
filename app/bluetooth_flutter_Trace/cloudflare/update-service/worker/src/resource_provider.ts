export type UsageState = "ok" | "stale" | "not_configured" | "permission_denied" | "unavailable" | "no_samples" | "refreshing";

export class ProviderError extends Error {
  constructor(readonly state: UsageState, readonly reason: string = state) { super(reason); }
}

export async function readProviderResponse(response: Response): Promise<Record<string, unknown>> {
  if (!response.ok) {
    await response.body?.cancel();
    throw new ProviderError([401,403].includes(response.status) ? "permission_denied" : "unavailable");
  }
  const reader = response.body?.getReader();
  if (!reader) throw new ProviderError("unavailable");
  let size = 0, value = "";
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > 256 * 1024) throw new ProviderError("unavailable", "response_too_large");
      value += decoder.decode(chunk.value,{stream:true});
    }
    value += decoder.decode();
    const parsed: unknown = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new ProviderError("unavailable");
    return parsed as Record<string, unknown>;
  } finally { await reader.cancel().catch(()=>{}); reader.releaseLock(); }
}

export async function providerRead(url: string, token: string, fetcher: typeof fetch, query?: string) {
  const response = await fetcher(url, {method:query ? "POST" : "GET",redirect:"manual",
    headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},
    ...(query ? {body:JSON.stringify({query})} : {}),signal:AbortSignal.timeout(7000)});
  return readProviderResponse(response);
}

export function providerFailure(error: unknown): { state: UsageState; reason: string } {
  return error instanceof ProviderError ? {state:error.state,reason:error.reason} : {state:"unavailable",reason:"unavailable"};
}

export function analyticsAccount(body: Record<string, unknown>): Record<string, unknown> {
  if (Array.isArray(body.errors) && body.errors.length) {
    const denied = body.errors.some(error=>/auth|permission|not allowed|not entitled/i.test(String(error?.message)));
    throw new ProviderError(denied ? "permission_denied" : "unavailable");
  }
  const data = body.data as {viewer?:{accounts?:unknown[]}} | null;
  const accounts = data?.viewer?.accounts;
  if (!Array.isArray(accounts) || accounts.length !== 1 || !accounts[0] || typeof accounts[0] !== "object" || Array.isArray(accounts[0])) {
    throw new ProviderError("unavailable");
  }
  return accounts[0] as Record<string, unknown>;
}

export function nonnegative(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= Number.MAX_SAFE_INTEGER ? value : null;
}
