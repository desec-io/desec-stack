<template>
  <v-dialog
    v-model="value"
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
        <p>
          To properly secure your domain with DNSSEC, please forward the following information to your domain registrar:
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

        <p>Once your domain registrar processes this information, your deSEC DNS setup will be ready to use.</p>

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
  methods: {
    close() {
      this.$emit('input', false);
      this.copied = '';
    },
  },
};
</script>

<style scoped>
  .caption {
    text-transform: uppercase;
  }
  pre {
    background: lightgray;
    overflow: auto;
  }
</style>
