<template>
  <v-textarea
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :model-value="inputValue"
    :type="type || ''"
    :placeholder="required ? '' : '(optional)'"
    :hint="hint"
    persistent-hint
    :required="required"
    :rules="[v => !required || !!v || 'Required.'].concat(rules)"
    @update:modelValue="updateValue"
    @keyup="handleKeyup"
    density="compact"
    rows="8"
  />
</template>

<script>
export default {
  name: 'GenericTextarea',
  props: {
    disabled: {
      type: Boolean,
      required: false,
    },
    errorMessages: {
      type: [String, Array],
      default: () => [],
    },
    hint: {
      type: String,
      default: '',
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
    rules: {
      type: Array,
      default: () => [],
    },
    modelValue: {
      type: [String, Number],
      required: false,
    },
    value: {
      type: [String, Number],
      required: false,
    },
    type: {
      type: String,
      required: false,
    },
  },
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

<style>
.v-textarea textarea {
  font-family: monospace;
  font-size: 80%;
  line-height: 1.1em;
  white-space: pre;
  overflow-wrap: normal;
  overflow-x: scroll;
}
</style>
