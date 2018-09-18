<template>
  <v-container fluid fill-height>
    <v-layout align-center justify-center>
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
              <v-btn flat color="primary" :to="{name: 'SignUp'}">Sign up</v-btn>
              <v-dialog v-model="reset_dialog" persistent max-width="500px">
                <v-btn slot="activator" flat color="primary">Forgot password</v-btn>
                <v-card>
                  <v-card-title>
                    <span class="headline">Reset Password</span>
                  </v-card-title>
                  <v-form @submit.prevent="reset()">
                    <v-card-text>
                      <v-container grid-list-md>
                        <v-layout wrap>
                          <v-flex xs12>
                            Please enter the email address associated with your deSEC account.
                            We will send you an email with additional instructions on how to recover your account.
                            There will be no error message if the email address has no associated deSEC account.
                          </v-flex>
                          <v-flex x12>
                            <v-alert :value="reset_errors && reset_errors.length" type="error">
                              <div v-if="errors.length > 1">
                                <li v-for="reset_error of reset_errors" :key="reset_error.message">
                                  <b>{{ reset_error.message }}</b>
                                  {{ reset_error }}
                                </li>
                              </div>
                              <div v-else>
                                {{ reset_errors[0] }}
                              </div>
                            </v-alert>
                          </v-flex>
                          <v-flex xs12>
                            <v-text-field label="E-Mail" v-model="email" required></v-text-field>
                          </v-flex>
                        </v-layout>
                      </v-container>
                    </v-card-text>
                    <v-card-actions>
                      <v-spacer></v-spacer>
                      <v-btn flat @click.native="reset_dialog = false">Abort</v-btn>
                      <v-btn type="submit" color="primary" :loading="working">Reset Password</v-btn>
                    </v-card-actions>
                  </v-form>
                </v-card>
              </v-dialog>
            </v-flex>
          </v-layout>
        </v-container>
      </v-flex>
    </v-layout>
  </v-container>
</template>

<script>
import {HTTP} from '../utils'
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
    errors: [],
    reset_dialog: false,
    reset_errors: []
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
    },
    async reset () {
      this.working = true
      this.reset_errors = []
      try {
        await HTTP.post('auth/password/reset/', {email: this.email})
        this.reset_dialog = false
      } catch (error) {
        if (error.response) {
          // The request was made and the server responded with a status code
          // that falls out of the range of 2xx
          if (error.response.status === 404) {
            this.reset_errors = ['There is no account associated with this email address.'] // TODO we should eliminate this status
          } else {
            this.reset_errors = ['Something went wrong at the server, but we currently do not know why. The customer support was already notified.']
          }
          console.log('Error', error)
        } else if (error.request) {
          this.reset_errors = ['Cannot contact our servers. Are you offline?']
        } else {
          this.reset_errors = [error.message]
        }
      }
      this.working = false
    }
  }
}
</script>

<style scoped>
</style>
