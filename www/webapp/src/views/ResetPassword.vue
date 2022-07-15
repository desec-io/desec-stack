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
                <v-form @submit.prevent="resetPassword" ref="form">
                    <v-card class="elevation-12 pb-4">
                        <v-toolbar
                                color="primary"
                                dark
                                flat
                        >
                            <v-toolbar-title>Reset Account Password</v-toolbar-title>
                        </v-toolbar>
                        <v-card-text>
                            <v-alert :value="!!(errors && errors.length)" type="error">
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
                            <v-alert v-if="done" type="success">
                                <p>
                                    We received the password reset request. If an account with this email address exists
                                    in our database, we sent an email with password reset instructions. If you did not
                                    receive an email, you can
                                    <router-link :to="{name: 'signup', params: email ? {email: email} : {}}">
                                        create an account
                                    </router-link>
                                    .
                                </p>
                            </v-alert>

                            <v-text-field
                                    v-model="email"
                                    label="Email"
                                    prepend-icon="mdi-email"
                                    outline
                                    required
                                    :disabled="working"
                                    :rules="email_rules"
                                    :error-messages="email_errors"
                                    @change="email_errors=[]"
                                    validate-on-blur
                                    ref="emailField"
                                    tabindex="1"
                            />

                              <v-container class="pa-0">
                                <v-row dense align="center" class="text-center">
                                  <v-col cols="12" sm="">
                                    <v-text-field
                                            v-model="captchaSolution"
                                            label="Type CAPTCHA text here"
                                            prepend-icon="mdi-account-check"
                                            outline
                                            required
                                            :disabled="working"
                                            :rules="captcha_rules"
                                            :error-messages="captcha_errors"
                                            @change="captcha_errors=[]"
                                            @keypress="captcha_errors=[]"
                                            class="uppercase"
                                            ref="captchaField"
                                            tabindex="3"
                                            :hint="captcha_kind === 'image' ? 'Can\'t see? Hear an audio CAPTCHA instead.' : 'Trouble hearing? Switch to an image CAPTCHA.'"
                                    />
                                  </v-col>
                                  <v-col cols="12" sm="auto">
                                    <v-progress-circular
                                          indeterminate
                                          v-if="captchaWorking"
                                    ></v-progress-circular>
                                    <img
                                          v-if="captcha && !captchaWorking && captcha_kind === 'image'"
                                          :src="'data:image/png;base64,'+captcha.challenge"
                                          alt="Passwords can also be reset by sending an email to our support."
                                    />
                                    <audio controls
                                          v-if="captcha && !captchaWorking && captcha_kind === 'audio'"
                                    >
                                      <source :src="'data:audio/wav;base64,'+captcha.challenge" type="audio/wav"/>
                                    </audio>
                                    <br/>
                                    <v-btn-toggle>
                                      <v-btn text outlined @click="getCaptcha(true)" :disabled="captchaWorking"><v-icon>mdi-refresh</v-icon></v-btn>
                                    </v-btn-toggle>
                                    &nbsp;
                                    <v-btn-toggle v-model="captcha_kind">
                                      <v-btn text outlined value="image" aria-label="Switch to Image CAPTCHA" :disabled="captchaWorking"><v-icon>mdi-eye</v-icon></v-btn>
                                      <v-btn text outlined value="audio" aria-label="Switch to Audio CAPTCHA" :disabled="captchaWorking"><v-icon>mdi-ear-hearing</v-icon></v-btn>
                                    </v-btn-toggle>
                                  </v-col>
                                </v-row>
                              </v-container>
                        </v-card-text>
                        <v-card-actions class="justify-center">
                            <v-btn
                                    depressed
                                    color="primary"
                                    type="submit"
                                    :disabled="working"
                                    :loading="working"
                                    tabindex="3"
                            >Reset Password
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-form>
            </v-col>
        </v-row>
    </v-container>
</template>

<script>
  import axios from 'axios';
  import {email_pattern} from '../validation';

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {},
  });

  export default {
    name: 'ResetPassword',
    data: () => ({
      valid: false,
      working: false,
      done: false,
      captchaWorking: true,
      errors: [],
      captcha: null,

      /* email field */
      email: '',
      email_rules: [v => !!email_pattern.test(v || '') || 'We need an email address for account recovery and technical support.'],
      email_errors: [],

      /* captcha field */
      captchaSolution: '',
      captcha_rules: [v => !!v || 'Please enter the text displayed in the picture so we are (somewhat) convinced you are human'],
      captcha_errors: [],
      captcha_kind: 'image',
    }),
    async mounted() {
      if ('email' in this.$route.params && this.$route.params.email !== undefined) {
        this.email = this.$route.params.email;
      }
      this.getCaptcha();
      this.initialFocus();
    },
    methods: {
      async getCaptcha(focus = false) {
        this.captchaWorking = true;
        this.captchaSolution = "";
        try {
          this.captcha = (await HTTP.post('captcha/', {kind: this.captcha_kind})).data;
          if(focus) {
            this.$refs.captchaField.focus()
          }
        } finally {
          this.captchaWorking = false;
        }
      },
      async initialFocus() {
        return this.$refs.emailField.focus();
      },
      async resetPassword() {
        if (!this.$refs.form.validate()) {
          return;
        }
        this.working = true;
        this.errors = [];
        try {
          await HTTP.post('auth/account/reset-password/', {
            email: this.email,
            captcha: {
              id: this.captcha.id,
              solution: this.captchaSolution,
            },
          });
          this.done = true;
        } catch (error) {
          if (error.response) {
            // status is not 2xx
            if (error.response.status < 500 && typeof error.response.data === 'object') {
              // 3xx or 4xx
              let extracted = false;
              this.getCaptcha(true);
              if ('captcha' in error.response.data) {
                if ('non_field_errors' in error.response.data.captcha) {
                  this.captcha_errors = [error.response.data.captcha.non_field_errors[0]];
                  extracted = true;
                }
                if ('solution' in error.response.data.captcha) {
                  this.captcha_errors = error.response.data.captcha.solution;
                  extracted = true;
                }
              }
              if (!extracted) {
                this.errors = error.response;
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
    },
    watch: {
      captcha_kind: function (oldKind, newKind) {
        if (oldKind !== newKind) {
          this.getCaptcha();
        }
      },
    },
  };
</script>

<style lang="scss">
    .uppercase input {
        text-transform: uppercase;
    }
</style>
