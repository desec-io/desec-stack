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
            <v-toolbar-title class="capitalize">{{ this.$route.params.action | replace(/-/g, ' ') }} Confirmation</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <v-alert :value="!!(errors && errors.length)" type="error">
              <div v-if="errors.length > 1">
                <li v-for="error of errors" :key="error.message" >
                  <b>{{ error.message }}</b>
                  {{ error }}
                </li>
              </div>
              <div v-else-if="errors.length == 1">
                {{ errors[0].detail || errors[0][0] || errors[0]}}
              </div>
            </v-alert>
            <v-form @submit.prevent="confirm" class="mb-4" v-model="valid" ref="form">
              <div
                      :is="this.actionHandler"
                      :payload="this.post_payload"
                      :response="this.post_response"
                      :valid="this.valid"
                      :working="this.working"
                      ref="actionHandler"
                      @autosubmit="confirm"
                      @clearerrors="clearErrors"
              ></div>
            </v-form>
            <h2 class="title">Keep deSEC Going</h2>
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
  import ResetPasswordActionHandler from '@/components/ResetPasswordActionHandler.vue';

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {'Content-Type': 'application/json'},
  });

  export default {
    name: 'Confirmation',
    components: {
      GenericActionHandler,
      ActivateAccountActionHandler,
      ResetPasswordActionHandler,
    },
    data: () => ({
      actionHandler: null,
      errors: [],
      handler_map: {'reset-password': 'ResetPasswordActionHandler', 'activate-account': 'ActivateAccountActionHandler'},
      post_payload: {},
      post_response: {},
      success: false,
      valid: true,
      working: false,
    }),
    async mounted() {
      this.actionHandler = this.handler_map[this.$route.params.action] || 'GenericActionHandler'
    },
    methods: {
      async confirm() {
        this.post_response = {}
        this.errors = []
        this.working = true
        let action = this.$route.params.action
        try {
          this.post_response = await HTTP.post(`v/${action}/${this.$route.params.code}/`, this.post_payload);
          this.success = true
        } catch (error) {
          this.post_response = error.response
          this.errors.push(error.response.data)
        }
        this.working = false
      },
      clearErrors() {
        this.errors = []
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
