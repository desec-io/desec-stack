<template>
  <div>
  <v-card outline tile class="pa-md-12 pa-8 elevation-4" style="overflow: hidden">
    <div class="d-none d-md-block triangle-bg"></div>
    <v-container class="pa-0">
      <v-row align="center">
        <v-col class="col-md-6 col-12 py-8 triangle-fg">
          <h1 class="text-h4 font-weight-bold">Modern DNS Hosting for Everyone</h1>
          <div class="text-subtitle-1 mt-2 pt-8 font-weight-regular">
            <p>
              deSEC is a <strong>free DNS hosting</strong> service, <strong>designed with security in mind</strong>.
            </p>
            <p>
              Running on <strong>open-source software</strong> and <strong>supported by <a href="https://securesystems.de/">SSE</a></strong>,
              deSEC is free for everyone to use.
            </p>
          </div>
          <div class="pa-2" v-if="!user.authenticated">
            <v-form @submit.prevent="signup" :value="valid" ref="form">
              <v-row>
                <v-col md="9" cols="12">
                  <div class="d-flex align-center flex-column">
                    <v-radio-group
                            v-model="domainType"
                            class="pb-2"
                            hide-details
                            row
                            @change="$router.push({query: {domainType: domainType}})"
                    >
                      <v-radio class="pb-2" label="Managed DNS account" value="custom"></v-radio>
                      <v-radio class="pb-2" label="dynDNS account" value="dynDNS"></v-radio>
                    </v-radio-group>
                  </div>
                  <v-text-field
                    outlined
                    solo
                    flat
                    v-model="email"
                    :prepend-inner-icon="mdiEmail"
                    type="email"
                    placeholder="Account Email Address"
                    :rules="email_rules"
                    validate-on-blur
                    ></v-text-field>
                  <v-btn
                    color="primary"
                    type="submit"
                    depressed
                    x-large
                    block
                  >
                    Create Account
                  </v-btn>
                </v-col>
              </v-row>
            </v-form>
          </div>
        </v-col>
      </v-row>
    </v-container>
  </v-card>
  <v-container fluid>
    <v-container>
      <v-row justify="center" class="py-8">
        <v-col class="col-12 col-sm-4 text-center" v-for="f in features" :key="f.title">
          <v-icon x-large>{{ f.icon }}</v-icon>
          <h1 class="grey--text text--darken-2"><span>{{ f.title }}</span></h1>
          <p v-html="f.text"></p>
        </v-col>
      </v-row>
    </v-container>
  </v-container>
  <v-container fluid class="grey lighten-4">
    <v-container class="py-8">
      <v-row align="center">
        <v-col class="text-center">
          <h2>Supporters</h2>
        </v-col>
      </v-row>
      <v-row align="center" class="py-2" justify="center">
        <v-col class="col-12 col-lg-3 py-4">
          <v-layout class="justify-center">
            <img loading="lazy" src="../assets/non-free/sse.logo.png" alt="SSE Logo" class="mr-6" style="max-width: 160px; width: 100%"/>
          </v-layout>
        </v-col>
        <v-col class="col-12 col-sm-10 col-lg-9 py-4 text-center">
          <a class="primary--text text--darken-2" href="https://securesystems.de/">SSE</a> supports us with staff for
          software development and our standardization activities within the IETF and ICANN.
          We trust them because creating and auditing security solutions is their daily business.
        </v-col>
      </v-row>
      <v-row align="center" class="py-2" justify="center">
        <v-col class="col-12 col-lg-3 py-4">
          <v-layout class="justify-center">
            <img loading="lazy" src="../assets/non-free/nlnet.logo.svg" alt="NLnet Foundation Logo" class="mr-6" style="max-width: 180px; width: 100%"/>
          </v-layout>
        </v-col>
        <v-col class="col-12 col-sm-10 col-lg-9 py-4 text-center">
          deSEC receives funding through <a class="primary--text text--darken-2" href="https://nlnet.nl/">NLnet
          Foundation</a> for its work on the automation and future viability of DNSSEC. The <strong>NGI Assure</strong>
          fund, established with financial support from the European Commission's <strong>Next Generation
          Internet</strong> programme, is dedicated to technologies providing strong assurances about the Internet's
          security and trustworthiness.
        </v-col>
      </v-row>
      <v-row align="center" class="py-2" justify="center">
        <v-col class="col-12 col-lg-3 py-4">
          <v-layout class="justify-center">
            <img loading="lazy" src="../assets/non-free/ripe-ncc.logo.svg" alt="RIPE NCC Logo" class="mr-6" style="margin-bottom: -7%; margin-top: -7%; max-width: 240px; width: 100%"/>
          </v-layout>
        </v-col>
        <v-col class="col-12 col-sm-10 col-lg-9 py-4 text-center">
          Through their Community Projects Fund, <a class="primary--text text--darken-2" href="https://ripe.net/">RIPE NCC</a>
          in 2023 supported the ongoing operation of our DNS platform and covers global Anycast network expenses in
          particular. We greatly appreciate their support.
        </v-col>
      </v-row>
      <v-row align="center" class="py-2" justify="center">
        <v-col class="col-12 col-lg-3 py-4">
          <v-layout class="justify-center">
            <img loading="lazy" src="../assets/non-free/eu.logo.svg" alt="EU Logo" class="mr-6" style="margin-bottom: 0; margin-top: 0; max-width: 200px; width: 100%"/>
          </v-layout>
        </v-col>
        <v-col class="col-12 col-sm-10 col-lg-9 py-4 text-center">
          As a <a class="primary--text text--darken-2" href="https://www.joindns4.eu/">DNS4EU</a> consortium member,
          deSEC works to ensure implementation of robust and modern DNS security and privacy features.
          This includes support for state-of-the-art DNSSEC as well as encrypted DNS transport.<br />
          The project is co-funded by the European Union (project number: 101095329 21-EU-DIG-EU-DNS, project name:
          DNS4EU and European DNS Shield).
        </v-col>
      </v-row>
    </v-container>
  </v-container>
  <v-container fluid>
    <v-container class="py-8">
      <v-row align="center">
        <v-col class="text-center">
          <h2>Partners</h2>
        </v-col>
      </v-row>
      <v-row align="center" class="py-2" justify="center">
        <v-col class="col-12 col-lg-3 py-4">
          <v-layout class="justify-center">
            <a href="https://www.joindns4.eu/"><img loading="lazy" src="../assets/non-free/dns4eu.logo.svg" alt="DNS4EU Logo" class="mr-6" style="margin-bottom: 0; margin-top: 0; max-width: 210px; width: 100%"/></a>
          </v-layout>
        </v-col>
        <v-col class="col-12 col-sm-10 col-lg-9 py-4 text-center">
          DNS4EU is an initiative of the European Commission to provide an EU-based alternative public DNS resolver.
          The purpose of DNS4EU is to provide EU citizens, companies, and institutions with a secure, privacy-compliant,
          and powerful recursive DNS to protect European digital independence.
        </v-col>
      </v-row>
      <v-row align="center" class="mt-6" justify="center" style="text-align: center">
        <v-col><a href="https://nextcloud.com/"><img loading="lazy" src="../assets/non-free/nextcloud-logo-inverted.svg" alt="Nextcloud Logo" style="max-height: 113px"/></a></v-col>
        <v-col><a href="https://sav.com/"><img loading="lazy" src="../assets/non-free/sav.logo.svg" alt="Sav Logo" style="height: 100%; max-height: 80px; vertical-align: middle"/></a></v-col>
        <v-col><a href="https://www.hanssonit.se/"><img loading="lazy" src="../assets/non-free/hanssonit.logo.png" alt="Hansson IT Logo" style="max-height: 113px"/></a></v-col>
      </v-row>
    </v-container>
  </v-container>
  <v-container fluid class="grey lighten-4">
    <v-container>
      <v-row align="center" justify="center">
        <v-card
          class="mx-auto col-12"
          color="grey lighten-5"
        >
          <v-card-text
                  class="pt-6"
                  style="position: relative;"
          >
            <h3 class="text-h4 mb-2 text--darken-2 grey--text text-center">
              deSEC Global Anycast Networks
            </h3>
            <div class="font-weight-light text-h6 mb-2">
              Global distribution of our frontend servers ensures quick answers to queries, regardless of the user's
              location on the globe. You can
              <a :href="'mailto:' + contact_email + '?subject=' + encodeURIComponent(contact_subject) +
                        '&body=' + encodeURIComponent(contact_body)"
              >support deSEC</a> by adopting a frontend server to help us cover the cost or adding a frontend server
              in a corner of the world where there is no frontend yet.
            </div>
          </v-card-text>
          <v-img
            src="../assets/anycast.worldmap.svg" alt="World Map of Anycast POPs" contain
            class="justify-center"
            style="display: block; width: 100%; aspect-ratio: 2/1"
          >
            <v-tooltip bottom v-for="f in frontends" :key="f.host">
              <template #activator="{ on }">
                <v-icon
                  v-on="on"
                  large
                  style="transform: translate(-50%, -100%); position: absolute"
                  :style="{color: f.adopted_by ? 'black' : 'rgba(0, 0, 0, 0.60)', left: f.left, top: f.top}"
                >{{ f.adopted_by ? mdiMapMarkerStar : mdiMapMarker }}</v-icon>
                <v-icon
                  v-if="!!f.adopted_by"
                  large
                  style="color: gold; transform: translate(-50%, -100%); position: absolute"
                  :style="{left: f.left, top: f.top}"
                >{{ mdiMapMarkerStarOutline }}</v-icon>
              </template>
              <span>
                {{ f.name }}<span v-if="f.adopted_by">, sponsored by {{ f.adopted_by }}</span>
                <span v-else> has no sponsor, support it now!</span>
              </span>
            </v-tooltip>
          </v-img>
        </v-card>
      </v-row>
    </v-container>
  </v-container>
  </div>
