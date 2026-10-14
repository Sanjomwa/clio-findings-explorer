# content/

Curated text written by a person: finding titles, summaries and caveats, and the methodology definitions. It is committed, separate from the snapshot, and loaded by the seed step (`docker compose run --rm seed`; compose mounts this folder read-only at `/content` for `seed` and `backend`). Nothing here is created by the app.

```
content/findings/<slug>.yaml   published findings (loaded by the seed)
content/methodology.yaml       optional definitions (read by GET /api/methodology)
content/drafts/<slug>.yaml     human-written drafts (never loaded by the seed)
```

## The rule

**Findings enter `content/findings/` only through `/new-finding <slug>`** ([`agent-capabilities/README.md`](../agent-capabilities/README.md)). The workflow reads a draft, has the `evidence-reviewer` subagent give every factual assertion a verdict, writes the log to `docs/reviews/<slug>.md`, and writes the finding only if nothing is `UNSUPPORTED`, `CORRECTED` or `EXTERNAL` without a source. Two backend unit tests enforce it in CI: no causal or targeting wording (`test_content_language.py`), and a clean verdict log for every finding (`test_content_reviewed.py`).

## Finding format

`content/findings/<slug>.yaml`, validated strictly by `backend/app/seed/content.py` (unknown or missing keys fail the seed). The file name must be `<slug>.yaml`.

| Key | Type | Rule |
|---|---|---|
| `slug` | string | `^[a-z0-9]+(-[a-z0-9]+)*$`, unique |
| `iso2` | string | `KE`; a `regime_weeks` row must exist for it and the week |
| `week_start_date` | date | `YYYY-MM-DD`, a week start in the snapshot |
| `position` | integer | >= 1, unique across findings (display order) |
| `title`, `teaser`, `summary_md` | string | non-blank |
| `published_at` | timestamp | ISO 8601 **with** a timezone |
| `caveats` | list | at least one; each exactly `{severity, caveat_md}`, severity `limitation` or `do_not_conclude`, `caveat_md` non-blank |
| `citations` | list | required, may be empty; each exactly `{claim, citation, url}`, all non-blank, `url` starts with `https://`; stored and served in file order. A file with the old key `sources` is rejected (renamed to `citations`) |

## `methodology.yaml` format

As read by `backend/app/routers/methodology.py`; each key is optional and an absent key gives an empty list (definitions are never invented). Values are validated by the response model, so a family, state, level or band outside the enum fails the request.

```yaml
families:           # list of {family, definition}: what each pressure family counts
  - {family: <protest|violence|suppression>, definition: <text>}
regime_states:      # list of {state, definition}
  - {state: <regime state>, definition: <text>}
confidence_levels:  # list of {level, definition}
  - {level: <confidence level>, definition: <text>}
family_bands:       # list of {band, definition}
  - {band: <band>, definition: <text>}
```

## Draft format

`content/drafts/<slug>.yaml` is exactly the finding format; `citations` is the same key, with the same rules, as in a published finding:

```yaml
citations:          # one item per real-world event statement in the draft; [] if there is none
  - claim: <the exact sentence or phrase it supports>
    citation: <publisher, title, date>
    url: <https URL>
```

`citations` is published with the finding (`FindingDetail.citations` in the API). It is distinct from the API's `sources`, which lists the data sources (ACLED, OONI, Google Transparency) behind the evidence cards. The reviewer checks that a citation is attached to each real-world event statement; a human checks that the citation supports the sentence.

Verdict logs are `docs/reviews/<slug>.md`. To resolve a `CORRECTED` row or an `EXTERNAL` row marked `NO SOURCE`, fix the draft, re-run `/new-finding`, and (only if a row legitimately stays) append `RESOLVED` to its evidence cell.
