<template>
  <v-layout>
    <div v-for="(field, index) in fields" :key="index">
      <v-text-field
        v-model="field.value"
        :clearable="clearable"
        :placeholder="field.placeholder"
        @input="$emit('update:content', value)"
        :hide-details="!$v.fields.$each[index].$invalid && !$v.fields[index].$invalid"
        :error="$v.fields.$each[index].$invalid || $v.fields[index].$invalid"
        :error-messages="fieldErrorMessages(index)"
        :style="{width: fieldWidth(index) }"
        ref="input"
      ></v-text-field>
      <span ref="mirror" aria-hidden="true" style="opacity: 0; position: absolute; width: auto; white-space: pre; z-index: -1"></span>
    </div>
  </v-layout>
</template>

<script>
import { required } from 'vuelidate/lib/validators'
import VueJsonPretty from 'vue-json-pretty'

export default {
  name: 'Record',
  components: {
    VueJsonPretty
  },
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
    errors: {
      required: 'This field is required.'
    },
    fields: [
      { 'name': 'value', 'value': '', 'validations': {} }
    ]
  }),
  beforeMount () {
    let values = this.content.split(' ')
    let last = values.slice(this.fields.length - 1).join(' ')
    values = values.slice(0, this.fields.length - 1).concat([last])

    values.forEach((value, i) => {
      this.fields[i].value = value
    })
  },
  validations () {
    const validations = {
      fields: {
        $each: {
          value: { required }
        }
      }
    }

    validations.fields = this.fields.reduce(
      (acc, field, index) => {
        acc[index] = { value: field.validations }
        return acc
      },
      validations.fields
    )

    return validations
  },
  computed: {
    value () {
      return this.fields.map(field => field.value).join(' ')
    }
  },
  methods: {
    fieldErrorMessages (index) {
      const fieldValidationStatus = (fields, index) => {
        return Object.keys(fields[index].value.$params).map(
          name => ({passed: fields[index].value[name], message: this.errors[name]})
        )
      }

      const validationStatus = [
        ...fieldValidationStatus(this.$v.fields, index),
        ...fieldValidationStatus(this.$v.fields.$each, index)
      ]

      return validationStatus.filter(val => !val.passed).map(val => val.message || 'Invalid input.')
    },
    fieldWidth (index) {
      let ret = 'auto'
      const inputs = this.$refs['input']
      const mirrors = this.$refs['mirror']
      if (index < this.fields.length - 1 && inputs && mirrors) {
        const mirror = mirrors[index]
        while (mirror.childNodes.length) {
          mirror.removeChild(mirror.childNodes[0])
        }

        const style = window.getComputedStyle(inputs[index].$el)
        mirror.style.border = style.getPropertyValue('border')
        mirror.style.fontSize = style.getPropertyValue('font-size')
        mirror.style.fontFamily = style.getPropertyValue('font-family')
        mirror.style.fontWeight = style.getPropertyValue('font-weight')
        mirror.style.fontStyle = style.getPropertyValue('font-style')
        mirror.style.fontFeatureSettings = style.getPropertyValue('font-feature-settings')
        mirror.style.fontKerning = style.getPropertyValue('font-kerning')
        mirror.style.fontStretch = style.getPropertyValue('font-stretch')
        mirror.style.fontVariant = style.getPropertyValue('font-variant')
        mirror.style.fontVariantCaps = style.getPropertyValue('font-variant-caps')
        mirror.style.fontVariantLigatures = style.getPropertyValue('font-variant-ligatures')
        mirror.style.fontVariantNumeric = style.getPropertyValue('font-variant-numeric')
        mirror.style.letterSpacing = style.getPropertyValue('letter-spacing')
        mirror.style.padding = style.getPropertyValue('padding')
        mirror.style.textTransform = style.getPropertyValue('text-transform')

        const value = this.fields[index].value || this.fields[index].placeholder
        mirror.appendChild(document.createTextNode(value + ' '))

        ret = mirror.getBoundingClientRect().width + 'px'
      }
      return ret
    }
  }
}
</script>

<style>
</style>
