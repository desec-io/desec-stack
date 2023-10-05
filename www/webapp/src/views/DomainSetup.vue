<template>
  <div v-if="this.LOCAL_PUBLIC_SUFFIXES.some((suffix) => domain.endsWith('.' + suffix))">
    <p class="mt-4">
      You're domain is fully configured.
    </p>
  </div>
  <div v-else>
    <p class="mt-4">
      The following steps need to be completed in order to use
      <span class="fixed-width">{{ domain }}</span> with deSEC.
    </p>

    <div v-if="!user.authenticated">
      <div class="text-subtitle-1">
        <v-icon>{{ mdiNumeric0Circle }}</v-icon>
        DNS Configuration
      </div>
      <p>
        To ensure a smooth transition when moving your domain to deSEC, setup a password for your deSEC account,
        log in and configure the DNS for <span class="fixed-width">{{ domain }}</span>, before you proceed below.
      </p>
      <v-btn outlined block :to="{name: 'reset-password'}" target="_blank">
        Assign Account Password
      </v-btn>
    </div>

    <div class="mt-2 text-subtitle-1">
      <v-icon>{{ mdiNumeric1Circle }}</v-icon>
      Delegate your domain
    </div>

    <p>
      Forward the following information to the organization/person where you bought the domain
      <strong>{{ domain }}</strong> (usually your provider or technical administrator):
    </p>
    <v-card>
      <v-tabs v-model="tab1" background-color="transparent" grow>
        <v-tab href="#ns">Nameservers</v-tab>
      </v-tabs>

      <v-tabs-items v-model="tab1" class="mb-3">
        <v-tab-item value="ns">
          <v-card flat v-if="ns.join('\n')">
            <pre class="pa-3">{{ ns.join('\n') }}</pre>
            <v-card-actions>
              <v-btn
                  @click="copyToClipboard(ns.join('\n'))"
                  outlined
                  text
              >
                <v-icon>{{ mdiContentCopy }}</v-icon>
                copy to clipboard
              </v-btn>
              <v-spacer></v-spacer>
            </v-card-actions>
          </v-card>
          <v-card flat v-else>
            <v-card-text>Nameservers could not be retrieved.</v-card-text>
          </v-card>
        </v-tab-item>
      </v-tabs-items>
    </v-card>

    <p>
      Once your provider processes this information, the Internet will start directing DNS queries to deSEC.
    </p>

    <div class="text-subtitle-1">
      <v-icon>{{ mdiNumeric2Circle }}</v-icon>
      Enable DNSSEC
    </div>
    <p>
      To enable DNSSEC security, you also need to forward one or more of the following information to your
      domain provider. Which information they accept varies from provider to provider.
    </p>

    <v-card>
      <v-tabs
          v-model="tab2"
          background-color="transparent"
          grow
      >
        <v-tab v-for="t in tabs" :key="t.key" :href="'#' + t.key">{{ t.title }}</v-tab>
      </v-tabs>

      <v-tabs-items v-model="tab2" class="mb-4">
        <v-tab-item v-for="t in tabs" :key="t.key" :value="t.key">
          <v-card flat v-if="t.data">
            <v-card-text>{{ t.banner }}</v-card-text>
            <pre class="pa-3">{{ t.data }}</pre>
            <v-card-actions>
              <v-btn
                  @click="copyToClipboard(t.data)"
                  outlined
                  text
              >
                <v-icon>{{ mdiContentCopy }}</v-icon>
                copy to clipboard
              </v-btn>
              <v-spacer></v-spacer>
            </v-card-actions>
          </v-card>
          <v-card flat v-else>
            <v-card-text>
              Records could not be retrieved, please
              <router-link :to="{name: 'login'}">log in</router-link>.
            </v-card-text>
          </v-card>
        </v-tab-item>
      </v-tabs-items>
    </v-card>

    <div class="text-subtitle-1">
      <v-icon>{{ mdiNumeric3Circle }}</v-icon>
      Check Setup
    </div>
    All set up correctly? <a :href="`https://dnssec-analyzer.verisignlabs.com/${domain}`" target="_blank">Take
    a
    look at DNSSEC Analyzer</a> to check the status of your domain.

    <!-- copy snackbar -->
    <v-snackbar v-model="snackbar">
      <v-icon v-if="snackbar_icon">{{ snackbar_icon }}</v-icon>
      {{ snackbar_text }}

      <template #action="{ attrs }">
        <v-btn
            color="pink"
            text
            v-bind="attrs"
            @click="snackbar = false"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script>
import {useUserStore} from "@/store/user";
import {mdiContentCopy, mdiAlert, mdiNumeric0Circle, mdiNumeric1Circle, mdiNumeric2Circle, mdiNumeric3Circle, mdiCheck} from "@mdi/js";

export default {
  name: 'DomainSetup',
  props: {
    domain: {
      type: String,
      required: true,
    },
    ds: {
      type: Array,
      default: () => [],
    },
    dnskey: {
      type: Array,
      default: () => [],
    },
    ns: {
      type: Array,
      default: () => import.meta.env.VITE_APP_DESECSTACK_NS.split(' '),
    },
  },
  data: () => ({
    mdiAlert,
    mdiCheck,
    mdiContentCopy,
    mdiNumeric0Circle,
    mdiNumeric1Circle,
    mdiNumeric2Circle,
    mdiNumeric3Circle,
    user: useUserStore(),
    snackbar: false,
    snackbar_icon: '',
    snackbar_text: '',
    tab1: 'ns',
    tab2: 'ds',
    LOCAL_PUBLIC_SUFFIXES: import.meta.env.VITE_APP_LOCAL_PUBLIC_SUFFIXES.split(' '),
  }),
  computed: {
    tabs: function () {
      let self = this;
      return [
        {
          key: 'ds', title: 'DS Records', data: self.ds.join('\n'),
          banner: 'Your provider may require you to input this information as a block or as individual values. ' +
              'To obtain individual values, split the text below at the spaces to obtain the key tag, algorithm, ' +
              'digest type, and digest (in this order).'
        },
        {
          key: 'dnskey', title: 'DNSKEY Records', data: self.dnskey.join('\n'),
          banner: 'Your provider may require you to input this information as a block or as individual values. ' +
              'To obtain individual values, split the text below at the spaces to obtain the flags, protocol, ' +
              'algorithm, and public key (in this order).'
        },
      ]
    },
  },
  methods: {
    copyToClipboard: async function (text) {
      try {
        await navigator.clipboard.writeText(text).then(
            () => {
              this.showSnackbar("Copied to clipboard.", mdiCheck);
            },
            () => {
              this.showSnackbar("Copy to clipboard not allowed. Please try again manually.", mdiAlert);
            },
        );
      } catch (e) {
        this.showSnackbar("Copy to clipboard failed. Please try again manually.", mdiAlert);
      }
    },
    showSnackbar: function (text, icon = '') {
      this.snackbar_icon = icon;
      this.snackbar_text = text;
      this.snackbar = true;
    }
  },
};
</script>

<style lang="scss" scoped>
.caption {
  text-transform: uppercase;
}

.code, .fixed-width {
  font-family: monospace;
}

pre {
  overflow: auto;
}
</style>
