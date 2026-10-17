import type { AcledEvidence, FindingRecord } from "../../api/client";
import { bandCode } from "../../lib/finding";
import { capitalise } from "../../lib/weeks";

type Family = "protest" | "violence" | "suppression";
const FAMILIES: Family[] = ["protest", "violence", "suppression"];
const LO = -2;
const HI = 4;
const X = (v: number) => ((Math.max(LO, Math.min(HI, v)) - LO) / (HI - LO)) * 300;

function zOf(acled: AcledEvidence | null): Record<Family, number | null> | null {
  const card = acled?.evidence;
  const s = card?.has_data ? card.supporting : null;
  if (!s || s.kind !== "acled") return null;
  return {
    protest: s.week.protest_pressure_z,
    violence: s.week.violence_pressure_z,
    suppression: s.week.suppression_z,
  };
}

function BandSvg({ z, code }: { z: number | null; code: string }) {
  return (
    <svg viewBox="0 0 300 20" preserveAspectRatio="none" aria-hidden="true">
      <rect x={X(1)} y="3" width={X(2) - X(1)} height="14" fill="var(--wash)" />
      <rect x={X(2)} y="3" width={X(4) - X(2)} height="14" fill="var(--wash)" opacity=".6" />
      <line x1={X(0)} y1="0" x2={X(0)} y2="20" stroke="var(--soft)" strokeWidth="1" />
      <line x1={X(1)} y1="0" x2={X(1)} y2="20" stroke="var(--rule)" strokeWidth="1" strokeDasharray="2 2" />
      <line x1={X(2)} y1="0" x2={X(2)} y2="20" stroke="var(--rule)" strokeWidth="1" strokeDasharray="2 2" />
      {z !== null && (
        <rect
          x={Math.min(X(0), X(z))}
          y="6"
          width={Math.abs(X(z) - X(0))}
          height="8"
          fill={`var(--b-${code})`}
        />
      )}
    </svg>
  );
}

interface Props {
  classification: FindingRecord["classification"];
  /** The ACLED card, or null while it loads or when it failed. */
  acled: AcledEvidence | null;
}

export default function Bands({ classification, acled }: Props) {
  const z = zOf(acled);
  return (
    <div className="bands rule-top">
      <div className="rec bands-cap">
        Family bands this week · z against own 12-week baseline · dashed lines at 1.0 (ELEVATED) and 2.0 (SEVERE)
      </div>
      {FAMILIES.map((f) => {
        const band = classification[`${f}_band`];
        const zv = z ? z[f] : null;
        return (
          <div className="band" key={f} data-family={f}>
            <span className="n">{capitalise(f)}</span>
            {z ? <BandSvg z={zv} code={bandCode(band)} /> : <span />}
            <span className="v">
              {band}
              {z ? ` · ${zv === null ? "–" : zv.toFixed(2)}` : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}
