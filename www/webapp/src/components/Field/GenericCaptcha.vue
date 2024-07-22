<template>
  <v-row dense align="center" class="text-center">
    <v-col cols="12" sm="">
      <v-text-field
          v-model="inputSolution"
          :label="l.inputSolution"
          :hint="kind === 'image' ? l.hintProblemWithImage : l.hintProblemWithAudio"
          :prepend-icon="mdiAccountCheck"
          :rules="rules"
          :error-messages="errors"
          :tabindex="tabindex"
          @input="emitChange()"
          @change="errors=[]"
          @keydown="errors=[]"
          outlined
          required
          class="uppercase"
          ref="captchaField"
      ></v-text-field>
    </v-col>
    <v-col cols="12" sm="auto">
      <v-progress-circular
          v-if="working"
          indeterminate
      ></v-progress-circular>
      <img
          v-if="captcha
          && !working
          && kind === 'image'"
          :src="'data:'+mimeImage+';base64,'+captcha.challenge"
          :alt="l.altImage"
      >
      <audio controls
             v-if="captcha
             && !working
             && kind === 'audio'"
      >
        <source :src="'data:'+mimeAudio+';base64,'+captcha.challenge" :type="mimeAudio">
      </audio>
      <br>
      <v-btn-toggle>
        <v-btn text outlined @click="getCaptcha(true)" :aria-label="l.newCaptcha" :disabled="working">
          <v-icon>{{ mdiRefresh }}</v-icon>
        </v-btn>
      </v-btn-toggle>
      &nbsp;
      <v-btn-toggle v-model="kind">
        <v-btn text outlined value="image" :aria-label="l.switchImage" :disabled="working">
          <v-icon>{{ mdiEye }}</v-icon>
        </v-btn>
        <v-btn text outlined value="audio" :aria-label="l.switchAudio" :disabled="working">
          <v-icon>{{ mdiEarHearing }}</v-icon>
        </v-btn>
      </v-btn-toggle>
    </v-col>
  </v-row>
</template>

<script>
import {mdiAccountCheck, mdiEarHearing, mdiEye, mdiRefresh} from '@mdi/js';
import axios from 'axios';

const HTTP = axios.create({
  baseURL: '/api/v1/',
  headers: {},
});

export default {
  name: 'GenericCaptcha',
  captcha_kind: '',
  props: {
    tabindex: {
      type: String,
      required: true,
    },
  },
  data: () => ({
    mdiAccountCheck,
    mdiEarHearing,
    mdiEye,
    mdiRefresh,
    captcha: null,
    working: true,
    inputSolution: '',
    rules: [v => !!v || 'Please enter the CAPTCHA text so we are (somewhat) convinced you are human.'],
    errors: [],
    kind: 'image',
    mimeAudio: 'audio/wav',
    mimeImage: 'image/png',
    l: {
      altImage: 'Sign up / password reset is also possible by sending an email to our support.',
      hintProblemWithAudio: 'Trouble hearing? Switch to an image CAPTCHA.',
      hintProblemWithImage: 'Can\'t see? Hear an audio CAPTCHA instead.',
      inputSolution: 'Type CAPTCHA text here',
      newCaptcha: 'Get new CAPTCHA',
      switchAudio: 'Switch to Audio CAPTCHA',
      switchImage: 'Switch to Image CAPTCHA',
    },
  }),
  methods: {
    async getCaptcha(focus = false) {
      this.working = true;
      this.inputSolution = '';
      await HTTP
          .post('captcha/', {kind: this.kind})
          .then((res) => {
            this.captcha = res.data;
          })
          .catch((e) => {
            if(e.response) {
              this.errors = ['Captcha request: Server error(' + e.response.status.toString() + '): ' + e.response.data.detail];
            } else if(e.request) {
              this.errors = ['Captcha request: Could not request from server.'];
            } else {
              this.errors = ['Captcha request: Unknown error.'];
            }
          })
      ;
      if(focus) {
        this.$refs.captchaField.focus();
      }
      this.working = false;
      this.emitChange();
    },
    addError(values) {
      this.errors.push(values);
    },
    captchaID() {
      return this.captcha.id;
    },
    captchaSolution() {
      return this.inputSolution.toUpperCase();
    },
    emitChange() {
      this.$emit('update', this.captchaID(), this.captchaSolution());
    }
  },
  async mounted() {
    await this.getCaptcha();
  },
  watch: {
    kind(oldKind, newKind) {
      if(oldKind !== newKind) {
        this.getCaptcha(true);
      }
    },
  },
};
</script>
