import { useEffect } from "react";
import { listFindings, type FindingList } from "../api/client";
import FindingRegister from "../components/FindingRegister";
import { useLoad } from "../lib/useLoad";

export default function Findings() {
  const [findings, retry] = useLoad<FindingList>(listFindings);
  useEffect(() => {
    document.title = "Published findings · CLIO Findings Explorer";
  }, []);

  const list = findings.kind === "ready" ? findings.data.findings : null;

  return (
    <div>
      <div className="rec">{list ? `Register · ${list.length} findings` : "Register"}</div>
      <h1 className="page-h1">Published findings</h1>
      <p className="dek">
        Each finding is one classified week, its evidence from three sources, and what that evidence does not establish.
      </p>
      {findings.kind === "loading" && <div className="register-placeholder" aria-busy="true" />}
      {findings.kind === "error" && (
        <>
          <p role="alert">The findings list could not be loaded.</p>
          <button type="button" className="btn" onClick={retry}>
            Try again
          </button>
        </>
      )}
      {list && <FindingRegister findings={list} />}
    </div>
  );
}
