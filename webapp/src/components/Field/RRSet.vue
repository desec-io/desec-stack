<template>
  <div>
    <component
      :is="getRecordComponentName(type)"
      v-for="(record, index) in value"
      :key="index"
      :content="value[index]"
      :clearable="value.length > 1"
      @update:content="$set(value, index, $event)"
    />
    <code style="white-space: normal">{{ value }}</code>
  </div>
</template>

<script>
import Record from './Record.vue';
import RecordA from './RecordA.vue';
import RecordCNAME from './RecordCNAME.vue';
import RecordMX from './RecordMX.vue';
import RecordSRV from './RecordSRV.vue';
import RecordNS from './RecordNS.vue';

export default {
  name: 'RRSet',
  components: {
    Record,
    RecordA,
    RecordCNAME,
    RecordMX,
    RecordSRV,
    RecordNS,
  },
  props: {
    value: {
      type: Array,
      required: true,
    },
    type: {
      type: String,
      required: true,
    },
  },
  data: () => ({
    types: ['A', 'AAAA', 'MX', 'CNAME', 'TXT', 'SPF', 'CAA', 'TLSA', 'OPENPGPKEY', 'PTR', 'SRV', 'DS', 'DNSKEY'],
  }),
  methods: {
    getRecordComponentName(type) {
      const genericComponentName = 'Record';
      const specificComponentName = genericComponentName + type;
      if (this.types.includes(type) && specificComponentName in this.$options.components) {
        return specificComponentName;
      }
      return genericComponentName;
    },
  },
};
</script>

<style scoped>
</style>
