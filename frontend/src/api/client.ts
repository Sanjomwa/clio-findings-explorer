// The only file in the frontend that calls fetch (AGENTS.md rule 3).
import type { components, operations } from "./schema";

export type Health = components["schemas"]["Health"];
export type TimelineResponse = components["schemas"]["TimelineResponse"];
export type RegimeState = components["schemas"]["RegimeState"];
export type TimelineQuery = NonNullable<operations["getTimeline"]["parameters"]["query"]>;
export type FindingList = operations["listFindings"]["responses"]["200"]["content"]["application/json"];
export type FindingDetail = operations["getFinding"]["responses"]["200"]["content"]["application/json"];
/** The finding itself, without the response envelope. */
export type FindingRecord = FindingDetail["finding"];
export type AcledEvidence = operations["getAcledEvidence"]["responses"]["200"]["content"]["application/json"];
export type OoniEvidence = operations["getOoniEvidence"]["responses"]["200"]["content"]["application/json"];
export type GoogleTransparencyEvidence =
  operations["getGoogleTransparencyEvidence"]["responses"]["200"]["content"]["application/json"];
export type Methodology = operations["getMethodology"]["responses"]["200"]["content"]["application/json"];

export class ApiError extends Error {
  readonly status: number;
  readonly url: string;

  constructor(status: number, url: string) {
    super(`API request failed with status ${status}: ${url}`);
    this.name = "ApiError";
    this.status = status;
    this.url = url;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

function base(): string {
  return import.meta.env.VITE_API_BASE ?? "";
}

async function getJson<T>(path: string, query?: Record<string, string | undefined>): Promise<T> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) params.set(key, value);
  }
  const qs = params.toString();
  const url = `${base()}${path}${qs ? `?${qs}` : ""}`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new ApiError(res.status, url);
  return (await res.json()) as T;
}

const seg = (slug: string) => encodeURIComponent(slug);

export const getHealth = () => getJson<Health>("/api/health");

export const getTimeline = (query: TimelineQuery = {}) =>
  getJson<TimelineResponse>("/api/timeline", query as Record<string, string | undefined>);

export const listFindings = () => getJson<FindingList>("/api/findings");

export const getFinding = (slug: string) => getJson<FindingDetail>(`/api/findings/${seg(slug)}`);

export const getAcledEvidence = (slug: string) =>
  getJson<AcledEvidence>(`/api/findings/${seg(slug)}/evidence/acled`);

export const getOoniEvidence = (slug: string) =>
  getJson<OoniEvidence>(`/api/findings/${seg(slug)}/evidence/ooni`);

export const getGoogleTransparencyEvidence = (slug: string) =>
  getJson<GoogleTransparencyEvidence>(`/api/findings/${seg(slug)}/evidence/google-transparency`);

export const getMethodology = () => getJson<Methodology>("/api/methodology");
