# Automatic Domain Limits & Scheduled Delegation Checks

Turning a user's intention to create another domain into an incentive to enable
DNSSEC: the domain limit is no longer a fixed number handed out by support, but
a function of how many domains the user has actually delegated to us securely.

Builds on the checks described in `PLAN.md` (status: implemented). Nothing here
changes how a check is *measured*; it changes when checks run and what their
outcomes are used for.

Status: **implemented**, as described below. §12 records the decisions that
shaped it; §13 lists what is deliberately deferred.

## 1. Goal

Two changes, in this order:

1. **A computed limit.** When `User.limit_domains` is `NULL`, the enforced
   limit is derived from the number of the user's securely delegated domains.
   An explicit value keeps overriding it, so support decisions stand.
2. **Checks that run on their own.** A Celery worker for delegation checks, fed
   both by a recurring sweep and by ad-hoc requests for a single user's
   domains, so that the computed limit reflects reality without anyone running
   a command.

The incentive only works if the two are close together in time: a user who
fixes their DS records and comes back to create a domain should find the limit
already raised. That is what §6's task granularity is for.

## 2. The formula

With `s` = the number of the user's securely delegated domains and `e` ⊆ `s`
the externally delegated ones (i.e. everything but the locally registrable):

    limit = s + max(DOMAIN_LIMIT_INSECURE_HEADROOM, round(sqrt(e)))

| `s` = `e` | 0 | 1 | 2 | 3 | 5 | 7 | 12 | 13 | 20 | 21 | 30 | 50 | 100 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| limit | 1 | 2 | 3 | 5 | 7 | 10 | 15 | 17 | 24 | 26 | 35 | 57 | 110 |

(with the floor at 1; at the production floor every row gains that floor minus
`round(sqrt(e))`, never less than zero.)

**Two terms, counting different things.** Every securely delegated domain pays
for its own slot — that is the `s`. The headroom on top is how many domains may
be held *without* being secured, and only externally delegated domains earn it.

The earned part of the headroom is sublinear on purpose: once it clears the
floor it is `1/(1+sqrt(e))` of the limit, which decreases monotonically, so the
incentive does not dilute as a portfolio grows. Securing one more external
domain always raises the limit, by 1 or 2 — never by 0, so progress is always
visible.

`LIMIT_USER_DOMAIN_COUNT_DEFAULT` is renamed to
`DOMAIN_LIMIT_INSECURE_HEADROOM`, which is what it now is: the floor of the
headroom rather than the value handed to new users. It keeps its meaning for a
fresh account ("how many domains you get before demonstrating anything": at
`s = 0` the limit is exactly it), its env var
(`DESECSTACK_API_LIMIT_USER_DOMAIN_COUNT_DEFAULT`, default 1), and its role in
the test settings, where it is 15. Flooring the headroom rather than the limit
means securing a domain always raises the limit, from the first one on.

`round()` is Python's banker's rounding, which differs from half-up only at
exactly `.5`. `sqrt(e)` is irrational for every non-square `e` and an integer
for every square one, so the tie never occurs. Worth a comment at the call
site, not worth an integer-only reimplementation.

### 2.1 Why locally registrable domains count towards `s` but not `e`

Domains under `dedyn.<domain>`, at any depth, are securely delegated: every zone
between them and the public root is one we host and sign, so their chain of
trust is ours end to end. They therefore count towards `s` — making a user's
dedyn.io domain crowd out quota they earned elsewhere would penalise them for a
delegation that is in perfect order.

They must not count towards `e`. The headroom is what an account gets for
securing a delegation it had to configure; a domain that arrives secure had
none to configure, so it moves `s` and the limit by exactly its own slot and
earns nothing on top.

With the split, a dedyn.io-only account sits at `limit = n + floor`: each name
pays for its own slot and the account keeps the free slots it started with, but
earns none. A domain under our own suffix arrives secure and needs no headroom,
so it is not owed any.

That still leaves free names as a cheap way to inflate `s`, which is why §4 caps
them at one per account.

## 3. Where `s` comes from

### 3.1 A new field, not a query over check history

