<template>
  <div>
    <v-card rounded="0" class="pa-md-12 pa-8 elevation-4" style="overflow: hidden">
      <div class="d-none d-md-block triangle-bg">?</div>
      <v-container class="pa-0">
        <v-row align="center">
          <v-col cols="12" md="6" class="py-8 triangle-fg">
            <h1 class="text-h4 font-weight-bold">Frequently Asked Questions</h1>
            <div class="text-subtitle-1 mt-2 py-8 font-weight-regular">
              <p>
                Answers to the questions we are asked most often. Can't find yours? Have a look at our
                <a :href="docs">documentation</a> and our <a href="https://talk.desec.io/">community forum</a>,
                or <a href="#contact-support" @click="followLink">contact support</a>.
              </p>
            </div>
          </v-col>
        </v-row>
      </v-container>
    </v-card>
    <v-container class="py-8 faq" @click="followLink">
      <v-row>
        <v-col cols="12" lg="4">
          <nav class="faq-toc" aria-label="Questions">
            <div v-for="section in sections" :key="section.id" class="mb-4">
              <a :href="`#${section.id}`" class="text-subtitle-1 font-weight-bold">{{ section.title }}</a>
              <ul class="mt-1">
                <li v-for="q in section.questions" :key="q.id"><a :href="`#${q.id}`">{{ q.q }}</a></li>
              </ul>
            </div>
          </nav>
        </v-col>
        <v-col cols="12" lg="8">
          <section v-for="section in sections" :key="section.id" class="mb-6">
            <h2 :id="section.id" class="text-h5 font-weight-bold mb-4">{{ section.title }}</h2>
            <div v-for="q in section.questions" :key="q.id" class="mb-8">
              <h3 :id="q.id" class="text-h6 mb-2 faq-question">
                <a :href="`#${q.id}`">{{ q.q }}</a>
              </h3>
              <div class="faq-answer" v-html="q.a"></div>
              <v-expansion-panels
                  v-if="q.guide"
                  :id="q.guide.id"
                  v-model="openGuides[q.guide.id]"
                  class="mt-4"
              >
                <v-expansion-panel value="guide">
                  <v-expansion-panel-title class="bg-primaryLight4">
                    <span><v-icon :icon="mdiFormatListNumbered" class="mr-2"/>{{ q.guide.title }}</span>
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <div class="faq-answer pt-4" v-html="q.guide.text"></div>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </div>
          </section>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script>
import {mdiFormatListNumbered} from '@mdi/js';
import {headerOffset} from '@/utils';

const docs = 'https://desec.readthedocs.io/en/latest/';

