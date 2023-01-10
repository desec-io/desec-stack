<template>
  <div>
    <v-alert v-if="done" type="success">
      <p>
        Thanks for your report.
      </p>
      <v-btn depressed outlined block :to="{name: 'home'}">Done</v-btn>
    </v-alert>
    <v-form v-if="!done" @submit.prevent="donate" ref="form">
      <error-alert v-bind:errors="errors"></error-alert>

      Which kind(s) of abuse are you reporting and which deSEC-hosted domain names are involved?

      <v-combobox
        v-model="kind"
        :items="['scam', 'spam', 'malware', 'phishing']"
        chips
        label="Form(s) of abuse"
        multiple
        :rules="kind_rules"
        :disabled="working"
        prepend-icon="mdi-format-section"
        >
      </v-combobox>

      <v-combobox
        v-model="domains"
        chips
        label="Domain(s) involved in the abuse. We understand wildcards. Must all use deSEC as auth DNS server."
        multiple
        :rules="domain_rules"
        :disabled="working"
        prepend-icon="mdi-form-textbox"
        >
      </v-combobox>

      <v-combobox
        v-model="proofs"
        chips
        label="Proof of abuse. If you need to attach a file, send us a download link."
        multiple
        :rules="proof_rules"
        :disabled="working"
        prepend-icon="mdi-check-decagram-outline"
        >
      </v-combobox>

      Acceptable forms of proof include entries on the
      <a href="https://transparencyreport.google.com/safe-browsing/" target="_blank">Google Safe Browsing List</a>.
      Note that not every website that looks like a phishing website is illegal, e.g. when such sites are used for
      security training and never actually send entered credentials.

      <v-radio-group
          v-model="urgency"
          mandatory
          row
          prepend-icon="mdi-alarm"
      >
        <v-radio label="Everyday abuse, react within 48 hours." :value="0"></v-radio>
        <v-radio label="Urgent, get people out of bed." :value="1"></v-radio>
      </v-radio-group>

      <v-text-field
              v-model="name"
              label="Your Name (Optional)"
              prepend-icon="mdi-account"
              outline
              required
              :disabled="working"
              :rules="name_rules"
              :error-messages="name_errors"
      />

      <v-text-field
              v-model="message"
              label="Message (optional)"
              prepend-icon="mdi-message-text-outline"
              outline
              :disabled="working"
              validate-on-blur
      />

      If you provide your email address, we can get back to you for questions or updates on the status of your report.

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
      >Send Report</v-btn>
    </v-form>
  </div>
</template>

<script>
  import axios from 'axios';
  import {email_pattern} from '../validation';
  import {digestError} from "../utils";
  import ErrorAlert from '@/components/ErrorAlert';

  const HTTP = axios.create({
    baseURL: '/api/v1/',
    headers: {
    },
  });

  export default {
    name: 'ReportAbuseForm',
    components: {
      ErrorAlert,
    },
    data: () => ({
      valid: false,
      working: false,
      done: false,
      errors: [],

      /* abuse kind field */
      kind: [],
      kind_rules: [v => v.length > 0 || 'Please select or enter at least one item.'],

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

      /* donation interval (every N months) */
      interval: 1,

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
        this.errors.splice(0, this.errors.length);
        try {
          let response = await HTTP.post('donation/', {
            amount: this.amount,
            name: this.name,
            iban: this.iban,
            bic: "",
            message: this.message,
            email: this.email,
            interval: this.interval,
          });
          this.mref = response.data.mref;
          this.done = true;
        } catch (ex) {
          let errors = await digestError(ex);
          for (const c in errors) {
            if (c === 'email') {
              this.email_errors = errors[c];
            } else if (c === 'amount') {
              this.amount_errors = errors[c];
            } else {
              this.errors.push(...errors[c]);
            }
          }
        }
        this.working = false;
      },
    },
  };
</script>
