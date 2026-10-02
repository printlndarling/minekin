import type { TimelineEvent, TimelineKind, TimelineOutcome } from "./model";
import { TIMELINE_KIND_LABELS, TIMELINE_OUTCOME_LABELS } from "./labels";

export interface TimelineFilter {
  readonly query: string;
  readonly kinds: readonly TimelineKind[];
  readonly outcome: TimelineOutcome | "all";
}

/** Search only the loaded read-model events; never infer missing history. */
export function filterTimeline(items: readonly TimelineEvent[], filter: TimelineFilter): readonly TimelineEvent[] {
  const terms = filter.query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return items.filter((event) => {
    if (filter.kinds.length && !filter.kinds.includes(event.kind)) return false;
    if (filter.outcome !== "all" && event.outcome !== filter.outcome) return false;
    const text = [event.title, event.detail, event.eventId, event.sourceRef,
      event.kind, TIMELINE_KIND_LABELS[event.kind], event.outcome,
      TIMELINE_OUTCOME_LABELS[event.outcome], event.sequence, event.generation]
      .join(" ").toLocaleLowerCase();
    return terms.every((term) => text.includes(term));
  });
}
