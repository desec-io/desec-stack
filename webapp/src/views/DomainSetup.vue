<template>
  <div>
    <v-alert
        :value="isNew"
        type="success"
    >
      Your domain <b>{{ domain }}</b> has been successfully created!
    </v-alert>
    <v-card-text>
      <p>
        The following steps need to be completed in order to use
        <span class="fixed-width">{{ domain }}</span> with deSEC.
      </p>

      <div v-if="!$store.state.authenticated">
        <div class="subtitle-1">
          <v-icon>mdi-numeric-0-circle</v-icon>
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

      <div class="mt-2 subtitle-1">
        <v-icon>mdi-numeric-1-circle</v-icon>
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
                    v-clipboard:copy="ns.join('\n')"
                    v-clipboard:success="copySuccess"
                    v-clipboard:error="copyError"
                    outlined
                    text
                >
                  <v-icon>mdi-content-copy</v-icon>
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

      <div class="subtitle-1">
        <v-icon>mdi-numeric-2-circle</v-icon>
        Enable DNSSEC
      </div>
      <p>
        To enable DNSSEC security, you also need to forward one or more of the following information to your
        domain provider. Which information they accept varies from provider to provider; unfortunately there are
        also providers that do not support DNSSEC altogether.
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
                    v-clipboard:copy="t.data"
                    v-clipboard:success="copySuccess"
                    v-clipboard:error="copyError"
                    outlined
                    text
                >
                  <v-icon>mdi-content-copy</v-icon>
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

      <div class="subtitle-1">
        <v-icon>mdi-numeric-3-circle</v-icon>
        Check Setup
      </div>
      <p>
        All set up correctly? <a :href="`https://dnssec-analyzer.verisignlabs.com/${domain}`" target="_blank">Take
        a
        look at DNSSEC Analyzer</a> to check the status of your domain.
      </p>

    </v-card-text>

    <!-- copy snackbar -->
    <v-snackbar v-model="snackbar">
      {{ snackbar_text }}

      <template v-slot:action="{ attrs }">
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
export default {
  name: 'DomainSetup',
  props: {
    domain: {
      type: String,
      required: true,
    },
    isNew: {
      type: Boolean,
      default: false,
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
      default: () => process.env.VUE_APP_DESECSTACK_NS.split(' '),
    },
  },
  data: () => ({
    snackbar: false,
    snackbar_text: '',
    tab1: 'ns',
    tab2: 'ds',
    LOCAL_PUBLIC_SUFFIXES: process.env.VUE_APP_LOCAL_PUBLIC_SUFFIXES.split(' '),
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
    copySuccess: function () {
      this.showSnackbar("Copied to clipboard.");
    },
    copyError: function () {
      this.showSnackbar("Copy to clipboard failed. Please try again manually.");
    },
    showSnackbar: function (text) {
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
