# Delegation & DS Configuration Checks

How a hosted zone is checked for being correctly delegated to deSEC and
correctly secured (DS records in the parent), and how the outcomes are
recorded.

Status: **implemented**, as described below. §10 lists what is deliberately
deferred; §11 collects operational constraints that are easy to trip over.

## 1. Goal

For a given hosted zone, determine and record two independent dimensions:

- **delegation security status** — is the delegation DNSSEC-secured, insecure,
  or broken?
- **nameserver status** — is the zone delegated to deSEC's nameservers, to
  someone else, or to a mix of both?

Invoked manually for individual domains, via a management command. Running
checks automatically (per account on login, and/or daily for all domains) is
explicitly out of scope for now — see §7.1 for what that would take and why
nothing here forecloses it.

## 2. Measurement approach

Two dimensions, two sources:

- **The nameservers** come from the *parent side* of the delegation — what the
  registry publishes and what a resolver follows. A resolver cannot supply it:
  asked for `<name> NS`, it answers from the child, whose copy of the RRset is
  authoritative but need not agree with the delegation. So the check locates the
  parent zone and asks the parent's servers directly, non-recursively.
- **The security status** comes from a validating resolver of our own, whose
  verdict we read off the AD bit rather than reimplementing validation.

Four steps, at most five queries.

### Step 1 — find the parent, and settle the easy security verdicts

Query `<name> DS` (RD=1, DO=1) through our resolver. The DS RRset, and the proof
that there is none, are served and signed *by the parent*, so a signed parent
names itself: the signer field of any RRSIG in the response is the parent zone.
That also settles where the zone cut is, which need not be one label up.

| Response to `<name> DS`       | parent is           | delegation security status |
| ----------------------------- | ------------------- | -------------------------- |
| NOERROR/NXDOMAIN, has RRSIG   | the RRSIG's signer  | see step 4                 |
| NOERROR/NXDOMAIN, no RRSIG    | the SOA owner       | `INSECURE`                 |
| SERVFAIL + DNSSEC-related EDE | the SOA owner       | `MISCONFIGURED`            |
| SERVFAIL, other/no EDE        | the SOA owner       | `ERROR`                    |
| timeout; other rcode          | — (check ends)      | `ERROR`                    |

An unsigned parent cannot carry a DS, so the delegation cannot be secure and the
status is settled without asking anything else. A SERVFAIL means the chain of
trust is broken above the name, which is conclusive in the same way; the EDE
decides which of the two rows it is.

Where there is no signature to read the parent off, strip one label and query the
resulting name for `SOA` — with CD=1, because we are locating a zone cut, not
judging it, and the reason for being here may well be that validation fails. The
owner name of the SOA in the answer or authority section is the parent. That is
a measurement rather than an assumption: it lands on the zone apex even when the
stripped name is in the middle of a zone (`sub.example.com` → `example.com`).

### Step 2 — the parent's nameservers

Query `<parent> NS` through our resolver, and resolve those names to addresses
(A records; see §11 on IPv6) one at a time — usually the first one answers. At
most three of them, drawn at random: a bulk run then spreads over a TLD's
servers instead of asking the alphabetically first one about every domain.

### Step 3 — the delegation, from the parent

Ask a parent nameserver for `<name> NS`, non-recursively. A referral carries the
delegation in the authority section; a parent whose servers are authoritative
for the child as well answers from the answer section; NXDOMAIN or NODATA means
there is no delegation. A server that times out, refuses or SERVFAILs says
nothing about the delegation, so the next one is asked — at most three in total,
which is what bounds the cost of an unreachable parent. The timeout is 3 s, the
budget a resolver gives a single try rather than a whole lookup, as there is no
resolver in between to retry or to remember what is slow. The query carries
EDNS(0), so that a referral with glue for a dozen nameservers fits into the UDP
response instead of costing a TCP round trip on top.

| Observed NS set                               | nameserver status     |
| --------------------------------------------- | --------------------- |
| non-empty, ⊆ ours                             | `CORRECTLY_DELEGATED` |
| non-empty, intersects ours, has foreign names | `MULTI_PROVIDER`      |
| non-empty, disjoint from ours                 | `OTHER_PROVIDER`      |
| empty (NXDOMAIN / NODATA)                     | `NOT_DELEGATED`       |
| parent or delegation not determinable         | `ERROR`               |

