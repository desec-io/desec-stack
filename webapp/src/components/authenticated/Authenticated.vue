<template>
  <div>
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
  </div>
</template>

<script>
import router from '../../router'
import {HTTP} from '../../http-common'

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
