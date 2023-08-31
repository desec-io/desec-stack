<template>
  <v-text-field
      v-bind="computedProps"
      v-on="$listeners"
      @click:append="toggleHide()"
  />
</template>

<script>
import {mdiEye, mdiEyeOff, mdiKey} from '@mdi/js';
import {VTextField} from 'vuetify/lib/components';

export default {
  name: 'GenericPassword',
  extends: VTextField,
  props: {
    errorMessages: {
      type: [String, Array],
      default: () => [],
    },
    label: {
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
    new: {
      type: Boolean,
      required: false,
    },
  },
  data() {
    return {
      hide_password: true,
    };
  },
  computed: {
    computedProps() {
      const icon = mdiKey;
      const iconToggle = this.hide_password ? mdiEyeOff : mdiEye;
      let label = 'Password';
      if(!this.required) {
        label += ' (Optional)';
      }
      if(this.new) {
        label = 'New ' + label;
      }
      if(this.label) { // override with custom label
        label = this.label;
      }
      const ruleDefs = {
        required: v => !!v || 'Password is required.',
        min: v => (v !== undefined && v.length >= 8) || 'Min 8 characters',
      };
      let rules = []
      if(this.required) {
        rules.push(ruleDefs.required)
      }
      if(this.new) {
        rules.push(ruleDefs.min)
      }
      return {
        ...this.$props,
        type: this.hide_password ? 'password' : 'text',
        label: label,
        autocomplete: this.new ? 'new-password' : '',
        prependIcon: this.standalone ? '' : icon,
        prependInnerIcon: this.standalone ? icon : '',
        appendIcon: iconToggle,
        flat: this.standalone,
        solo: this.standalone,
        outlined: true,
        rules: rules,
        errorMessages: this.errorMessages,
        validateOnInput: true,
      }
    }
  },
  methods: {
    toggleHide() {
      this.hide_password = !this.hide_password;
    }
  },
};
</script>
