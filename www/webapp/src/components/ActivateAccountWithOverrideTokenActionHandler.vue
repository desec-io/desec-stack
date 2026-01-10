<template>
  <div>
    <div v-if="!success">
      <p>
        On this page, you can activate your deSEC account. <b>By doing so, you will also grant
        permission for your DNS to be managed by the party listed in the confirmation email
        that contained the link to this page.</b>
      </p>
      <p>
        DNS management permission is limited to domains that the authorized party will
        create in your account. The authorized party will have permission to both modify and
        delete the domains created by them.<br />
        If you create additional domains in your account by hand, they will not be visible
        to the authorized party.
      </p>
      <p>
        If you ever would like to revoke this authorization, you can remove it in the
        "Token Management" section of our web interface. Authorization can also be
        withdrawn by the authorized party itself.
      </p>
      <div class="text-center">
        <generic-captcha
            @update="(id, solution) => {setCaptchaPayload(id, solution)}"
            tabindex="1"
            ref="captchaField"
        />
        <v-row class="justify-center">
          <v-checkbox
                v-model="payload.outreach_preference"
                hide-details
                tabindex="2"
          >
            <template #label>
              <v-col>
                Tell me about deSEC developments. No ads. <small>(recommended)</small>
              </v-col>
            </template>
          </v-checkbox>
        </v-row>

        <v-row class="justify-center">
          <v-checkbox
                v-model="terms"
                hide-details="auto"
                :rules="terms_rules"
                tabindex="3"
          >
            <template #label>
              <v-col>
                Yes, I agree to the <span @click.stop><router-link :to="{name: 'terms'}" target="_blank">Terms of Use</router-link></span> and
                <span @click.stop><router-link :to="{name: 'privacy-policy'}" target="_blank">Privacy Policy</router-link></span>.
              </v-col>
            </template>
          </v-checkbox>
        </v-row>
        <v-btn
                variant="flat"
                class="mt-4"
                color="primary"
                type="submit"
                :disabled="working || !valid"
                :loading="working"
                tabindex="4"
        >Submit</v-btn>
      </div>
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
    name: 'ActivateAccountWithOverrideTokenActionHandler',
    components: {GenericCaptcha},
    extends: GenericActionHandler,
    data: () => ({
      terms: false,
      terms_rules: [v => !!v || 'You can only use our service if you agree with the terms'],
    }),
    async created() {
      this.payload.outreach_preference = true;
    },
    methods: {
      /* captcha field */
      setCaptchaPayload(id, solution) {
        this.payload.captcha = {
          id: id,
          solution: solution,
        };
      },
    },
  };
</script>
