<template>
  <v-combobox
    v-bind:value="value"
    v-on:input="input($event)"
    :items="types"
  ></v-combobox>
</template>

<script>
export default {
  name: 'RRSetType',
  props: {
    value: {
      type: String,
      required: true
    }
  },
  data: () => ({
    types: [
      'A',
      'AAAA',
      'MX',
      'CNAME',
      'TXT',
      'SPF',
      'CAA',
      'TLSA',
      'OPENPGPKEY',
      'PTR',
      'SRV',
      'DS',
      'DNSKEY'
    ]
  }),
  methods: {
    input: function (event) {
      this.$emit('input', event)
    }
  }
}
</script>

<style>

</style>
