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
        <v-form
            @submit.prevent="signup"
            :disabled="working"
            ref="form"
        >
          <v-card class="elevation-12 pb-4">
            <v-toolbar
                    color="primary"
                    dark
                    flat
            >
              <v-toolbar-title>Create new Account</v-toolbar-title>
            </v-toolbar>
            <v-card-text>
              <error-alert :errors="errors"></error-alert>

              <v-text-field
                      v-model="email"
                      label="Email"
                      :prepend-icon="mdiEmail"
                      outlined
                      required
                      :rules="email_rules"
                      :error-messages="email_errors"
                      @change="email_errors=[]"
                      validate-on-blur
                      ref="emailField"
                      tabindex="1"
              />

              <v-radio-group
                      v-model="domainType"
                      hint="You can also use our REST API or web interface to create domains."
                      label="Do you want to set up a domain right away?"
                      persistent-hint
                      :prepend-icon="mdiDns"
              >
                <v-alert type="info">
                  dynDNS registrations are suspended at this time.
                  <strong>We do <i>not</i> process requests for exceptions.</strong><br/>
                  <small>Please do not contact support about this. You will have to register a domain elsewhere.</small>
                </v-alert>
                <v-radio label="Configure your own domain (Managed DNS)." value="custom" tabindex="2"></v-radio>
                <v-radio :label="`Register a new domain under ${LOCAL_PUBLIC_SUFFIXES[0]} (dynDNS).`" disabled="disabled" value="dynDNS" tabindex="2"></v-radio>
                <v-radio label="No, I'll add one later." value="none" tabindex="2"></v-radio>
              </v-radio-group>

              <v-text-field
                      v-model="domain"
                      :label="domainType === 'dynDNS' ? 'DynDNS domain' : 'Domain name'"
                      prepend-icon="mdi-blank"
                      outlined
                      required
                      :disabled="domainType === 'none' || domainType === undefined"
                      :rules="domainType === 'dynDNS' ? dyn_domain_rules : (domainType === 'custom' ? domain_rules : [])"
                      :error-messages="domain_errors"
                      :suffix="domainType === 'dynDNS' ? ('.' + LOCAL_PUBLIC_SUFFIXES[0]) : ''"
                      @change="domain_errors=[]"
                      class="lowercase"
                      ref="domainField"
                      tabindex="3"
                      :hint="domainType === 'dynDNS'
                        ? 'After sign-up, we will send you instructions on how to configure your dynDNS client (such as your router).'
                        : 'Your first domain (you can add more later). – To use with dynDNS, please see the docs.'
                      "
                      persistent-hint
              />

              <v-container class="pa-0">
                <v-row dense align="center" class="text-center">
                  <v-col cols="8" sm="">
                    <v-text-field
                        v-model="captchaSolution"
                        label="Type CAPTCHA text here"
                        :prepend-icon="mdiAccountCheck"
                        outlined
                        required
                        :rules="captcha_rules"
                        :error-messages="captcha_errors"
                        @change="captcha_errors=[]"
                        @keypress="captcha_errors=[]"
                        class="uppercase"
                        ref="captchaField"
                        tabindex="4"
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
                          alt="Sign up is also possible by sending an email to our support."
                    />
                    <audio controls
                          v-if="captcha && !captchaWorking && captcha_kind === 'audio'"
                    >
                      <source :src="'data:audio/wav;base64,'+captcha.challenge" type="audio/wav"/>
                    </audio>
                    <br/>
                    <v-btn-toggle>
                      <v-btn text outlined @click="getCaptcha(true)" :disabled="captchaWorking"><v-icon>{{ mdiRefresh }}</v-icon></v-btn>
                    </v-btn-toggle>
                    &nbsp;
                    <v-btn-toggle v-model="captcha_kind">
                      <v-btn text outlined value="image" aria-label="Switch to Image CAPTCHA" :disabled="captchaWorking"><v-icon>{{ mdiEye }}</v-icon></v-btn>
                      <v-btn text outlined value="audio" aria-label="Switch to Audio CAPTCHA" :disabled="captchaWorking"><v-icon>{{ mdiEarHearing }}</v-icon></v-btn>
                    </v-btn-toggle>
                  </v-col>
                </v-row>
              </v-container>

              <v-layout class="justify-center">
                <v-checkbox
                      v-model="outreach_preference"
                      hide-details
                      type="checkbox"
                      tabindex="5"
                >
                  <template #label>
                    <v-flex>
                      Tell me about deSEC developments. No ads. <small>(recommended)</small>
                    </v-flex>
                  </template>
                </v-checkbox>
              </v-layout>

              <v-layout class="justify-center">
                <v-checkbox
                      v-model="terms"
                      hide-details="auto"
                      type="checkbox"
                      :rules="terms_rules"
                      tabindex="6"
                >
                  <template #label>
                    <v-flex>
                      Yes, I agree to the <span @click.stop><router-link :to="{name: 'terms'}" target="_blank">Terms of Use</router-link></span> and
                      <span @click.stop><router-link :to="{name: 'privacy-policy'}" target="_blank">Privacy Policy</router-link></span>.
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
                      :loading="working"
                      tabindex="7"
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
  import {domain_pattern, email_pattern} from '@/validation';
  import {digestError} from '@/utils';
  import ErrorAlert from "@/components/ErrorAlert.vue";
  import {mdiAccountCheck, mdiDns, mdiEarHearing, mdiEmail, mdiEye, mdiRefresh} from "@mdi/js";

  const LOCAL_PUBLIC_SUFFIXES = import.meta.env.VITE_APP_LOCAL_PUBLIC_SUFFIXES.split(' ');

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {
    },
  });

  export default {
    name: 'SignUp',
    components: {
      ErrorAlert,
    },
    data: () => ({
      valid: false,
      working: false,
      captchaWorking: true,
      errors: [],
      captcha: null,
      LOCAL_PUBLIC_SUFFIXES: LOCAL_PUBLIC_SUFFIXES,

      mdiAccountCheck: mdiAccountCheck,
      mdiDns: mdiDns,
      mdiEarHearing: mdiEarHearing,
      mdiEmail: mdiEmail,
      mdiEye: mdiEye,
      mdiRefresh: mdiRefresh,

      /* email field */
      email: '',
      email_rules: [v => !!email_pattern.test(v || '') || 'We need an email address for account recovery and technical support.'],
      email_errors: [],

      /* captcha field */
      captchaSolution: '',
      captcha_rules: [v => !!v || 'Please enter the text displayed in the picture so we are (somewhat) convinced you are human'],
      captcha_errors: [],
      captcha_kind: 'image',

      /* outreach preference */
      outreach_preference: true,

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
      this.domainType = this.$route.query.domainType || 'custom';
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
        this.errors.splice(0, this.errors.length);
        let domain = this.domain === '' ? undefined : this.domain.toLowerCase();
        if (domain && this.domainType === 'dynDNS') {
           domain += '.' + this.LOCAL_PUBLIC_SUFFIXES[0];
        }
        try {
          await HTTP.post('auth/', {
            email: this.email,
            password: null,
            captcha: {
              id: this.captcha.id,
              solution: this.captchaSolution.toUpperCase(),
            },
            domain: domain,
            outreach_preference: this.outreach_preference,
          });
          this.$router.push({name: 'welcome', params: domain !== '' ? {domain: domain} : {}});
        } catch (ex) {
          this.getCaptcha(true);
          let errors = await digestError(ex);
          for (const c in errors) {
            if (c === undefined) {
              this.errors.push(...errors[c]);
            } else if (c === 'captcha') {
              this.captcha_errors.push(...(errors[c]['non_field_errors'] ?? []));
              this.captcha_errors.push(...(errors[c]['solution'] ?? []));
            } else if (c === 'domain') {
              this.domain_errors.push(...errors[c]);
            } else if (c === 'email') {
              this.email_errors.push(...errors[c]);
            } else {
              this.errors.push(...errors[c]);
            }
          }
        }
        this.working = false;
      },
    },
    watch: {
      domainType: function() {
        this.$nextTick(() => {
          if (this.domainType === 'none') {
            this.domain = '';
          }
          this.$refs.domainField.validate();
        })
      },
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
  .lowercase input {
    text-transform: lowercase;
  }
</style>