`MULTI_PROVIDER` carries a **TODO** to inspect the DNSSEC configuration in more
detail (multi-signer setups need per-provider DNSKEY/DS analysis, which the AD
bit alone cannot express).

### Step 4 — is the delegation secured?

Reached only when the parent is signed, i.e. when step 1 did not settle the
question. One more query to our resolver, and its AD bit is the verdict:

- **delegated** (step 3 found nameservers): query `<name> CDS`. Answering it
  requires validating the whole chain, DS included. CDS specifically, because
  comparing the child's CDS against the parent's DS is the natural next check to
  add (§10) — when it is added, the response is already there.
- **not delegated**: query `<parent> DNSKEY`. The question then is whether the
  parent is signed — i.e. whether this name *could* be secured at all once it is
  delegated.

| Response                      | delegation security status |
| ----------------------------- | -------------------------- |
| NOERROR/NXDOMAIN, AD=1        | `SECURE`                   |
| NOERROR/NXDOMAIN, AD=0        | `INSECURE`                 |
| SERVFAIL + DNSSEC-related EDE | `MISCONFIGURED`            |
| SERVFAIL, other/no EDE        | `ERROR`                    |
| timeout; other rcode          | `ERROR` (logged)           |

**Why the parent's DNSKEY, and not the parent's denial of the name.** It is
tempting to read the security status of an undelegated name off the AD bit of
the NXDOMAIN it already produced — a signed parent returns a signed proof of
non-existence, after all. That is wrong for most of the DNS: a parent using
NSEC3 **opt-out** cannot prove the non-existence of an unsigned name, so its
denial validates as *insecure* however well the parent itself is signed.
Measured against `.de`, `.com`, `.org` and `.io` (all signed, all opt-out), the
denial comes back AD=0, while `.se`, `.nl`, `.cz` and the root return AD=1. The
DNSKEY question is unaffected by opt-out and is what the status is meant to say.

DNSSEC-related EDE codes (RFC 8914) are 5 *DNSSEC Indeterminate*, 6 *DNSSEC
Bogus*, 7 *Signature Expired*, 8 *Signature Not Yet Valid*, 9 *DNSKEY Missing*,
10 *RRSIGs Missing*, 11 *No Zone Key Bit Set*, 12 *NSEC Missing*. Everything
else (22 *No Reachable Authority*, 23 *Network Error*, …) counts as `ERROR`.
The set lives in one constant so it can be tuned in one place.

Notes:

- The raw NS set is stored on every check, so subset-of-ours-but-incomplete
  (e.g. only `ns1.desec.io` delegated) can be analyzed later without a schema
  change; it is deliberately *not* a separate status value for now.
- When the parent or the delegation cannot be determined, the check ends with
  `nameserver_status = ERROR`, an error logged to stderr and a counter
  incremented (§6). A security status already determined in step 1 is kept —
  "unsigned parent" remains true even if the delegation cannot be read. When
  only step 4 fails, the nameserver status stands and just the security status
  becomes `ERROR`.
- The two dimensions stay orthogonal, so anything counting "secure domains" must
  filter on the nameserver dimension too: an undelegated name below a signed
  parent is recorded as `SECURE` + `NOT_DELEGATED`.

### Cache independence

