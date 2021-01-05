<template>
  <v-text-field
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :value="value"
    type="number"
    :min="min"
    :placeholder="required ? '' : '(optional)'"
    :required="required"
    :rules="[v => !required || !!v || 'Required.', v => v >= min || `Value must be ${min} or greater.`]"
    @input="changed('input', $event)"
    @input.native="$emit('dirty', $event)"
    @keyup="changed('keyup', $event)"
  />
</template>

<script>
export default {
  name: 'TTL',
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
    min: {
      type: Number,
      default: 3600,
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
  },
  methods: {
    changed(event, e) {
      this.$emit(event, e);
      this.$emit('dirty');
    },
  },
};
</script>
