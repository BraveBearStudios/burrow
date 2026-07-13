<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# RELX-03 Runbook: Exclude the release-please branch from the `oss` ruleset

**Phase:** 15 Pipeline Unblock & Green Main
**Requirement:** RELX-03
**Type:** GitHub repo-admin change (NOT a repo file edit; nothing here is committed to the repo)
**Ruleset:** `oss`, id `18189353`
**Operator-run:** yes. The session `gh` token lacks `admin:org` / repo-admin, so Claude
cannot apply this. Run every command below with YOUR admin-scoped authenticated `gh`.

## Why

The active `oss` repo ruleset (id `18189353`) enforces `pull_request`,
`non_fast_forward`, and `required_linear_history` across ~all branches. The
release-please bot runs as `github-actions[bot]` (the workflow `GITHUB_TOKEN`) and
force-updates its own transient branch `refs/heads/release-please--branches--main`.
Because that bot is not a bypass actor, every release-please run fails at
`Error updating ref heads/release-please--branches--main` and the release PR never
maintains.

Per the locked CONTEXT decision (RELX-03), the fix is a SURGICAL exclusion: add the
single glob `refs/heads/release-please--**` to the ruleset's
`conditions.ref_name.exclude`. This is chosen deliberately OVER adding
`github-actions[bot]` to `bypass_actors`, so branch protection stays fully intact
everywhere else and no actor gains a standing bypass.

**Only the release-please glob is excluded.** `pull_request`, `non_fast_forward`, and
`required_linear_history` stay enforced on `main` and on every developer branch. No
`bypass_actor` is added. Do not change `enforcement`, `rules`, `bypass_actors`, or the
`include` list.

## Substitution note

The commands below target `BraveBearStudios/burrow` (the current `origin`). If you run
this against a fork or a renamed repo, replace `BraveBearStudios/burrow` with the actual
`<owner>/<repo>` in every command. The ruleset id `18189353` is the `oss` ruleset on the
canonical repo; confirm the id with `gh api repos/<owner>/<repo>/rulesets` if unsure.

## Apply (gh api fetch, modify, PUT)

Run these from a bash shell (Git Bash / WSL / Linux / macOS). See the PowerShell note at
the end if you are on native Windows PowerShell.

### 1. Fetch the current ruleset to a file

```bash
gh api repos/BraveBearStudios/burrow/rulesets/18189353 > ruleset.json
```

### 2. Append the release-please glob AND strip the server read-only fields

A GET returns server-managed read-only fields (`id`, `node_id`, `source`,
`source_type`, `created_at`, `updated_at`, `_links`, `current_user_can_bypass`) that a
PUT must NOT carry. This `jq` transform (a) sets `.conditions.ref_name.exclude` to the
existing exclude array (or `[]` if absent) plus `refs/heads/release-please--**`, deduped,
then (b) projects the body down to exactly
`{name, target, enforcement, bypass_actors, conditions, rules}` so the PUT cannot silently
reset any protection:

```bash
jq '
  .conditions.ref_name.exclude =
    ((.conditions.ref_name.exclude // []) + ["refs/heads/release-please--**"] | unique)
  | {name, target, enforcement, bypass_actors, conditions, rules}
' ruleset.json > ruleset.new.json
```

Sanity-check before you PUT: the ONLY change should be the single added glob in
`conditions.ref_name.exclude`, plus the removal of the read-only keys.

```bash
jq '.conditions.ref_name.exclude' ruleset.new.json
diff <(jq -S . ruleset.json) <(jq -S . ruleset.new.json)
```

The `diff` should show only the dropped read-only keys and the one added exclude glob.
`name`, `target`, `enforcement`, `bypass_actors`, `rules`, and the `include` list must be
unchanged.

### 3. Apply the modified ruleset

```bash
gh api --method PUT repos/BraveBearStudios/burrow/rulesets/18189353 --input ruleset.new.json
```

A `200` with the updated ruleset JSON in the response means it applied.

## Fallback: repo Settings UI

If you prefer the UI, or the API PUT is rejected:

1. GitHub repo, then **Settings** -> **Rules** -> **Rulesets**.
2. Open the `oss` ruleset.
3. Under **Target branches**, click **Add target** -> **Exclude by pattern**.
4. Enter `refs/heads/release-please--**`.
5. **Save changes.**

Leave every rule (`pull_request`, `non_fast_forward`, `required_linear_history`), the
enforcement status, and the bypass list untouched.

## Confirm (RELX-03 live proof)

### A. Verify the exclusion is present and nothing else moved

```bash
gh api repos/BraveBearStudios/burrow/rulesets/18189353 | jq '.conditions.ref_name.exclude'
```

The output array must contain `refs/heads/release-please--**`. Then confirm the rules and
enforcement are unchanged and no new bypass actor was added:

```bash
gh api repos/BraveBearStudios/burrow/rulesets/18189353 \
  | jq '{enforcement, rules: [.rules[].type], bypass_actors}'
```

`rules` must still list `pull_request`, `non_fast_forward`, and `required_linear_history`;
`enforcement` must be unchanged; `bypass_actors` must be unchanged (no bot added).

### B. Trigger release-please and confirm no ref rejection

Push a commit to `main` (or re-run the last failed release-please run from the Actions
tab). Open the release-please job log and confirm:

- The job updates `refs/heads/release-please--branches--main` successfully.
- There is NO `Error updating ref heads/release-please--branches--main`.
- The release PR opens / updates cleanly.

Once that run is clean, RELX-03 is live. Reply `applied` to resume Phase 15 (or paste the
error to iterate).

## Cleanup

```bash
rm -f ruleset.json ruleset.new.json
```

## Windows PowerShell note

Native PowerShell `>` redirection writes UTF-16, which breaks `jq`. On PowerShell, either
run these commands inside Git Bash, or force UTF-8 on the fetch:

```powershell
gh api repos/BraveBearStudios/burrow/rulesets/18189353 | Out-File -Encoding utf8 ruleset.json
```

then run the `jq` transform (jq is shell-agnostic) and the
`gh api --method PUT ... --input ruleset.new.json` apply step unchanged.