Each check starts with `flush_delegation <name>` on the resolver, from your
[patched unbound](https://github.com/peterthomassen/unbound/tree/flush-delegation)
(`37c8e65d19` adds `val_neg_remove_ds_denial()`, `407b674c07` adds the
`unbound-control` command on top). It removes SOA/NS/DS/DNSKEY/NSEC/CNAME at
the name, the parent-side copy of the NS RRset, the validator key-cache entry,
and — the part no stock command reaches — the NSEC/NSEC3 records in the parent
that deny the DS. Without the last one, a newly created DS stays invisible
until the denial expires.

Flush **before** each query, not after: a check is then independent of anything
that happened earlier, including a crash between check and cleanup, or a
resolver shared with something else.

Two consequences worth knowing:

- `val_neg_remove_ds_denial()` empties the negative-cache contents of the
  closest zone above the name, i.e. checking `a.example.de` drops the cached
  negative data for `de` as a whole. Correctness is unaffected (it is re-fetched)
  but it costs upstream queries, so keep check concurrency modest.
- Two concurrent checks of the *same* name interfere: each flush throws away
  what the other just fetched, and a check spanning a change can mix the state
  from before it with the state from after. Neither can produce a *stale*
  answer — a flush only ever removes data — but both waste queries. One check
  per domain per run makes this a non-issue; do not parallelize per-name
  retries.

## 3. Where the code lives

Two new flat modules in `api/desecapi/`, matching the existing style
(`pdns.py`, `pch.py`, `dns.py`):

- **`api/desecapi/unbound.py`** — transport. A minimal `unbound-control`
  client and a query helper against our resolver. Querying an authoritative
  server directly (step 3 of §2, which no resolver can answer) has nothing to
  do with unbound, so it goes to the existing `dns.py` instead.
- **`api/desecapi/delegation.py`** — the measurement logic: orchestrates flush
  → parent → delegation → security status, and returns a plain result object
  (`DelegationCheckResult`). It imports `DelegationCheck` for the two status
  vocabularies, but does no ORM work of its own: measuring is separate from
  recording, which is the model's job (§5). The classifier tests run under
  `SimpleTestCase` (§8) to keep it that way.

Rationale for putting this in `desecapi` rather than in a standalone service:
the check needs the `Domain` table, the metrics registry, and (later) the
mail/Celery plumbing — the same reasons `check-secondaries` lives here. The
resolver itself is the only new moving part that has to be its own container.

### Control channel

`unbound-control` speaks a trivial line protocol: connect, send
`UBCT1 <command>\n`, read the text response (`ok` on success). Rather than
installing unbound's tooling into the API image (Alpine + Python), speak it
directly from Python — roughly 30 lines in `unbound.py`.

**Settled: plain TCP**, with `control-use-cert: no` on the private rear
network, so there is no client certificate to generate or distribute into the
API container. Should that ever need to change, the same client works over
`ssl`; only the socket setup differs. Two details of the protocol that the
implementation had to get right: the daemon reads the magic string with a
single six-byte `recv()` and compares it against `"UBCT1 "` including the
trailing space, and it closes the connection after the response, so the client
reads to EOF.

## 4. The resolver service

New compose service `unbound`, built from a new top-level `unbound/` directory
(`Dockerfile`, `conf/unbound.conf.var`, `entrypoint.sh`), following the
`nslord/` layout including `envsubst`-based config templating.

- **Image**: multi-stage build compiling the `flush-delegation` branch, pinned
  by commit SHA (`ARG UNBOUND_COMMIT=407b674c07…`, the branch tip that adds the
  `unbound-control` command), runtime stage on a slim base.
  Everything else in this stack installs distro packages, so this is the one
  place that carries real maintenance burden: the branch has to be rebased onto
  upstream releases. The commits are written in NLnet Labs style, Changelog
  entries and unit test included — if `flush_delegation` lands upstream, switch
  back to a package and drop the build stage.
- **Network**: a new `rearapi_unbound` bridge network (next free subnet,
  `${DESECSTACK_IPV4_REAR_PREFIX16}.9.0/24`), joined only by `api` (`.9.10`)
  and `unbound` (`.9.11`). The resolver must never be reachable from the front
  network — it is an open recursive resolver by design. Recursion needs egress
  to port 53, which the default bridge NAT provides.
- **Config essentials**: `auto-trust-anchor-file` seeded by `unbound-anchor` in
  the entrypoint, in a directory the `unbound` user can write (see §11);
  `ede: yes` (without it the SERVFAIL branch cannot be classified);
  `serve-expired: no`; `prefetch: no`; `qname-minimisation: yes`;
  `access-control` limited to the rear subnet; `remote-control` on
  `control-port: 8953`, bound to the container's rear address (`.9.11`, which
  is why the addresses are static); `num-threads` filled in with the core count
  by the entrypoint, plus `so-reuseport: yes`, because checks are run
  concurrently and a single-threaded resolver would serialize them again.
- **Env**: the service adds no new environment variables. `DESECSTACK_API_UNBOUND_HOST`/`_PORT`
  are not needed (the service name resolves inside compose), and the deSEC
  nameserver set comes from `DESECSTACK_NS` (below).

### Our nameservers

