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
            <v-alert :value="!!(errors && errors.length)" type="error">
              <div v-if="errors.length > 1">
                <li v-for="error of errors" :key="error.message" >
                  <b>{{ error.message }}</b>
                  {{ error }}
                </li>
              </div>
              <div v-else>
                {{ errors[0] }}
              </div>
            </v-alert>
            <p>
              Congratulations, you are now the owner of <span class="fixed-width">{{ $route.params.domain }}</span>!
            </p>
            <h2 class="title">Set Up Your Domain</h2>
            <p>
              All operations on your domain require the following authorization token listed below:
            </p>
            <p align="center">
              <code>{{token}}</code>
            </p>
            <p>
              Please keep this token in a safe place.
              If lost, it cannot be recovered and must be replaced with a new token.
            </p>
            <p>
              There are several options to connect your new domain name to an IP address.
              Choose an option that is right for you, then confirm that your setup is working using the check below.
            </p>
            <v-expansion-panels class="mb-4" focusable>
              <v-expansion-panel>
                <v-expansion-panel-header class="subtitle-1">Configure Your Router</v-expansion-panel-header>
                <v-expansion-panel-content>
                  <p>
                    To continuously update your domain to point to your home router, configure your
                    router or any other dynamic DNS client in your network with the following parameters:
                  </p>

                  <v-simple-table>
                    <tbody>
                    <tr>
                      <td>URL</td>
                      <td class="fixed-width">https://update.{{LOCAL_PUBLIC_SUFFIXES[0]}}/</td>
                    </tr>
                    <tr>
                      <td>Username</td>
                      <td class="fixed-width">{{domain}}</td>
                    </tr>
                    <tr>
                      <td>Password</td>
                      <td class="fixed-width">{{token}}</td>
                    </tr>
                    </tbody>
                  </v-simple-table>

                  <p>
                    Please only update your IP address when it has changed. If your client is
                    unable to determine when your address changes, please refer to our
                    <a href="https://desec.readthedocs.io/en/latest/dyndns/configure.html">documentation</a>
                    for alternative IP update approaches.
                  </p>
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header class="subtitle-1">One-Off Manual Update</v-expansion-panel-header>
                <v-expansion-panel-content>
                  <p>
                    Your domain can be configured to your current public IP address as seen by our servers.
                    To update your IP, open the following link in any way.
                  </p>
                  <p>
                    <a :href="updateURL" class="fixed-width">{{ updateURL }}</a>
                  </p>
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header class="subtitle-1">Alternative IP Update Approaches</v-expansion-panel-header>
                <v-expansion-panel-content>
                  <p>
                    For alternative approaches to updating your IP address and for a
                    detailed explanation of the update protocol, please refer to our
                    <a href="https://desec.readthedocs.io/en/latest/dyndns/update-api.html">documentation</a>.
                  </p>
                </v-expansion-panel-content>
              </v-expansion-panel>
            </v-expansion-panels>
            <p>
              Questions? Please check out our forum at <a href="https://talk.desec.io/">talk.desec.io</a>. Chances are
              that someone had the same question before.
            </p>

            <h2 class="title">Check Domain Status</h2>
            <v-alert type="info" v-if="ips !== undefined && ips.length === 0">
              <p>
                Currently, no IPv4 or IPv6 address is associated with
                <span class="fixed-width">{{ $route.params.domain }}</span>.
                Please verify that your client is using the credentials provided by deSEC and then come back to check
                again.
              </p>
              <v-btn depressed outlined block @click="check" :loading="working">Check Again</v-btn>
            </v-alert>
            <v-alert type="success" v-if="ips !== undefined && ips.length > 0">
              <p>
                The IP <span v-if="ips.length > 1">addresses</span><span v-if="ips.length === 1">address</span>
                associated with <span class="fixed-width">{{ $route.params.domain }} </span>
                <span v-if="ips.length > 1">are:</span><span v-if="ips.length === 1">is:</span>
              </p>
              <ul class="mb-4">
                <li v-for="ip in ips" :key="ip"><span class="fixed-width">{{ip}}</span></li>
              </ul>
              <p>
                The last time your DNS information changed was at {{lastChanged}}.
              </p>
              <p>
                Your deSEC account setup looks good and is ready to use.
                Enjoy!
              </p>
              <p>
                <v-btn depressed outlined block @click="check" :loading="working">Update</v-btn>
              </p>
              <p>
                Please note that deSEC only assigns your IP address to your domain name.
                To connect to services on your domain, further configuration of your firewall etc. may be necessary.
              </p>
            </v-alert>

            <div v-if="!$store.state.authenticated">
              <h2 class="title">Optional: Assign deSEC Account Password</h2>
              <p>
                To use more features of deSEC, assign a password to your account. This is not required for using deSEC
                for dynamic DNS only, but enables to you add more domains and other DNS information.
                You can also assign a password later at any time.
              </p>
              <v-btn outlined block :to="{name: 'reset-password'}">
                Assign Account Password
              </v-btn>
            </div>

            <h2 class="title mt-4">Keep deSEC Going</h2>
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
  import axios from 'axios';

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {
    },
  });

  export default {
    name: 'DynSetup',
    data: () => ({
      working: false,
      domain: undefined,
      errors: [],
      ips: undefined,
      token: undefined,
      LOCAL_PUBLIC_SUFFIXES: process.env.VUE_APP_LOCAL_PUBLIC_SUFFIXES.split(' '),
      lastChanged: undefined,
    }),
    async mounted() {
      if ('domain' in this.$route.params && this.$route.params.domain !== undefined) {
        this.domain = this.$route.params.domain;
      }
      this.token = this.$route.hash.substr(1);
      this.check();
    },
    computed: {
      updateURL: function () {
        return 'https://update.' + this.LOCAL_PUBLIC_SUFFIXES[0] +
                '/update?username=' + this.domain + '&password=' + this.token;
      }
    },
    methods: {
      async check() {
        this.working = true;
        this.errors = [];
        try {
          let responseDomain = await HTTP.get(`domains/${this.domain}/`, {headers: {'Authorization': `Token ${this.token}`}});
          this.lastChanged = responseDomain.data.published;
        } catch (error) {
          this.ips = undefined;
          this.errorHandler(error);
        }

        this.ips = [];
        try {
          this.ips = this.ips.concat(await this.retrieveRecords('A') || []);
          this.ips = this.ips.concat(await this.retrieveRecords('AAAA') || []);
        } catch (e) {
          this.ips = undefined;
        }
        this.working = false;
      },
      async retrieveRecords(qtype) {
        try {
          let response = await HTTP.get(
                  `domains/${this.domain}/rrsets/@/${qtype}/`,
                  {headers: {'Authorization': `Token ${this.token}`}}
          );
          return response.data.records;
        } catch (error) {
          return this.errorHandler(error);
        }
      },
      errorHandler(error) {
        if (error.response) {
          // status is not 2xx
          if (error.response.status < 500) {
            // 3xx or 4xx
            if (error.response.status === 404) {
              return null;
            }
            this.errors = error.response;
          } else {
            // 5xx
            this.errors = ['Something went wrong at the server, but we currently do not know why. The support was already notified.'];
          }
        } else if (error.request) {
          this.errors = ['Cannot contact our servers. Are you offline?'];
        } else {
          this.errors = [error.message];
        }
        throw this.errors
      },
    },
  };
</script>

<style lang="scss">
  .fixed-width {
    font-family: monospace;
  }
</style>
