<template>
  <v-text-field v-if="!readonly"
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :value="value"
    :type="type || ''"
    :placeholder="required ? '' : '(optional)'"
    :required="required"
    :rules="[v => !required || !!v || 'Required.']"
    @input="$emit('input', $event)"
    @input.native="$emit('dirty', $event)"
    @keyup="$emit('keyup', $event)"
  />
  <span v-else>{{ value }}</span>
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
};
</script>
