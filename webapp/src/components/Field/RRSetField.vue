<template>
  <div>
    <code>{{ value }}</code>
    <component
      :is="'Record' + type"
      v-for="(record, index) in value"
      :key="index"
      :content="value[index]"
      :clearable="value.length > 1"
      @update:content="$set(value, index, $event)"
    ></component>
  </div>
</template>

<script>
import Record from '../Domain/Record'
import RecordA from '../Domain/RecordA'
import RecordCNAME from '../Domain/RecordCNAME'
import RecordMX from '../Domain/RecordMX'
import RecordSRV from '../Domain/RecordSRV'
import RecordNS from '../Domain/RecordNS'

export default {
  name: 'RRSetField',
  components: {
    Record,
    RecordA,
    RecordCNAME,
    RecordMX,
    RecordSRV,
    RecordNS
  },
  props: {
    value: {
      type: Array,
      required: true
    },
    type: {
      type: String,
      required: true
    }
  },
  data: () => ({
    types: ['A', 'AAAA', 'MX', 'CNAME', 'TXT', 'SPF', 'CAA', 'TLSA', 'OPENPGPKEY', 'PTR', 'SRV', 'DS', 'DNSKEY']
  }),
  methods: {
    getRecordComponentName () {
      let genericComponentName = 'Record'
      let specificComponentName = genericComponentName + this.type
      if (this.types.includes(this.type) && specificComponentName in this.$options.components) {
        return specificComponentName
      }
      return genericComponentName
    }
  }
}
</script>

<style scoped>
</style>
