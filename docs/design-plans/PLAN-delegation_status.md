# Delegation Status in the Webapp, and Re-checking on Demand

Showing users what the delegation checks found, and letting them ask for a
fresh check after they have changed something at their registrar.

Builds on `PLAN_delegation-checker.md` (how a check is measured and recorded)
and `PLAN-limit_domains.md` (when checks run, and how they feed the limit).
Picks up three items those plans deferred: surfacing per-domain status on the
domain serializer (limits §13, checker §7.1), a user-triggered "re-check now"
endpoint (limits §13, checker §7.1), and the webapp half of the incentive,
including `secure_domains` (limits §13).

Status: **implemented**, as described below.

## 1. Goal

1. **See it.** Each domain in the domain list shows whether it is securely
   delegated, and if not, what is wrong in one word. The setup instructions
   dialog (optionally) says what was observed, when, and what to do about it.
2. **Re-check it.** A button per domain asks for a fresh check. The result
   appears in the UI within seconds, and a domain that turned secure raises the
   limit shown in the create dialog without a reload.
3. **Explain the limit where it bites.** The create dialog says how many
   domains are securely delegated.

The incentive in `PLAN-limit_domains.md` only works if the user can see which
domain is holding them back and can confirm a fix right away; today they can
do neither.

## 2. API: the `status` field

### 2.1 Shape

A new read-only field on `DomainSerializer`, present in list, retrieve and
create responses:

    "status": {
        "secure_since": "2026-09-01T12:00:00.000000Z",
        "checked": "2026-10-24T08:12:03.000000Z",
        "nameserver_status": "correctly_delegated",
        "security_status": "secure",
        "nameservers": ["ns1.desec.io", "ns2.desec.org"]
    }

| field | source | null when |
|---|---|---|
| `secure_since` | `Domain.secure_delegation_since` | not (known to be) securely delegated |
| `checked` | `current_delegation_check.checked` | never checked |
| `nameserver_status` | `current_delegation_check.nameserver_status` | never checked |
| `security_status` | `current_delegation_check.security_status` | never checked, or not delegated (below) |
| `nameservers` | `current_delegation_check.nameservers` | never checked (then `[]`) |

The object itself is always present, so clients need no null check on it.

**Status values** are the lowercased `IntegerChoices` names (`secure`,
`insecure`, `misconfigured`, `error`; `correctly_delegated`, `multi_provider`,
`other_provider`, `not_delegated`, `error`), as the model's comment already
anticipates. The integers stay an implementation detail.

**"Secure" is `secure_since != null`**, with one exception: domains under a
local public suffix count as secure without ever being measured (limits §3.3),
so their `secure_since` is null. Clients that care match the suffix themselves;
the webapp shows them as secure (§4.1, §4.2). No separate `secure` field.

**`security_status` is null when `nameserver_status` is `not_delegated`.**
Without a delegation there is no child zone to ask, so the check asks for the
parent's `DNSKEY` instead (`_classify_security`), and the stored value
describes the parent: `SECURE` + `NOT_DELEGATED` means "the parent is signed".
A field whose subject changes with another field's value is a trap for every
API client (a green "secure" on an undelegated domain), and nothing in this
plan needs what it says about the parent (§4.1, unsigned parents). The stored
value is untouched; only the serializer drops it.

**`nameservers`** is the observed NS set from the parent. It is what lets the
details view say *where* a domain is delegated when it is `OTHER_PROVIDER`, and
spot the incomplete-but-ours case (only `ns1.desec.io`), which is deliberately
recorded as `CORRECTLY_DELEGATED` (checker §2 notes). Cheap: it is on the row
that is already joined.

