import { range, recId } from "../../lib/weeks";

interface Props {
  weekStart: string;
  country: string;
  snapshotVersion: string;
  position: number | null;
  count: number | null;
}

export default function RecordHeader({ weekStart, country, snapshotVersion, position, count }: Props) {
  return (
    <div className="meta rec">
      <span>
        Record <b>{recId(weekStart, country)}</b>
      </span>
      <span>
        Week <b>{range(weekStart)}</b>
      </span>
      <span>
        Snapshot <b>{snapshotVersion}</b>
      </span>
      {position !== null && count !== null && (
        <span>
          Finding{" "}
          <b>
            {position} of {count}
          </b>
        </span>
      )}
    </div>
  );
}
