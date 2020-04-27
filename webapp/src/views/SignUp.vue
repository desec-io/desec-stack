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
              sm="10"
              md="8"
              lg="6"
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

              <v-radio-group
                      v-model="domainType"
                      hint="Your first domain (you can add more later). – To use dynDNS with your custom domain, please get in touch with us."
                      label="Do you want to set up a domain right away?"
                      persistent-hint
                      prepend-icon="mdi-dns"
              >
                <v-radio :label="`Register a new domain under ${LOCAL_PUBLIC_SUFFIXES[0]} (dynDNS).`" value="dynDNS" tabindex="2"></v-radio>
                <v-radio label="Configure your own domain (Managed DNS)." value="custom" tabindex="2"></v-radio>
                <v-radio label="No, I'll add one later through the API." value="none" tabindex="2"></v-radio>
              </v-radio-group>

              <v-text-field
                      v-model="domain"
                      :label="domainType == 'dynDNS' ? 'DynDNS domain' : 'Domain name'"
                      prepend-icon="mdi-blank"
                      outline
                      required
                      :disabled="working || domainType == 'none' || domainType === undefined"
                      :rules="domainType == 'dynDNS' ? dyn_domain_rules : (domainType == 'custom' ? domain_rules : [])"
                      :error-messages="domain_errors"
                      :suffix="domainType == 'dynDNS' ? ('.' + LOCAL_PUBLIC_SUFFIXES[0]) : ''"
                      @change="domain_errors=[]"
                      class="lowercase"
                      ref="domainField"
                      tabindex="3"
                      :hint="domainType == 'dynDNS'
                        ? 'Enter a domain name here. After sign-up, we will send you instructions on how to configure your dynDNS client (such as you router).'
                        : 'You can also use our REST API to create a domain.'
                      "
                      persistent-hint
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
                        tabindex="4"
                    />
                  </v-col>
                  <v-col cols="8" sm="auto">
                    <v-progress-circular
                          indeterminate
                          v-if="captchaWorking"
                    ></v-progress-circular>
                    <img
                          v-if="captcha && !captchaWorking"
                          :src="'data:image/png;base64,'+captcha.challenge"
                          alt="Sign up is also possible by sending an email to our support."
                    >
                  </v-col>
                  <v-col cols="4" sm="auto">
                    <v-btn text outlined @click="getCaptcha(true)" :disabled="captchaWorking"><v-icon>mdi-refresh</v-icon></v-btn>
                  </v-col>
                </v-row>
              </v-container>

              <v-layout class="justify-center">
                <v-checkbox
                      v-model="terms"
                      type="checkbox"
                      required
                      :disabled="working"
                      :rules="terms_rules"
                      tabindex="5"
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
                      tabindex="6"
              >Sign up</v-btn>
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
      domainType: null,
      domain_rules: [v => !!v && !!domain_pattern.test(v) || 'Domain names can only contain letters, numbers, dots (.), and dashes (-), and must end with a top-level domain.'],
      dyn_domain_rules: [v => !!v && v.indexOf('.') < 0 && !!domain_pattern.test(v + '.' + LOCAL_PUBLIC_SUFFIXES[0]) || 'Your domain name can only contain letters, numbers, and dashes (-).'],
      domain_errors: [],
    }),
    async mounted() {
      if ('email' in this.$route.params && this.$route.params.email !== undefined) {
        this.email = this.$route.params.email;
      }
      this.getCaptcha();
      this.initialFocus();
    },
    created() {
      this.domainType = this.$route.query.domainType || 'dynDNS';
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
        if(this.$route.query.domainType === undefined) {
          return;
        }
        return this.email ? this.$refs.domainField.focus() : this.$refs.emailField.focus();
      },
      async signup() {
        if (!this.$refs.form.validate()) {
          return;
        }
        this.working = true;
        this.errors = [];
        let domain = this.domain === '' ? undefined : this.domain.toLowerCase();
        if (domain && this.domainType == 'dynDNS') {
           domain += '.' + this.LOCAL_PUBLIC_SUFFIXES[0];
        }
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
    watch: {
      domainType: function() {
        this.$nextTick(() => {
          if (this.domainType == 'none') {
            this.domain = '';
          }
          this.$refs.domainField.validate();
        })
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