// Each question has a stable id: other pages, the API, and our support replies
// link to them (e.g. /faq/#domain-limit). Rename only with care.
const sections = [
  {
    id: 'limit',
    title: 'Domain limit',
    questions: [
      {
        id: 'domain-limit',
        q: "Why can't I add another domain? How does the domain limit work?",
        a: `
          <p>
            Your domain limit grows with the number of domains you have delegated to deSEC securely, that is, with
            deSEC's nameservers and DNSSEC enabled. Each such domain counts for its own slot. On top of that, you get
            some headroom for domains that are not secured yet: one domain at first, and more as you secure more
            domains (the square root of their number, rounded).
          </p>
          <table>
            <tr><th>Securely delegated domains</th><td>0</td><td>1</td><td>2</td><td>3</td><td>5</td><td>7</td><td>12</td><td>20</td><td>50</td><td>100</td></tr>
            <tr><th>Domain limit</th><td>1</td><td>2</td><td>3</td><td>5</td><td>7</td><td>10</td><td>15</td><td>24</td><td>57</td><td>110</td></tr>
          </table>
          <p>
            Domains that are not securely delegated take up a slot, but do not raise the limit. A domain under
            dedyn.io counts as secure and takes its own slot, but adds no headroom.
          </p>
          <p>
            The dialog for creating a domain shows how many of your domains are securely delegated, and the
            <i>Delegation</i> column of your domain list shows which ones.
          </p>`,
      },
      {
        id: 'limit-not-grown',
        q: "I enabled DNSSEC. Why hasn't my limit grown?",
        a: `
          <p>
            The limit grows as soon as we have seen that the domain is securely delegated. To have us look right away,
            use the <i>Re-check delegation</i> button next to the domain in your domain list, or the <i>Re-check</i>
            button in the domain's setup instructions. The result usually appears within seconds. We also check all
            domains automatically at least once a day, and whenever you create a domain or reach your limit.
          </p>
          <p>
            If the re-check does not say <i>Secure</i>, it tells you what is missing (see
            <a href="#delegation-states">what the states mean</a>). Often, it is a matter of time: after you submit DS
            records at your registrar, it can take from minutes up to a day until the registry publishes them. Re-check
            once they are published. Some registries (such as .ch, .cz, and .se) enable DNSSEC automatically. How long
            that takes depends on the registry.
          </p>`,
      },
      {
        id: 'delegation-states',
        q: 'What do the states in the Delegation column mean?',
        a: `
          <dl>
            <dt>Secure</dt>
            <dd>All set: the domain is delegated to deSEC with DNSSEC enabled, and counts towards your limit.</dd>
            <dt>No DNSSEC</dt>
            <dd>
              The domain uses deSEC's nameservers, but its parent zone has no DS records for it. Forward the DS records
              from the domain's setup instructions to your registrar. The setup instructions have a button that copies
              a ready-made request. If your registrar does not accept DS records, see
              <a href="#registrar-no-ds">below</a>.
            </dd>
            <dt>DNSSEC broken</dt>
            <dd>
              DNSSEC validation fails, so many resolvers cannot resolve your domain at all. Usually, your registrar
              still has DS records from a previous DNS provider. Replace them with deSEC's DS records as soon as possible.
            </dd>
            <dt>Not delegated</dt>
            <dd>
              The parent zone does not point to deSEC's nameservers yet. Set ns1.desec.io and ns2.desec.org as
              nameservers at your registrar.
            </dd>
            <dt>Delegated elsewhere</dt>
            <dd>The domain uses other nameservers (shown in the tooltip). Replace them with deSEC's.</dd>
            <dt>Check failed</dt>
            <dd>
              We could not complete the check, for example because a nameserver did not respond. We retry
              automatically. A domain that was secure before keeps counting as secure in the meantime.
            </dd>
            <dt>Not checked yet</dt>
            <dd>New domains are checked within a day. You can re-check right away.</dd>
          </dl>
          <p>Domains under dedyn.io are secured by deSEC automatically, and always show as <i>Secure</i>.</p>`,
      },
      {
        id: 'limit-raise',
        q: 'Can you raise my limit manually?',
        a: `
          <p>
            As a rule, no: the limit is automatic, so that nobody has to wait for us. Secure the domains you have,
            and the limit follows, with more headroom the more domains you secure.
          </p>
          <p>
            We make exceptions very rarely, and only for a strong reason why the automatic limit cannot work for you.
            Moving many domains is usually not such a reason, as your headroom grows along the way (see
            <a href="#migration">moving many domains</a>). If you believe that your case is an exception, write to us
            <a href="#contact-support">from your account's email address</a>, and explain why.
          </p>`,
      },
      {
        id: 'migration',
        q: "I'm moving many domains to deSEC. Do I have to move them one by one?",
        a: `
          <p>
            Not quite: your headroom grows as you go. With 3 securely delegated domains, your limit is 5; with 7, it
            is 10 (<a href="#domain-limit">details</a>). Some tips:
          </p>
          <ul>
            <li>Delete zones that you no longer need: they take up slots.</li>
            <li>
              You can prepare a zone at deSEC before switching its nameservers, and test it with
              <code>dig @ns1.desec.io example.com</code>.
            </li>
            <li>
              For a domain without DNSSEC: switch the nameservers first, wait a day for resolver caches to expire,
              then add the DS records.
            </li>
            <li>For a domain with DNSSEC: see <a href="#migrate-dnssec">moving a domain that has DNSSEC</a>.</li>
            <li>During a registrar transfer, DS records often cannot be changed. Complete the transfer first.</li>
          </ul>`,
      },
      {
        id: 'registry-delay',
        q: 'Securing a domain takes a day or more. Can you raise my limit in the meantime?',
        a: `
          <p>
            We understand that this can feel slow. The wait happens at the registry: some publish new DS records
            within minutes (.com and .cz, for example), others only once a day. A careful switch also waits for cached
            records to expire. Our re-check sees a DS record as soon as the registry has published it.
          </p>
          <p>
            It can be much faster. Our platform implements automatic DNSSEC setup
            (<a href="https://www.rfc-editor.org/info/rfc10026/">RFC 10026</a>). Registries that support it, such as
            .ch and .li, then secure your domain on their own, without you copying any DS records. If your registry
            does not support it yet, please ask your registrar or registry for it.
          </p>
          <p>
            Meanwhile, you can work on several domains at once, as many as your headroom allows, and the headroom
            grows as you go (<a href="#domain-limit">details</a>).
          </p>
          <p>
            As you may know, deSEC's mission is to improve Internet security by increasing the adoption of DNSSEC.
            Our state-of-the-art hosting platform is how we pursue it, and the limit makes sure that securing domains
            keeps pace with adding them. Domains that are added first, to be secured later, are hard for us to follow
            up on, and in our experience are often forgotten. That is why we do not raise the limit to bridge such
            waiting times. Thank you for your patience, and for helping make DNSSEC the norm!
          </p>`,
      },
      {
        id: 'limit-lower',
        q: 'My limit used to be higher. What happened?',
        a: `
          <p>
            In September 2026, we replaced most individually granted limits with the automatic limit. We always
            granted those limits on the condition that DNSSEC is enabled for the domains; the automatic limit now
            takes care of that. If your limit is lower than before, some domains in your account are not securely
            delegated, and the <i>Delegation</i> column shows which. Once you secure them (or delete those that you
            do not need), your limit grows again.
          </p>`,
      },
      {
        id: 'limit-donation',
        q: 'Can I donate or pay for a higher limit?',
        a: `
          <p>
            Donations are very welcome, and they keep deSEC running (<a href="/donate/">donate here</a>). They do not
            change the limit, though: the limit is not about cost, but about DNSSEC. Secure your domains, and the limit
            grows for free.
          </p>`,
      },
      {
        id: 'why-dnssec',
        q: 'Why does deSEC require DNSSEC?',
        a: `
          <p>
            deSEC is a non-profit organization with a mission: making the Internet more secure, in particular by
            spreading DNSSEC. That is why we offer DNS hosting for free, and why our <a href="/terms/">terms of use</a>
            (§4) require domains at deSEC to be delegated to our nameservers with a DNSSEC chain of trust. Domains that
            do not meet this requirement may receive a deletion warning, and may be deleted four weeks thereafter.
          </p>`,
      },
    ],
  },
  {
    id: 'dnssec-impossible',
    title: 'When DNSSEC seems impossible',
    questions: [
      {
        id: 'registrar-no-ds',
        q: "My registrar doesn't let me add DS records.",
        a: `
          <p>
            Please ask them to. For most top-level domains (all except country codes like .de or .ru), registrars are
            obliged to do so by their accreditation agreement with ICANN:
          </p>
          <blockquote>
            Registrar must allow its customers to use DNSSEC upon request by relaying orders to add, remove or change
            public key material (e.g., DNSKEY or DS resource records) on behalf of customers
            (<a href="https://itp.cdn.icann.org/en/files/accredited-registrars/registrar-accreditation-agreement-21jan24-en.htm">Registrar Accreditation Agreement</a>)
          </blockquote>
          <p>
            The setup instructions for your domain have a <i>Copy request for your registrar</i> button, which copies a
            ready-made message with the DS records. Registrars and registries add DNSSEC support when their customers
            ask for it.
          </p>
          <p>
            If your registrar still refuses, consider transferring the domain to one that supports DNSSEC. Usually, you
            do not lose money that way: the year you pay for at the new registrar is added to your current registration
            period. This is the case for generic top-level domains like .com, and for most country codes. (Known
            exceptions are .at, .de, .it, and .nl.)
          </p>`,
      },
      {
        id: 'tld-unsigned',
        q: "My top-level domain doesn't support DNSSEC at all.",
        a: `
          <p>
            A few top-level domains are not signed with DNSSEC, so none of their domains can be secured. You can check
            with <code>dig +short DS example.</code> (with your top-level domain in place of <i>example</i>): if the
            output is empty, the top-level domain is not signed.
          </p>
          <p>
            Such a domain takes up a slot without raising your limit. In moderation, that is fine: your headroom grows
            as you secure your other domains (<a href="#domain-limit">details</a>). If an unsigned top-level domain
            keeps you from adding domains altogether, <a href="#contact-support">write to us</a>.
          </p>`,
      },
    ],
  },
  {
    id: 'subdomains',
    title: 'Subdomains, ACME, and tokens',
    questions: [
      {
        id: 'subdomain-records',
        q: 'Do I need a separate domain for each subdomain?',
        a: `
          <p>
            No. Subdomains like mail.example.com or www.example.com are records in your domain: create a record, and
            put the subdomain part (e.g. <code>mail</code>) into the <i>Subname</i> field. A separate domain at deSEC
            is only needed for a subdomain whose parent is hosted elsewhere (see the next question).
          </p>`,
      },
      {
        id: 'subdomain-delegation',
        q: 'Can I host a subdomain (like acme.example.com) at deSEC, and keep the parent domain elsewhere?',
        a: `
          <p>
            Yes, as long as DNSSEC works for it, just like for any other domain: the parent domain (example.com) must
            be signed with DNSSEC, and it needs both NS and DS records for the subdomain. You find them in the
            subdomain's setup instructions at deSEC.
          </p>
          <p>
            If the parent's DNS provider cannot sign the parent domain, or cannot add DS records for subdomains, please
            consider moving the parent domain to a provider that can, such as deSEC. Our terms require a DNSSEC chain
            of trust for every domain, including subdomains.
          </p>`,
      },
      {
        id: 'token-scope',
        q: 'Can I give a host, customer, or team a token that can change only its own records?',
        a: `
          <p>
            Yes, with token policies. They restrict a token to certain domains, subnames, and record types, so one
            domain can serve many hosts, customers, or teams, each with their own token. There is no need to create a
            separate domain for each of them. For example, a token for a host's certificates can be restricted to
            writing TXT records at <code>_acme-challenge.host</code>.
          </p>
          <p>
            Policies are managed via the API, see
            <a href="${docs}auth/tokens.html#token-scoping-policies">Token Scoping: Policies</a>.
          </p>`,
      },
      {
        id: 'acme-ttl',
        q: 'ACME DNS-01 validation sometimes fails. Should I lower the TTL?',
        a: `
          <p>
            No: certificate authorities ask our nameservers directly, so TTLs and caches do not play a role. When
            validation fails right after a change, our globally distributed nameservers have not all received the
            change yet. Configure your ACME client to wait a few minutes before validation (most clients have a
            setting for this).
          </p>`,
      },
    ],
  },
  {
    id: 'multi-provider',
    title: 'Secondary DNS, backup, and migration',
    questions: [
      {
        id: 'secondary',
        q: 'Can I use deSEC as a secondary or backup DNS provider?',
        a: `
          <p>
            deSEC does not offer secondary DNS (zone transfers from another primary server), see
            <a href="https://talk.desec.io/t/dns-secondary-support/41">this forum thread</a>. Keeping a zone at deSEC
            on standby, without delegating it, is not covered by our terms (§4): domains must be delegated to our
            nameservers with DNSSEC. It also makes for an unreliable failover, as resolvers keep using the previous
            nameservers for hours after a switch.
          </p>
          <p>
            To use deSEC alongside another provider, list both providers' nameservers in the delegation, and keep the
            records in sync, e.g. with a tool like DNSControl or OctoDNS. With DNSSEC, this is a
            <i>multi-signer</i> setup: each provider signs with its own keys, and the parent zone has DS records for
            both. The <a href="#migrate-dnssec-guide">step-by-step guide</a> below describes how to set it up (stop
            after step 7).
          </p>`,
      },
      {
        id: 'migrate-dnssec',
        q: 'How do I move a domain that already has DNSSEC to deSEC?',
        a: `
          <p>
            Simply replacing the nameservers can break resolution, because resolvers may have the old DS or DNSKEY
            records cached. There are two safe ways:
          </p>
          <ul>
            <li>
              Temporarily <i>go insecure</i> (easier): remove the old DS records at your registrar, wait 24 hours,
              switch the nameservers to deSEC, wait 24 hours, then add deSEC's DS records.
            </li>
            <li>
              Keep DNSSEC enabled throughout, with a temporary <i>multi-signer</i> setup (RFC 8901). This requires
              that your current provider lets you add DNSKEY records. See the step-by-step guide below.
            </li>
          </ul>`,
        guide: {
          id: 'migrate-dnssec-guide',
          title: 'Step by step: moving with a multi-signer setup',
          text: `
            <ol>
              <li>Create your domain at deSEC, with all records that you would like to have in your zone.</li>
              <li>Get deSEC's DNSKEY record(s) from the domain's setup instructions.</li>
              <li>
                Get your current provider's DNSKEY record(s), preferably from their web interface or API. (Querying
                their nameservers, e.g. with <code>dig</code>, also returns them, but that answer is often not
                validated end-to-end.)
              </li>
              <li>
                At your current provider, add DNSKEY records with deSEC's values. At deSEC, add a DNSKEY record (with
                an empty subname) with your current provider's values.
              </li>
              <li>Add deSEC's DS records at your registrar. Do not remove the existing ones yet.</li>
              <li>
                Wait for the longest TTL of your current provider's DNSKEY records and the parent's DS records.
                Typically, 24 hours is safe. (Until then, resolvers may have outdated DNSKEY and DS records cached.)
              </li>
              <li>At your registrar, add deSEC's nameservers (ns1.desec.io and ns2.desec.org).</li>
            </ol>
            <p>
              If you want to keep both providers, you are done: this is a permanent multi-signer setup. Otherwise,
              remove your previous provider's nameservers at your registrar (in the same step, if you like), and
              continue:
            </p>
            <ol start="8">
              <li>
                Wait for the NS TTL of the delegation (for example, 48 hours for .com). During this time, some queries
                arrive at your previous provider, and some at deSEC. Both serve both providers' keys, and the parent
                has DS records for both, so validation succeeds either way.
              </li>
              <li>
                Remove your previous provider's DS records at your registrar, and their DNSKEY record at deSEC.
              </li>
            </ol>
            <p>Questions? We're happy to help: <a href="#contact-support">contact us</a>.</p>`,
        },
      },
    ],
  },
  {
    id: 'dyndns',
    title: 'dynDNS (dedyn.io)',
    questions: [
      {
        id: 'dyndns-hosts',
        q: 'How do I add more hostnames to my dedyn.io domain?',
        a: `
          <p>
            Each account can have one domain under dedyn.io. For more hostnames, add records to it: for example, a
            record with the subname <code>nas</code> in example.dedyn.io creates nas.example.dedyn.io. The
            <a href="${docs}dyndns/update-api.html">dynDNS update API</a> can update such names as well.
          </p>`,
      },
      {
        id: 'dyndns-ttl',
        q: 'I need a short TTL for my dynamic IP address.',
        a: `
          <p>
            Records set through the <a href="${docs}dyndns/update-api.html">dynDNS update API</a> have a TTL of 60
            seconds. This works for any domain at deSEC, not only under dedyn.io, and is what routers and dynDNS
            clients use.
          </p>`,
      },
      {
        id: 'dyndns-deleted',
        q: 'My dedyn.io domain was deleted. Can I get it back?',
        a: `
          <p>
            dedyn.io domains are meant for dynamic DNS. If a domain has not been updated for six months, we send a
            warning, and delete it four weeks later unless you confirm that it is in use. The warning email contains a
            link for that.
          </p>
          <p>
            As registration under dedyn.io is suspended, you cannot recreate a deleted domain yourself. If yours was
            deleted (for inactivity or by accident), write to us from your account's email address, naming the domain.
            If your account was deleted as well, <a href="/signup/">sign up</a> again first, without a domain.
          </p>`,
      },
    ],
  },
  {
    id: 'account',
    title: 'Account and support',
    questions: [
      {
        id: 'no-email',
        q: "I didn't receive the verification or password reset email.",
        a: `
          <ul>
            <li>Check your spam folder.</li>
            <li>
              Wait a while: during waves of abusive sign-ups, we slow down sending, and emails may take a few hours to
              arrive.
            </li>
            <li>Make sure that your email domain can receive mail (MX records), and that it does not reject ours.</li>
            <li>
              The links in our emails are valid for 24 hours. Accounts that are never activated are removed after that,
              and you can then sign up again.
            </li>
          </ul>
          <p>If nothing arrives within a day, <a href="#contact-support">write to us</a> from that address.</p>`,
      },
      {
        id: 'password-changed',
        q: "I received a “Password changed” email, but I didn't change my password.",
        a: `
          <p>
            We also send this email when a password is set for the first time, for example right after you sign up.
            If you are sure that it was not you, <a href="/reset-password/">reset your password</a>, check your tokens,
            and let us know.
          </p>`,
      },
      {
        id: 'lost-2fa',
        q: 'I lost access to my second factor (2FA).',
        a: `
          <p>
            Write to us from your account's email address. We cannot simply turn off 2FA on request, as it protects
            you from someone who has taken over your email account. Instead, we send you a recovery procedure, in which
            you prove control over the domains in your account, for example by temporarily setting special nameservers
            at your registrar. Domains whose control you cannot prove are set aside before we turn off 2FA.
          </p>
          <p>To avoid this situation, keep a backup of your TOTP secret, or set up a second authenticator.</p>`,
      },
      {
        id: 'domain-exists',
        q: "Creating my domain fails with “domain with this name already exists”.",
        a: `
          <p>
            Another deSEC account holds this domain. Often, that is an older account of yours, e.g. with another email
            address. Write to us from the address of the account that should get the domain: we forward your message
            to the account that holds it, so that you (or its owner) can confirm the transfer.
          </p>
          <p>
            If the other account is not yours, you can claim the domain by proving control over it at the registry (§3
            of our <a href="/terms/">terms of use</a>): we give you a special nameserver to set at your registrar, and
            notify the other account's owner. If they do not respond within 48 hours, we transfer the domain.
          </p>`,
      },
      {
        id: 'move-domain',
        q: 'How do I move a domain to another deSEC account?',
        a: `
          <p>
            Write to us from the addresses of both accounts (or have the other account's owner confirm), naming the
            domain, and we move it including its records.
          </p>
          <p>
            To move everything from one of your accounts to another, it is often easier to delete the account that you
            do not need, and change the email address of the remaining one (<i>more</i> menu &rarr;
            <i>Change Email Address</i>, after logging in).
          </p>`,
      },
      {
        id: 'delete-account',
        q: 'How do I delete my account?',
        a: `
          <p>
            Log in, and choose <i>Delete Account</i> from the <i>more</i> menu. This deletes your account with all its
            domains, records, and tokens.
          </p>`,
      },
      {
        id: 'contact-support',
        q: 'How do I contact support?',
        a: `
          <p>Contact us via email. To help us help you:</p>
          <ul>
            <li>
              Write from the email address of your deSEC account. For your security, we do not act on requests from
              other addresses.
            </li>
            <li>Name the domain(s) concerned.</li>
            <li>Write in English or German.</li>
          </ul>
          <p>
            We monitor our systems continuously, and respond to incidents very quickly. Inquiries that are not
            time-sensitive for our operations may take a bit longer. This FAQ, our <a href="${docs}">documentation</a>,
            and our <a href="https://talk.desec.io/">community forum</a> often have an answer sooner.
          </p>`,
      },
    ],
  },
  {
    id: 'records',
    title: 'Records and API',
    questions: [
      {
        id: 'minimum-ttl',
        q: 'What is the minimum TTL, and can it be lowered?',
        a: `
          <p>
            The minimum TTL is 900 seconds (15 minutes); the API shows it for each domain as <code>minimum_ttl</code>.
          </p>
          <p>
            For dynamic IP addresses, use the <a href="#dyndns-ttl">dynDNS update API</a>, which sets a TTL of 60
            seconds. For ACME DNS-01 challenges, the TTL does not matter (<a href="#acme-ttl">why</a>). For other use
            cases, such as failover, you can apply for an exception: write to us from your account's email address,
            and explain your use case. The domain needs to have DNSSEC enabled first.
          </p>`,
      },
      {
        id: 'throttled',
        q: 'My requests are throttled.',
        a: `
          <p>
            Our API has <a href="${docs}rate-limits.html">rate limits</a>. A throttled response says how long to wait,
            also in its <code>Retry-After</code> header. Most often, a script makes many requests in a loop: use
            <a href="${docs}dns/rrsets.html#bulk-operations">bulk operations</a> instead, which change many records
            with one request, and send updates only when something has changed. If you have a use case that the limits
            do not accommodate, let us know.
          </p>`,
      },
      {
        id: 'cname-apex',
        q: "Why can't I create a CNAME (or ALIAS) record at my domain's apex?",
        a: `
          <p>
            The DNS standard does not allow a CNAME record next to other records, and a domain's apex always has other
            records (such as NS and SOA). ALIAS records are provider-specific workarounds outside the DNS standard,
            which deSEC does not offer. To point your apex to a service, use its IP addresses (A/AAAA records), or an
            HTTPS record. See also the <a href="${docs}dns/rrsets.html#caveats">caveats in our documentation</a>.
          </p>`,
      },
    ],
  },
  {
    id: 'abuse',
    title: 'Reporting abuse',
    questions: [
      {
        id: 'report-abuse',
        q: 'How do I report abuse?',
        a: `
          <p>Send your report to us via email. <b>We act on evidence, so please include:</b></p>
          <ol>
            <li>the domain name, and the URLs where the abuse can be seen,</li>
            <li>
              the evidence itself, in the email body (screenshots as images or PDF are fine; we do not open office
              documents),
            </li>
            <li>plain links, not wrapped by a redirector (such as google.com/url?&hellip;).</li>
          </ol>
          <p>
            Please verify that the domain actually exists and serves the content you are reporting. Subdomains under
            dedyn.io are operated by their owners; we forward security reports about them to the owner.
          </p>`,
      },
    ],
  },
  {
    id: 'support-us',
    title: 'Supporting deSEC',
    questions: [
      {
        id: 'donate',
        q: 'How can I support deSEC?',
        a: `
          <p>
            Thank you! deSEC is funded by donations: see our <a href="/donate/">donation page</a> for ways to donate,
            and for donation receipts. Organizations can also support us by adopting a frontend server in a region of
            their choice; <a href="#contact-support">write to us</a> if you are interested.
          </p>`,
      },
    ],
  },
];

