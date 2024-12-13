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
        <v-card class="elevation-12">
          <v-toolbar
                  color="primary"
                  dark
                  flat
          >
            <v-toolbar-title class="capitalize">{{ actionName }} Confirmation</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <error-alert :errors="errors"></error-alert>
            <v-form @submit.prevent="confirm" class="mb-4" v-model="valid" ref="form">
              <component
                      :is="this.actionHandler"
                      :payload="this.post_payload"
                      :response="this.post_response"
                      :valid="this.valid"
                      :working="this.working"
                      ref="actionHandler"
                      @autosubmit="confirm"
                      @clearerrors="clearErrors"
              ></component>
            </v-form>
            <h2 class="text-h6">Keep deSEC Going</h2>
            <p>
              To offer free DNS hosting for everyone, deSEC relies on donations only.
              If you like our service, please consider donating.
            </p>
            <p>
              <v-btn block outlined :to="{name: 'donate'}">Donate</v-btn>
            </p>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
  import axios from 'axios';
  import GenericActionHandler from '@/components/GenericActionHandler.vue';
  import ActivateAccountActionHandler from '@/components/ActivateAccountActionHandler.vue';
  import ActivateAccountWithOverrideTokenActionHandler from '@/components/ActivateAccountWithOverrideTokenActionHandler.vue'
  import CreateTOTPActionHandler from '@/components/CreateTOTPActionHandler.vue';
  import ResetPasswordActionHandler from '@/components/ResetPasswordActionHandler.vue';
  import {digestError} from '@/utils';
  import ErrorAlert from '@/components/ErrorAlert.vue';

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {'Content-Type': 'application/json'},
  });

  export default {
    name: 'ConfirmationPage',
    components: {
      GenericActionHandler,
      ActivateAccountActionHandler,
      ActivateAccountWithOverrideTokenActionHandler,
      CreateTOTPActionHandler,
      ResetPasswordActionHandler,
      ErrorAlert,
    },
    data: () => ({
      actionHandler: null,
      errors: [],
      handler_map: {
        'activate-account': ActivateAccountActionHandler.name,
        'activate-account-with-override-token': ActivateAccountWithOverrideTokenActionHandler.name,
        'create-totp': CreateTOTPActionHandler.name,
        'reset-password': ResetPasswordActionHandler.name,
      },
      post_payload: {},
      post_response: {},
      success: false,
      valid: true,
      working: false,
    }),
    computed: {
      actionName() {
        const text = this.$route.params.action ?? '';
        return text.replace(/-/g, ' ');
      },
    },
    async mounted() {
      this.actionHandler = this.handler_map[this.$route.params.action] || GenericActionHandler.name
    },
    methods: {
      async confirm() {
        this.post_response = {}
        this.clearErrors();
        this.working = true
        let action = this.$route.params.action
        try {
          this.post_response = await HTTP.post(`v/${action}/${this.$route.params.code}/`, this.post_payload);
          this.success = true
        } catch (ex) {
          let errors = await digestError(ex);
          this.post_response = ex.response
          for (const c in errors) {
            if (c === 'captcha' && this.$refs.actionHandler.$refs.captchaField !== undefined) {
              this.$refs.actionHandler.$refs.captchaField.addError(...(errors[c]['id'] ?? []));
              this.$refs.actionHandler.$refs.captchaField.addError(...(errors[c]['non_field_errors'] ?? []));
              this.$refs.actionHandler.$refs.captchaField.addError(...(errors[c]['solution'] ?? []));
            } else {
              this.errors.push(...errors[c]);
            }
          }
        }
        this.working = false
      },
      clearErrors() {
        this.errors.splice(0, this.errors.length);
      }
    },
    filters: {
      replace: function (value, a, b) {
        return value.replace(a, b)
      }
    },
  };
</script>

<style lang="scss">
  .fixed-width {
    font-family: monospace;
  }
  .capitalize {
    text-transform: capitalize;
  }
</style>
