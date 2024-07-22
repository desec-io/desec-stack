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
                    @submit.prevent="resetPassword"
                    :disabled="working"
                    ref="form"
                >
                    <v-card class="elevation-12 pb-4">
                        <v-toolbar
                                color="primary"
                                dark
                                flat
                        >
                            <v-toolbar-title>Reset Account Password</v-toolbar-title>
                        </v-toolbar>
                        <v-card-text>
                            <error-alert :errors="errors"></error-alert>
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
                            <generic-captcha
                                @update="(id, solution) => {captchaID=id; captchaSolution=solution}"
                                tabindex="3"
                                ref="captchaField"
                            />
                        </v-card-text>
                        <v-card-actions class="justify-center">
                            <v-btn
                                    depressed
                                    color="primary"
                                    type="submit"
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
  import {email_pattern} from '@/validation';
  import {digestError} from '@/utils';
  import ErrorAlert from '@/components/ErrorAlert.vue';
  import {mdiEmail} from "@mdi/js";
  import GenericCaptcha from "@/components/Field/GenericCaptcha.vue";

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {},
  });

  export default {
    name: 'ResetPassword',
    components: {
      GenericCaptcha,
      ErrorAlert,
    },
    data: () => ({
      valid: false,
      working: false,
      done: false,
      errors: [],

      mdiEmail: mdiEmail,

      /* email field */
      email: '',
      email_rules: [v => !!email_pattern.test(v || '') || 'We need an email address for account recovery and technical support.'],
      email_errors: [],

      /* captcha field */
      captchaID: null,
      captchaSolution: '',
      captcha_errors: [],
    }),
    async mounted() {
      if ('email' in this.$route.params && this.$route.params.email !== undefined) {
        this.email = this.$route.params.email;
      }
      this.initialFocus();
    },
    methods: {
      async initialFocus() {
        return this.$refs.emailField.focus();
      },
      async resetPassword() {
        if (!this.$refs.form.validate()) {
          return;
        }
        this.working = true;
        this.errors.splice(0, this.errors.length);
        try {
          await HTTP.post('auth/account/reset-password/', {
            email: this.email,
            captcha: {
              id: this.captchaID,
              solution: this.captchaSolution,
            },
          });
          this.done = true;
        } catch (ex) {
          await this.$refs.captchaField.getCaptcha(true);
          let errors = await digestError(ex);
          for (const c in errors) {
            if (c === 'captcha') {
              this.$refs.captchaField.addError(...(errors[c]['non_field_errors'] ?? []));
              this.$refs.captchaField.addError(...(errors[c]['solution'] ?? []));
            } else {
              this.errors.push(...errors[c]);
            }
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
</style>