export default {
  name: 'FaqPage',
  data() {
    return {
      docs,
      sections,
      openGuides: {},  // guide id -> 'guide' while its panel is open
      mdiFormatListNumbered,
    };
  },
  watch: {
    '$route.hash': {
      immediate: true,
      handler(hash) {
        const id = (hash || '').slice(1);
        if (this.guideIds.includes(id)) {
          this.openGuides[id] = 'guide';
        }
      },
    },
  },
  computed: {
    guideIds() {
      return this.sections.flatMap(section => section.questions).filter(q => q.guide).map(q => q.guide.id);
    },
  },
  methods: {
    /**
     * Links in the answers are plain HTML. Follow those within the webapp
     * through the router, so that the page is not reloaded, and so that
     * anchors end up below the app bar.
     */
    followLink(event) {
      const link = event.target.closest?.('a');
      if (!link || link.target || event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      const href = link.getAttribute('href') || '';
      if (href.startsWith('#')) {
        event.preventDefault();
        if (href === this.$route.hash) {
          this.scrollTo(href);  // the router ignores navigation to where it already is
        } else {
          this.$router.push({hash: href});
        }
      } else if (href.startsWith('/')) {
        event.preventDefault();
        this.$router.push(href);
      }
    },
    scrollTo(hash) {
      const element = document.getElementById(hash.slice(1));
      if (element) {
        window.scrollTo({top: element.getBoundingClientRect().top + window.scrollY - headerOffset()});
      }
    },
  },
};
</script>

<style scoped>
  div.triangle-bg {
    position: absolute;
    bottom: 0;
    width: 100%;
    z-index: 1;
    right: .2em;
    height: 100%;
    text-align: right;
    font-size: 20em;
    line-height: 1.2;
    font-weight: bold;
    color: #eee;
  }
  .triangle-fg {
    z-index: 2;
  }
  .faq-toc ul {
    list-style: none;
    padding-left: 0;
  }
  .faq-toc li {
    margin: 4px 0;
  }
  /* Questions in the text color, as headings: the link color is hard to read
     in long lists. (It is !important in App.vue, hence here, too.) */
  .faq-toc a, .faq-question a {
    color: inherit !important;
    text-decoration: none;
  }
  .faq-toc a:hover, .faq-question a:hover {
    text-decoration: underline;
  }
  @media (min-width: 1280px) {
    .faq-toc {
      position: sticky;
      top: 128px;
      max-height: calc(100vh - 144px);
      overflow-y: auto;
    }
  }
  .faq-answer :deep(p), .faq-answer :deep(ul), .faq-answer :deep(ol), .faq-answer :deep(dl),
  .faq-answer :deep(table), .faq-answer :deep(blockquote) {
    margin-bottom: 12px;
  }
  .faq-answer :deep(ul), .faq-answer :deep(ol) {
    padding-left: 24px;
  }
  .faq-answer :deep(dt) {
    font-weight: bold;
  }
  .faq-answer :deep(dd) {
    margin: 0 0 8px 24px;
  }
  .faq-answer :deep(blockquote) {
    border-left: 4px solid #ddd;
    padding-left: 12px;
    color: #555;
  }
  .faq-answer :deep(table) {
    border-collapse: collapse;
    display: block;
    overflow-x: auto;
  }
  .faq-answer :deep(th), .faq-answer :deep(td) {
    border: 1px solid #ddd;
    padding: 4px 8px;
    text-align: center;
    white-space: nowrap;
  }
  .faq-answer :deep(th) {
    text-align: left;
  }
</style>
