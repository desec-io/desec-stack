<template>
  <v-switch
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :input-value="value"
    :required="required"
    :rules="[v => !required || !!v || 'Required.']"
    @change="input($event)"
    @keyup="keyup($event)"
  />
</template>

<script>
export default {
  name: 'SwitchBox',
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
      type: Boolean,
      required: true,
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
