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
                <v-form @submit.prevent="deleteAccount" ref="form">
                    <v-card class="elevation-12 pb-4">
                        <v-toolbar
                                color="primary"
                                dark
                                flat
                        >
                            <v-toolbar-title>Delete Account</v-toolbar-title>
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
                                    Please check your mail box for further instructions to delete your account.
                                </p>
                            </v-alert>

                            <v-text-field
                                    v-model="email"
                                    label="Current Email"
                                    prepend-icon="mdi-blank"
                                    outline
                                    required
                                    :disabled="true"
                                    validate-on-blur
                            />
                            <v-text-field
                                    v-model="password"
                                    :append-icon="show ? 'mdi-eye' : 'mdi-eye-off'"
                                    prepend-icon="mdi-blank"
                                    label="Password"
                                    required
                                    :disabled="working"
                                    :rules="[rules.required]"
                                    :type="show ? 'text' : 'password'"
                                    :error-messages="password_errors"
                                    @change="password_errors=[]"
                                    @click:append="show = !show"
                                    ref="password"
                                    tabindex="1"
                            ></v-text-field>
                        </v-card-text>
                        <v-card-actions class="justify-center">
                            <v-btn
                                    depressed
                                    color="primary"
                                    type="submit"
                                    :disabled="working"
                                    :loading="working"
                                    tabindex="2"
                            >Delete Account
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-form>
            </v-col>
        </v-row>
    </v-container>
</template>

<script>
  import { HTTP, withWorking } from '@/utils';

  export default {
    name: 'DeleteAccount',
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
      password_errors: [],

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
      async deleteAccount() {
        if (!this.$refs.form.validate()) {
          return;
        }
        this.working = true;
        this.errors = [];
        try {
          await HTTP.post('auth/account/delete/', {
            email: this.email,
            password: this.password,
          });
          this.done = true;
        } catch (error) {
          if (error.response) {
            // status is not 2xx
            if (error.response.status < 500 && typeof error.response.data === 'object') {
              // 3xx or 4xx
              this.errors = [error.response.data.detail];
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
  };
</script>

<style lang="scss">
    .uppercase input {
        text-transform: uppercase;
    }
</style>
