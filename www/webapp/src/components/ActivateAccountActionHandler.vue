<template>
  <div>
    <div class="text-center" v-if="captcha_required && !success">
        <generic-captcha
            @update="(id, solution) => {setCaptchaPayload(id, solution)}"
            tabindex="1"
            ref="captchaField"
        />
        <v-layout class="justify-center">
          <v-checkbox
                v-model="terms"
                hide-details="auto"
                type="checkbox"
                :rules="terms_rules"
                tabindex="2"
          >
            <template #label>
              <v-flex>
                Yes, I agree to the <span @click.stop><router-link :to="{name: 'terms'}" target="_blank">Terms of Use</router-link></span> and
                <span @click.stop><router-link :to="{name: 'privacy-policy'}" target="_blank">Privacy Policy</router-link></span>.
              </v-flex>
            </template>
          </v-checkbox>
        </v-layout>
        <v-btn
                depressed
                class="mt-4"
                color="primary"
                type="submit"
                :disabled="working || !valid"
                :loading="working"
                tabindex="3"
        >Submit</v-btn>
    </div>
    <v-alert type="success" v-if="success">
      <p>{{ this.response.data.detail }}</p>
    </v-alert>
  </div>
</template>

<script>
  import GenericActionHandler from "./GenericActionHandler.vue"
  import GenericCaptcha from "@/components/Field/GenericCaptcha.vue";

  export default {
    name: 'ActivateAccountActionHandler',
    components: {GenericCaptcha},
    extends: GenericActionHandler,
    data: () => ({
      auto_submit: true,
      LOCAL_PUBLIC_SUFFIXES: import.meta.env.VITE_APP_LOCAL_PUBLIC_SUFFIXES.split(' '),

      captcha_required: false,
      terms: false,
      terms_rules: [v => !!v || 'You can only use our service if you agree with the terms'],
    }),
    methods: {
      setCaptchaPayload(id, solution) {
        this.payload.captcha = {
          id: id,
          solution: solution,
        };
      },
    },
    watch: {
      error(value) {
        if(value && this.response.data.captcha !== undefined) {
          // Captcha is required because not verified during the initial registration.
          this.$emit('clearerrors');
          this.captcha_required = true;
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
