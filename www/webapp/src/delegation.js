// What the delegation checks found for a domain, as shown to the user.
// The API's status object is described in docs/dns/domains.rst; the mapping
// below is docs/design-plans/PLAN-delegation_status.md §4.1.
import {
  mdiAlertCircleOutline,
  mdiHelpCircleOutline,
  mdiLinkVariantOff,
  mdiShieldAlert,
  mdiShieldCheck,
  mdiShieldOffOutline,
  mdiSwapHorizontal,
} from '@mdi/js';

function localPublicSuffixes() {
  return (import.meta.env.VITE_APP_LOCAL_PUBLIC_SUFFIXES || '').split(' ').filter(Boolean);
}

/**
 * Whether the domain is below one of our local public suffixes, at any depth.
 * Such domains are delegated and secured by us, never checked, and have no
 * status to show. Mirrors Domain.is_under_local_public_suffix in the API.
 */
export function isUnderLocalPublicSuffix(name, suffixes = localPublicSuffixes()) {
  return suffixes.some(suffix => name.endsWith(`.${suffix}`));
}

/**
 * Whether the domain is an immediate child of a local public suffix, i.e.
 * whether we maintain its delegation ourselves. Unlike the above, this does
 * not hold for deeper names. Mirrors Domain.is_locally_registrable.
 */
export function isLocallyRegistrable(name, suffixes = localPublicSuffixes()) {
  return suffixes.some(suffix => (
      name.split('.').length == suffix.split('.').length + 1
      && name.endsWith(`.${suffix}`)
  ));
}

/**
 * Whether the domain counts as securely delegated, which is what raises the
 * domain limit. secure_since survives failed checks, unlike the statuses.
 */
export function isSecure(status) {
  return !!status?.secure_since;
}

/**
 * Sort order for the domain list: domains holding the limit back first, then
 * by name.
 */
export function compareBySecurity(a, b) {
  const secure = d => (isSecure(d.status) || isUnderLocalPublicSuffix(d.name) ? 1 : 0);
  return secure(a) - secure(b) || a.name.localeCompare(b.name);
}

function formatDate(timestamp) {
  return new Date(timestamp).toLocaleDateString();
}

function nameserverList(status) {
  return (status.nameservers || []).map(ns => ns.replace(/\.$/, '')).join(', ');
}

/**
 * Maps a status object to what the user sees: a state, a short label, a color
 * and an icon, a one-line hint (for tooltips), and the longer explanation
 * (paragraphs, for the setup instructions dialog).
 *
 * First match wins. secure_since goes first because it is error-immune: a
 * domain whose latest check failed is still secure. For undelegated domains,
 * the API reports no security status, so the nameserver status decides.
 */
export function delegationSummary(status, name = 'This domain') {
  const failed = status?.nameserver_status === 'error' || status?.security_status === 'error';

  if (isSecure(status)) {
    const since = formatDate(status.secure_since);
    const details = [`${name} has been securely delegated to deSEC since ${since}.`];
    if (failed) {
      details.push('We could not complete the most recent check, and will retry. Until then, the domain keeps counting as securely delegated.');
    }
    return {
      state: 'secure',
      label: 'Secure',
      color: 'success',
      icon: mdiShieldCheck,
      hint: failed
        ? `Securely delegated since ${since}. We could not complete the most recent check, and will retry.`
        : `Securely delegated since ${since}.`,
      details,
    };
  }

  if (!status?.checked) {
    return {
      state: 'unchecked',
      label: 'Not checked yet',
      color: 'grey',
      icon: mdiHelpCircleOutline,
      hint: 'Not checked yet. Checks run at least daily.',
      details: ['We have not checked this domain yet. Checks run at least once a day, or you can re-check now.'],
    };
  }

  if (status.security_status === 'misconfigured') {
    return {
      state: 'misconfigured',
      label: 'DNSSEC broken',
      color: 'error',
      icon: mdiShieldAlert,
      hint: 'DNSSEC validation fails, so many resolvers cannot resolve this domain. Usually outdated DS records at the registrar.',
      details: [
        `DNSSEC validation fails for ${name}, so resolvers that validate DNSSEC cannot resolve it.`,
        'This is usually caused by outdated DS records at your registrar, for example from a previous DNS provider. Replace them with the DS records below.',
      ],
    };
  }

  if (status.nameserver_status === 'not_delegated') {
    return {
      state: 'not_delegated',
      label: 'Not delegated',
      color: 'grey',
      icon: mdiLinkVariantOff,
      hint: "Not delegated yet. Set deSEC's nameservers at your registrar.",
      details: [`${name} is not delegated yet. Set deSEC's nameservers at your registrar, as described below.`],
    };
  }

  if (status.nameserver_status === 'other_provider') {
    const nameservers = nameserverList(status);
    return {
      state: 'other_provider',
      label: 'Delegated elsewhere',
      color: 'warning',
      icon: mdiSwapHorizontal,
      hint: `Delegated to other nameservers: ${nameservers}.`,
      details: [
        `${name} is delegated to other nameservers: ${nameservers}.`,
        "To use deSEC, replace them with deSEC's nameservers at your registrar, as described below.",
      ],
    };
  }

  if (status.nameserver_status !== 'error' && status.security_status === 'insecure') {
    return {
      state: 'insecure',
      label: 'No DNSSEC',
      color: 'warning',
      icon: mdiShieldOffOutline,
      hint: 'Delegated to deSEC, but not secured. Forward the DS records to your registrar.',
      // The parent may lack the DS, or be unsigned altogether; the check does
      // not tell. Either way, the user's lever is their registrar, and the
      // aim is demand for DNSSEC there rather than an exception here.
      details: [
        `${name} is delegated to deSEC, but the parent zone has no DS records for it. DNSSEC therefore does not protect it yet, and it does not raise your domain limit.`,
        'Forward the DS records below to the organization where you registered the domain (usually your registrar). If they cannot accept DS records, or tell you that DNSSEC is not available for your domain, please ask them to change that. Registrars and registries add DNSSEC support when their customers ask for it.',
      ],
    };
  }

  return {
    state: 'error',
    label: 'Check failed',
    color: 'grey',
    icon: mdiAlertCircleOutline,
    hint: 'We could not complete the last check, and will retry.',
    details: ['We could not complete the most recent check of this domain, and will retry automatically.'],
  };
}
