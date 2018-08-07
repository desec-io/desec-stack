<!--
TODO
- not logged in: vertical align bottom logo area
-->

<template>
  <v-app id="inspire">
    <v-content>
      <v-container fluid fill-height>
        <v-layout column align-center justify-center>
          <v-flex xs12 sm8 md4>
            <img src="./assets/logo.png">
          </v-flex>
          <v-flex xs12 sm8 md4>
            <router-view/>
          </v-flex>
        </v-layout>
      </v-container>
    </v-content>
  </v-app>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
</style>
