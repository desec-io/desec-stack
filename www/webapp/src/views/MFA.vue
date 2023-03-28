<template>
  <v-dialog
    v-model="show"
    max-width="700px"
    persistent
    scrollable
  >
    <v-form @submit.prevent="verify" ref="form">
      <v-card>
        <v-card-title>
          <div class="text-h6">
            2FA Required
          </div>
          <v-spacer/>
        </v-card-title>
        <v-divider/>

        <error-alert :errors="errors"></error-alert>

        <v-card-text class="text-center">
          <div>
            <p class="mt-2">
              <v-icon>{{ mdiNumeric1Circle }}</v-icon>
              Please select a TOTP token:
            </p>
            <v-container class="pa-0">
              <v-row dense align="center" class="justify-center">
                <v-col cols="12" sm="6">
                  <v-select
                    :items="factors"
                    item-text="name"
                    item-value="id"
                    v-model="id"
                    label="Token"
                    tabindex="1"
                  ></v-select>
                </v-col>
              </v-row>
            </v-container>

            <p class="mt-6">
              <v-icon>{{ mdiNumeric2Circle }}</v-icon>
              Enter the code displayed in the authenticator app to continue:
            </p>
            <v-container class="pa-0">
              <v-row dense align="center" class="justify-center">
                <v-col cols="12" sm="6">
                  <v-otp-input
                      v-model="code"
                      length="6"
                      type="number"
                      required
                      :disabled="working"
                      tabindex="2"
                      @finish="verify"
                  />
                </v-col>
              </v-row>
              <v-row dense align="center" class="justify-center">
                <v-col cols="auto">
                  <v-btn
                          depressed
                          color="primary"
                          type="submit"
                          :disabled="working || code.length != 6"
                          :loading="working"
                          ref="submit"
                          tabindex="3"
                  >Verify</v-btn>
                </v-col>
                <v-col cols="auto"></v-col>
              </v-row>
            </v-container>
          </div>
        </v-card-text>
      </v-card>
    </v-form>
  </v-dialog>
</template>

<script>
import {digestError, HTTP, withWorking} from '@/utils'
import ErrorAlert from "../components/ErrorAlert";
import {mdiNumeric1Circle, mdiNumeric2Circle} from "@mdi/js";

export default {
  name: 'MFA',
  components: {
    ErrorAlert,
  },
  data: () => ({
    code: "",
    errors: [],
    factors: [],
    id: null,
    working: false,
    show: true,
    mdiNumeric1Circle,
    mdiNumeric2Circle,
  }),
  async created() {
    const self = this;
    const url = '/auth/totp/';
    await withWorking(this.error, () => HTTP
            .get(url)
            .then(r => self.factors = r.data.filter((v) => !!v.last_used))
    );
    if(self.factors.length == 1) {
      self.id = self.factors[0].id;
    }
  },
  methods: {
    async verify() {
      if (!this.$refs.form.validate()) {
        return;
      }
      this.working = true;
      this.errors.splice(0, this.errors.length);
      try {
        await withWorking(undefined,
            () => HTTP.post('auth/totp/' + this.id + '/verify/', {code: this.code})
        );
        if ('redirect' in this.$route.query && this.$route.query.redirect) {
          this.$router.replace(this.$route.query.redirect);
        } else {
          this.$router.replace({ name: 'domains' });
        }
      } catch (ex) {
        let errors = await digestError(ex);
        for (const c in errors) {
          this.errors.push(...errors[c]);
        }
      }
      this.working = false;
    },
  },
};
</script>