`Domain.current_delegation_check` points at the newest check, whatever its
outcome. Counting `s` off it directly would mean that a resolver outage — which
records `ERROR` — silently reduces every affected user's limit. The requirement
is the opposite: errors must never count against a user.

So: a new nullable field, maintained by `DelegationCheckManager.record()`.

    Domain.secure_delegation_since = models.DateTimeField(null=True, blank=True)

Set in `record()` from the *result being recorded*, in three cases:

| result | `secure_delegation_since` |
|---|---|
| `SECURE` + `CORRECTLY_DELEGATED` | set to the check's `created`, if currently `NULL`; otherwise left alone |
| conclusive, but not the above | set to `NULL` |
| either status is `ERROR` | **left untouched** |

"Conclusive" means neither dimension is `ERROR`. `INSECURE`, `MISCONFIGURED`,
`NOT_DELEGATED` and `OTHER_PROVIDER` are all statements about the domain and
therefore clear the field; `ERROR` is a statement about our ability to check,
and changes nothing.

This gives error-immunity by construction, in one place, without suppressing
any history: `current_delegation_check` still records the `ERROR` honestly, and
the UI can say "secure since X; we could not re-check it today", which is more
useful than either field alone.

Preserving the *original* transition time (rather than bumping it on every
confirmation) makes the field mean "secure since", which is what a later
hysteresis rule ("secure for at least 7 days") would need, and what the webapp
would want to display.

### 3.2 No freshness window

`s` counts domains with `secure_delegation_since IS NOT NULL`, with no maximum
age. The alternative — requiring a check newer than N days — sounds safer but
inverts the failure mode: if the sweep stops running, every limit collapses at
once. Without a window, a stalled sweep freezes limits instead, which is the
direction to fail in. Staleness is an operations problem; §9 explains why it
does not currently have a metric.

### 3.3 The query

One `DomainQuerySet` method carries the definition:

    def securely_delegated(self):
        return self.filter(
            under_local_public_suffix_q() | Q(secure_delegation_since__isnull=False)
        )

    User.secure_domain_count          = domains.securely_delegated().count()
    User.secure_external_domain_count = domains.securely_delegated()
                                               .exclude_under_local_public_suffix()
                                               .count()

An OR rather than a union, because the two sets overlap: a
`check-delegation --include-local` run sets `secure_delegation_since` on domains
under our own public suffixes too, and they must not be counted twice. Those
domains are otherwise never measured — nothing a check could report about them
is news — which is why the sweep and the ad-hoc planner both skip them.

The predicate is `under_local_public_suffix_q()` in `models/domains.py`, which
the command, the planner tasks and these counts all share. It matches at any
depth, and is therefore deliberately broader than
`Domain.is_locally_registrable`, which stays "immediate child" and drives
auto-delegation.

## 4. Enforcement and API surface

- `User.effective_limit_domains` (property): returns `limit_domains` when it is
  not `NULL`, else the formula. One extra `COUNT` per call.
- `permissions.WithinDomainLimit` compares against it. The current
  `limit_domains is None → unlimited` branch goes away (see §5).
- `UserSerializer.limit_domains` becomes a `SerializerMethodField` returning
  the effective value, so the field keeps its name, its type and its meaning
  for clients. It must be removed from `Meta.read_only_fields` at the same
  time — DRF asserts when a declared field also appears there.
- `docs/auth/account.rst` §`limit_domains` gains a paragraph on automatic
  growth. This is the user-facing half of the incentive, so it is not optional.

- `secure_domains` (i.e. `s`) is exposed as a second read-only field, for the
  webapp's progress display: the UI can say "3 of your domains are securely
  delegated; securing one more raises your limit to 6" instead of only showing
  the resulting number. Without it the incentive is invisible.

`manage.py limit domains <email> <n>` gains the ability to set `NULL` (spelled
`auto`), so support can hand an account back to the automatic rule.

### 4.1 One locally registrable domain per account

`DomainViewSet.perform_create` refuses a second one with `400` and a message
naming the one in the way. It sits next to the existing `REGISTER_LPS` check,
which is the other policy refusal on the same path.

