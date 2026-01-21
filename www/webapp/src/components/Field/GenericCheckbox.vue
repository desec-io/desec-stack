<template>
  <v-checkbox
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :model-value="inputValue"
    :required="required"
    :rules="[v => !required || !!v || 'Required.']"
    @update:modelValue="change"
  />
</template>

<script>
export default {
  name: 'GenericCheckbox',
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
      type: Boolean,
      required: false,
    },
    value: {
      type: Boolean,
      required: false,
    },
  },
  computed: {
    inputValue() {
      return this.modelValue ?? this.value;
    },
  },
  methods: {
    change(value) {
      this.$emit('update:modelValue', value);
      this.$emit('input', value);
      this.$emit('dirty', {target: this.$el});
    },
  },
};
</script>
