<template>
  <div>
  <v-card outline tile class="pa-md-12 pa-8 elevation-4" style="overflow: hidden">
    <div class="d-none d-md-block triangle-bg"></div>
    <v-container class="pa-0">
      <v-row align="center">
        <v-col class="col-md-6 col-12 py-8 triangle-fg">
          <h1 class="display-1 font-weight-bold">Modern DNS Hosting for Everyone</h1>
          <h3 class="subheading mt-2 pt-8 font-weight-regular">
            <p>
              deSEC is a <strong>free DNS hosting</strong> service, <strong>designed with security in mind</strong>.
            </p>
            <p>
              Running on <strong>open-source software</strong> and <strong>supported by <a href="//securesystems.de/">SSE</a></strong>,
              deSEC is free for everyone to use.
            </p>
          </h3>
          <div class="pa-2">
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
                    prepend-inner-icon="mdi-email"
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
      <v-row class="py-8">
        <v-col class="col-12 col-sm-4 text-center" v-for="f in features" :key="f.title">
          <v-icon x-large>{{f.icon}}</v-icon>
          <h1 class="grey--text text--darken-2"><span>{{f.title}}</span></h1>
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
      <v-row justify="center">
        <v-col class="col-12 col-lg-2 py-4">
          <v-layout class="justify-center">
            <v-img :src="require('../assets/non-free/sse.logo.png')" alt="SSE Logo" class="mr-6" contain style="max-width: 160px; width: 100%"></v-img>
          </v-layout>
        </v-col>
        <v-col class="col-12 col-sm-10 col-lg-8 py-4 text-center">
          <a class="primary--text text--darken-2" href="//securesystems.de/">SSE</a> supports us with development staff
          and provides financial resources for our global Anycast network infrastructure. We trust them because creating
          and auditing security solutions is their daily business.
        </v-col>
      </v-row>
    </v-container>
  </v-container>
  <v-container fluid>
    <v-container>
      <v-row align="center" justify="center">
        <v-card
          class="mx-auto col-12"
          color="grey lighten-4"
        >
          <v-card-text
                  class="pt-6"
                  style="position: relative;"
          >
            <h3 class="display-1 mb-2 text--darken-2 grey--text text-center">
              deSEC Global Anycast Networks
            </h3>
            <div class="font-weight-light title mb-2">
              Global distribution of our frontend servers ensures quick answers to queries, regardless of the user's
              location on the globe. You can
              <a :href="'mailto:' + contact_email + '?subject=' + encodeURIComponent(contact_subject) +
                        '&body=' + encodeURIComponent(contact_body)"
              >support deSEC</a> by adopting a frontend server to help us cover the cost or adding a frontend server
              in a corner of the world where there is no frontend yet.
            </div>
          </v-card-text>
          <v-img
            :src="require('../assets/anycast.worldmap.svg')" alt="World Map of Anycast POPs" contain
            class="justify-center"
            style="display: block;"
          >
            <v-tooltip bottom v-for="f in frontends" :key="f.host">
              <template v-slot:activator="{ on }">
                <v-img
                  v-on="on"
                  :src="require('../assets/mapmarker.svg')" alt="Anycast POP" height="2em" width="2em"
                  :style="{left: f.left, top: f.top}"
                  style="transform: translate(-50%, -100%); position: absolute; overflow: visible;" contain
                >
                </v-img>
              </template>
              <span>
                {{f.name}}
                <span v-if="f.adopted_by">sponsored by {{f.adopted_by}}</span>
                <span v-else>has no sponsor, support it now!</span>
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
import {email_pattern} from "../validation";

