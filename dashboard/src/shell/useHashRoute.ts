import { useCallback, useEffect, useState } from "react";
import { pageFromHash, type PageId } from "./navigation";

/**
 * The page the address bar selects, kept in `#fragment` so a panel can be deep-linked
 * and a browser back step lands where the operator came from.
 *
 * Writing the fragment with `pushState` keeps a history entry for each selected page and
 * the query string intact: `?adapter=gateway&gateway=/gateway` is what makes the page
 * read the real Kin at all, and losing it on a tab click would silently re-point the
 * whole shell at the unconfigured adapter.
 */
export function useHashRoute(initialPage?: PageId): readonly [PageId, (next: PageId) => void] {
  const [page, setPage] = useState<PageId>(() => initialPage ?? pageFromHash(window.location.hash));

  useEffect(() => {
    const onHashChange = (): void => setPage(pageFromHash(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    window.addEventListener("popstate", onHashChange);
    return () => {
      window.removeEventListener("hashchange", onHashChange);
      window.removeEventListener("popstate", onHashChange);
    };
  }, []);

  const select = useCallback((next: PageId): void => {
    if (window.location.hash !== `#${next}`) window.history.pushState(null, "", `#${next}`);
    setPage(next);
  }, []);

  // Nothing selects a page on first paint, so the rendered page writes its own fragment to
  // keep the address bar and the panel naming the same thing.
  useEffect(() => {
    if (window.location.hash === "") window.history.replaceState(null, "", `#${page}`);
    // Only the mount-time page needs a fragment; later changes come from `select`.
  }, [page]);

  return [page, select] as const;
}
