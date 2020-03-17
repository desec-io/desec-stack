<template>
  <div>
  <v-card outline tile class="pa-md-12 pa-8 elevation-4" style="overflow: hidden">
    <div class="d-none d-md-block triangle-bg"></div>
    <v-container class="pa-0">
      <v-row align="center">
        <v-col class="col-md-6 col-12 py-8 triangle-fg">
          <h1 class="display-1 font-weight-bold">Modern DNS Hosting for Everyone</h1>
          <h3 class="subheading mt-2 py-8 font-weight-regular">
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
                    Create Beta Account
                  </v-btn>
                  <p class="mt-4 body-2 grey--text text--darken-1">While currently in beta test, we have reached stable operation and are approaching official launch.</p>
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
          <p>{{f.text}}</p>
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
          and provides deSEC with our global Anycast networking infrastructure for delivering signed DNS data to the
          public. We trust them because creating and auditing security solutions is their daily business.
        </v-col>
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
      if (this.$refs.form.validate()) this.$router.push({name: 'signup', params: this.email !== '' ? {email: this.email} : {}});
    },
  },
  data: () => ({
    email: '',
    email_rules: [
      v => !!email_pattern.test(v || '') || 'Invalid email address.'
    ],
    valid: false,
    features: [
      {
        href: '#',
        icon: 'mdi-lock-outline',
        title: 'DNSSEC',
        text: 'DNS information hosted with deSEC is signed using DNSSEC, always.',
      },
      {
        href: '#',
        icon: 'mdi-ip-network-outline',
        title: 'IPv6',
        text: 'deSEC is fully IPv6-aware: administration can be done using v6, AAAA-records '
                + 'containing IPv6 addresses can be set up, our name servers are reachable via IPv6.',
      },
      {
        href: '#',
        icon: 'mdi-certificate',
        title: 'DANE / TLSA',
        text: 'Secure your web service with TLSA records, hardening it against fraudulently issued SSL '
                + 'certificates. You can also use other DANE techniques, such as OPENPGPKEY key exchange.',
      },
      {
        href: '#',
        icon: 'mdi-robot',
        title: 'REST API',
        text: 'Configure your DNS information via a modern API. You can easily integrate our API into your scripts, '
              + 'tools, or even CI/CD pipeline.',
      },
      {
        href: '#',
        icon: 'mdi-run-fast',
        title: 'Fast Updates',
        text: 'Updates to your DNS information will be published by deSEC within a few seconds. '
                + 'Minimum required TTLs are low.',
      },
      {
        href: '#',
        icon: 'mdi-flower',
        title: 'Open Source',
        text: 'deSEC runs 100% on free open-source software. Start hacking away ...',
      },
      {
        href: '#',
        icon: 'mdi-lan',
        title: 'Low-latency Anycast',
        text: 'We run a global network of 8 high-performance frontend DNS servers (Europe, US, Asia). Your query is '
              + 'routed to the closest server via Anycast, so clients receive answers as fast as possible.',
      },
      {
        href: '#',
        icon: 'mdi-gift',
        title: 'Non-profit',
        text: 'deSEC is organized as a non-profit charitable organization based in Berlin. We make sure that privacy '
              + 'is not compromised by business interest.',
      },
      {
        href: '#',
        icon: 'mdi-file-certificate',
        title: "Let's Encrypt Integration",
        text: "We provide easy integration with Let's Encrypt and their certbot tool.",
      },
    ],
  })
}
</script>
