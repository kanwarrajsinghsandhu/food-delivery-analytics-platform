# LinkedIn Post — Hand-off Brief

Read this after `project_Plan.md` phases 1–6 are actually done. This is not a draft post — it's the context and checklist needed to write one, incorporating a Claude-generated review of the earlier draft. Do not write the final post from this document alone; pull the real numbers, screenshots, and story details it points to first.

## Why this doc exists

The first draft (a 5-point emoji listicle: Bronze → Silver → Testing → CI/CD → Gold) was reviewed for credibility and audience reaction. Verdict: solid and beginner-friendly, but generic to a senior/hiring-manager audience because (a) the format is a saturated LinkedIn template, (b) it had no real screenshots — only architecture diagrams, (c) it led with infrastructure instead of the one finding that actually signals analysis was done, and (d) it had zero "what broke" framing despite the build having several genuine debugging incidents worth using.

## Hard requirements before drafting (from the review)

- [ ] **Lead with the finding, not the architecture.** The strongest line in the whole draft was the parenthetical about rating vs. order volume. It should open the post, not close it.
- [ ] **At least one real screenshot**, not just a clean diagram: the actual `dbt docs` DAG, a real GitHub Actions run (green or — better — one that's red because a test caught something), or the literal macro SQL.
- [ ] **A "what broke / what I'd rebuild" beat.** Self-deprecating, specific, and technical — this outperforms polish for engagement because it invites comments. Real candidates from this build (see below), not invented ones.
- [ ] **Kill the generic CTA.** "Swipe through for the architecture" appears verbatim in thousands of posts. Replace with something specific to what's actually on the next slide.
- [ ] **Don't default to the 1-5 emoji listicle.** It's not wrong, just undifferentiated. Consider leading with a 2–3 sentence narrative hook (the finding + the "why Snowflake, why dbt" framing) before any structured breakdown.

## Real "what broke" material (already happened — use one of these, don't fabricate a better one)

1. **The default-profile trap.** `dbt init` silently reused a leftover `jaffle_shop` profile instead of prompting for a new one, which produced two duplicate example-project folders (`jaffle_shop`, `jaffle_shop_1`) before the real `zomato` profile was set up correctly. Good story about profiles.yml being sticky state you don't expect.
2. **Credentials exposure.** A Snowflake password was briefly stored in plain text in `~/.dbt/profiles.yml` after being typed at an interactive prompt — dbt's default behavior, not a mistake exactly, but the fix (env var via `{{ env_var('DBT_SNOWFLAKE_PASSWORD') }}`, password reset) is a legitimately useful lesson for anyone following the same tutorial path.
3. **(Pending, from Phase 3)** Whatever the `order_total_reconciles` macro actually turns up when run against real Snowflake data — if any real order rows fail reconciliation, that's a live data-quality finding, which is a stronger story than a hypothetical one.

Pick one, maybe two. Don't stack all three — the review's point was "one honest crack in the polish," not a confession list.

## Audience calibration (from the review — keep this framing when choosing what to emphasize)

| Audience | What lands | What to avoid |
|---|---|---|
| Beginners/learners | The macro + testing + CI/CD framing as a teaching moment | Don't over-index here at the expense of the senior read |
| Mid-level DA/DE | Competent dbt usage, mildly positive | This audience has seen medallion+dbt+CI many times — don't lean on the architecture alone to impress them |
| Senior DE / hiring managers | The finding, real code/screenshots, the debugging story | Generic diagrams, generic CTAs, no evidence of actually running the thing |

## Assets to gather before writing (pull from Phase 6 of `project_Plan.md`)

- [ ] Real `sales_amount` reconciliation result — pass rate or specific failure count from real Snowflake data
- [ ] Real number from the `rating_vs_volume` mart — the actual correlation direction/strength, not the placeholder "they don't always"
- [ ] Screenshot: `dbt docs` DAG
- [ ] Screenshot: GitHub Actions run (ideally one red, one green, to show the gate actually works)
- [ ] Screenshot or code block: the real `test_order_total_reconciles` macro file, as committed
- [ ] One sentence on why Snowflake was chosen for this (vs. e.g. local Postgres/BigQuery) — the review flagged this as a missing constraint/reasoning signal

## Suggested structural shift (not a final draft)

Old shape: hook → 5-step listicle (Bronze/Silver/Testing/CI-CD/Gold) → generic close.

New shape to draft against once assets above are collected:
1. Open with the finding (1–2 sentences, plain language, no jargon)
2. One sentence on the "why" — why this dataset, why Snowflake/dbt, what was being learned
3. The build, but anchored to real evidence (screenshot callouts, not just named steps)
4. The one real thing that broke, briefly, with what it taught
5. Close on the finding again or an open question, not a CTA cliché

Carry over from the original draft, still good: "small dataset, same discipline production pipelines run on" — this line tested well and preempts the "just a tutorial" dismissal. Keep it.