These names are free, and under §2 they raise the limit's base by one each. Even
without earning headroom they would let an account inflate `s` — and hence the
number of *external* domains it may hold — at no cost, simply by registering
dedyn.io names. One per account removes that entirely, and matches what the
names are for: a dynDNS host, not an inventory.

Only while the limit is computed. An account whose `limit_domains` support has
pinned is exempt: with the limit no longer a function of `s`, inflating `s`
buys nothing, and the pin is already the decision on how much that account may
hold.

Enforced at creation only. Accounts that already hold several keep them; the
rule is about what can be obtained from here on.

## 5. The meaning of `NULL`

`limit_domains IS NULL` used to mean **unlimited**; it now means **automatic**.
That is safe only because no account currently has it: the production count of
`User.objects.filter(limit_domains__isnull=True)` was checked and is zero, so no
grant is silently downgraded and no data migration is needed for it. Had it not
been, those rows would have needed converting to an explicit large value first,
in a separate, earlier deploy.

Migration `0049` therefore only drops the field default, so that *new* users are
on the automatic track. With `s = 0` the formula yields the floor, which is what
they would have been given anyway — so new accounts behave exactly as before.

"Unlimited" no longer has a spelling. Nothing needs one today; a very large
explicit value serves if it ever comes up.

## 6. Task architecture

### 6.1 Can an ad-hoc check interrupt a running sweep?

Not by preemption — Celery has no such thing; `revoke(terminate=True)` kills a
task, which is not what is wanted. The answer is granularity: **there is no long
task to interrupt**. The sweep is not one task that checks 100k domains, it is
100k tasks that check one domain each.

With per-domain tasks, one worker consuming both queues, and
`worker_prefetch_multiplier = 1` together with `task_acks_late = True`, the
worker holds exactly as many unacked messages as it has busy slots. Kombu
round-robins between the queues named in `-Q`, so a waiting ad-hoc message is
picked up as soon as any slot frees. The worst-case wait is therefore **one
check**, not one sweep — typically under two seconds, bounded by the check's own
timeouts at roughly 30s, and hard-capped by `CELERY_TASK_TIME_LIMIT = 300`.

Because ordering across queues is handled by round-robin, RabbitMQ message
priorities are not needed. If strict isolation is ever wanted, splitting into
two worker processes is a compose change, not a code change.

### 6.2 Two tasks, in `desecapi/tasks.py`

    plan_user_delegation_checks(user_id, max_age)  queue: delegation_adhoc
    check_domain_delegation(domain_id, max_age)    queue: as enqueued

- The planner selects IDs and enqueues `check_domain_delegation` on the ad-hoc
  queue. It touches the database only. The bulk side has no planner task: the
  management command fills that role (§7.1).
- `check_domain_delegation` re-reads the domain, returns immediately if its
  check is fresher than `max_age`, else calls `delegation.check()` and
  `DelegationCheck.objects.record()`. This is what makes duplicate enqueues
  harmless: the cost of a redundant message is one indexed read.
- Politeness towards TLD operators is bounded by worker concurrency (`-c 8`),
  twice what `check-delegation --concurrency 4` does by default; the checks
  wait on the network, so this is about how many queries parents see at once,
  not about CPU. No Celery `rate_limit`, which would be shared between bulk and
  ad-hoc anyway since they are the same task name.

  Prefork, not `-P threads`: the thread pool ignores the timeout that
  `CELERY_TASK_TIME_LIMIT = 300` sets (`celery/concurrency/thread.py` drops it
  in `on_apply()`), and the cap is what bounds an ad-hoc check's wait in §6.1.
  A thread per check would save the memory of a process per check, which at
  this concurrency is not what we are short of; the database connection each
  slot holds is the same either way.
- Both are `acks_late`, per task rather than as a global setting: the email
  lanes share this Celery app, and at-least-once delivery is right for a check
  and wrong for a message that has already gone out.
- `unbound.UnboundException` from a check means our resolver is unavailable,
  which says nothing about the domain. The task logs and returns rather than
  failing: failing would mail admins once per domain in the backlog, and the
  failure is already counted in `desecapi_delegation_check_failure` where it
  happens.