The set a delegation is expected to point at is `settings.DEFAULT_NS` (from
`DESECSTACK_NS`), i.e. the same names we publish in NS RRsets — no separate
setting. Should the two ever need to diverge (a delegation pointing at names we
accept but do not publish, such as `ns.desec.{ch,cz,li}`), `check()` takes the
set as an argument, so adding a setting then is a one-line change.

## 5. Where outcomes are stored

New model in `api/desecapi/models/delegation.py`, exported from
`models/__init__.py` (repo convention):

```python
class DelegationCheck(ExportModelOperationsMixin("DelegationCheck"), models.Model):
    class SecurityStatus(models.IntegerChoices):
        SECURE = 0
        INSECURE = 1
        MISCONFIGURED = 2
        ERROR = 3

    class NameserverStatus(models.IntegerChoices):
        CORRECTLY_DELEGATED = 0
        MULTI_PROVIDER = 1
        OTHER_PROVIDER = 2
        NOT_DELEGATED = 3
        ERROR = 4

    domain = models.ForeignKey(Domain, on_delete=models.CASCADE,
                               related_name="delegation_checks")
    created = models.DateTimeField(auto_now_add=True)   # when this state began
    checked = models.DateTimeField(auto_now=True)       # last confirmation
    security_status = models.IntegerField(choices=SecurityStatus.choices)
    nameserver_status = models.IntegerField(choices=NameserverStatus.choices)
    nameservers = ArrayField(models.CharField(...), default=list)
    ede_code = models.PositiveSmallIntegerField(null=True)
    ede_text = models.TextField(blank=True)
    rcode = models.PositiveSmallIntegerField(null=True)
```

`IntegerChoices`, like `Domain.RenewalState`. Where a name is wanted —
Prometheus labels, (later) API output — it comes from `.name` or `.label`, so
the stored representation stays an implementation detail.

**History as a change log, not an append-only trail.** A daily run over all
domains would otherwise write one row per domain per day forever, almost all of
them identical. Instead: if the newest row for a domain matches the new outcome
(status pair + NS set), just bump `checked`; otherwise insert a new row. You
get "this domain has been `SECURE` since `created`, confirmed at `checked`" and
a compact history of actual transitions. Retention: let the table grow for now;
if it ever becomes a problem, add pruning of rows older than a year to
`chores`. This lives in `DelegationCheck.objects.record(domain, result)`, with
`agrees_with()` defining what "matches" means — deliberately only the status
pair and the NS set, so a changed EDE text or rcode does not start a new state.

