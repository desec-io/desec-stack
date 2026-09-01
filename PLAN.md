# Automatic delegation of domains within an account

Extend auto-delegation (currently: domains one label under a local public suffix, LPS) to
any domain whose closest existing ancestor domain is either owned by the same account or an
LPS. Delegation records are maintained record-by-record so that non-deSEC `NS`/`DS` records
at the delegation point survive.

Branch: `20260820_auto_delegation`.

## c0 — refuse subdomains underneath a domain registered under an LPS

*(committed second, after c1, whose lookup it uses)*

`Domain.is_registrable()`: reject if the closest existing ancestor domain lies strictly below
this domain's public suffix and that public suffix is an LPS. So with `b.dedyn.io` registered,
neither `x.b.dedyn.io` nor `x.y.b.dedyn.io` can be registered, by anyone; `a.b.dedyn.io`
without an intermediate `b.dedyn.io` stays registrable (its closest ancestor is the LPS
itself). Prevents circumvention of the restrictions on LPS-delegated domains.

Commit message notes the circumvention aspect.

## c1 — closest-ancestor lookup

`DomainManager.parent_zone(name, *, exclude=())` returns the closest ancestor domain present
in the database, built on the existing `filter_qname()`; docstring states that no ownership
check is performed, so callers needing one have to do it themselves. `Domain.parent_zone` is a
plain (uncached) property — creating or deleting an intermediate domain changes the answer
within a single request.

Committed first, since c0 uses it.

## c2 — extend LPS restrictions to everything under an LPS

`Domain.is_locally_registrable` becomes "closest ancestor domain is an LPS", so names like
`a.b.dedyn.io` (no intermediate `b.dedyn.io`) are covered by:

- `REGISTER_LPS` suspension (`views/domains.py`), whose message now names the parent domain,
- the blocked-subnet check on `A` records (`serializers/records.py`), moved to
  `is_under_local_public_suffix` in c8,
- `renewal_state = FRESH` at construction (`models/domains.py`), i.e. scavenging, likewise
  moved in c8.

Pulled along by the same property: the NS-modification lock (`serializers/records.py`,
`views/records.py`), moved to `is_under_local_public_suffix` in c8, and signup's dyndns-token
response (`views/authenticated_actions.py`, unchanged in practice since signup only creates
direct LPS children).

## c3 — record-level delegation maintenance

Replaces `Domain.update_delegation(child)` (wipe and rebuild) with, on the parent:

- `add_delegation(child_name, ds)` — union with existing contents, keeping the existing
  RRset's TTL; creates the RRset with the previous defaults (NS 3600, DS 300) when absent.
- `remove_delegation(child_name, ds)` — `NS` minus `settings.DEFAULT_NS`; if nothing remains,
  the NS and DS RRsets are deleted (a DS at a non-delegation point is invalid, and this also
  clears DS gone stale through key rollover). If foreign NS survive, only `ds` is subtracted
  from the DS RRset, which is deleted when it becomes empty.

Both canonicalize through `RR.canonical_presentation_format()` before the set arithmetic.
`Domain.ds_contents` collects the DS records of a domain's keys. Metrics
`desecapi_autodelegation_created` / `_deleted` are kept. A TODO on the union path records that
joining a delegation carrying foreign NS/DS makes the domain multi-signer (RFC 8901) and that
automating it requires ZSK import/export between the providers.

Still only invoked for LPS parents, so the only visible change is that foreign records survive.

## c4 — delegate into the account's own parent domains

- `Domain.delegation_parent` — `parent_zone` filtered by "same owner, or an LPS".
- `Domain.auto_delegate()` — no-op without an eligible parent; keeps the "currently has no
  keys" `APIException`.
- `Domain.delegation_state()` / `auto_undelegate(state)` — the state is captured *before*
  deletion, since DS records come from pdns and are gone with the zone.
- `Domain.delegation_error()` — reports why a domain cannot be delegated (CNAME at the
  delegation point, or subname too long for `RRset.subname`); raised as a 400 from
  `DomainSerializer.validate_name` instead of failing after the domain was created.

Call sites: `views/domains.py` (create/destroy), `views/authenticated_actions.py`,
`management/commands/scavenge-unused.py`, `tests/base.py`. Token domain policies are bypassed
(system action), as they are today for LPS parents.