`api/api/celery.py` hardcodes `include="desecapi.mail_backends"`. Django's
`autodiscover_tasks()` would find `desecapi/tasks.py` anyway, but the include
list should name it explicitly, both to be honest and because the mail module
being named there sets the precedent.

### 6.3 Resolving the domain list at run time

Neither planner ever receives a list of domains — only a `user_id` or nothing
at all. The set is resolved inside the task, because it can change between
enqueueing and running (the ad-hoc trigger of §7.2 fires precisely when a user
is creating domains).

`plan_user_delegation_checks` selects:

    user.domains
        .exclude_under_local_public_suffix()
        .filter(secure_delegation_since__isnull=True)          # not secure, or unknown
        .filter(Q(current_delegation_check__isnull=True)
                | Q(current_delegation_check__checked__lt=now - max_age))
        .order_by(F("current_delegation_check__checked").asc(nulls_first=True))
        [:MAX_ADHOC_DOMAINS]

The first filter is exactly "not yet securely delegated to us, or unknown" —
one predicate, because `secure_delegation_since` is `NULL` in both cases. The
cap (20) keeps one user with a large portfolio from monopolising the ad-hoc
queue; the ordering makes repeated triggers work through the backlog.

**Deduplication** at enqueue time, via the memcached that the worker already
reaches on `rearapi_celery`:

    if cache.add(f"delegation-adhoc-{user.pk}", True, timeout=60):
        plan_user_delegation_checks.delay(user.pk, max_age=900)

One ad-hoc plan per user per minute, regardless of how many triggers fire. This
is the primary defence against the abuse vector in §7.2.

## 7. Scheduling and triggers

### 7.1 The recurring sweep — cron, not beat

Celery *can* do it: `celery -A api beat` with `CELERY_BEAT_SCHEDULE`, in its own
container, with a writable schedule file (`--schedule` on a tmpfs) and exactly
one instance running.

Recommended instead: `--concurrency 0` on `check-delegation`, which makes the
command enqueue `check_domain_delegation` per selected domain rather than
running checks inline, plus one line in `api/cronhook/crontab`:

    23 */2 * * * … manage.py check-delegation --stale 79200 --concurrency 0

**Two-hourly at 22 hours, not nightly at 24.** A run selects what is already
stale, so with period `P` and threshold `S` a domain is actually re-checked
somewhere in `[S, S + P]` — the sweep can only ever be late, never early. Two
consequences.

First, `S` must be *below* the intended ceiling, not equal to it. A nightly run
with `--stale 86400` sets `S = P`: a domain checked minutes after one night's
run is minutes short of stale at the next one and is skipped, so its interval is
`2 × 24 h`. Every domain lands on a 48-hour cadence rather than the intended 24.
Choosing `S = 86400 − P` closes the gap by construction: with `P = 2 h` and
`S = 79200`, the interval is in `[22 h, 24 h]` and 24 hours is a ceiling that
holds, not a target it drifts past.

Second, a short period spreads the work. Each run picks up only what crossed the
threshold in the last two hours, so after a settling period the inventory
distributes itself across the twelve daily runs instead of arriving as one
nightly burst that a four-slot worker needs hours to drain.

Reasons: the crontab already exists and is where periodic maintenance lives
(`chores`, `check-secondaries`, `scavenge-unused`); no extra container, no
schedule-file state, no split-brain risk from two beats; and the command's
selection logic — `--stale`, the locally-registrable exclusion, explicit domain
names — is reused verbatim instead of being restated in a beat schedule. The
command keeps working inline without the flag, which is what an operator wants
when debugging a single domain.

A separate bulk planner task is therefore not needed and does not exist: the
command is the planner.

Enqueueing a full sweep produces one small message per stale domain. RabbitMQ
handles that comfortably, and the freshness re-check in §6.2 means a later run
re-enqueueing a not-yet-drained backlog costs reads, not checks.

### 7.2 On domain creation

In `DomainViewSet.perform_create`, after the transaction commits:

    transaction.on_commit(lambda: enqueue_user_delegation_check(user, max_age=900))

