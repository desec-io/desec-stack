<template>
  <v-text-field
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :model-value="value"
    :type="type || ''"
    :placeholder="placeholder || (required ? '' : '(optional)')"
    :hint="hint"
    persistent-hint
    :required="required"
    :rules="[v => !required || !!v || 'Required.'].concat(rules)"
    @update:model-value="changed('input', $event)"
    @update:model-value.native="$emit('dirty', $event)"
    @keyup="changed('keyup', $event)"
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
    placeholder: {
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
/* Removes dropdown icon from read-only select */
.v-application--is-ltr .v-text-field.v-input--is-disabled .v-input__append-inner {
  display: none;
}
/* remove underline from disabled text fields so they look like regular text */
:not(v-select).theme--light.v-text-field.v-input--is-disabled .v-input__slot::before {
  content: none;
}
/* display disabled text fields in normal color */
.theme--light.v-input--is-disabled input {
  color: rgba(0, 0, 0, 0.87);
}
/* Work around Firefox not propagating click events to parent element, see
   https://bugzilla.mozilla.org/show_bug.cgi?id=1107929 (old),
   https://bugzilla.mozilla.org/show_bug.cgi?id=1653882 (new).
   It looks like Chrome 110 will follow: https://github.com/whatwg/html/issues/5886
*/
.v-input--is-disabled {
  pointer-events: none;  /* thanks to https://stackoverflow.com/a/66029445/6867099 */
}
</style>