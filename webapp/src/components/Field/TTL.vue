<template>
  <v-text-field
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :value="value"
    type="number"
    max="86400"
    :min="min"
    :placeholder="required ? '' : '(optional)'"
    :required="required"
    :rules="rules"
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
  data() { return {
    rules: [
      v => !this.required || !!v || 'Required.',
      v => v >= this.min && v <= 86400 || `${this.min} ≤ … ≤ 86400`,
    ],
  }},
  methods: {
    changed(event, e) {
      this.$emit(event, e);
      this.$emit('dirty');
    },
  },
};
</script>
