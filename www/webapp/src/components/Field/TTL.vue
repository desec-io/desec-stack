<template>
  <v-text-field
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :model-value="inputValue"
    type="number"
    max="86400"
    :min="min"
    :placeholder="required ? '' : '(optional)'"
    :required="required"
    :rules="rules"
    @update:modelValue="updateValue"
    @keyup="handleKeyup"
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
    modelValue: {
      type: [String, Number],
      required: false,
    },
    value: {
      type: [String, Number],
      required: false,
    },
  },
  data() { return {
    rules: [
      v => !this.required || !!v || 'Required.',
      v => v >= this.min && v <= 86400 || `${this.min} ≤ … ≤ 86400`,
    ],
  }},
  computed: {
    inputValue() {
      return this.modelValue ?? this.value;
    },
  },
  methods: {
    updateValue(value) {
      this.$emit('update:modelValue', value);
      this.$emit('input', value);
      this.$emit('dirty');
    },
    handleKeyup(event) {
      this.$emit('keyup', event);
      this.$emit('dirty');
    },
  },
};
</script>
