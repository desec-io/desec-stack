<template>
  <v-dialog
    v-model="show"
    max-width="700px"
    persistent
    scrollable
    @keydown.esc="close"
  >
    <v-form @submit.prevent="verify" ref="form">
      <v-card>
        <v-card-title>
          <div class="text-h6">
            Verify TOTP: <b>{{ name }}</b>
          </div>
          <v-spacer/>
          <v-icon @click.stop="close">
            {{ mdiClose }}
          </v-icon>
        </v-card-title>
        <v-divider/>

        <v-alert class="mb-0" :value="!!detail" type="warning">
          {{ detail }}
        </v-alert>
        <v-alert class="mb-0" :value="!!successDetail" type="success">
          {{ successDetail }}
        </v-alert>
        <error-alert :errors="errors"></error-alert>

        <v-card-text v-if="!!successDetail" class="text-center">
          <p class="mt-2">
            <v-icon>{{ mdiCheck }}</v-icon>
            Great! Continue to <router-link :to="{name: 'login'}">log in</router-link>.
          </p>
        </v-card-text>

        <v-card-text v-if="!!data && !successDetail" class="text-center">
          <p class="mt-2">
            <v-icon>{{ mdiNumeric1Circle }}</v-icon>
            Please scan the following QR code with an authenticator app (e.g. Google Authenticator).<br />
            <strong>This code is only displayed once.</strong>
          </p>
          <div class="text-center">
            <qrcode-vue :value="data.uri" size="300" level="H"/>
          </div>
          <p class="mt-6">
            <v-icon>{{ mdiNumeric2Circle }}</v-icon>
            Enter the code displayed in the authenticator app to confirm and activate the token:
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
          <v-divider class="my-4"/>
          <p>
            <small>
            Want to know what's in the code? — It's your TOTP secret:<br />
            {{ data.secret }}</small>
          </p>
        </v-card-text>
      </v-card>
    </v-form>
  </v-dialog>
</template>

<script>
import {digestError, HTTP, logout, withWorking} from '@/utils'
import ErrorAlert from "@/components/ErrorAlert.vue";
import QrcodeVue from '../../modules/qrcode.vue/dist/qrcode.vue.esm'
import {mdiCheck, mdiClose, mdiNumeric1Circle, mdiNumeric2Circle} from "@mdi/js";

export default {
  name: 'TOTPVerifyDialog',
  components: {
    ErrorAlert,
    QrcodeVue,
  },
  props: {
    name: {
      type: String,
      required: true,
    },
    detail: {
      type: String,
      required: false,
    },
    data: {
      type: Object,
      required: false,
    },
  },
  data: () => ({
    code: "",
    successDetail: "",
    errors: [],
    working: false,
    show: true,
    mdiCheck,
    mdiClose,
    mdiNumeric1Circle,
    mdiNumeric2Circle,
  }),
  methods: {
    close() {
      this.show = false;
    },
    async verify() {
      if (!this.$refs.form.validate()) {
        return;
      }
      this.working = true;
      this.errors.splice(0, this.errors.length);
      try {
        let res = await withWorking(undefined,
            () => HTTP.post('auth/totp/' + this.data.id + '/verify/', {code: this.code})
        );
        this.successDetail = res.data.detail;
        await logout();
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
