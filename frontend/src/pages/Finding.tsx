import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ApiError,
  getAcledEvidence,
  getFinding,
  getGoogleTransparencyEvidence,
  getOoniEvidence,
  getTimeline,
  listFindings,
  type AcledEvidence,
  type FindingDetail,
  type FindingList,
  type TimelineResponse,
} from "../api/client";
import Bands from "../components/finding/Bands";
import ContextStrip from "../components/finding/ContextStrip";
import ExhibitCard, { ExhibitError, ExhibitLoading, type ExhibitSource } from "../components/finding/ExhibitCard";
import Limits from "../components/finding/Limits";
import Pager from "../components/finding/Pager";
import RecordHeader from "../components/finding/RecordHeader";
import { Citations, DataSources } from "../components/finding/Sources";
import StateLine from "../components/finding/StateLine";
import { contextRange, paragraphs, splitKeyPhrase } from "../lib/finding";
import { titleNoDate } from "../lib/weeks";

type Part<T> = { kind: "loading" } | { kind: "ready"; data: T } | { kind: "error"; error: unknown };
const LOADING = { kind: "loading" } as const;

interface Loaded {
  slug: string;
  finding: Part<FindingDetail>;
  list: Part<FindingList>;
  timeline: Part<TimelineResponse>;
  acled: Part<AcledEvidence>;
  ooni: Part<AcledEvidence>;
  google: Part<AcledEvidence>;
}

function settle<T>(p: Promise<T>, set: (part: Part<T>) => void) {
  p.then(
    (data) => set({ kind: "ready", data }),
    (error: unknown) => set({ kind: "error", error }),
  );
}

function initial(slug: string): Loaded {
  return { slug, finding: LOADING, list: LOADING, timeline: LOADING, acled: LOADING, ooni: LOADING, google: LOADING };
}

function useFindingParts(slug: string, attempt: number): Loaded {
  const [state, setState] = useState<Loaded>(() => initial(slug));
  useEffect(() => {
    let live = true;
    const put =
      <K extends keyof Loaded>(key: K) =>
      (part: Loaded[K]) => {
        if (live) setState((s) => (s.slug === slug ? { ...s, [key]: part } : s));
      };
    settle(getFinding(slug), put("finding"));
    settle(listFindings(), put("list"));
    settle(getAcledEvidence(slug), put("acled"));
    settle(getOoniEvidence(slug), put("ooni"));
    settle(getGoogleTransparencyEvidence(slug), put("google"));
    return () => {
      live = false;
    };
  }, [slug, attempt]);
  return state;
}

/** The timeline needs the finding's week, so it starts as soon as the finding arrives. */
function useTimeline(week: string | null): Part<TimelineResponse> {
  const [state, setState] = useState<{ week: string; part: Part<TimelineResponse> } | null>(null);
  useEffect(() => {
    if (!week) return;
    let live = true;
    settle(getTimeline(contextRange(week)), (part) => {
      if (live) setState({ week, part });
    });
    return () => {
      live = false;
    };
  }, [week]);
  return state && state.week === week ? state.part : LOADING;
}

function Dek({ teaser, keyPhrase }: { teaser: string; keyPhrase: string | null | undefined }) {
  const split = splitKeyPhrase(teaser, keyPhrase);
  return (
    <p className="dek">
      {split ? (
        <>
          {split.before}
          <mark>{split.mark}</mark>
          {split.after}
        </>
      ) : (
        teaser
      )}
    </p>
  );
}

function evidenceNode(source: ExhibitSource, part: Part<AcledEvidence>, weekStart: string) {
  if (part.kind === "loading") return <ExhibitLoading source={source} />;
  if (part.kind === "error") return <ExhibitError source={source} />;
  return <ExhibitCard response={part.data} weekStart={weekStart} />;
}

/** Remounts per slug, so every part of the page starts again when the reader moves to another finding. */
export default function Finding() {
  const { slug = "" } = useParams();
  return <FindingView key={slug} slug={slug} />;
}

function FindingView({ slug }: { slug: string }) {
  const [attempt, setAttempt] = useState(0);
  const parts = useFindingParts(slug, attempt);
  const week = parts.finding.kind === "ready" ? parts.finding.data.finding.week_start_date : null;
  const timeline = useTimeline(week);

  const title = parts.finding.kind === "ready" ? titleNoDate(parts.finding.data.finding.title) : null;
  useEffect(() => {
    if (title) document.title = `${title} · CLIO Findings Explorer`;
  }, [title]);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [slug]);

  if (parts.finding.kind === "loading") {
    return <div className="finding-placeholder" aria-busy="true" aria-label="Loading the finding" />;
  }

  if (parts.finding.kind === "error") {
    if (parts.finding.error instanceof ApiError && parts.finding.error.isNotFound) {
      return (
        <div>
          <h1>No finding with this name.</h1>
          <p>
            <Link to="/">Back to the ledger</Link> · <Link to="/findings">All findings</Link>
          </p>
        </div>
      );
    }
    return (
      <div>
        <h1>This finding could not be loaded.</h1>
        <button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>
          Try again
        </button>
      </div>
    );
  }

  const { snapshot_version, finding } = parts.finding.data;
  const list = parts.list.kind === "ready" ? parts.list.data.findings : null;
  const acled = parts.acled.kind === "ready" ? parts.acled.data : null;

  return (
    <article>
      <RecordHeader
        weekStart={finding.week_start_date}
        country={finding.country_iso}
        snapshotVersion={snapshot_version}
        position={list ? finding.position : null}
        count={list ? list.length : null}
      />
      <StateLine finding={finding} />
      <h1 className="finding-h1">{titleNoDate(finding.title)}</h1>
      <Dek teaser={finding.teaser} keyPhrase={finding.key_phrase} />
      <div className="two">
        <div className="two-main">
          <div className="read">
            {paragraphs(finding.summary_md).map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
          <Bands classification={finding.classification} acled={acled} />
          {timeline.kind === "ready" && timeline.data.weeks.length > 0 && (
            <div className="context">
              <div className="rec context-cap">The 13 weeks either side</div>
              <ContextStrip weeks={timeline.data.weeks} anchor={finding.week_start_date} slug={finding.slug} />
            </div>
          )}
        </div>
        <Limits caveats={finding.caveats} />
      </div>
      <section className="block">
        <h2>Exhibits</h2>
        <div className="exhibits">
          {evidenceNode("acled", parts.acled, finding.week_start_date)}
          {evidenceNode("ooni", parts.ooni, finding.week_start_date)}
          {evidenceNode("google_transparency", parts.google, finding.week_start_date)}
        </div>
      </section>
      <Citations citations={finding.citations} />
      <DataSources sources={finding.sources} />
      {parts.list.kind === "ready" && <Pager findings={parts.list.data.findings} slug={finding.slug} />}
    </article>
  );
}