Not exposed: `created` of the current check, `ede_code`/`ede_text`, `rcode`.
EDE text would help explain `MISCONFIGURED` ("Signature Expired" vs "DNSSEC
Bogus"); worth adding if the first version's wording proves too vague.

### 2.2 Local domains on the server

The re-check endpoint (§3.1) needs to know per object whether a domain is
secure, local ones included. A Python counterpart to
`under_local_public_suffix_q()`:

    @property
    def is_under_local_public_suffix(self):
        return any(self.name.endswith(f".{s}") for s in settings.LOCAL_PUBLIC_SUFFIXES)

Two definitions of one predicate, so a test asserts that they agree on a
fixture set: an immediate child of a local suffix, a deeper one, the suffix
itself, an external domain, and a name that merely ends in the suffix's
characters (`notdedyn.io`).

### 2.3 Query cost

`DomainViewSet.get_queryset()` gains `.select_related("current_delegation_check")`.
Without it the list is N+1 on the pointer. A test pins the query count for a
list of several checked domains.

## 3. API: re-checking

### 3.1 One domain

    POST /api/v1/domains/{name}/status/
    GET  /api/v1/domains/{name}/status/

`POST` asks for a check of this one domain:

| situation | response |
|---|---|
| domain is under a local public suffix | `200`, body: the status object, nothing enqueued |
| last check confirmed less than 60 s ago | `200`, as above |
| otherwise | `202`, body: the current status object, plus `"requested": "<server time>"` |
| broker unreachable | `503` |
| throttled | `429` (§3.3) |

`200` always means "this is the answer, no check needed"; `202` means "a check
is coming". Clients need no further case.

`GET` returns the status object (the domain's `status` field, §2.1) and
nothing else, so polling for the result neither retrieves DNSSEC keys from
pdns (as `GET /domains/{name}/` does) nor transfers the whole list.

**`requested` is server time.** The client waits until `checked >=
requested`, which avoids comparing against its own clock. `checked` is
`auto_now`, so any recorded outcome bumps it, including one that agrees with
the previous state.

**The 60 s shortcut** covers the common case of a re-check right after domain
creation, whose trigger (limits §7.2) has usually just checked the domain.
Enqueueing then would only make two concurrent checks of the same name
interfere (checker §2, cache independence).

**Secure domains are re-checked, too.** A check of a secure domain can only
lower the limit, but users who change their DNSSEC setup (a key rollover, new
DS records at the registrar, a change of registrar) want to see that it is
still in order, and a broken setup is theirs to know about before the next
sweep. The 60 s shortcut and §3.3 bound the load. The planner keeps skipping
secure domains (limits §6.3), as no user asked for those checks. Local domains
are the exception: nothing a check could report about them is news (limits
§3.3). Not an error, though: the current state is the answer, so `200`.

**Unlike the triggers, this one fails loudly.** `enqueue_user_delegation_check`
swallows errors because a check there is a side effect of another request
(limits §12). Here the check *is* the request, so a broker outage is a `503`.

### 3.2 Task side

A new helper in `desecapi/tasks.py`, next to `enqueue_user_delegation_check`:

    def enqueue_domain_delegation_check(domain):
        check_domain_delegation.apply_async((domain.pk, 0), queue=ADHOC_QUEUE)

- **Ad-hoc queue**, so the wait is one check, not one sweep (limits §6.1).
- **`max_age=0`**: the user asked for a fresh measurement; the freshness test
  in the task would otherwise skip it. Duplicate messages are bounded by the
  throttle instead.
- **`record_failure=True`**: if our resolver cannot be operated
  (`UnboundException`), the task records a check with `ERROR` for both
  statuses. That keeps `secure_delegation_since` (limits §3.1) and bumps
  `checked`, so the client waiting for it gets an answer, which the webapp
  already shows ("Check failed", or for a secure domain, the note that the
  most recent check could not be completed). Bulk checks keep skipping
  silently (limits §6.2): recording there would write a state per domain and
  make each look freshly checked to re-plans.

### 3.3 Throttling

Each check costs outbound queries to third-party nameservers and flushes the
resolver's negative cache for the parent zone (checker §2), so §3.1 needs
tighter limits than `dns_api_expensive`. Two scopes, both enforced:

| scope | rates | bucket |
|---|---|---|
| `dns_api_per_domain_status_check` | `1/min`, `10/h`, `30/d` | per domain (`throttle_scope_bucket`, as for `zonefile`) |
| `dns_api_status_check` | `30/h`, `100/d` | per account |

**Per domain**: someone waiting for a registrar or registry to publish a DS
retries every few minutes while active (`10/h`), and on and off over the
publication delay, which can be most of a day at some registries (`30/d`).

**Per account: what it protects, and whom it affects.** It protects other users
more than the outside world. The ad-hoc queue is FIFO across users (the
round-robin of limits §6.1 only separates ad-hoc from bulk), so an account that
enqueues a hundred checks puts every other user's re-check button behind them:
a hundred checks over eight worker slots, at up to ~30 s each for slow parents,
is minutes. The planner's 20-domain cap exists for the same reason.

With secure domains re-checkable (§3.1), any account with more than 30
domains can produce such a burst. Re-checks require a login token (§3.4), so
that is one click per domain in the webapp, or a script that logs in with the
account's password; the cap binds for the latter rather than for people. Its
cost for a large
portfolio is that confirming a batch change domain by domain takes hours; the
sweep serves bulk confirmation instead (and a re-check-all, should one be added,
§8). A cap proportional to the domain count would just restate the per-domain
rate, and would not bound the burst.

**Every `POST` counts**, including those answered with `200`: throttling runs
before the view, as everywhere else in the API. The `200`s that remain are
local domains, for which the webapp offers no re-check, and checks less than
60 s old, which the per-domain `1/min` mostly covers anyway, so little budget
goes to them. The user documentation says that re-checks are for interactive
use (hence the login token), that automation should read the status, which the
sweep keeps current, and that we welcome feedback on this. `desecapi_throttle_failure` with
`scope="dns_api_status_check"` shows whether the account rates bind real users.

`ScopedRatesThrottle` reads one scope attribute per view, so the second scope
needs a small subclass that reads another (`AccountScopedRatesThrottle`, from
`throttle_scope_account`). It sits in `DEFAULT_THROTTLE_CLASSES` next to the
first, and is inert for views that do not set the attribute; the view sets it
for `POST` on `status/` only. `GET` stays on `dns_api_cheap`.
`docs/rate-limits.rst` gains both rows.

Views bind `DEFAULT_THROTTLE_CLASSES` at import, when the test settings have
replaced it, so the throttle tests patch the view's `throttle_classes`.

### 3.4 Permissions

`DomainViewSet.permission_classes` raises for any unsafe method it does not
know about, and `POST` currently means "create". The `status` action is
handled before the `match`: `POST` gets the base classes (`IsAuthenticated`,
`MFARequiredIfEnabledOrAPIToken`, `IsOwner`) plus `IsLoginToken`; `GET` gets
only the base classes.

**Why a login token.** A re-check is for a person confirming a change they just
made (§3.1), and login tokens are the ones "intended for use by humans" (user
documentation, 2FA). Automation reads the status, which the sweep keeps
current within a day. API tokens, including the kind handed out most freely
(monitoring, dashboards, DS-sync scripts), thus cannot use up the account's
budget (§3.3). With 2FA enabled, the base classes already require the login
token to have passed it. This may change if automation turns out to need
re-checks (§8).

Login tokens carry `perm_create_domain` (`views/users.py`), which the existing
triggers require: the creation trigger (limits §7.2) runs only after a
successful create, and the limit-denial trigger (limits §7.3) only fires after
`HasCreateDomainPermission` has passed, as DRF stops at the first failing
permission. The webapp, which uses login tokens, is unaffected.

Not policy-based write permission: policies are `(domain, subname, type)`-
granular and govern RRset writes only, so "write permission for the domain"
would need an arbitrary definition (apex policy? default policy? any policy
with `perm_write`?).

## 4. Webapp

### 4.1 One mapping from API fields to what the user sees

A pure function in a new `src/delegation.js`, so the list, the details and the
tests share it:

    delegationSummary(status, name) → { state, label, color, icon, hint, details }

Evaluated in this order, first match wins:

| # | condition | state | label | color |
|---|---|---|---|---|
| 1 | `secure_since` set | `secure` | Secure | success |
| 2 | `checked` null | `unchecked` | Not checked yet | grey |
| 3 | security `misconfigured` | `misconfigured` | DNSSEC broken | error |
| 4 | NS `not_delegated` | `not_delegated` | Not delegated | grey |
| 5 | NS `other_provider` | `other_provider` | Delegated elsewhere | warning |
| 6 | security `insecure`, NS not `error` | `insecure` | No DNSSEC | warning |
| 7 | otherwise (an `error` in either dimension) | `error` | Check failed | grey |

`secure_since` goes first because it is error-immune (limits §3.1): a domain
whose latest check failed is still secure, and row 1 says so, with "could not
re-check …; we will retry" in its hint. With `security_status` null for
undelegated domains (§2.1), no other ordering subtlety remains. Row 6 requires
a known delegation: an unsigned parent settles `insecure` even when the
delegation cannot be read, and "delegated to deSEC" would then be a guess.

Unit-tested with vitest against every row.

**What each combination means** (raw values, from `delegation.py`); this is
the reasoning behind §2.1 and the rows above:

| NS status | security | meaning |
|---|---|---|
| ours / multi | `secure` | chain validates into the zone: the goal |
| ours / multi | `insecure` | no DS at the parent, or parent unsigned |
| ours / multi | `misconfigured` | validation fails, usually a stale DS from a previous provider |
| ours / multi | `error` | no DNSSEC verdict (timeout, SERVFAIL without DNSSEC EDE) |
| other | any | as above, but for someone else's zone |
| not delegated | `secure` | the *parent* is signed: the name could be secured once delegated |
| not delegated | `insecure` | the parent is unsigned (or an island of trust) |
| not delegated | `misconfigured` | the parent's own chain is broken |
| not delegated | `error` | no verdict |
| error | `insecure` / `misconfigured` / `error` | only step 1 of checker §2 settled anything |
| error | `secure` | impossible: `SECURE` comes from step 4, which needs the delegation |

**Hints.** Short for the tooltip, longer for the details (§4.5):

| state | tooltip |
|---|---|
| `secure` | Securely delegated as of 4 Sep 2026. |
| `unchecked` | Not checked yet. Checks run at least daily. |
| `misconfigured` | DNSSEC validation fails, so many resolvers cannot resolve this domain. Usually outdated DS records at the registrar. |
| `not_delegated` | Not delegated yet. Set deSEC's nameservers at your registrar. |
| `other_provider` | Delegated to other nameservers: …. |
| `insecure` | Delegated to deSEC, but not secured. Forward the DS records to your registrar. |
| `error` | We could not complete the last check, and will retry. |

**Dates.** `secure_since` is when a check first found the domain secure. For
domains secured before the checks began (2026-09-04), that is their first
check, so the text says "as of", which holds either way. Dates are formatted
with date-fns as `d MMM yyyy`: with the month as a word, "4 Sep 2026" reads the
same in every locale, and it is English like the text around it.

**Local domains** get their own summary, `localSummary(name)`: Secure, in the
success color, with the tooltip "Automatically secured by deSEC." They count
towards `secure_domains` like any other secure domain, so they show like one,
and the create dialog's count (§4.6) adds up with the chips.

**`insecure`, and unsigned parents.** `INSECURE` does not say whether the
parent lacks the DS or is unsigned altogether (checker §2, steps 1 and 4). The
wording does not need to know: in both cases the user's lever is the same
party, their registrar, which in turn is the registry's customer. The goal in
the unsigned case is not an exception but demand for DNSSEC at the parent, so
the details text (§4.5) asks the user to create it:

> **Not secured yet.** *example.com* is delegated to deSEC, but the parent
> zone has no DS records for it. DNSSEC therefore does not protect it yet, and
> it does not raise your domain limit.
>
> Forward the DS records below to the organization where you registered the
> domain (usually your registrar). If they cannot accept DS records, or tell
> you that DNSSEC is not available for your domain, please ask them to change
> that. Registrars and registries should add DNSSEC support when their
> customers ask for it.

"The parent zone has no DS records for it" is true in both cases, so nothing
needs recording. Optionally, a "Copy request" button next to it puts a
ready-made message on the clipboard ("Please publish the following DS records
for example.com: …. If you do not support DNSSEC for this domain yet, please
add support."), so asking costs the user one paste.

### 4.2 Domain list (`CrudListDomain.vue`)

- **Column** "Delegation" between Name and Published, rendered by a new
  `components/Field/DelegationStatus.vue`: a small chip (Vuetify's `v-chip`, a
  pill-shaped, tinted label with an icon and a word or two), with a tooltip
  carrying the hint and "checked … ago".
  Sortable by the state that the chip shows, most urgent first: DNSSEC
  broken, No DNSSEC, Not delegated, Check failed, Not checked yet, Delegated
  elsewhere, and then Secure, with local domains among them. Domains in the
  same state tie, so the table's other sort columns order them (§4.3).
- **Row action** "Re-check delegation" (`mdiRefresh`), hidden for local
  domains (§3.1); shows a spinner while that domain's check is under way. The
  actions are right-aligned with the re-check leftmost, so the others keep
  their place, and the chip's tooltip says why there is nothing to check.
- **Local domains** (under a local public suffix, at any depth): a "Secure"
  chip (§4.1), no re-check. A new `isUnderLocalPublicSuffix(name)` next to the
  summary, from `VITE_APP_LOCAL_PUBLIC_SUFFIXES`, mirroring §2.2.
  `DomainSetup.hasAutomaticDelegationMaintenance` stays as it is: it means
  "auto-delegated", which the server does only for immediate children
  (`Domain.is_locally_registrable`), so broadening it would claim "fully
  configured" for deeper domains whose delegation nobody maintains. Both
  predicates move into one module so the difference is visible.
- **After a re-check** the row's `status` is replaced; if it turned secure or
  lost secure status, `auth/account/` is fetched again so that `limit_domains`
  and `secure_domains` update.
- **On phones** (Vuetify's `xs`), a fourth column would push the row's actions
  out of view (560 px of table in 334 px). So there, the chip shows its icon
  only (label in the tooltip and `aria-label`), the Published column is hidden,
  and the re-check action is left to the setup instructions dialog, which has
  the explanation that a tooltip cannot give on touch screens. That brings the
  table back to its previous width (355 px, from 350).

### 4.3 `CrudList.vue` changes this needs

Small and generic, so they stay out of the domain view:

- `cellUsesPlainText()` special-cases `TimeAgo` today. A column flag (e.g.
  `richReadonly: true`) generalizes it, so read-only display components render.
- `getActions()` takes the row, and an action's `if` may be a function of it,
  so the re-check action can be hidden per row rather than disabled.
- `filterSearchableCols()` skips object values; otherwise a search for
  "object" matches every row via `[object Object]`.
- A `hideOnXs` column flag, for §4.2's phone layout.
- Row actions may have a `loading` function, which disables the button and
  shows a spinner.
- A notification snackbar (`notify(text, color)`) alongside the existing one,
  which is for errors only.
- Sorting keeps the previous order among ties: clicking a column makes it the
  primary sort column, followed by the previous ones, and clicking the primary
  column again reverses it (`updateSortBy()`, with Vuetify's `multi-sort` for
  the numbered badges that show each column's rank). Users thus choose whether
  domains in the same delegation state are ordered by name or by publication.

### 4.4 Re-check flow, and what is shown meanwhile

One module (`src/delegationCheck.js`), used by both list and details:

1. `POST …/status/`. On `200`, show the returned state; done.
   On `202`, keep `requested`.
2. Poll `GET …/status/` at 2, 3, 5, 8, 13 s, then every 15 s, until
   `checked >= requested`, for at most 90 s.
3. On timeout: restore the previous state, and say "The check is taking longer
   than expected. It will finish in the background; reload later." A resolver
   outage is recorded as a failed check (§3.2) and ends the poll, so a timeout
   means a slow check, or one lost with the worker.
4. `503` surfaces through the error snackbar. `429` names the wait instead
   ("You can re-check example.com again in 40 seconds.", from `Retry-After`), as
   a notification rather than an error.

Requests go out directly, not through `withWorking()`, which would disable
the whole page for as long as the poll runs.

**While the check runs:**

- **List:** the chip reads "Checking…" with a small spinner in place of its
  icon; its tooltip keeps the previous result ("Before: No DNSSEC, checked 3
  hours ago"). The row's re-check button is disabled.
- **Details:** the status block shows "Checking… This usually takes a few
  seconds." with an indeterminate progress bar; the previous result stays
  visible beneath it, dimmed; the button is disabled.

**When the result arrives:**

- The chip or block shows the new state, "checked just now". Unchanged is
  confirmed by that alone.
- Turned secure: success snackbar "example.com is now securely delegated. Your
  domain limit has grown to 7." Lost secure status: warning snackbar
  "example.com is no longer securely delegated. Your domain limit has dropped
  to 4." Both after `auth/account/` is fetched again, and the second sentence
  only when the limit changed, which it does not for a limit set by support.
  The domain name and the limit are bold (notifications are rendered as HTML).
- Check not completed (`error` in either status): warning snackbar "We could
  not complete the check of example.com. Please try again in a few minutes."
- Leaving the page stops the polling; the check completes server-side, and the
  next load shows it.

Polls count against `dns_api_cheap` (50/min), at up to 6 per minute and
re-check. §3.3 does not keep re-checks from overlapping (an account may start
30 within a minute), so a throttled poll (`429`) is repeated after its
`Retry-After` (else after 15 s), within the 90 s. Only a throttled re-check
request reaches the user as a notification.

### 4.5 Details (optional)

**Setup instructions dialog** (`DomainSetupDialog.vue`): a status block above
the instructions, with the summary, the longer text (`details`, e.g. §4.1's
text for `insecure`, which names the observed nameservers when they are not
ours), when the domain was last checked, the re-check button, and for
`insecure` the "Copy request" button. The instructions are the remedy, so this
is where the status helps most. The block goes into the dialog, not into
`DomainSetup.vue`, which is also rendered on the post-signup page
(`DomainSetupPage.vue`) where there is no status yet. For local domains, it
shows their summary (§4.1) without the re-check button. Not shown right after
creating a domain, which cannot be delegated yet.

The dialog receives the row itself and the list's map of checks under way, and
asks the list to re-check (a `recheck` event), so that a re-check started in
either place shows in both. The text of the block is in the default text color:
long text in a tonal alert's color is hard to read.

Not on the records page.

### 4.6 The create dialog

`auth/account/` already returns `secure_domains` (`s`), added for exactly this
(limits §4) and unused so far (limits §13).

- **Below the limit**, the existing line gains the count: "You have 2 of 7
  domains left. 4 of your 5 domains are correctly delegated, with DNSSEC
  enabled (see *Delegation* column). Each domain you secure raises your limit."
- **At the limit**, the warning reads: "Domain limit reached. 4 of your 7
  domains are correctly delegated, with DNSSEC enabled (see *Delegation*
  column). Securing another one will raise your limit." The counts are bold.
  (The warning is rendered as HTML, like the dialog's other texts.)

Without domains, or before the account is loaded, the previous generic
sentence stays.

## 5. Testing

**API** (`test_domains.py`, new `test_domain_status.py`):

- The exact key set in `test_retrieve_my_domain`, and the field list in
  `test_create_domains`, gain `status`.
- Serializer, one case per state: never checked; secure; secure followed by an
  `ERROR` check (`secure_since` kept, statuses read `error`); each conclusive
  non-secure outcome; `SECURE` + `NOT_DELEGATED` serializes `security_status`
  as null.
- Parity of `is_under_local_public_suffix` with `under_local_public_suffix_q()`
  (§2.2).
- Query count for the list (§2.3).
- §3.1: `202` enqueues on the ad-hoc queue with `max_age=0` (mock
  `apply_async`, assert the queue, as limits §10 does for the planner); fresh
  check → `200` and no enqueue, also for a secure domain; a secure domain →
  `202`, also with an `ERROR` latest check; local domain → `200` and no
  enqueue; foreign domain → `404`; an API token, even with
  `perm_create_domain`, → `403` on `POST`, `200` on `GET`, and its `403` does
  not consume the throttle budget,
  while a `200` does; both throttles, each rate → `429`; broker failure → `503`; `GET` makes no pdns request (`assertRequests` with none);
  other methods → `405`. The tests for the permission, the ad-hoc queue and the
  account-wide rate were checked by mutating the source and confirming that
  they fail.
- §3.2: with `record_failure`, a resolver failure is recorded as `ERROR` for
  both statuses, keeping `secure_delegation_since`; without it, nothing is
  recorded.

**Webapp** (vitest):

- `delegationSummary()` against every row of §4.1, including the two
  orderings, the local-suffix predicates, and `compareBySecurity()`'s order.
- The polling module, with a mocked HTTP client and a recorded `sleep`: `200`
  short-circuit, completion, timeout, stopping, throttled polls waited out
  (or given up on past the timeout), other errors passed on.
- `DelegationStatus.vue`: chip, "Checking…", "Secure" for local domains, icon
  only on phones, not disabled with the row.
- `CrudListDomain.vue`, mounted with the API mocked: statuses per row, where
  the re-check action shows (and not on phones), a re-check that turns the
  domain secure or not secure updating the row and the limit (mentioned only
  when it changed), a re-check that could not be completed, a throttled
  re-check, the create-dialog texts, the search fix, and sorting that keeps
  the previous order among ties.
- `DomainSetupDialog.vue`: the status block, the `recheck` event, following a
  re-check under way, copying the registrar request, the block for local
  domains, and when the block is not shown.

`src/test/setup.js` gains a `visualViewport` stub, which Vuetify's overlays
(snackbars) need under jsdom. `npm run lint`, and the production build.

**Integration**: none. An end-to-end test needs the local-root e2e2 setup that
checker §8 proposes and that does not exist yet.

## 6. Files touched

    api/desecapi/models/domains.py                is_under_local_public_suffix
    api/desecapi/serializers/domains.py           status field
    api/desecapi/views/domains.py                 select_related, status action,
                                                  permissions, throttles
    api/desecapi/throttling.py                    account-scoped throttle subclass
    api/desecapi/tasks.py                         enqueue_domain_delegation_check
    api/api/settings.py                           two throttle scopes
    api/desecapi/tests/test_domains.py            key sets
    api/desecapi/tests/test_domain_status.py      new
    docs/dns/domains.rst                          status field and endpoint
    docs/rate-limits.rst                          two rows
    www/webapp/src/delegation.js (+ .spec.js)     new: summary, local-suffix predicates
    www/webapp/src/delegationCheck.js (+ .spec.js) new
    www/webapp/src/components/Field/DelegationStatus.vue (+ .spec.js)  new
    www/webapp/src/views/CrudList.vue             rich read-only cells, phone columns,
                                                  per-row actions, search fix,
                                                  notification snackbar
    www/webapp/src/views/CrudListDomain.vue (+ .spec.js)  column, action, create dialog
    www/webapp/src/views/DomainSetup.vue          predicate moved to delegation.js
    www/webapp/src/views/Console/DomainSetupDialog.vue (+ .spec.js)  status block
    www/webapp/src/test/setup.js                  visualViewport stub
    docs/design-plans/PLAN-limit_domains.md       §13: point here for the picked-up items

## 7. Commits

Matching the repository's conventional-commit scopes:

1. `docs: delegation status display & re-check design`
2. `feat(api): expose delegation status on domains` (§2)
3. `feat(api): let users request a delegation re-check` (§3)
4. `feat(webapp): show delegation status in the domain list` (§4.1–4.3)
5. `feat(webapp): re-check a domain's delegation` (§4.4)
6. `feat(webapp): explain the domain limit with secure_domains` (§4.6)
7. `feat(webapp): show delegation status with the setup instructions` (§4.5)

Each API commit carries its docs and tests.

## 8. Deferred

- **Re-checking all of a user's unsecured domains.** Could be done via
  `POST /domains/*/status/`, running the planner the triggers use
  (`enqueue_user_delegation_check`: 1/min dedup, 15-minute freshness filter, 20
  domains, limits §6.3). Whether that is the best design is open.
  What makes it worth having: the limit-denial trigger (limits §7.3) fires only
  when a create is refused with `403`, and the webapp never sends that request,
  as it disables the create form at the limit (`createInhibited`). For webapp
  users, the moment the incentive turns on therefore triggers nothing until the
  next sweep. With such an endpoint, the create dialog would call it on opening
  at the limit, and enable the form if the limit went up.
- **Pinned limits.** "Each one you secure raises your limit" is false for
  accounts whose limit support has pinned, and the existing create-dialog text
  makes the same claim. The API cannot tell clients (`limit_domains` is the
  effective value).
- **Showing that a re-check is pending across reloads.** Would need the request
  remembered server-side (a short-lived cache entry per domain, read in bulk for
  the list).
- **Re-checks with API tokens.** If it turns out that automation cannot work
  reasonably without re-checks (say, a script that hands DS records to a
  registrar's API and needs the raised limit before the next sweep), `POST` may
  accept API tokens with `perm_create_domain` instead of requiring a login
  token (§3.4), which is the permission the other triggers require. The
  per-account rate (§3.3) then still bounds the queue. Preferable, though, is
  for parents to provision DS records themselves: by processing CDS/CDNSKEY
  (RFC 7344, RFC 8078, and RFC 9615 for bootstrapping), prompted by generalized
  NOTIFY (RFC 9859), so that no user automation is involved.
