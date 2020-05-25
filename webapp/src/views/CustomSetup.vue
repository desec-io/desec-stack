<template>
  <v-container
          class="fill-height"
          fluid
  >
    <v-row
            align="center"
            justify="center"
    >
      <v-col
              cols="12"
              sm="8"
              md="6"
      >
        <v-card class="elevation-12">
          <v-toolbar
                  color="primary"
                  dark
                  flat
          >
            <v-toolbar-title>Domain Registration Completed</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <p>
              Congratulations, you have now configured <span class="fixed-width">{{ $route.params.domain }}</span>!
            </p>
            <h2 class="title">Secure Your Domain</h2>
            <p>
              To properly secure your domain with DNSSEC, please forward the following information to your domain registrar:</p>
            <v-layout flex align-end>
              <div class="caption font-weight-medium">NS records</div>
              <v-spacer></v-spacer>
              <div v-if="copied != 'ns'">
                <v-icon
                  small
                  v-clipboard:copy="nsList.join('\n')"
                  v-clipboard:success="() => (copied = 'ns')"
                  v-clipboard:error="() => (copied = '')"
                >mdi-content-copy</v-icon>
              </div>
              <div v-else>copied! <v-icon small>mdi-check</v-icon></div>
            </v-layout>
            <pre
              class="mb-3 pa-3"
              v-clipboard:copy="nsList.join('\n')"
              v-clipboard:success="() => (copied = 'ns')"
              v-clipboard:error="() => (copied = '')"
            >{{ nsList.join('\n') }}</pre>

            <div v-if="dsList.length > 0">
              <v-layout flex align-end>
                <div class="caption font-weight-medium">DS records (also available via our API)</div>
                <v-spacer></v-spacer>
                <div v-if="copied != 'ds'">
                  <v-icon
                    small
                    v-clipboard:copy="dsList.join('\n')"
                    v-clipboard:success="() => (copied = 'ds')"
                    v-clipboard:error="() => (copied = '')"
                  >mdi-content-copy</v-icon>
                </div>
                <div v-else>copied! <v-icon small>mdi-check</v-icon></div>
              </v-layout>
              <pre
                class="mb-3 pa-3"
                v-clipboard:copy="dsList.join('\n')"
                v-clipboard:success="() => (copied = 'ds')"
                v-clipboard:error="() => (copied = '')"
              >{{ dsList.join('\n') }}</pre>
            </div>
            <div v-else>
              <div class="caption font-weight-medium">DS records (also available via our API)</div>
              <p>(unavailable)</p>
            </div>

            <p>Once your domain registrar processes this information, your deSEC DNS setup will be ready to use.</p>
            <p>
              Questions? Please check out our forum at <a href="https://talk.desec.io/">talk.desec.io</a>. Chances are
              that someone had the same question before.
            </p>

            <h2 class="title">Keep deSEC Going</h2>
            <p>
              To offer free DNS hosting for everyone, deSEC relies on donations only.
              If you like our service, please consider donating.
            </p>
            <p>
              <v-btn block outlined :to="{name: 'donate'}">Donate</v-btn>
            </p>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
  export default {
    name: 'CustomSetup',
    data: () => ({
      copied: '',
      dsList: [],
      nsList: process.env.VUE_APP_DESECSTACK_NS.split(' '),
    }),
    async mounted() {
      let keys = this.$route.params.keys;
      if (keys) {
        this.dsList = keys.map(key => key.ds);
        this.dsList = this.dsList.concat.apply([], this.dsList);
      }
    },
  };
</script>

<style lang="scss" scoped>
  .fixed-width {
    font-family: monospace;
  }
  pre {
    background: lightgray;
    overflow: auto;
  }
</style>
