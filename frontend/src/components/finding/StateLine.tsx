import type { FindingRecord } from "../../api/client";
import { confidenceText, preTransitionSentence, stableSentence } from "../../lib/finding";
import { stateLabel } from "../../lib/weeks";

export default function StateLine({ finding }: { finding: FindingRecord }) {
  const conf = confidenceText(finding);
  const stable = stableSentence(finding);
  const pre = preTransitionSentence(finding.classification.pre_transition_target);
  return (
    <>
      <div className="state">
        <span className="lbl">{stateLabel(finding)}</span>
        {conf && <span className="conf">{conf}</span>}
      </div>
      {(stable || pre) && (
        <p className="state-note">
          {stable}
          {stable && pre ? " " : ""}
          {pre}
        </p>
      )}
    </>
  );
}
