<template>
  <v-card flat>
    <v-form v-model="valid" v-on:submit.prevent="login">
      <v-toolbar flat>
        <v-toolbar-title>Log in</v-toolbar-title>
      </v-toolbar>
      <v-card-text>
        <v-alert :value="errors && errors.length" type="error">
          <div v-if="errors.length > 1">
            <li v-for="error of errors" :key="error.message">
              <b>{{ error.message }}</b>
              {{ error }}
            </li>
          </div>
          <div v-else>
            {{ errors[0] }}
          </div>
        </v-alert>
        <v-text-field
          v-model="email"
          :rules="email_rules"
          label="E-mail"
          required
        ></v-text-field>
        <v-text-field
          v-model="password"
          :append-icon="hide_password ? 'visibility' : 'visibility_off'"
          @click:append="() => (hide_password = !hide_password)"
          :type="hide_password ? 'password' : 'text'"
          label="Enter your password"
          counter
          required
        ></v-text-field>
      </v-card-text>
      <v-card-actions>
        <v-btn
          type="submit"
          color="primary"
          :disabled="!valid || working"
          id="login-button"
          :loading="working"
        >
          Log in
        </v-btn>
      </v-card-actions>
    </v-form>
  </v-card>
</template>

<script>
import {HTTP} from '../http-common'
import router from '../router'

export default {
  name: 'LogIn',
  data: () => ({
    ack: false,
    email: '',
    email_rules: [
      v => !!v || 'E-mail is required',
      v => /^\w+([.-]?\w+)*@\w+([.-]?\w+)*(\.\w{2,3})+$/.test(v) || 'E-mail must be valid'
    ],
    hide_password: true,
    password: '',
    valid: false,
    working: false,
    errors: []
  }),
  methods: {
    async login () {
      this.errors = []
      this.working = true
      try {
        const response = await HTTP.post('auth/token/create/', {email: this.email, password: this.password})
        HTTP.defaults.headers.common['Authorization'] = 'Token ' + response.data.auth_token
        if ('go' in this.$route.query && this.$route.query.go) {
          router.replace(this.$route.query.go)
        } else {
          router.replace({name: 'DomainList'})
        }
      } catch (e) {
        this.working = false
        try {
          this.errors = e.response.data.non_field_errors
        } catch (ex) {
          this.errors = [e, ex]
        }
      }
    }
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
  #login-button {
    width: 100%;
  }
</style>
