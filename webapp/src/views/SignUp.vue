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
        <v-form @submit.prevent="signup" ref="form">
          <v-card class="elevation-12 pb-4">
            <v-toolbar
                    color="primary"
                    dark
                    flat
            >
              <v-toolbar-title>Create new Account</v-toolbar-title>
            </v-toolbar>
            <v-card-text>
              <v-alert :value="!!(errors && errors.length)" type="error">
                <div v-if="errors.length > 1">
                  <li v-for="error of errors" :key="error.message" >
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

              <p class="mt-4 pl-8 heading">
                To use our <strong>dynDNS service</strong>, enter a domain name here. After sign-up, we will send you
                instructions on how to configure your dynDNS client, such as you router.<br>
                If instead you are interested in <strong>general DNS hosting</strong>, please do not provide a domain
                name. After sign-up, you can login and create a token to use our DNS REST API.
              </p>

              <v-text-field
                      v-model="domain"
                      label="DynDNS domain (optional)"
                      prepend-icon="mdi-dns"
                      outline
                      required
                      :disabled="working"
                      :rules="domain_rules"
                      :error-messages="domain_errors"
                      :suffix="'.' + LOCAL_PUBLIC_SUFFIXES[0]"
                      @change="domain_errors=[]"
                      class="lowercase"
                      ref="domainField"
                      tabindex="2"
              />

              <v-layout>
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
                />
                <div class="ml-4 text-center">
                  <v-progress-circular
                          indeterminate
                          v-if="captchaWorking"
                  ></v-progress-circular>
                  <img
                          v-if="captcha && !captchaWorking"
                          :src="'data:image/png;base64,'+captcha.challenge"
                          alt="Sign up is also possible by sending an email to our support."
                  >
                  <br/>
                  <v-btn text outlined @click="getCaptcha(true)" :disabled="captchaWorking">New Captcha</v-btn>
                </div>
              </v-layout>

              <v-layout class="justify-center">
                <v-checkbox
                      v-model="terms"
                      type="checkbox"
                      required
                      :disabled="working"
                      :rules="terms_rules"
                      tabindex="4"
                >
                  <template slot="label">
                    <v-flex>
                      Yes, I agree to the <a @click.stop="open_route('terms')">Terms of Use</a> and
                      <a @click.stop="open_route('privacy-policy')">Privacy Policy</a>.
                    </v-flex>
                  </template>
                </v-checkbox>
              </v-layout>
            </v-card-text>
            <v-card-actions class="justify-center">
              <v-btn
                      depressed
                      class="px-4"
                      color="primary"
                      type="submit"
                      :disabled="working"
                      :loading="working"
                      tabindex="5"
              >Sign up for Account</v-btn>
            </v-card-actions>
          </v-card>
        </v-form>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
  import axios from 'axios';
  import {LOCAL_PUBLIC_SUFFIXES} from '../env';
  import {domain_pattern, email_pattern} from '../validation';

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {
    },
  });

  export default {
    name: 'SignUp',
    data: () => ({
      valid: false,
      working: false,
      captchaWorking: true,
      errors: [],
      captcha: null,
      LOCAL_PUBLIC_SUFFIXES: LOCAL_PUBLIC_SUFFIXES,

      /* email field */
      email: '',
      email_rules: [v => !!email_pattern.test(v || '') || 'We need an email address for account recovery and technical support.'],
      email_errors: [],

      /* captcha field */
      captchaSolution: '',
      captcha_rules: [v => !!v || 'Please enter the text displayed in the picture so we are (somewhat) convinced you are human'],
      captcha_errors: [],

      /* terms field */
      terms: false,
      terms_rules: [v => !!v || 'You can only use our service if you agree with the terms'],

      /* domain field */
      domain: '',
      domain_rules: [v => !!domain_pattern.test(v + '.' + LOCAL_PUBLIC_SUFFIXES[0]) || 'Domain names can only contain letters, numbers, underscores (_), dots (.), and dashes (-), and must end in a letter.'],
      domain_errors: [],
    }),
    async mounted() {
      if ('email' in this.$route.params && this.$route.params.email !== undefined) {
        this.email = this.$route.params.email;
      }
      this.getCaptcha();
      this.initialFocus();
    },
    methods: {
      async open_route(route) {
        window.open(this.$router.resolve({name: route}).href);
        this.terms = !this.terms; // silly but easy fix for "accidentally" checking the box by clicking the link
      },
      async getCaptcha(focus = false) {
        this.captchaWorking = true;
        this.captchaSolution = "";
        try {
          this.captcha = (await HTTP.post('captcha/')).data;
          if(focus) {
            this.$refs.captchaField.focus()
          }
        } finally {
          this.captchaWorking = false;
        }
      },
      async initialFocus() {
        return this.email ? this.$refs.domainField.focus() : this.$refs.emailField.focus();
      },
      async signup() {
        if (!this.$refs.form.validate()) {
          return;
        }
        this.working = true;
        this.errors = [];
        let domain = this.domain === '' ? undefined : this.domain.toLowerCase() + '.' + this.LOCAL_PUBLIC_SUFFIXES[0];
        try {
          await HTTP.post('auth/', {
            email: this.email.toLowerCase(),
            password: null,
            captcha: {
              id: this.captcha.id,
              solution: this.captchaSolution.toUpperCase(),
            },
            domain: domain,
          });
          this.$router.push({name: 'welcome', params: domain !== '' ? {domain: domain} : {}});
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
              if ('domain' in error.response.data) {
                this.domain_errors = [error.response.data.domain[0]];
                extracted = true;
              }
              if ('email' in error.response.data) {
                this.email_errors = [error.response.data.email[0]];
                extracted = true;
              }
              if (!extracted) {
                this.errors = error.response;
              }
            } else {
              // 5xx
              this.errors = ['Something went wrong at the server, but we currently do not know why. The customer support was already notified.'];
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
  };
</script>

<style lang="scss">
  .uppercase input {
    text-transform: uppercase;
  }
  .lowercase input {
    text-transform: lowercase;
  }
</style>