export default {
  name: 'home',
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
        this.$store.commit('alert', news);
      }
    }
  },
  data: () => ({
    contact_email: process.env.VUE_APP_EMAIL,
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
        adopted_by: 'SSE Secure Systems Engineering',
        left: '22%',
        top: '85%',
      },
      {
        name: 'London (ns2.desec.org)',
        host: 'lhr-1.c.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '45%',
        top: '20%',
      },
      {
        name: 'Singapore (ns2.desec.org)',
        host: 'sin-1.c.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '81%',
        top: '57.5%',
      },
      {
        name: 'Dubai (ns2.desec.org)',
        host: 'dxb-1.c.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '64%',
        top: '40.2%',
      },
      {
        name: 'Los Angeles (ns2.desec.org)',
        host: 'lax-1.c.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '6%',
        top: '32%',
      },
      {
        name: 'Tokyo (ns2.desec.org)',
        host: 'tyo-1.c.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '90.4%',
        top: '32.2%',
      },
      {
        name: 'Frankfurt (ns2.desec.org)',
        host: 'fra-1.c.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '49.0%',
        top: '23.0%',
      },
      {
        name: 'New York (ns2.desec.org)',
        host: 'lga-1.c.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '22%',
        top: '29%',
      },

      {
        name: 'Amsterdam (ns1.desec.io)',
        host: 'ams-1.a.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '47%',
        top: '22%',
      },
      {
        name: 'Frankfurt (ns1.desec.io)',
        host: 'fra-1.a.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '48.5%',
        top: '23.5%',
      },
      {
        name: 'Johannesburg (ns1.desec.io)',
        host: 'jnb-1.a.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '54%',
        top: '81%',
      },
      {
        name: 'São Paulo (ns1.desec.io)',
        host: 'gru-1.a.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '29.3%',
        top: '78%',
      },
      {
        name: 'Sydney (ns1.desec.io)',
        host: 'syd-1.a.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '93%',
        top: '84%',
      },
      {
        name: 'Dallas, TX (ns1.desec.io)',
        host: 'dfw-1.a.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '13%',
        top: '34%',
      },
      {
        name: 'Hong Kong (ns1.desec.io)',
        host: 'hkg-1.a.desec.io',
        adopted_by: 'SSE Secure Systems Engineering',
        left: '83.5%',
        top: '42.2%',
      },
    ],
    features: [
      {
        href: '#',
        icon: 'mdi-lock-outline',
        title: 'DNSSEC',
        text: 'DNS information hosted with deSEC is <b>signed using DNSSEC, always</b>. We use state-of-the-art '
                + 'elliptic-curve cryptography and follow operational best practice.',
      },
      {
        href: '#',
        icon: 'mdi-cloud-check',
        title: 'Cloud Integration',
        text: 'Thanks to <a href="https://talk.desec.io/t/tools-implementing-desec/11" target="_blank">cloud '
                + 'integrations and language bindings</a>, deSEC works out of the box in automated environments. '
                + 'Examples include <b>Terraform</b> providers and <b>Go, Python, and JavaScript bindings.</b>',
      },
      {
        href: '#',
        icon: 'mdi-dns',
        title: 'Modern Record Types',
        text: 'We support a <a href="https://desec.readthedocs.io/en/latest/dns/rrsets.html#supported-types" target="_blank">broad '
                + 'array of record types</a>, including novel types such as <code>HTTPS</code>/<code>SVCB</code> (for '
                + '<code>CNAME</code>-like behavior at the apex), <code>CDNSKEY</code>/<code>CDS</code> (RFC 8078, RFC '
                + '8901), or <code>OPENPGPKEY</code>, <code>SMIMEA</code>, and <code>TLSA</code>.',
      },
      {
        href: '#',
        icon: 'mdi-database-arrow-up',
        title: 'Scalability',
        text: 'Are you a web hoster? Start using deSEC, <b>even with thousands of domains</b>. Our global network '
                + 'ensures <b>high availability and performance everywhere</b>. <a href="mailto:support@desec.io">Talk '
                + 'to us</a> about your use case.',
      },
      {
        href: '#',
        icon: 'mdi-robot',
        title: 'REST API',
        text: 'Configure your DNS information via a <b>modern API</b>. You can easily integrate our API into your '
              + 'scripts, tools, or even CI/CD pipeline.',
      },
      {
        href: '#',
        icon: 'mdi-ip-network-outline',
        title: 'IPv6',
        text: 'deSEC is <b>fully IPv6-aware</b>: administration can be done using v6, AAAA-records '
                + 'containing IPv6 addresses can be set up, our name servers are reachable via IPv6.',
      },
      {
        href: '#',
        icon: 'mdi-certificate',
        title: 'DANE / TLSA',
        text: 'Secure your web service with <code>TLSA</code> records, <b>hardening it against fraudulently issued SSL '
                + 'certificates</b>. You can also use other DANE techniques, such as <code>OPENPGPKEY</code> key '
                + 'exchange.',
      },
      {
        href: '#',
        icon: 'mdi-file-certificate',
        title: "Let's Encrypt Integration",
        text: 'We provide <b>easy integration</b> with Let\'s Encrypt and their certbot tool. '
               + '<a href="https://talk.desec.io/t/tools-implementing-desec/11">Further integration with ACME '
               + 'clients</a> like acme.sh, lego, and Terraform is available.',
      },
      {
        href: '#',
        icon: 'mdi-run-fast',
        title: 'Fast Updates',
        text: 'Updates to your DNS information will be <b>published world-wide within a few seconds</b>. '
                + 'Minimum required TTLs are low.',
      },
      {
        href: '#',
        icon: 'mdi-lan',
        title: 'Low-latency Anycast',
        text: 'We run <b>global networks of high-performance frontend DNS servers</b>. Your query is routed to the '
              + '<b>closest server</b> via Anycast, so clients receive answers as fast as possible.',
      },
      {
        href: '#',
        icon: 'mdi-flower',
        title: 'Open Source',
        text: 'deSEC runs <b>100% on free and open-source</b> software. Start hacking away!',
      },
      {
        href: '#',
        icon: 'mdi-gift',
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
        icon: 'mdi-heart-broken',
        teaser: 'deSEC API and web services have been unavailable on 17 Oct 2020 starting at 4:26 am UTC and resumed ' +
            'normal operations at 10:13 am UTC. DNS operations continued throughout.',
        button: 'deSEC Status Details',
        href: '//desec-status.net/',
      },
    ],
  })
}
</script>