**Cheap access to the current state.** For list views (a user's domains), a
per-domain subquery on the history table is an N+1 trap. Add a denormalized
pointer on `Domain`:

```python
current_delegation_check = models.OneToOneField(
    "DelegationCheck", null=True, blank=True, on_delete=models.SET_NULL,
    related_name="+")
```

updated in the same transaction as the check. One migration
(`0047_delegation`) adds the table and the column. `blank=True` is not
cosmetic: `Domain.save()` runs `full_clean()`, which rejects a `None` value on
a field that is merely `null=True`.

## 6. Metrics

Counters in `metrics.py`, incremented in `delegation.py`:

- `desecapi_delegation_check_total{security_status, nameserver_status}`
- `desecapi_delegation_check_failure{reason}` (resolver unreachable, control
  channel error, timeout, and the three inconclusive outcomes of §2: `parent`,
  `delegation`, `security`)
- histogram `desecapi_delegation_check_duration_seconds`, with explicit buckets
  up to 60 s — one control command, up to four resolver queries and up to three
  authoritative ones put the tail well past the 10 s where the default buckets
  stop resolving anything

Prometheus already scrapes the API, so nothing else needs configuring. These
also give the operational signal for whether the resolver container is healthy.

## 7. How it is invoked

In scope: a management command. Everything automated is deferred (§7.1).

`api/desecapi/management/commands/check-delegation.py`, modeled on
`check-secondaries`:

    manage.py check-delegation example.com example.net   # named domains
    manage.py check-delegation --all                     # every domain
    manage.py check-delegation --stale 86400             # not checked in 24h
    manage.py check-delegation --dry-run                 # print, don't store
    manage.py check-delegation --all --include-local     # incl. dedyn.io subdomains
    manage.py check-delegation --all --concurrency 8    # more at a time (default 4)
    manage.py check-delegation --stale 3600 --user foo@example.com   # one account

Prints a line per domain and writes the results. This covers the "check
individual domains" case and doubles as the entry point for everything in §7.1,
so it is the only invocation path that needs building now.

Checks run in a thread pool of `--concurrency` (default 4) — they wait on the
network, so this is about the load our resolver and the parents' nameservers
see, not about CPU. **Measuring happens in the pool, recording does not**:
`delegation.check()` touches no database (§3), so keeping every ORM call on the
main thread spares us per-thread connections and their lifecycle. Domains are
handled in batches of 1000, so a bulk run neither loads the whole inventory into
memory nor creates a future per domain up front, and `map()` preserves order, so
output stays sorted by name.

**Domains under a local public suffix are skipped by default.** Everything
below `dedyn.io`, at any depth, reaches us through zones we host and sign, so a
check measures our own hosting rather than anything the user could get wrong,
and would dominate any bulk run. They are only checked when named explicitly on
the command line, or when `--include-local` is passed to a bulk selector. Named
domains are always checked — the filter applies to `--all`/`--stale`, never to
an explicit argument.

**`--user` narrows whatever was selected** to one account's domains, taking
either a UUID or an email address. Unlike `--include-local` it is a filter and
not a selector: it applies to named domains too, and does not by itself say
which domains to look at, so it wants `--all` or `--stale` alongside it.

### 7.1 Out of scope for now

Deferred deliberately; the design above does not depend on any of it, and the
data the command produces is what should inform these decisions.

- **Celery task and worker.** Celery is configured
  (`CELERY_BROKER_URL = "amqp://rabbitmq"`) but so far only carries email, with
  `app = Celery("api", include="desecapi.mail_backends")` hardcoding the task
  module. Adding `desecapi/tasks.py`, a `delegation` queue and a
  `celery-delegation` worker (same pattern as `celery-email`, plus the
  `rearapi_unbound` network) is the route to bounded-concurrency background
  checks — worth it once checks run continuously, not before.
- **Login trigger.** Enqueueing checks for a user's stale domains on login, so
  the webapp can show something current.
- **Automated runs.** Note these do *not* require Celery: `check-secondaries`
  shows the precedent of a cron entry in `api/cronhook/crontab` calling the
  command directly, which would be the cheapest first step. Whenever it
  happens, the load question decides the shape — every check is at minimum one
  uncached delegation resolution against the parent zone's servers, so a
  full-inventory sweep needs a per-run cap, a `--stale` filter and spreading
  over the day to stay well-behaved towards TLD operators.
- **Surfacing.** Read-only fields on the domain serializer
  (`delegation_status`, `nameserver_status`, `checked`), webapp display, and a
  throttled "re-check now" endpoint.

Keeping the measurement logic free of *task* imports, and free of ORM work of
its own (§3), is what keeps all of these cheap to add later: `delegation.check()`
takes a name and returns a result, so a Celery task, a login hook and a cron
entry can each wrap it without any of them being visible to the others.

## 8. Testing

- **Unit** (`api/desecapi/tests/test_delegation.py`): drive the check with
  synthetic `dns.message` objects, one per step of §2. The fixture describes a
  securely delegated `example.com`, and each test states only the response it
  is about: parent from an RRSIG signer vs. from an SOA lookup, SERVFAIL with
  each EDE code, referral vs. answer vs. NXDOMAIN from the parent's servers,
  mixed NS sets, CDS and DNSKEY with AD set or clear, and every inconclusive
  path. No resolver, no network; the unbound client is mocked. This is where
  the decision tables in §2 are pinned down. These run under `SimpleTestCase`,
  which is what enforces that a check performs no queries (§3).
- **Control-client** test against a socket that speaks the `UBCT1` handshake,
  asserting the exact command string and error handling.
- **Recording and command** tests (`TestCase`): the change-log semantics of
  §5, and the domain selection of §7 — in particular that `--all` skips
  domains under a local public suffix while an explicitly named one is still
  checked.
- **Integration**: **not built**; proposed shape below.

  The natural home is `test/e2e2/`, and the interesting design question is
  where the trust anchor comes from. Rather than pointing the checks at the
  public internet, give the e2e2 `unbound` a **local root**: a root zone served
  by `nslord`/`nsmaster`, `root-hints` pointing at it, and a static
  `trust-anchor:` for its KSK in place of `auto-trust-anchor-file`. Every
  outcome in §2 then becomes constructible and deterministic — delegate a test
  zone with a matching DS (`SECURE`), without one (`INSECURE`), with a
  deliberately wrong one (`MISCONFIGURED`), point it at foreign NS names
  (`OTHER_PROVIDER`, `MULTI_PROVIDER`), or leave it undelegated
  (`NOT_DELEGATED`) — with no internet dependency and nothing to skip in CI.

  It is also the only way to test the reason the patched unbound exists:
  publish a DS *after* a check has already cached the parent's denial of it,
  and assert that the next check sees `SECURE` rather than the stale answer.
  A public-internet variant against third-party zones would be cheaper, but it
  cannot test that at all, and it fails whenever a third party re-signs or
  changes providers.

## 9. Files touched

    unbound/Dockerfile                                  new
    unbound/conf/unbound.conf.var                       new
    unbound/entrypoint.sh                               new
    docker-compose.yml                                  + service, + network
    docker-compose.dev.yml                              + json-file logging
    README.md                                           + service
    api/api/settings.py                                 + resolver host
    api/desecapi/unbound.py                             new
    api/desecapi/dns.py                                 + query_server
    api/desecapi/delegation.py                          new
    api/desecapi/models/delegation.py                   new
    api/desecapi/models/__init__.py                     + export
    api/desecapi/models/domains.py                      + current_delegation_check
    api/desecapi/migrations/0047_delegation.py          new
    api/desecapi/metrics.py                             + counters
    api/desecapi/management/commands/check-delegation.py new
    api/desecapi/tests/test_delegation.py               new

## 10. Deferred until after the first implementation

- `MULTI_PROVIDER`: what "correct" means for multi-signer setups (the TODO from
  your brief; the raw NS set is stored meanwhile, so the data will be there).
- Comparing the child's CDS against the parent's DS, i.e. whether a key rollover
  the child announced has been picked up. Step 4 of §2 already fetches the CDS
  RRset for its own reasons, so this is a question of what to record, not of
  what to measure.
- Upstreaming `flush_delegation`, which would remove the source-build step in
  §4.
- Scheduling policy (daily / on login / both), with the rest of §7.1.

Settled: recording non-delegated domains as `SECURE`/`INSECURE` +
`NOT_DELEGATED` (§2), history retention (§5), skipping locally registrable
domains (§7), not storing DS/DNSKEY details for now — the two status dimensions
plus the NS set are what gets recorded — and the control channel, which runs
plain over the private rear network (§3).

## 11. Operational notes

Five constraints that are easy to trip over and are not visible from the
configuration alone.

- **The trust anchor needs a writable directory of its own.** RFC 5011 updates
  write a temporary file *next to* `root.key`, so the anchor cannot live in the
  read-only config directory; it is in `/opt/unbound/var/`, owned by the
  `unbound` user. `unbound-checkconf` does not catch a violation of this — it
  only shows up as a failure on the first query.
- **`api` does not `depends_on: unbound`.** Building unbound from source takes
  ~4 minutes, and the `test-api` and `test-missing-migrations` CI jobs build a
  subset of images but then run `docker compose run api`, which would drag the
  build in for tests that never touch the resolver. Nothing is lost: `compose
  up` starts the resolver either way, and the command exits with a clean
  `Resolver unavailable` if it is down. `test-e2e2` builds all images, so it
  still pays the four minutes; trimming its image list is an open CI question,
  not a design one.
- **`api` queries the internet on port 53 itself.** Step 3 of §2 goes to the
  parent's nameservers directly, so it is not enough for the *resolver* to have
  egress; the API container needs it too. It already does (the PSL client uses
  it), and the bridge NAT provides it, but a network policy that only whitelists
  the `unbound` container would break the check, not slow it down.
- **Parent nameservers are reached over IPv4.** Their names are resolved to A
  records only, matching the resolver's `do-ip6: no`. A parent whose servers are
  v6-only would end up as `ERROR`; none of the TLDs are, and lifting this means
  querying AAAA as well and knowing that the API container has v6 egress.
- **The §7 filter is a suffix match**, and deliberately broader than
  `Domain.is_locally_registrable` (which is "immediate child of a local public
  suffix" and drives auto-delegation). `sub.mine.dedyn.io` is skipped along with
  `mine.dedyn.io`: both sit in zones we host and sign, so neither has a
  delegation the user could get wrong. A test pins that.
