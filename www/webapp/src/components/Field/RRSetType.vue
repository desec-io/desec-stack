<template>
  <v-combobox
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    hint="You can also enter other types. For a full list, check the documentation."
    :persistent-hint="!readonly"
    :model-value="inputValue"
    :items="types"
    :required="required"
    :rules="[v => !required || !!v || 'Required.']"
    @update:modelValue="input"
  />
</template>

<script>
export default {
  name: 'RRSetType',
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
    modelValue: {
      type: String,
      required: false,
    },
    value: {
      type: String,
      required: false,
    },
  },
  data: () => ({
    types: [
      'A',
      'AAAA',
      'MX',
      'CNAME',
      'TXT',
      'HTTPS',
      'CAA',
      'TLSA',
      'OPENPGPKEY',
      'SMIMEA',
      'PTR',
      'SRV',
      'NS',
      'DS',
    ],
  }),
  computed: {
    inputValue() {
      return this.modelValue ?? this.value;
    },
  },
  methods: {
    input(event) {
      this.$emit('update:modelValue', event);
      this.$emit('input', event);
    },
  },
};
</script>
