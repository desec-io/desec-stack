<template>
  <div v-if="hasAutomaticDelegationMaintenance">
    <p class="mt-4">
      You're domain is fully configured.
    </p>
  </div>
  <div v-else>
    <p class="mt-4">
      The following steps need to be completed in order to use your domain with deSEC.
    </p>

    <div v-if="!user.authenticated">
      <div class="my-2 text-h6">
        <v-icon class="primary--text">{{ mdiNumeric0Circle }}</v-icon>
        Configure your DNS records
      </div>
      <p>Before delegating your domain, you might want to take the following steps:</p>
      <ul>
        <li><router-link :to="{name: 'reset-password'}" target="_blank">Set up a password for your deSEC account</router-link>,</li>
        <li>Log in and <b>configure the DNS records for your domain</b>,</li>
        <li>Proceed with the next step below.</li>
      </ul>
    </div>

    <div class="my-2 text-h6">
      <v-icon class="primary--text">{{ mdiNumeric1Circle }}</v-icon>
      Delegate your domain
    </div>
    <p>
      Forward the following information to the organization/person where you bought the domain
      <strong>{{ domain }}</strong> (usually your provider or technical administrator):
    </p>
    <v-card class="mb-4" v-if="ns">
      <v-card-title class="grey lighten-2">
        <v-row>
          <v-col cols="auto">Nameservers</v-col>
          <v-spacer></v-spacer>
          <v-col class="text-right">
            <v-btn @click="copyToClipboard(ns.join('\n'))" text small>
              <v-icon>{{ mdiContentCopy }}</v-icon>
              Copy
            </v-btn>
          </v-col>
        </v-row>
      </v-card-title>
      <v-divider></v-divider>
      <v-card-text v-if="ns.length">
        <record-list readonly type="NS" :value="ns"></record-list>
      </v-card-text>
      <v-alert type="error" v-else>Nameservers could not be retrieved.</v-alert>
    </v-card>
    <p>Once your provider processes this information, the Internet will start directing DNS queries to deSEC.</p>

    <div v-if="user.authenticated">
      <div class="my-2 text-h6">
        <v-icon class="primary--text">{{ mdiNumeric2Circle }}</v-icon>
        Enable DNSSEC
      </div>
      <p>
        You also need to forward the following DNSSEC information to your domain provider.
        The exact steps depend on your provider:
        You may have to enter the information as a block in either <b>DS format</b> or <b>DNSKEY format</b>, or as
        <b>individual values</b>.
      </p>
      <p class="small">
        Notes: When using block format, some providers require you to add the domain name in the beginning. (Also,
        <a class="grey--text text--darken-1" href="https://github.com/oskar456/cds-updates" target="_blank">depending on
        your domain's suffix</a>, we will perform this step automatically.)
      </p>

      <v-card class="mb-4">
        <v-card-title class="grey lighten-2">
          <v-row>
            <v-col cols="auto">DS Format</v-col>
            <v-spacer></v-spacer>
            <v-col class="text-right">
              <v-btn @click="copyToClipboard(ds.join('\n'))" text small>
                <v-icon>{{ mdiContentCopy }}</v-icon>
                Copy
              </v-btn>
            </v-col>
          </v-row>
        </v-card-title>
        <v-divider></v-divider>
        <v-card-text style="overflow-x: scroll; overflow-y: hidden" v-if="ds.length">
          <record-list readonly type="DS" :value="ds"></record-list>
        </v-card-text>
        <v-alert type="error" v-else>Parameters could not be retrieved. (Are you logged in?)</v-alert>
      </v-card>

      <v-card>
        <v-card-title class="grey lighten-2">
          <v-row>
            <v-col cols="auto">DNSKEY Format</v-col>
            <v-spacer></v-spacer>
            <v-col class="text-right">
              <v-btn @click="copyToClipboard(dnskey.join('\n'))" text small>
                <v-icon>{{ mdiContentCopy }}</v-icon>
                Copy
              </v-btn>
            </v-col>
          </v-row>
        </v-card-title>
        <v-divider></v-divider>
        <v-card-text style="overflow-x: scroll; overflow-y: hidden" v-if="dnskey.length">
          <record-list readonly type="DNSKEY" :value="dnskey"></record-list>
        </v-card-text>
        <v-alert type="error" v-else>Parameters could not be retrieved. (Are you logged in?)</v-alert>
      </v-card>

      <div class="my-2 text-h6">
        <v-icon class="primary--text">{{ mdiNumeric3Circle }}</v-icon>
        Check Setup
      </div>
      <p>
        All set up correctly? <a :href="`https://dnssec-analyzer.verisignlabs.com/${domain}`" target="_blank">Take a
        look at DNSSEC Analyzer</a> to check the status of your domain.
      </p>
    </div>

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
import RecordList from '@/components/Field/RecordList.vue';
import {useUserStore} from "@/store/user";
import {mdiContentCopy, mdiAlert, mdiNumeric0Circle, mdiNumeric1Circle, mdiNumeric2Circle, mdiNumeric3Circle, mdiCheck} from "@mdi/js";

export default {
  name: 'DomainSetup',
  components: {
    RecordList,
  },
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
      default: () => import.meta.env.VITE_APP_DESECSTACK_NS.split(' ').map(v => `${v}.`),
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
    LOCAL_PUBLIC_SUFFIXES: import.meta.env.VITE_APP_LOCAL_PUBLIC_SUFFIXES.split(' '),
  }),
  computed: {
    hasAutomaticDelegationMaintenance: function () {
      let self = this;
      return self.LOCAL_PUBLIC_SUFFIXES.some(
          (suffix) => (
              self.domain.split('.').length == suffix.split('.').length + 1
              && self.domain.endsWith('.' + suffix)
          )
      )
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
