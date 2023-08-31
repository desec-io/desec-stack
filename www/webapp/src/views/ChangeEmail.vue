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
                    @submit.prevent="changeEmail"
                    :disabled="working"
                    ref="form"
                >
                    <v-card class="elevation-12 pb-4">
                        <v-toolbar
                                color="primary"
                                dark
                                flat
                        >
                            <v-toolbar-title>Change Account Email Address</v-toolbar-title>
                        </v-toolbar>
                        <v-card-text>
                            <error-alert :errors="errors"></error-alert>
                            <v-alert v-if="done" type="success">
                                <p>
                                    Please check your new email address for messages. If the new email address is not
                                    yet in use for another deSEC account, you will receive a message with further
                                    instructions.
                                </p>
                            </v-alert>

                            <generic-email
                                v-model="email"
                                label="Current Email Address"
                                :readonly="true"
                            />

                            <generic-password
                                v-model="password"
                                ref="password"
                                tabindex="1"
                            />

                            <generic-email
                                    v-model="new_email"
                                    :new="true"
                                    tabindex="2"
                            />
                        </v-card-text>
                        <v-card-actions class="justify-center">
                            <v-btn
                                    depressed
                                    color="primary"
                                    type="submit"
                                    :loading="working"
                                    tabindex="3"
                            >Change Email Address
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-form>
            </v-col>
        </v-row>
    </v-container>
</template>

<script>
  import { HTTP, withWorking ,digestError} from '@/utils';
  import ErrorAlert from "@/components/ErrorAlert.vue";
  import GenericEmail from "@/components/Field/GenericEmail.vue";
  import GenericPassword from "@/components/Field/GenericPassword.vue";

  export default {
    name: 'ChangeEmail',
    components: {
      GenericEmail,
      GenericPassword,
      ErrorAlert,
    },
    data: () => ({
      valid: false,
      working: false,
      done: false,
      errors: [],
      email: '',
      rules: {
        required: v => !!v || 'Required.',
      },
      show: false,

      /* password field */
      password: '',

      /* email field */
      new_email: '',
      email_errors: [],
    }),
    mounted() {
      if ('email' in this.$route.params && this.$route.params.email !== undefined) {
        this.new_email = this.$route.params.email;
      }
      this.initialFocus();
    },
    async created() {
      const self = this;
      await withWorking(this.error, () => HTTP
          .get('auth/account/')
          .then(r => self.email = r.data.email)
      );
    },
    methods: {
      initialFocus() {
        return this.$refs.password.focus();
      },
      async changeEmail() {
        if (!this.$refs.form.validate()) {
          return;
        }
        this.working = true;
        this.errors.splice(0, this.errors.length);
        try {
          await HTTP.post('auth/account/change-email/', {
            email: this.email,
            password: this.password,
            new_email: this.new_email
          });
          this.done = true;
        } catch (ex) {
          let errors = await digestError(ex, this);
          for (const c in errors) {
            this.errors.push(...errors[c]);
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
