<template>
  <div>
    <div class="text-center" v-if="captcha_required && !success">
      <v-container class="pa-0">
        <v-row dense align="center" class="text-center">
          <v-col cols="12" sm="">
            <v-text-field
                    v-model="payload.captcha.solution"
                    label="Type CAPTCHA text here"
                    prepend-icon="mdi-account-check"
                    outline
                    required
                    :disabled="working"
                    :rules="captcha_rules"
                    :error-messages="captcha_errors"
                    @change="captcha_errors=[]"
                    @keypress="captcha_errors=[]"
                    class="uppercase"
                    ref="captchaField"
                    tabindex="3"
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
                  alt="Passwords can also be reset by sending an email to our support."
            />
            <audio controls
                  v-if="captcha && !captchaWorking && captcha_kind === 'audio'"
            >
              <source :src="'data:audio/wav;base64,'+captcha.challenge" type="audio/wav"/>
            </audio>
            <br/>
            <v-btn-toggle>
              <v-btn text outlined @click="getCaptcha(true)" :disabled="captchaWorking"><v-icon>mdi-refresh</v-icon></v-btn>
            </v-btn-toggle>
            &nbsp;
            <v-btn-toggle v-model="captcha_kind">
              <v-btn text outlined value="image" aria-label="Switch to Image CAPTCHA" :disabled="captchaWorking"><v-icon>mdi-eye</v-icon></v-btn>
              <v-btn text outlined value="audio" aria-label="Switch to Audio CAPTCHA" :disabled="captchaWorking"><v-icon>mdi-ear-hearing</v-icon></v-btn>
            </v-btn-toggle>
          </v-col>
        </v-row>
      </v-container>
        <v-btn
                depressed
                color="primary"
                type="submit"
                :disabled="working || !valid"
                :loading="working"
                tabindex="2"
        >Submit</v-btn>
    </div>
    <v-alert type="success" v-if="success">
      <p>{{ this.response.data.detail }}</p>
    </v-alert>
  </div>
</template>

<script>
  import axios from 'axios';
  import GenericActionHandler from "./GenericActionHandler"

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {},
  });

  export default {
    name: 'ActivateAccountActionHandler',
    extends: GenericActionHandler,
    data: () => ({
      auto_submit: true,
      captchaWorking: false,
      LOCAL_PUBLIC_SUFFIXES: process.env.VUE_APP_LOCAL_PUBLIC_SUFFIXES.split(' '),
      captcha: null,
      captcha_required: false,

      /* captcha field */
      captchaSolution: '',
      captcha_rules: [v => !!v || 'Please enter the text displayed in the picture so we are (somewhat) convinced you are human'],
      captcha_errors: [],
      captcha_kind: 'image',
    }),
    computed: {
      captcha_error: function () {
        return this.error && this.response.data.captcha !== undefined
      }
    },
    methods: {
      async getCaptcha() {
        this.captchaWorking = true;
        this.captchaSolution = "";
        try {
          this.captcha = (await HTTP.post('captcha/', {kind: this.captcha_kind})).data;
          this.payload.captcha.id = this.captcha.id;
          this.$refs.captchaField.focus()
        } finally {
          this.captchaWorking = false;
        }
      },
    },
    watch: {
      captcha_error(value) {
        if(value) {
          this.$emit('clearerrors');
          this.captcha_required = true;
          this.payload.captcha = {};
          this.getCaptcha();
        }
      },
      captcha_kind: function (oldKind, newKind) {
        if (oldKind !== newKind) {
          this.getCaptcha();
        }
      },
      success(value) {
        if(value) {
          let domain = this.response.data.domain;
          if(domain === undefined) {
            return;
          }
          if(this.LOCAL_PUBLIC_SUFFIXES.some((suffix) => domain.name.endsWith('.' + suffix))) {
            let token = this.response.data.token;
            this.$router.push({ name: 'dynSetup', params: { domain: domain.name }, hash: `#${token}` });
          } else {
            let ds = domain.keys.map(key => key.ds);
            ds = ds.concat.apply([], ds)
            this.$router.push({
              name: 'customSetup',
              params: {
                domain: domain.name,
                ds: ds,
                dnskey: domain.keys.map(key => key.dnskey),
                isNew: true,
              },
            });
          }
        }
      }
    }
  };
</script>
