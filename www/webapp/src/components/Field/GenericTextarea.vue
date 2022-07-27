<template>
  <v-textarea
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :value="value"
    :type="type || ''"
    :placeholder="required ? '' : '(optional)'"
    :hint="hint"
    persistent-hint
    :required="required"
    :rules="[v => !required || !!v || 'Required.'].concat(rules)"
    @input="changed('input', $event)"
    @input.native="$emit('dirty', $event)"
    @keyup="changed('keyup', $event)"
    dense
    rows="8"
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
    value: {
      type: [String, Number],
      required: false,
    },
    type: {
      type: String,
      required: false,
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