`on_commit` matters: the task must not observe a half-written domain, and the
worker runs in a different process against the same database.

The domain just created is almost always `NOT_DELEGATED` — the user has not
configured anything yet — so checking it is nearly wasted. The point is the
*other* domains: creating a domain is the moment the user is thinking about
delegation, and re-measuring their existing insecure ones is what can raise the
limit before they hit it. The `max_age=900` filter and the §6.3 cap keep the
waste bounded.

**Abuse vector**: domain create/delete in a loop would otherwise generate
outbound DNS load at third-party nameservers on demand. Four things bound it —
the per-user dedup lock (1/min), the 1h freshness filter, the 20-domain cap per
plan, and the existing `dns_api_expensive` throttle scope on domain creation.
Worth stating in the commit message; worth a test for the lock.

### 7.3 On limit denial

The single highest-value trigger: the user is at the wall *right now*. The same
enqueue fires when `WithinDomainLimit` denies a create, and its message no
longer says only "contact support" — it says the domains are being re-checked
and what actually raises the limit.

A DRF permission must not have side effects, so the hook is in
`DomainViewSet.permission_denied()`, keyed on a `code` the permission carries
(DRF passes `permission.code` through to that method), not in `permissions.py`.

## 8. Compose and networking

New service `celery-delegation`, modelled on `celery-email`:

    command: celery -A api worker -Q delegation_adhoc,delegation_bulk -c 8
             -n delegation --prefetch-multiplier 1 -l info --uid nobody --gid nogroup
    networks: rearapi_celery, rearapi_dbapi, rearapi_unbound (static .9.12)
    depends_on: dbapi, rabbitmq
    environment: mirror the `api` service's block

Three constraints, all from `PLAN.md` §11:

- **`rearapi_unbound` is required twice over.** The worker talks to the
  resolver *and* queries parent nameservers directly on port 53; that bridge's
  NAT is what provides egress. A worker on `rearapi_celery` alone would fail
  every check.
- **No ACL change needed.** `unbound.conf.var` allows the whole
  `${PREFIX}.9.0/24`, so a third member of that network is already permitted.
- **Do not add `depends_on: unbound`, and do not add `celery-delegation` to
  `api.depends_on`.** Building unbound from source takes ~4 minutes; the
  `test-api` and `test-missing-migrations` CI jobs run `docker compose run api`,
  which starts `api`'s dependencies — `celery-email` is one of them today. Keeping
  the delegation worker out of that graph keeps the unbound build out of CI.

Also: `docker-compose.dev.yml` gains a `json-file` logging override for the new
service, matching every other service there. `README.md`'s service list gains a
row. No new `DESECSTACK_*` variables — intervals and caps are Django settings
constants.

## 9. Metrics

**None.** The three counters designed in `PLAN.md` §6 are not implemented — the
commit that would have introduced them no longer does — and the planned
`desecapi_delegation_check_enqueued` was never worth adding. `PLAN.md` §6 is
left standing as the design it was; this section is why none of it shipped.

Prometheus scrapes exactly one target for this stack's Django code, `api:8080`,
and `prometheus_multiproc_dir` is set in one place, `uwsgi.ini` — so only the
uwsgi worker processes export anything. A delegation check runs in neither: the
sweep runs in cron (which does not inherit that variable), and every check now
runs in `celery-delegation`, a container that is not a scrape target, has no
exporter, and is not even on `rearmonitoring_api`. Every counter here would have
been incremented into a file nobody reads.

That also kills the argument this section used to make against a "how many
domains are secure" gauge — that `desecapi_delegation_check_total` going flat
says the same thing, so alert on the counter instead. It does not say it, and
there is nothing to alert on. Instrumenting this properly means either giving
the worker an exporter and a monitoring network, or writing progress to a table
the api container can read. Deferred (§13); until then `delegation.py` logs, and
`DelegationCheck` rows are the record of what was measured and when.

## 10. Testing

New `api/desecapi/tests/test_domain_limits.py` (39 tests), plus additions to
`test_delegation.py`, `test_limit.py` and `test_domains.py`:

