<template>
  <v-container fluid fill-height>
    <v-layout align-center justify-center>
      <v-flex style="max-width: 400px">
        <v-container text-xs-center>
          <v-form v-on:submit.prevent="reset" v-model="valid">
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
              <v-flex xs12 headline mb-5>
                Reset Password
              </v-flex>
              <v-flex x12>
                <v-text-field
                  v-model="password"
                  label="Choose new password"
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
                >Reset Password</v-btn>
              </v-flex>
            </v-layout>
          </v-form>
          <v-layout column>
            <v-flex xs12 mt-5>
              <v-btn flat color="primary" :to="{name: 'LogIn'}">Log in</v-btn>
              <v-btn flat color="primary" :to="{name: 'SignUp'}">Sign up</v-btn>
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
  name: 'Reset',
  data: () => ({
    valid: false,
    working: false,
    password: '',
    password_rules: [
      v => !!v || 'Choose a password to protect access to your account.',
      v => v.toString().length >= 8 || 'Your password must contain at least 8 characters.'
    ],
    hide_password: true,
    errors: []
  }),
  methods: {
    async reset () {
      this.working = true
      this.errors = []
      try {
        await HTTP.post('auth/password/reset/confirm/', {uid: this.$route.params.uid, token: this.$route.params.token, new_password: this.password})
        router.replace({name: 'LogIn'}) // TODO automatically login instead? Then we need the email address, too
      } catch (error) {
        if (error.response) {
          // The request was made and the server responded with a status code
          // that falls out of the range of 2xx
          this.errors = ['Something went wrong at the server, but we currently do not know why. The customer support was already notified.']
          console.log('Error', error)
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
