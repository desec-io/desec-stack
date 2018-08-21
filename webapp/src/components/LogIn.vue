<template>
  <v-flex style="max-width: 400px">
    <v-container text-xs-center>
      <v-form v-on:submit.prevent="login" v-model="valid">
        <v-layout column>
          <v-flex xs12 mb-5>
            <img src="@/assets/logo.png">
          </v-flex>
          <v-flex x12>
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
          </v-flex>
          <v-flex x12>
            <v-text-field
              v-model="email"
              label="E-Mail"
              outline
              required
              :disabled="working"
              :rules="email_rules"
              :error-messages="email_errors"
              @change="email_errors=[]"
            ></v-text-field>
          </v-flex>
          <v-flex x12>
            <v-text-field
              v-model="password"
              label="Password"
              :append-icon="hide_password ? 'visibility' : 'visibility_off'"
              @click:append="() => (hide_password = !hide_password)"
              :type="hide_password ? 'password' : 'text'"
              outline
              required
              :disabled="working"
              :rules="password_rules"
            ></v-text-field>
          </v-flex>
          <v-flex x12>
            <v-btn
              block
              type="submit"
              color="primary"
              :disabled="!valid || working"
              :loading="working"
            >Log In</v-btn>
          </v-flex>
        </v-layout>
      </v-form>
      <v-layout column>
        <v-flex xs12 mt-5>
          No account yet?
          <v-btn flat color="primary" :to="{name: 'SignUp'}">Sign up</v-btn>
        </v-flex>
      </v-layout>
    </v-container>
  </v-flex>
</template>

<script>
import {HTTP} from '../http-common'
import router from '../router'

export default {
  name: 'LogIn',
  data: () => ({
    valid: false,
    working: false,
    email: '',
    password: '',
    terms: false,
    email_rules: [ v => !!v || 'Please enter the email address associated with your account' ],
    email_errors: [],
    password_rules: [
      v => !!v || 'Enter your password to log in'
    ],
    hide_password: true,
    errors: []
  }),
  methods: {
    async login () {
      this.working = true
      this.errors = []
      try {
        const response = await HTTP.post('auth/token/create/', {email: this.email, password: this.password})
        HTTP.defaults.headers.common['Authorization'] = 'Token ' + response.data.auth_token
        if ('go' in this.$route.query && this.$route.query.go) {
          router.replace(this.$route.query.go)
        } else {
          router.replace({name: 'DomainList'})
        }
      } catch (error) {
        if (error.response) {
          // The request was made and the server responded with a status code
          // that falls out of the range of 2xx
          if (error.response.status < 500) {
            // 3xx or 4xx
            if ('email' in error.response.data) {
              this.email_errors = [error.response.data.email[0]]
            } else if ('non_field_errors' in error.response.data) {
              this.errors = error.response.data.non_field_errors
            } else {
              this.errors = error.response
              console.log('Error', error)
            }
          } else {
            // 5xx
            this.errors = ['Something went wrong at the server, but we currently do not know why. The customer support was already notified.']
            console.log('Error', error)
          }
        } else if (error.request) {
          this.errors = ['Cannot contact our servers. Are you offline?']
        } else {
          this.errors = [error.message]
        }
      }
      this.working = false
    }
  }
}
</script>

<style scoped>
</style>
