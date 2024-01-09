<template>
  <v-text-field
      v-bind="computedProps"
      v-on="$listeners"
  />
</template>

<script>
import {email_pattern} from '@/validation';
import {mdiEmail, mdiEmailLock} from '@mdi/js';
import {VTextField} from 'vuetify/lib/components';

export default {
  name: 'GenericEmail',
  extends: VTextField,
  props: {
    value: {
      type: String,
      required: false,
    },
    errorMessages: {
      type: [String, Array],
      default: () => [],
    },
    label: {
      type: String,
      required: false,
    },
    placeholder: {
      type: String,
      required: false,
    },
    required: {
      type: Boolean,
      default: true,
    },
    standalone: {
      type: Boolean,
      default: false,
    },
    readonly: {
      type: Boolean,
      required: false,
    },
    autofocus: {
      type: Boolean,
      required: false,
    },
    new: {
      type: Boolean,
      required: false,
    },
  },
  computed: {
    computedProps() {
      let label = 'Email Address';
      if(!this.required) {
        label += ' (optional)';
      }
      if(this.new) {
        label = 'New ' + label;
      }
      if(this.standalone) {
        label = '';
      }
      if(this.label) { // Override if custom is set.
        label = this.label;
      }
      const icon = this.readonly ? mdiEmailLock : mdiEmail;
      const ruleDefs = {
        required: v => !!v || 'Email is required.',
        valid: v => (v !== undefined && !!email_pattern.test(v)) || 'We need an valid email address for account recovery and technical support.',
      };
      let rules = []
      if(this.required) {
        rules.push(ruleDefs.required);
      }
      if(this.new) {
        rules.push(ruleDefs.valid);
      }
      return {
        type: 'email',
        value: this.value,
        'error-messages': this.errorMessages,
        label: label,
        required: this.required,
        disabled: this.readonly,
        autofocus: this.autofocus,
        placeholder: this.placeholder ?? 'Email Address',
        prependIcon: this.standalone ? '' : icon,
        prependInnerIcon: this.standalone ? icon : '',
        flat: this.standalone,
        solo: this.standalone,
        outlined: true,
        rules: rules,
        validateOnInput: true,
      }
    }
  },
};
</script>