</template>

<style scoped>
  div.triangle-bg {
    border: 80em solid transparent;
    border-right: 60em solid #FFC107;
    position: absolute;
    right: 0;
    bottom: -20em;
    width: 0;
    z-index: 1;
  }
  .triangle-fg {
    z-index: 2;
  }
</style>

<script>
import {email_pattern} from '@/validation';
import {useUserStore} from "@/store/user";
import {
    mdiCertificate,
    mdiCloudCheck,
    mdiDatabaseArrowUp,
    mdiDns, mdiEmail, mdiFileCertificate, mdiFlower, mdiGift, mdiHeartBroken,
    mdiIpNetworkOutline, mdiLan,
    mdiLockOutline,
    mdiMapMarker, mdiMapMarkerStar, mdiMapMarkerStarOutline,
    mdiMonitorCellphoneStar,
    mdiRobot, mdiRunFast,
    mdiTwoFactorAuthentication
} from "@mdi/js";

export default {
  name: 'HomePage',
  components: {
  },
  methods: {
    async signup() {
      if (this.$refs.form.validate()) {
        this.$router.push({name: 'signup', params: this.email ? {email: this.email} : {}, query: {domainType: this.domainType}});
      }
    },
  },
  created() {
    this.domainType = this.$route.query.domainType || 'none';
    for (let news of this.breaking_news) {
      if (new Date() >= news.start && new Date() < news.end) {
        useUserStore().alert(news);
      }
    }
  },
  data: () => ({
    user: useUserStore(),
    mdiEmail,
    contact_email: import.meta.env.VITE_APP_EMAIL,
    contact_subject: 'Adopting of a Frontend Server',
    contact_body: 'Dear deSEC,\n\nI would like to adopt a frontend server in your networks!',
    domainType: null,
    email: '',
    email_rules: [
      v => !!email_pattern.test(v || '') || 'Invalid email address.'
    ],
    valid: false,
    frontends: [
      {
        name: 'Santiago de Chile (ns2.desec.org)',
        host: 'scl-1.c.desec.io',
        left: '22%',
        top: '85%',
        adopted_by: 'Klaus Alexander Seistrup',
      },
      {
        name: 'London (ns2.desec.org)',
        host: 'lhr-1.c.desec.io',
        left: '45%',
        top: '20%',
        adopted_by: 'Layershift',
      },
      {
        name: 'Singapore (ns2.desec.org)',
        host: 'sin-1.c.desec.io',
        left: '81%',
        top: '57.5%',
        adopted_by: 'Layershift',
      },
      {
        name: 'Dubai (ns2.desec.org)',
        host: 'dxb-1.c.desec.io',
        left: '64%',
        top: '40.2%',
      },
      {
        name: 'Los Angeles (ns2.desec.org)',
        host: 'lax-1.c.desec.io',
        left: '6%',
        top: '32%',
        adopted_by: 'Brian Banerjee',
      },
      {
        name: 'Tokyo (ns2.desec.org)',
        host: 'tyo-1.c.desec.io',
        left: '90.4%',
        top: '32.2%',
        adopted_by: 'Klaus Alexander Seistrup',
      },
      {
        name: 'Frankfurt (ns2.desec.org)',
        host: 'fra-1.c.desec.io',
        left: '49.0%',
        top: '23.0%',
        adopted_by: 'Christian Hase',
      },
      {
        name: 'New York (ns2.desec.org)',
        host: 'lga-1.c.desec.io',
        left: '22%',
        top: '29%',
        adopted_by: 'Layershift',
      },

      {
        name: 'Amsterdam (ns1.desec.io)',
        host: 'ams-1.a.desec.io',
        left: '47%',
        top: '22%',
        adopted_by: 'Jason Liquorish',
      },
      {
        name: 'Frankfurt (ns1.desec.io)',
        host: 'fra-1.a.desec.io',
        left: '48.5%',
        top: '23.5%',
        adopted_by: 'Liip AG',
      },
      {
        name: 'Johannesburg (ns1.desec.io)',
        host: 'jnb-1.a.desec.io',
        left: '54%',
        top: '81%',
        adopted_by: 'Klaus Alexander Seistrup',
      },
      {
        name: 'São Paulo (ns1.desec.io)',
        host: 'sao-1.a.desec.io',
        left: '29.3%',
        top: '78%',
      },
      {
        name: 'Sydney (ns1.desec.io)',
        host: 'syd-1.a.desec.io',
        left: '93%',
        top: '84%',
      },
      {
        name: 'Dallas, TX (ns1.desec.io)',
        host: 'dfw-1.a.desec.io',
        left: '13%',
        top: '34%',
      },
      {
        name: 'Hong Kong (ns1.desec.io)',
        host: 'hkg-1.a.desec.io',
        left: '83.5%',
        top: '42.2%',
        adopted_by: 'Christian Hase',
      },
    ].sort((a, b) => !b.adopted_by - !a.adopted_by),
    features: [
      {
        href: '#',
        icon: mdiLockOutline,
        title: 'DNSSEC',
        text: 'DNS information hosted at deSEC is <b>signed with DNSSEC, always</b>. We use state-of-the-art '
               + 'elliptic-curve cryptography. Besides following operational best practice, we adopt '
               + '<a href="https://datatracker.ietf.org/doc/draft-ietf-dnsop-dnssec-bootstrapping/" target="_blank">cutting-edge '
               + 'developments</a>.',
      },
      {
        href: '#',
        icon: mdiCloudCheck,
        title: 'Cloud Integration',
        text: 'Thanks to <a href="https://talk.desec.io/t/tools-implementing-desec/11" target="_blank">cloud '
                + 'integrations and language bindings</a>, deSEC works out of the box in automated environments. '
                + 'Examples include <b>Terraform</b> providers and <b>Go, Python, and JavaScript bindings.</b>',
      },
      {
        href: '#',
        icon: mdiDns,
        title: 'Modern Record Types',
        text: 'We support a <a href="https://desec.readthedocs.io/en/latest/dns/rrsets.html#supported-types" target="_blank">broad '
                + 'array of record types</a>, including novel types such as <code>HTTPS</code>/<code>SVCB</code> (for '
                + '<code>CNAME</code>-like behavior at the apex), <code>CDNSKEY</code>/<code>CDS</code> (RFC 8078, RFC '
                + '8901), or <code>OPENPGPKEY</code>, <code>SMIMEA</code>, and <code>TLSA</code>.',
      },
      {
        href: '#',
        icon: mdiMonitorCellphoneStar,
        title: 'Web Interface',
        text: 'We think we have the <b>coolest GUI on the market</b>. Thanks to <b>real-time record validation</b> and '
               + 'parsing, it is <b>very intuitive and fast</b> to use (even on mobile devices). Get started by '
               + 'importing your domain.',
      },
      {
        href: '#',
        icon: mdiRobot,
        title: 'REST API',
        text: 'Exert full control over your DNS via our <b>modern API</b> and benefit from advanced features such as '
               + ' bulk operations. It is <a href="https://desec.readthedocs.io/en/latest/dns/domains.html" target="_blank">well-documented</a> '
               + ' and easily integrates into your scripts, tools, or CI/CD pipeline.',
      },
      {
        href: '#',
        icon: mdiTwoFactorAuthentication,
        title: 'Multi-Factor Auth (2FA)',
        text: 'Accidentally shared your password with someone? Enable MFA to <b>keep your account safe</b>. We '
              + 'currently support <b>TOTP tokens</b> (Authenticator app), with WebAuthn in the making.',
      },
      {
        href: '#',
        icon: mdiDatabaseArrowUp,
        title: 'Scalability',
        text: 'Are you a web hoster? Start using deSEC, <b>even with thousands of domains</b>. Our global network '
                + 'ensures <b>high availability and performance everywhere</b>. <a href="mailto:support@desec.io">Talk '
                + 'to us</a> about your use case.',
      },
      {
        href: '#',
        icon: mdiIpNetworkOutline,
        title: 'IPv6',
        text: 'deSEC is <b>fully IPv6-aware</b>: administration can be done using v6, AAAA-records '
                + 'containing IPv6 addresses can be set up, our name servers are reachable via IPv6.',
      },
      {
        href: '#',
        icon: mdiRunFast,
        title: 'Fast Updates',
        text: 'Updates to your DNS information will be <b>published world-wide within a few seconds</b>. '
                + 'Minimum required TTLs are low.',
      },
      {
        href: '#',
        icon: mdiCertificate,
        title: 'DANE / TLSA',
        text: 'Secure your web service with <code>TLSA</code> records, <b>hardening it against fraudulently issued SSL '
                + 'certificates</b>. You can also use other DANE techniques, such as <code>OPENPGPKEY</code> key '
                + 'exchange.',
      },
      {
        href: '#',
        icon: mdiFileCertificate,
        title: "Let's Encrypt Integration",
        text: 'We provide <b><a href="https://pypi.org/project/certbot-dns-desec/">easy integration</a> with Let\'s '
               + 'Encrypt</b> and their certbot tool. '
               + '<a href="https://talk.desec.io/t/tools-implementing-desec/11">Further integration with other '
               + 'tools</a> like acme.sh, lego, and Terraform is available.',
      },
      {
        href: '#',
        icon: mdiLan,
        title: 'Low-latency Anycast',
        text: 'We run <b>global networks of high-performance frontend DNS servers</b>. Your query is routed to the '
              + '<b>closest server</b> via Anycast, so clients receive answers as fast as possible.',
      },
      {
        href: '#',
        icon: mdiFlower,
        title: 'Open Source',
        text: 'deSEC runs <b>100% on free and open-source</b> software. Start hacking away!',
      },
      {
        href: '#',
        icon: mdiGift,
        title: 'Non-profit',
        text: 'deSEC is organized as a <b>non-profit organization based in Berlin</b>. We make sure that privacy '
              + 'is not compromised by business interest.',
      },
    ],
    breaking_news: [
      {
        id: 'news-20201017001',
        start: new Date(Date.UTC(2020, 10 - 1, 17)),  // first day of showing
        end: new Date(Date.UTC(2020, 10 - 1, 20)),  // first day of not showing
        icon: mdiHeartBroken,
        teaser: 'deSEC API and web services have been unavailable on 17 Oct 2020 starting at 4:26 am UTC and resumed ' +
            'normal operations at 10:13 am UTC. DNS operations continued throughout.',
        button: 'deSEC Status Details',
        href: '//desec-status.net/',
      },
      {
        id: 'news-20221010001',
        start: new Date(Date.UTC(2022, 10 - 1, 10)),  // first day of showing
        end: new Date(Date.UTC(2022, 10 - 1, 12)),  // first day of not showing
        icon: mdiHeartBroken,
        teaser: "From 10 Oct 2022 11:32 am UTC until 10 Oct 2022 16:33 UTC, the deSEC web interface was unavailable " +
            "when accessed via direct links, e.g. though emails sent by deSEC. The issue has been fixed; links that " +
            "have not expired in the meantime are now working when opened. Direct login to the web interface and " +
            "deSEC DNS operations were not affected.",
      },
      {
        id: 'news-20231226001',
        start: new Date(Date.UTC(2023, 12 - 1, 26)),  // first day of showing
        end: new Date(Date.UTC(2024, 1 - 1, 8)),  // first day of not showing
        icon: mdiHeartBroken,
        teaser: "Due to a recent spike in abusive domain registrations, new accounts need manual verification before " +
            "domains can be created. Please contact support explaining your use case to enable domain creation.",
      },
    ],
    mdiMapMarker,
    mdiMapMarkerStar,
    mdiMapMarkerStarOutline,
  })
}
</script>
