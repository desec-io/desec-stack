<template>
  <div>
    <v-alert v-if="done" type="success">
      <p>
        We hereby confirm your donation to deSEC. We would like to <b>thank you</b> for
        your support. If you have any questions concerning your donation, how
        we use your money, or if we can do anything else for you: Please do not
        hesitate to contact us anytime.
      </p>
      <p>
        We will debit {{ amount }} € from your account within the next
        two weeks. Your mandate reference number is {{ mref }}; our
        creditor identifier is {{ creditorid }}.
      </p>
      <p>
        Please note that the payment is handled by {{ creditorname }}, which
        may be the name appearing on your bank statement.
      </p>
      <p>Again, thank you so much.</p>
      <v-btn flat depressed outlined block :to="{name: 'home'}">Done</v-btn>
    </v-alert>
    <v-form v-if="!done" @submit.prevent="donate" ref="form">
      <v-alert :value="!!(errors && errors.length)" type="error">
        <div v-if="errors.length > 1">
          <li v-for="error of errors" :key="error.message" >
            <b>{{ error.message }}</b>
            {{ error }}
          </li>
        </div>
        <div v-else>
          {{ errors[0] }}
        </div>
      </v-alert>

      <v-text-field
              v-model="name"
              label="Full Name of the Account Holder"
              prepend-icon="mdi-account"
              outline
              required
              :disabled="working"
              :rules="name_rules"
              :error-messages="name_errors"
      />

      <v-text-field
              v-model="iban"
              label="IBAN"
              prepend-icon="mdi-bank"
              outline
              required
              :disabled="working"
              :rules="iban_rules"
              :error-messages="iban_errors"
              validate-on-blur
      />

      <v-text-field
              v-model="amount"
              label="Amount in Euros"
              prepend-icon="mdi-cash-100"
              outline
              required
              :disabled="working"
              :rules="amount_rules"
              :error-messages="amount_errors"
      />

      <v-text-field
              v-model="message"
              label="Message (optional)"
              prepend-icon="mdi-message-text-outline"
              outline
              :disabled="working"
              validate-on-blur
      />

      <v-text-field
              v-model="email"
              label="Email Address (optional)"
              prepend-icon="mdi-email"
              outline
              :disabled="working"
              :rules="email_rules"
              :error-messages="email_errors"
              validate-on-blur
      />

      <v-btn
              depressed
              block
              color="primary"
              type="submit"
              :disabled="working"
              :loading="working"
      >Donate Now</v-btn>
    </v-form>
  </div>
</template>

<script>
  import axios from 'axios';
  import {email_pattern} from '../validation';

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {
    },
  });

  export default {
    name: 'SignUp',
    data: () => ({
      valid: false,
      working: false,
      done: false,
      errors: [],

      /* from env */
      creditorid: process.env.VUE_APP_DESECSTACK_API_SEPA_CREDITOR_ID,
      creditorname: process.env.VUE_APP_DESECSTACK_API_SEPA_CREDITOR_NAME,

      /* account holder name field */
      name: '',
      name_rules: [v => !!v || 'We need the account holder\'s name to debit an account.'],
      name_errors: [],

      /* IBAN field */
      iban: '',
      iban_rules: [v => !!v || 'For direct debit, an IBAN is required. If you do not have an IBAN, please consider using alternative donation methods.'],
      iban_errors: [],

      /* amount field */
      amount: 10,
      amount_rules: [
              v => !!v || 'Please specify the amount you want to donate, in Euros.',
              v => !isNaN(v) || 'Please specify the amount as a decimal number.'
      ],
      amount_errors: [],

      /* message field */
      message: '',

      /* email field */
      email: '',
      email_rules: [v => v === '' || !!email_pattern.test(v || '') || 'This is not an email address.'],
      email_errors: [],

      /* sent by server */
      mref: '',
    }),
    methods: {
      async reset() {
        this.$refs.form.reset();
      },
      async donate() {
        if (!this.$refs.form.validate()) {
          return;
        }
        this.working = true;
        this.errors = [];
        try {
          let response = await HTTP.post('donation/', {
            amount: this.amount,
            name: this.name,
            iban: this.iban,
            bic: "",
            message: this.message,
            email: this.email,
          });
          this.mref = response.data.mref;
          this.done = true;
        } catch (error) {
          if (error.response) {
            // status is not 2xx
            if (error.response.status < 500 && typeof error.response.data === 'object') {
              // 3xx or 4xx
              let extracted = false;
              if ('email' in error.response.data) {
                this.email_errors = [error.response.data.email[0]];
                extracted = true;
              }
              if ('amount' in error.response.data) {
                this.amount_errors = [error.response.data.amount[0]];
                extracted = true;
              }
              // TODO extract more errors
              if (!extracted) {
                this.errors = [error.response];
              }
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
