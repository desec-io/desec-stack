<template>
  <v-container fluid fill-height>
    <v-layout align-center justify-center>
      <v-flex style="max-width: 400px">
        <v-container text-xs-center>
          <v-form v-on:submit.prevent="signup" v-model="valid">
            <v-layout column>
              <v-flex xs12 mb-2>
                <img src="@/assets/logo.png">
              </v-flex>
              <v-flex xs12 headline mb-5>
                Sign up a new account
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
              <v-flex>
                <v-checkbox
                  v-model="terms"
                  type="checkbox"
                  required
                  :disabled="working"
                  :rules="terms_rules"
                >
                  <template slot="label">
                    <v-layout>
                      <v-flex x12>
                        Yes, I agree to the <a @click.stop href="//desec.io/" target="_blank">terms of service</a> and
                        the <a @click.stop href="//desec.io/" target="_blank">privacy policy</a>.
                      </v-flex>
                    </v-layout>
                  </template>
                </v-checkbox>
              </v-flex>
              <v-flex x12>
                <v-btn
                  block
                  type="submit"
                  color="primary"
                  :disabled="!valid || working"
                  :loading="working"
                >Sign Up</v-btn>
              </v-flex>
            </v-layout>
          </v-form>
          <v-layout column>
            <v-flex xs12 mt-5>
              Already registered?
              <v-btn flat color="primary" :to="{name: 'LogIn'}">Sign in</v-btn>
            </v-flex>
          </v-layout>
        </v-container>
      </v-flex>
    </v-layout>
  </v-container>
</template>

<script>
import {HTTP} from '../http-common'
import router from '../router'

export default {
  name: 'SignUp',
  data: () => ({
    valid: false,
    working: false,
    email: '',
    password: '',
    terms: false,
    email_rules: [ v => !!v || 'We will need an email address for account recovery and such' ],
    email_errors: [],
    password_rules: [
      v => !!v || 'Choose a password to protect access to your account.',
      v => v.toString().length >= 8 || 'Your password must contain at least 8 characters.'
    ],
    terms_rules: [ v => !!v || 'You can only use our service if you agree with the terms' ],
    hide_password: true,
    errors: []
  }),
  methods: {
    async login () {
      this.working = true
      this.errors = []
      try {
        await HTTP.post('auth/users/create/', {email: this.email, password: this.password})
        const loginResponse = await HTTP.post('auth/token/create/', {email: this.email, password: this.password})
        HTTP.defaults.headers.common['Authorization'] = 'Token ' + loginResponse.data.auth_token
        router.replace({name: 'DomainList'}) // TODO replace with welcome new users?
      } catch (error) {
        if (error.response) {
          // The request was made and the server responded with a status code
          // that falls out of the range of 2xx
          if (error.response.status < 500) {
            // 3xx or 4xx
            if ('email' in error.response.data) {
              this.email_errors = [ error.response.data.email[0] ]
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