## c5 — re-parenting

- `Domain.delegated_children()` — descendant domains whose delegation this domain maintains
  (closest ancestor is this domain, and eligible), computed from a single query.
- On creation, the new domain adopts its descendants' delegations and removes them from the
  domain that delegated them before (`Domain.objects.parent_zone(..., exclude=[self.name])`).
  E.g. an account holding `a.b.dedyn.io` (delegated at `a.b` in `dedyn.io`) that creates
  `b.dedyn.io` ends up with the records at `a` in `b.dedyn.io` and none at `a.b` in `dedyn.io`.
- On deletion, children captured in `delegation_state()` are re-delegated in the next eligible
  ancestor, if any.

## c6 — `manage.py fix-auto-delegations`

Repairs drift, e.g. after rolling out c4/c5. Without arguments, all domains are considered;
otherwise only the given names, each treated both as a parent and as a child name (a name given
as a parent also covers the delegations it maintains). Dry run by default, `--apply` performs
the changes through `PDNSChangeTracker`, one per delegation.

- as child: the delegation parent must carry `settings.DEFAULT_NS` and the domain's current DS
  records at the delegation point,
- as parent: every non-apex NS RRset containing `settings.DEFAULT_NS` must correspond to a
  domain whose delegation parent is this domain — otherwise our NS/DS records are removed
  (this also catches delegations left occluded by a closer domain).

Not part of `api/cronhook/crontab`; operator-invoked.

## c7 — docs and webapp

- `docs/dns/domains.rst`: "Automatic Delegation" section in plain language (no "zone",
  "closest ancestor", "public suffix"), including the note that additional NS/DS records at the
  delegation point mean multi-provider operation and require extra configuration — contact
  support. Cross-referenced from `docs/dns/rrsets.rst`.
- `www/webapp/src/views/DomainSetup.vue`: `hasAutomaticDelegationMaintenance` currently
  pattern-matches "one label under an LPS". It becomes "ends in an LPS, or the account owns a
  parent domain", where the latter is answered by a single
  `GET /api/v1/domains/?owns_qname=<domain minus its first label>` request — `DomainViewSet`
  returns the longest owned match for that query and disables pagination for it, so the
  paginated domain list in the store is not consulted.

## Tests

`tests/base.py` first: ancestor-based `_find_auto_delegation_zone`,
`requests_desec_domain_deletion` gains the child's crypto-keys fetch (before the zone deletes)
and loses its `is_locally_registrable` condition, `DomainOwnerTestCase.setUpPdns` moves to the
new API. Existing dedyn.io auto-delegation tests pass unchanged; `test_create_api_known_domain`
needs the delegation requests, as `www.<my_domain>` is now delegated.

Per commit: c0 refusal cases (owner and third party, one and two labels below); c2 deep-LPS
names hitting suspension, blocked subnets and FRESH; c3 union and survival of foreign records;
c4 one- and multi-label children of an owned parent, CNAME conflict → 400; c5 child-then-parent,
intermediate insertion, parent deletion re-delegating upward; c6 seeded drift, dry run vs apply,
unknown name → error.

## Rollout note

Production may contain grandfathered `x.b.dedyn.io` rows created before c0. They do not resolve
today (no delegation, and the NS lock prevents the owner from creating one), but c4 delegates
them, and under "closest ancestor is an LPS" they escape the blocked-subnet check and stay
`IMMORTAL`. Check for such rows before deploying c4.

## c8 — restrictions that do not depend on which domains exist

`Domain.is_locally_registrable` changes with the domains that exist: once `b.dedyn.io` is
registered, `a.b.dedyn.io` no longer has the LPS as its closest ancestor and sheds the
restrictions (c0 only rules this out for names registered from now on, not for rows created
before it). `Domain.is_under_local_public_suffix` tests the name against
`settings.LOCAL_PUBLIC_SUFFIXES` alone — no database, and false for the LPS itself — and takes
over the blocked-subnet check, the NS-modification lock and the `FRESH` renewal state.
`REGISTER_LPS` and signup's dyndns response keep using `is_locally_registrable`.

Effective retroactively for the blocked-subnet check and the NS lock, which run per RRset
write. The renewal state is only assigned when a domain is created, so grandfathered rows keep
the `renewal_state` they were stored with; correcting those needs a one-off `UPDATE`.