- **Formula** — table test against the §2 table, including the floor and the
  `DOMAIN_LIMIT_INSECURE_HEADROOM` override, plus a sweep over `s = 0…100`
  asserting every step raises the limit by 1 or 2 — the property the whole
  choice of `round(sqrt(s))` rests on.
- **Backfill** — the `0049` data migration is run against real rows (its
  function takes the app registry, so the live one can be passed in). It runs
  once, in production, and its `Subquery` is the kind of thing that compiles
  fine against an empty table.
- **Error immunity** — record `SECURE`/`CORRECTLY_DELEGATED`, then an `ERROR`
  result; assert `secure_delegation_since` and `s` are unchanged while
  `current_delegation_check` did move. This is the requirement most likely to
  regress silently.
- **Transitions** — each conclusive non-secure status clears the field; a
  repeated secure result does not bump it.
- **Enforcement** — creating past the computed limit is 403; marking a domain
  secure and retrying succeeds. `limit_domains` set explicitly still wins.
- **Serializer** — `limit_domains` reports the effective value, stays
  read-only.
- **Under a local public suffix** — they count towards `s` without ever having
  been measured, at any depth, and measuring one anyway does not count it
  twice. They earn no headroom: swept over `n = 1…39`, a user holding only such
  domains has `limit == n + floor`, i.e. each one moves the limit by exactly its
  own slot.
- **One per account** (`test_domains.py`) — the second one is a 400 that names
  the domain in the way and creates nothing; after deleting it, registration
  works again; the ordinary domain limit still applies alongside; an account
  with a pinned `limit_domains` may register a second one.
- **Command** — `limit domains <email> auto` clears the pin and the account
  falls back to the computed limit; pinning it again still works.
- **Tasks** — the planner resolves domains at call time, not at enqueue time
  (the enqueue is mocked, the domain set is changed, *then* the task is run with
  the captured arguments — a test that merely calls the task cannot show this);
  it enqueues on the **ad-hoc** queue and passes `max_age` through, which is the
  point of §6.1 and would otherwise regress silently; it orders least recently
  checked first, with never-checked domains ahead of those (`checked` is set
  explicitly via `queryset.update()`, since `auto_now` would make the order
  depend on how fast the loop runs); the per-domain task skips a fresh domain
  without calling `delegation.check`; the dedup lock suppresses a second enqueue
  within the window; neither a deleted user nor a malformed `user_id` is an
  incident.
- **Trigger** — domain creation enqueues exactly one plan, and does so after
  commit: the mock is asserted *uncalled* inside `captureOnCommitCallbacks`
  before the block exits, which is the only way the test distinguishes an
  `on_commit` registration from a direct call.
- **Enqueue failures** — a dead broker and a dead cache each make
  `enqueue_user_delegation_check` return `False` rather than raise, because both
  triggers sit in the request path.

Three of the assertions that carry the design — `on_commit`, the ad-hoc queue,
and the `ValidationError` guard — were checked by mutating the source and
confirming the corresponding test fails.

Test settings must not reach a broker. `settings_quick_test.py` gets
`CELERY_BROKER_URL = "memory://"`; tasks are asserted via mocks on `.delay`
rather than by enabling `task_always_eager`, which would run real checks inside
`MockPDNSTestCase` and trip its network interception.

## 11. Files touched

    api/desecapi/models/users.py                    + effective_limit_domains, the two counts, default None
    api/desecapi/models/domains.py                  + secure_delegation_since, queryset helpers
    api/desecapi/models/delegation.py               record() maintains the new field
    api/desecapi/tasks.py                           new
    api/desecapi/permissions.py                     WithinDomainLimit
    api/desecapi/serializers/users.py               limit_domains as method field
    api/desecapi/views/domains.py                   create trigger, permission_denied trigger,
                                                    one locally registrable domain per account
    api/desecapi/tests/test_domains.py              local domain cap, DYN fixtures hold >1
    api/desecapi/management/commands/check-delegation.py  --concurrency 0
    api/desecapi/management/commands/limit.py       accept "auto"
    api/desecapi/migrations/0049_*.py               new field, backfill, User default
    api/api/celery.py                               include desecapi.tasks
    api/api/settings_quick_test.py                  memory:// broker
    api/cronhook/crontab                            2-hourly --stale 79200 --concurrency 0
    api/desecapi/metrics.py                         - delegation check metrics (§9)
    api/desecapi/delegation.py                      - metric call sites, log instead
    api/desecapi/views/tokens.py                    override accounts stay on the rule
    api/desecapi/tests/test_limit.py                + "auto"
    api/desecapi/tests/test_domain_limits.py        new
    api/desecapi/tests/test_delegation.py           + --concurrency 0
    api/desecapi/tests/test_user_management.py      + secure_domains in account fields
    docker-compose.yml                              + celery-delegation
    docker-compose.dev.yml                          + logging override
    docs/auth/account.rst                           automatic growth, secure_domains
    docs/dns/domains.rst                            one locally registrable domain per account
    README.md                                       service list

