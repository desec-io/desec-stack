<template>
  <div>
    <v-text-field
      v-model="value"
      :clearable="clearable"
      :hide-details="!$v.value.$invalid"
      :error="$v.value.$invalid"
      :error-messages="errorMessages"
      @input="$emit('update:content', value)"
    ></v-text-field>
    {{ value }}
  </div>
</template>

<script>
import { required } from 'vuelidate/lib/validators'

export default {
  name: 'Record',
  props: {
    content: {
      type: String,
      required: true
    },
    clearable: {
      type: Boolean,
      default: false
    }
  },
  data: () => ({
    messagePool: {
      required: 'This field is required.'
    },
    value: ''
  }),
  beforeMount () {
    this.value = this.content
  },
  validations: {
    value: { required }
  },
  computed: {
    errorMessages () {
      return Object.entries(this.messagePool).filter(entry => !this.$v.value[entry[0]]).map(entry => entry[1])
    }
  }
}
</script>

<style>
</style>
