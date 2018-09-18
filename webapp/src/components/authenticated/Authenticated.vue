<template>
  <v-container fluid align-start>
    <v-flex md10 offset-md1>
      <v-layout row justify-space-between>
        <v-flex>
          <img src="../../assets/logo.png">
        </v-flex>
        <v-flex text-xs-right>
          authenticated
        </v-flex>
      </v-layout>
    </v-flex>
    <v-layout row>
      <v-flex md10 offset-md1>
        <code>{{ token }}</code>
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
</template>

<script>
import router from '../../router'
import {HTTP} from '../../utils'

export default {
  name: 'Authenticated',
  data: () => ({
    token: '',
    working: false
  }),
  mounted () {
    if (!HTTP.defaults.headers.common['Authorization']) {
      router.replace({ name: 'LogIn', query: { go: this.$route.path } })
    } else {
      this.token = HTTP.defaults.headers.common['Authorization']
    }
  },
  methods: {
    async logout () {
      this.working = true
      try {
        await HTTP.post('auth/token/destroy/')
      } catch (e) {
        this.working = false
        console.log(e) // TODO improve error handling
      }
      HTTP.defaults.headers.common['Authorization'] = ''
      router.go({name: 'LogIn'})
    }
  }
}
</script>

<style>
</style>