`api/api/settings.py` is untouched: the queue names and caps live in
`desecapi/tasks.py`, prefetch is a worker flag, and `acks_late` is per task.

## 12. Decisions taken

- **Accounts with `limit_domains IS NULL`**: none exist, so `NULL` was
  repurposed from "unlimited" to "automatic" without a conversion (§5).
- **`MULTI_PROVIDER` counts towards `s`.** A validly signed zone that has us
  among several providers is work the user did, and the zone is secure either
  way. `PLAN.md` §10 still defers what "correct" means for multi-signer setups,
  but that question is about how to *display* the status, not about whether the
  user earned the slot. It is one entry in one tuple in
  `DelegationCheckManager._secure_since`, should it need revisiting.
- **Cron, not beat** (§7.1), via `check-delegation --concurrency 0`, every two
  hours at `--stale 79200` rather than nightly at `86400` — a sweep can only be
  late, so the threshold has to sit one period below the intended ceiling (§7.1).
- **The limit-denial trigger ships now** (§7.3): it is the moment the whole
  incentive turns on.
- **The triggers never raise.** `enqueue_user_delegation_check` swallows
  everything and returns `False`. Both call sites are in the request path, and
  the `perform_create` one runs *after* the commit, so a broker or memcached
  outage would otherwise turn a created domain into a 500 and leave the client
  retrying into "name unavailable". A lost check costs nothing — the sweep gets
  the domain within a day. (The email lanes make the opposite trade on purpose:
  a lost message is not recoverable, so a failed enqueue there should fail.)
- **No metrics at all** (§9), rather than counters nothing scrapes.
- **Locally registrable domains count towards `s`, not towards the headroom**
  (§2.1), and are capped at one per account (§4.1). Counting them at all is a
  reversal: they are securely delegated, so excluding them penalised users for a
  delegation that is correct. They earn no headroom, because they arrive secure
  without the user having configured anything.
- **Accounts created through an override token stay on the automatic rule.**
  `views/tokens.py` used to pin them at `limit_domains=15`, which under the new
  meaning of the field would have opted them out of the incentive permanently.
  They now start at the floor like everyone else.

## 13. Deferred

- Hysteresis on losing secure status (`secure_delegation_since` older than N
  days before it counts, or a grace period before `s` drops). The field is
  shaped to allow it; nothing needs it yet.
- Counting distinct registrable names (eTLD+1) rather than domains, against
  quota farming with many cheap subdomains under one registration.
  `Domain.public_suffix` can derive it, at the cost of a PSL lookup per domain —
  affordable in a sweep, not in a request.
- A user-triggered "re-check now" endpoint (`PLAN.md` §7.1). §7.2 and §7.3
  cover the cases that matter for the limit; an explicit endpoint mainly serves
  the status display.
- Surfacing per-domain delegation status on the domain serializer.
- Observability for the checks themselves (§9): either an exporter and a
  monitoring network for `celery-delegation`, or a summary row the api container
  can serve. Until then, "did the sweep run" is a question for the logs and for
  `DelegationCheck.checked`.
- The webapp still says "Contact support to apply for a higher limit"
  (`CrudListDomain.vue`) and does not use `secure_domains`. The API half of the
  incentive is complete; the UI half is not, and the two now disagree.
