import type { Evidence } from "./types";

export default function Timeline({ evidence }: { evidence: Evidence[] }) {
  const events = evidence.filter((event) => event.timestamp).sort((left, right) => new Date(left.timestamp || 0).getTime() - new Date(right.timestamp || 0).getTime()).slice(0, 8);
  return <div className="timeline-block">
    {events.map((event) => <div className="timeline-event" key={event.evidence_id}>
      <time>{event.timestamp}</time>
      <span className={`timeline-level ${event.severity}`}>{event.severity}</span>
      <span className="timeline-message">{event.message}</span>
    </div>)}
    {events.length === 0 && <div className="timeline-empty">No timestamped records were parsed; source order is preserved in evidence references.</div>}
  </div>;
}