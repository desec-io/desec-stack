<!--
TODO
- not logged in: vertical align bottom logo area
-->

<template>
  <v-app id="inspire">
    <v-content>
      <v-container v-if="!loggedIn()" fluid fill-height>
        <v-layout column align-center justify-center>
          <v-flex xs12 sm8 md4>
            <img src="./assets/logo.png">
            <p>not logged in</p>
          </v-flex>
          <v-flex xs12 sm8 md4>
            <router-view/>
          </v-flex>
        </v-layout>
      </v-container>

      <v-container v-else fluid align-start>
        <v-flex md10 offset-md1>
          <v-layout row justify-space-between>
            <v-flex>
              <img src="./assets/logo.png">
            </v-flex>
            <v-flex text-xs-right>
              logged in
            </v-flex>
          </v-layout>
        </v-flex>
        <v-layout row>
          <v-flex md10 offset-md1>
            <router-view/>
          </v-flex>
        </v-layout>
      </v-container>
    </v-content>
  </v-app>
</template>

<script>
export default {
  name: 'App',
  data: () => ({
    // loggedIn: true
  }),
  methods: {
    loggedIn () {
      return (this.$router.currentRoute.path !== '/')
    }
  }
}
</script>

<style>
</style>
