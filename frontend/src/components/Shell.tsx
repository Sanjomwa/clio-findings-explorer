import { useEffect, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { getHealth } from "../api/client";
import ThemeSwitch from "./ThemeSwitch";

type SnapshotState = { kind: "loading" } | { kind: "ready"; version: string } | { kind: "unavailable" };

function useSnapshot(): SnapshotState {
  const [state, setState] = useState<SnapshotState>({ kind: "loading" });
  useEffect(() => {
    let live = true;
    getHealth().then(
      (h) => {
        if (live) setState(h.snapshot_version ? { kind: "ready", version: h.snapshot_version } : { kind: "unavailable" });
      },
      () => {
        if (live) setState({ kind: "unavailable" });
      },
    );
    return () => {
      live = false;
    };
  }, []);
  return state;
}

const NAV = [
  { to: "/", label: "Ledger", end: true },
  { to: "/findings", label: "Findings", end: false },
  { to: "/methodology", label: "Methodology", end: false },
  { to: "/about", label: "About", end: false },
];

export default function Shell() {
  const snapshot = useSnapshot();
  const label =
    snapshot.kind === "loading" ? "…" : snapshot.kind === "ready" ? snapshot.version : null;

  return (
    <>
      <a className="skip" href="#main">
        Skip to main content
      </a>
      <header className="mast gut">
        <div className="sheet">
          <Link className="brand" to="/">
            CLIO <span>Findings Explorer</span>
          </Link>
          <nav className="main" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <ThemeSwitch />
        </div>
      </header>
      <div className="strip gut">
        <div className="sheet">
          <span>
            Archive, <b>not a live monitor</b>
          </span>
          <span>Kenya</span>
          <span>{label === null ? <b>Snapshot unavailable</b> : <>Snapshot <b>{label}</b></>}</span>
          <span>
            Weeks run <b>Saturday to Friday</b>
          </span>
        </div>
      </div>
      <main id="main" tabIndex={-1} className="gut">
        <div className="sheet">
          <Outlet />
        </div>
      </main>
      <footer className="foot gut">
        <div className="sheet">
          Data: CLIO (Civil Liberties Intelligence Observatory) classifications from ACLED conflict events; OONI
          network measurements; Google Transparency Report government removal requests. All figures come from the
          snapshot committed to the repository.
        </div>
      </footer>
    </>
  );
}
