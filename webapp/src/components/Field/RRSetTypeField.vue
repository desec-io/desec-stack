<template>
  <div>
    <code>{{ value }}</code>
    <v-combobox
      v-bind:value="value"
      v-on:input="input($event)"
      :items="types"
    ></v-combobox>
  </div>
</template>

<script>
export default {
  name: 'RRSetTypeField',
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
