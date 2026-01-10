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
        <v-card-title class="d-flex align-center">
          <span class="text-h6">
            Verify TOTP: <b>{{ displayName }}</b>
          </span>
          <v-spacer/>
          <v-btn
            icon
            variant="text"
            :aria-label="'Close dialog'"
            @click.stop="close"
          >
            <v-icon :icon="mdiClose" />
          </v-btn>
        </v-card-title>
        <v-divider/>

        <v-alert class="mb-0" :model-value="!!detail" type="warning">
          {{ detail }}
        </v-alert>
        <v-alert class="mb-0" :model-value="!!successDetail" type="success">
          {{ successDetail }}
        </v-alert>
        <error-alert :errors="errors"></error-alert>

        <v-card-text v-if="!!successDetail" class="text-center">
          <p class="mt-2">
            <v-icon :icon="mdiCheck" />
            Great! Continue to <router-link :to="{name: 'login'}">log in</router-link>.
          </p>
        </v-card-text>

        <v-card-text v-if="!!payload && !successDetail" class="text-center">
          <p class="mt-2">
            <v-icon :icon="mdiNumeric1Circle" />
            Please scan the following QR code with an authenticator app (e.g. Google Authenticator).<br />
            <strong>This code is only displayed once.</strong>
          </p>
          <div class="text-center">
            <qrcode-vue :value="payload.uri" size="300" level="H"/>
          </div>
          <p class="mt-6">
            <v-icon :icon="mdiNumeric2Circle" />
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
                        variant="flat"
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
            {{ payload.secret }}</small>
          </p>
        </v-card-text>
      </v-card>
    </v-form>
  </v-dialog>
</template>

<script>
import {digestError, HTTP, logout, withWorking} from '@/utils'
import ErrorAlert from "@/components/ErrorAlert.vue";
import QrcodeVue from '@/components/QrcodeVue.vue'
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
      required: false,
      default: '',
    },
    detail: {
      type: String,
      required: false,
      default: '',
    },
    data: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data: () => ({
    code: "",
    successDetail: "",
    errors: [],
    working: false,
    show: true,
    sessionData: null,
    mdiCheck,
    mdiClose,
    mdiNumeric1Circle,
    mdiNumeric2Circle,
  }),
  computed: {
    payload() {
      return this.data || this.sessionData;
    },
    displayName() {
      return this.name || this.$route.query.name || this.payload?.name || '';
    },
  },
  mounted() {
    if (!this.data) {
      const raw = sessionStorage.getItem('totpVerifyData');
      if (raw) {
        try {
          this.sessionData = JSON.parse(raw);
        } catch {
          this.sessionData = null;
        }
        sessionStorage.removeItem('totpVerifyData');
      }
    }
  },
  methods: {
    close() {
      this.show = false;
    },
    async verify() {
      const { valid } = await this.$refs.form.validate();
      if (!valid) {
        return;
      }
      this.working = true;
      this.errors.splice(0, this.errors.length);
      try {
        let res = await withWorking(undefined,
            () => HTTP.post('auth/totp/' + this.payload.id + '/verify/', {code: this.code})
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
