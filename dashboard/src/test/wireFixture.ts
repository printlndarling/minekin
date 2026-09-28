import type { FieldGapStatus } from "../domain/model";

/**
 * Wire-shape helpers for tests. The mock fixtures already ship wire-shaped
 * documents (one decoder path, no drift), so the remaining jobs here are
 * building member envelopes for hand-made bytes and safely mutating copies.
 */

/** A member of a `known` group that has a carrier. */
export function wireFilled(value: unknown): Record<string, unknown> {
  return { value };
}

/** A member of a `known` group that does not. */
export function wireGapField(status: FieldGapStatus, reason: string): Record<string, unknown> {
  return { gap: { status, reason } };
}

/** Deep copy so a discriminator test can break exactly one key. */
export function cloneWire<T>(document: T): T {
  return JSON.parse(JSON.stringify(document)) as T;
}
