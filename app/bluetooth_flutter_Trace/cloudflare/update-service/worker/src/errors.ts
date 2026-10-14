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
  | "RELEASE_NOTES_REQUIRED"
  | "UNKNOWN_DEVICE_MODEL"
  | "HARDWARE_INCOMPATIBLE"
  | "LAYOUT_INCOMPATIBLE"
  | "BOOT_TOO_OLD"
  | "PROTOCOL_UNSUPPORTED"
  | "RELEASE_CONFLICT"
  | "RELEASE_INCOMPLETE"
  | "RELEASE_NOT_READY"
  | "RELEASE_ARCHIVED"
  | "RELEASE_IN_USE"
  | "RECOVERY_ASSET_UNAVAILABLE"
  | "R2_VERIFY_FAILED"
  | "R2_OBJECT_CONFLICT"
  | "IDEMPOTENCY_CONFLICT"
  | "IDEMPOTENCY_RESULT_EXPIRED";

export class ApiError extends Error {
  constructor(
    public readonly code: ErrorCode,
    message: string,
    public readonly status: number,
    public readonly details?: Record<string, string | number>
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
