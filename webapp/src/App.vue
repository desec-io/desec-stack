<!--
TODO
- not logged in: vertical align bottom logo area
-->

<template>
  <v-app id="inspire">
    <v-content>
      <v-container fill-height>
        <v-layout align-center justify-center>
          <router-view/>
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
