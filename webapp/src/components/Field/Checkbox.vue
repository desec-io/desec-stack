<template>
  <v-checkbox
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :input-value="value"
    :required="required"
    :rules="[v => !required || !!v || 'Required.']"
    @change="change"
  />
</template>

<script>
export default {
  name: 'Checkbox',
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
    change(event) {
      this.$emit('input', event);
      this.$emit('dirty', {target: this.$el});
    },
  },
};
</script>
