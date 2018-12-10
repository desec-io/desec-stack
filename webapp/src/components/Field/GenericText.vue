<template>
  <v-text-field
    v-bind:value="value"
    v-on:input="input($event)"
    placeholder="(empty)"
  ></v-text-field>
</template>

<script>
export default {
  name: 'GenericText',
  props: {
    value: {
      type: String | Number,
      required: true
    }
  },
  methods: {
    input: function (event) {
      this.$emit('input', event)
    }
  }
}
</script>
