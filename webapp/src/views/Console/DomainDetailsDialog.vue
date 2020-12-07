<template>
  <v-dialog
    v-model="show"
    max-width="700px"
    persistent
    @keydown.esc="close"
  >
    <v-card>
      <v-card-title>
        <div class="title">
          Domain details for <b>{{ name }}</b>
        </div>
        <v-spacer />
        <v-icon @click.stop="close">
          mdi-close
        </v-icon>
      </v-card-title>
      <v-divider />
      <v-alert
        :value="isNew"
        type="success"
      >
        Your domain <b>{{ name }}</b> has been successfully created!
      </v-alert>
      <v-card-text>
        <div class="mt-2 subtitle-1"><v-icon>mdi-numeric-1-circle</v-icon> Delegate your domain</div>
        <p>
          Forward the following information to the organization/person where you bought the domain
          <strong>{{name}}</strong> (usually your provider or technical administrator):
        </p>
        <v-layout flex align-end>
          <div class="caption font-weight-medium">NS records</div>
          <!--v-spacer></v-spacer>
          <div v-if="copied != 'ns'">
            <v-icon
                    small
                    v-clipboard:copy="ns.join('\n')"
                    v-clipboard:success="() => (copied = 'ns')"
                    v-clipboard:error="() => (copied = '')"
            >mdi-content-copy</v-icon>
          </div>
          <div v-else>copied! <v-icon small>mdi-check</v-icon></div-->
        </v-layout>
        <pre
                class="mb-3 pa-3"
                v-clipboard:copy="ns.join('\n')"
                v-clipboard:success="() => (copied = 'ns')"
                v-clipboard:error="() => (copied = '')"
        >{{ ns.join('\n') }}</pre>

        <p>
          Once your provider processes this information, the Internet will start directing DNS queries to deSEC.
        </p>

        <div class="subtitle-1"><v-icon>mdi-numeric-2-circle</v-icon> Enable DNSSEC</div>
        <p>
          You also need to forward <strong>either the <span class="code">DS</span> records <em>or</em> the
          <span class="code">DNSKEY</span> record(s)</strong> to your domain provider (depending on what they accept).
          This is required to enable DNSSEC security.
        </p>

        <div v-if="ds.length > 0">
          <v-layout flex align-end>
            <div class="caption font-weight-medium">DS records</div>
            <!--v-spacer></v-spacer>
            <div v-if="copied != 'ds'">
              <v-icon
                      small
                      v-clipboard:copy="ds.join('\n')"
                      v-clipboard:success="() => (copied = 'ds')"
                      v-clipboard:error="() => (copied = '')"
              >mdi-content-copy</v-icon>
            </div>
            <div v-else>copied! <v-icon small>mdi-check</v-icon></div-->
          </v-layout>
          <pre
                  class="mb-3 pa-3"
                  v-clipboard:copy="ds.join('\n')"
                  v-clipboard:success="() => (copied = 'ds')"
                  v-clipboard:error="() => (copied = '')"
          >{{ ds.join('\n') }}</pre>
        </div>
        <div v-else>
          <div class="caption font-weight-medium">DS records</div>
          <p>(unavailable, please contact support)</p>
        </div>

        <div v-if="dnskey.length > 0">
          <v-layout flex align-end>
            <div class="caption font-weight-medium">DNSKEY records</div>
            <!--v-spacer></v-spacer>
            <div v-if="copied != 'dnskey'">
              <v-icon
                      small
                      v-clipboard:copy="dnskey.join('\n')"
                      v-clipboard:success="() => (copied = 'dnskey')"
                      v-clipboard:error="() => (copied = '')"
              >mdi-content-copy</v-icon>
            </div>
            <div v-else>copied! <v-icon small>mdi-check</v-icon></div-->
          </v-layout>
          <pre
                  class="mb-3 pa-3"
                  v-clipboard:copy="dnskey.join('\n')"
                  v-clipboard:success="() => (copied = 'dnskey')"
                  v-clipboard:error="() => (copied = '')"
          >{{ dnskey.join('\n') }}</pre>
        </div>
        <div v-else>
          <div class="caption font-weight-medium">DNSKEY records</div>
          <p>(unavailable, please contact support)</p>
        </div>

        <div v-if="this.LOCAL_PUBLIC_SUFFIXES.some((suffix) => name.endsWith(`.${suffix}`))">
          <v-divider class="pb-3"></v-divider>
          <p>
            The IP <span v-if="ips.length == 1">address</span><span v-else>addresses</span> associated with
            this domain <span v-if="ips.length == 1">is:</span><span v-else>are:</span>
          </p>
          <ul class="mb-4">
            <li v-for="ip in ips" :key="ip"><span class="fixed-width">{{ip}}</span></li>
            <li v-if="!ips.length">(none)</li>
          </ul>
        </div>
        <p>
          All set up correctly? <a :href="`https://dnssec-analyzer.verisignlabs.com/${name}`" target="_blank">Take a
          look at DNSSEC Analyzer to check the status of your domain.</a>
        </p>

        <v-divider></v-divider>

        <p class="mt-4">
          The DNS information of this domain was last changed {{ published ? timeAgo.format(new Date(published)) : 'never' }}.
        </p>
      </v-card-text>
      <v-card-actions class="pa-3">
        <v-spacer />
        <v-btn depressed :to="{name: 'donate'}">Donate</v-btn>
        <v-btn
          color="primary"
          dark
          depressed
          @click.native="close"
        >
          Close
        </v-btn>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { timeAgo } from '@/utils';

export default {
  name: 'DomainDetailsDialog',
  props: {
    name: {
      type: String,
      required: true,
    },
    isNew: {
      type: Boolean,
      default: false,
    },
    ds: {
      type: Array,
      required: true,
    },
    dnskey: {
      type: Array,
      required: true,
    },
    ns: {
      type: Array,
      default: () => process.env.VUE_APP_DESECSTACK_NS.split(' '),
    },
    ips: {
      type: Array,
      default: () => [],
    },
    published: {
      type: String,
      default: '(unknown)',
    },
    value: {
      type: Boolean,
      default: true,
    },
  },
  data: () => ({
    copied: '',
    LOCAL_PUBLIC_SUFFIXES: process.env.VUE_APP_LOCAL_PUBLIC_SUFFIXES.split(' '),
    timeAgo: timeAgo,
  }),
  computed: {
    show: {
      get() {
        return this.value
      },
      set(value) {
         this.$emit('input', value)
      }
    }
  },
  methods: {
    close() {
      this.show = false;
      this.copied = '';
    },
  },
};
</script>

<style scoped>
  .caption {
    text-transform: uppercase;
  }
  .code {
    font-family: monospace;
  }
  pre {
    background: lightgray;
    overflow: auto;
  }
</style>
