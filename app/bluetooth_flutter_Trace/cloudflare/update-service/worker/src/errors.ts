export type ErrorCode =
  | "NO_UPDATE"
  | "CHANNEL_STOPPED"
  | "CLIENT_TOO_OLD"
  | "TOKEN_EXPIRED"
  | "TOKEN_INVALID"
  | "ASSET_DISABLED"
  | "ASSET_ARCHIVED"
  | "RATE_LIMITED"
  | "BACKEND_UNAVAILABLE"
  | "FALLBACK_UNAVAILABLE"
  | "INVALID_PARAMETER"
  | "SIGNING_REQUIRED"
  | "FORMAL_RELEASE_REQUIRED"
  | "CAS_CONFLICT"
  | "VERSION_REGRESSION"
  | "RELEASE_NOT_FOUND"
  | "RELEASE_DISABLED"
  | "RELEASE_NOTES_REQUIRED";

export class ApiError extends Error {
  constructor(
    public readonly code: ErrorCode,
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function backendUnavailable(message = "Update backend unavailable"): ApiError {
  return new ApiError("BACKEND_UNAVAILABLE", message, 503);
}

export function invalidParameter(message: string): ApiError {
  return new ApiError("INVALID_PARAMETER", message, 400);
}
