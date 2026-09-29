import type { IdentityInfo } from "./model";

/**
 * The name rule Core enforces in `minekin_core.domain.offline_identity.is_valid_username`:
 * 3-16 letters, digits or underscore. Kept here so the panel validates the same way the
 * Gateway and Core do — a name the panel lets through is a name the server will accept, and
 * one it blocks is a name the server would refuse. The panel's copy is a courtesy check
 * before submit; it never replaces the server-side validation.
 */
export const USERNAME_PATTERN = /^[A-Za-z0-9_]{3,16}$/;

/** The name a brand-new identity starts on. Nothing about play renames a Kin off it. */
export const DEFAULT_IDENTITY_NAME = "minekin";

export function isValidUsername(value: string): boolean {
  return USERNAME_PATTERN.test(value);
}

/**
 * The operator-facing warning the rename form must show before it will submit. The
 * offline UUID is derived from the exact name, so a rename resolves a new player and an
 * already-joined server treats the Kin as a different one — inventory, position and
 * advancements do not follow. This is the reason rename sits behind a stopped-session,
 * explicit confirmation rather than a launch flag.
 */
export const RENAME_WARNING =
  "离线 UUID 由名字本身推导而来。改名会解析出一个新的离线 UUID：已经加入过的服务器会把它当作另一个玩家，" +
  "背包、坐标与进度都不会自动迁移。请只在会话停止时、在确知后果的情况下改名。";

/** Freshness of an identity reading against a caller-supplied clock. */
export function identityIsStale(identity: IdentityInfo, nowMs: number): boolean {
  const at = Date.parse(identity.observedAt);
  if (!Number.isFinite(at)) return false;
  return nowMs - at > identity.staleAfterMs;
}
