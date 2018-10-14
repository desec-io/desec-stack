<template>
  <v-app id="inspire">
    <v-content>
      <router-view v-if="!authenticated"/>
      <v-container v-else fluid align-start>
        <v-flex md10 offset-md1>
          <v-layout row justify-space-between>
            <v-flex>
              <img src="./assets/logo.png">
            </v-flex>
            <v-flex text-xs-right>
              authenticated
            </v-flex>
          </v-layout>
        </v-flex>
        <v-layout row>
          <v-flex md10 offset-md1>
            <code>{{ $store.state.token }}</code>
            <v-btn
              :loading="working"
              :disabled="working"
              color="secondary"
              @click.native="logout()"
            >
              Logout
            </v-btn>
            <router-view/>
          </v-flex>
        </v-layout>
      </v-container>
    </v-content>
  </v-app>
</template>

<script>
import {logout} from '@/utils'

export default {
  name: 'App',
  data: () => ({
    working: false
  }),
  methods: {
    async logout () {
      this.working = true
      await logout()
      this.working = false
      this.$router.replace({name: 'Login', query: { redirect: this.$route.fullPath }})
    }
  },
  computed: {
    authenticated () {
      return this.$store.state.authenticated
    }
  }
}
</script>

<style>
  html {
    overflow-y: auto;  /* to remove always-there y-scrollbar, cf github.com/vuetifyjs/vuetify/issues/1197 */
  }
  button.hover-red:hover {
    color: #C62828 !important; /* red darken-3 */
  }
</style>
