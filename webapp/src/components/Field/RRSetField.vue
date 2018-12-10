<template>
  <div>
    <code>{{ value }}</code>
    <component
      :is="type"
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
    }
  }
}
</script>

<style scoped>
</style>
