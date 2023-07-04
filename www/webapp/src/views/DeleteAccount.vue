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
                    @submit.prevent="deleteAccount"
                    :disabled="working"
                    ref="form"
                >
                    <v-card class="elevation-12 pb-4">
                        <v-toolbar
                                color="primary"
                                dark
                                flat
                        >
                            <v-toolbar-title>Delete Account</v-toolbar-title>
                        </v-toolbar>
                        <v-card-text>
                            <error-alert :errors="errors"></error-alert>
                            <v-alert v-if="done" type="success">
                                <p>
                                    Please check your mail box for further instructions to delete your account.
                                </p>
                            </v-alert>

                            <v-text-field
                                    v-model="email"
                                    label="Current Email"
                                    prepend-icon="mdi-blank"
                                    outlined
                                    required
                                    :disabled="true"
                                    validate-on-blur
                            />
                            <v-text-field
                                    v-model="password"
                                    :append-icon="show ? 'mdi-eye' : 'mdi-eye-off'"
                                    prepend-icon="mdi-blank"
                                    outlined
                                    label="Password"
                                    required
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
  import { HTTP, withWorking, digestError } from '@/utils';
  import ErrorAlert from "../components/ErrorAlert";

  export default {
    name: 'DeleteAccount',
    components: {ErrorAlert},
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
    }),
    mounted() {
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
        this.errors.splice(0, this.errors.length);
        try {
          await HTTP.post('auth/account/delete/', {
            email: this.email,
            password: this.password,
          });
          this.done = true;
        } catch (ex) {
          let errors = await digestError(ex, this);
          for (const c in errors) {
            this.errors.push(...errors[c])
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
