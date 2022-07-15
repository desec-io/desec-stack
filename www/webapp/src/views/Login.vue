<template>
  <v-container
          class="fill-height"
          fluid
  >
    <v-row
            align="center"
            justify="center"
    >
      <v-col
              cols="12"
              sm="8"
              md="6"
      >
        <v-form
          v-model="valid"
          @submit.prevent="login"
        >
          <v-card class="elevation-12 pb-4">
            <v-toolbar
                    color="primary"
                    dark
                    flat
            >
              <v-toolbar-title>Log In</v-toolbar-title>
            </v-toolbar>
            <v-card-text>
              <v-alert
                :value="!!errors && !!errors.length"
                type="error"
              >
                <div v-if="errors.length > 1">
                  <li
                    v-for="error of errors"
                    :key="error.message"
                  >
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
                label="Email"
                outline
                required
                :disabled="working"
                :rules="email_rules"
                :error-messages="email_errors"
                tabindex="1"
                @change="email_errors=[]"
              />
              <v-text-field
                v-model="password"
                label="Password"
                :append-icon="hide_password ? 'mdi-eye' : 'mdi-eye-off'"
                :type="hide_password ? 'password' : 'text'"
                outline
                required
                :disabled="working"
                :rules="password_rules"
                tabindex="2"
                @click:append="() => (hide_password = !hide_password)"
              />
              <v-layout class="justify-center">
                <v-checkbox
                  v-model="useSessionStorage"
                  label="Remember me during this browser session"
                  tabindex="3"
                />
              </v-layout>
              <p class="text-center"><strong>Note:</strong> Login sessions expire after 1 hour of inactivity, or after 7 days at the latest.</p>
            </v-card-text>
            <v-card-actions class="justify-center">
              <v-btn
                type="submit"
                color="primary"
                depressed
                :disabled="!valid || working"
                :loading="working"
                tabindex="4"
              >
                Log In
              </v-btn>
              <v-btn
                id="forgotPassword"
                text
                color="primary"
                :to="{name: 'reset-password', params: email ? {email: email} : {}}"
                tabindex="5"
              >
                Forgot password
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-form>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { HTTP } from '../utils';

export default {
  name: 'Login',
  data: () => ({
    valid: false,
    working: false,
    email: '',
    password: '',
    terms: false,
    useSessionStorage: false,
    email_rules: [v => !!v || 'Please enter the email address associated with your account'],
    email_errors: [],
    password_rules: [
      v => !!v || 'Enter your password to log in',
    ],
    hide_password: true,
    errors: [],
    reset_dialog: false,
    reset_errors: [],
  }),
  methods: {
    async login() {
      this.working = true;
      this.errors = [];
      try {
        const response = await HTTP.post('auth/login/', {
          email: this.email,
          password: this.password,
        });
        HTTP.defaults.headers.common.Authorization = `Token ${response.data.token}`;
        this.$store.commit('login', response.data);
        if (this.useSessionStorage) {
          sessionStorage.setItem('token', JSON.stringify(response.data));
        }
        if ('redirect' in this.$route.query && this.$route.query.redirect) {
          this.$router.replace(this.$route.query.redirect);
        } else {
          this.$router.replace({ name: 'domains' });
        }
      } catch (error) {
        if (error.response) {
          // The request was made and the server responded with a status code
          // that falls out of the range of 2xx
          if (error.response.status < 500 && typeof error.response.data === 'object') {
            // 3xx or 4xx
            if ('email' in error.response.data) {
              this.email_errors = [error.response.data.email[0]];
            } else if ('non_field_errors' in error.response.data) {
              this.errors = error.response.data.non_field_errors;
            } else {
              this.errors = [error.response.data.detail];
            }
          } else {
            // 5xx
            this.errors = ['Something went wrong at the server, but we currently do not know why. The support was already notified.'];
          }
        } else if (error.request) {
          this.errors = ['Cannot contact our servers. Are you offline?'];
        } else {
          this.errors = [error.message];
        }
      }
      this.working = false;
    },
    async reset() {
      this.working = true;
      this.reset_errors = [];
      try {
        await HTTP.post('auth/account/reset-password/', { email: this.email });
        this.reset_dialog = false;
        this.$router.replace({ path: '/reset' });
      } catch (error) {
        if (error.response) {
          // The request was made and the server responded with a status code
          // that falls out of the range of 2xx
          this.reset_errors = ['Something went wrong at the server, but we currently do not know why. The support was already notified.'];
        } else if (error.request) {
          this.reset_errors = ['Cannot contact our servers. Are you offline?'];
        } else {
          this.reset_errors = [error.message];
        }
      }
      this.working = false;
    },
  },
};
</script>

<style scoped>
</style>
