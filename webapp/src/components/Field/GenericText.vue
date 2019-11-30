<template>
  <v-text-field
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :value="value"
    :type="type || ''"
    :placeholder="required ? '' : '(optional)'"
    :required="required"
    :rules="[v => !required || !!v || 'Required.']"
    @input="input($event)"
    @keyup="keyup($event)"
  />
</template>

<script>
export default {
  name: 'GenericText',
  props: {
    disabled: {
      type: Boolean,
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
    readonly: {
      type: Boolean,
      required: false,
    },
    required: {
      type: Boolean,
      default: false,
    },
    value: {
      type: [String, Number],
      required: true,
    },
    type: {
      type: String,
      required: false,
    },
  },
  methods: {
    input(event) {
      this.$emit('input', event);
    },
    keyup(event) {
      this.$emit('keyup', event);
    },
  },
};
</script>
