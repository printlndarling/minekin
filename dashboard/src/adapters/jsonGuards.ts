export function asRecord(raw: unknown): Record<string, unknown> | null {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return null;
  return raw as Record<string, unknown>;
}

export function asString(raw: unknown): string | null {
  return typeof raw === "string" ? raw : null;
}

export function asNumber(raw: unknown): number | null {
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

export function asInteger(raw: unknown): number | null {
  const n = asNumber(raw);
  return n === null || !Number.isInteger(n) ? null : n;
}

export function asBoolean(raw: unknown): boolean | null {
  return typeof raw === "boolean" ? raw : null;
}

export function asNullableString(raw: unknown): string | null | undefined {
  if (raw === null) return null;
  return typeof raw === "string" ? raw : undefined;
}

export function asNullableNumber(raw: unknown): number | null | undefined {
  if (raw === null) return null;
  const n = asNumber(raw);
  return n === null ? undefined : n;
}

export function oneOf<T extends string>(raw: unknown, allowed: readonly T[]): T | null {
  return typeof raw === "string" && (allowed as readonly string[]).includes(raw) ? (raw as T) : null;
}
