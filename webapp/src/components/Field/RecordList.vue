<template>
  <div>
    <component
            :is="getRecordComponentName(type)"
            v-for="(item, index) in value"
            :key="index"
            :content="item"
            :error-messages="errorMessages[index] ? errorMessages[index].content : []"
            :hide-label="index > 0"
            :append-icon="value.length > 1 ? 'mdi-close' : ''"
            :disabled="disabled"
            :readonly="readonly"
            :required="required"
            ref="inputFields"
            @update:content="$set(value, index, $event)"
            @input.native="$emit('dirty', $event)"
            @remove="(e) => removeHandler(index, e)"
            @keyup="(e) => $emit('keyup', e)"
    />
    <v-btn
            @click="addHandler"
            class="px-0 text-none"
            color="grey"
            small
            text
            v-if="!readonly && !disabled"
    ><v-icon>mdi-plus</v-icon> add another value</v-btn>
    <!--div><code style="white-space: normal">{{ value }}</code></div-->
  </div>
</template>

<script>
import Record from './Record.vue';
import RecordA from './Record/A.vue';
import RecordAAAA from './Record/AAAA.vue';
import RecordCAA from './Record/CAA.vue';
import RecordCDNSKEY from './Record/CDNSKEY.vue';
import RecordCDS from './Record/CDS.vue';
import RecordCNAME from './Record/CNAME.vue';
import RecordDNSKEY from './Record/DNSKEY.vue';
import RecordDS from './Record/DS.vue';
import RecordHTTPS from './Record/HTTPS.vue';
import RecordMX from './Record/MX.vue';
import RecordNS from './Record/NS.vue';
import RecordOPENPGPKEY from './Record/OPENPGPKEY.vue';
import RecordPTR from './Record/PTR.vue';
import RecordSMIMEA from './Record/SMIMEA.vue';
import RecordSRV from './Record/SRV.vue';
import RecordSVCB from './Record/SVCB.vue';
import RecordTLSA from './Record/TLSA.vue';
import RecordTXT from './Record/TXT.vue';
import RecordSubnet from './Record/Subnet.vue';

export default {
  name: 'RecordList',
  components: {
    Record,
    RecordA,
    RecordAAAA,
    RecordCAA,
    RecordCDNSKEY,
    RecordCDS,
    RecordCNAME,
    RecordDNSKEY,
    RecordDS,
    RecordHTTPS,
    RecordMX,
    RecordNS,
    RecordOPENPGPKEY,
    RecordPTR,
    RecordSMIMEA,
    RecordSRV,
    RecordSVCB,
    RecordTLSA,
    RecordTXT,
    RecordSubnet,
  },
  props: {
    errorMessages: {
      type: Array,
      default: () => [],
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    readonly: {
      type: Boolean,
      default: false,
    },
    required: {
      type: Boolean,
      default: true,
    },
    value: {
      type: Array,
      default: () => [],
    },
    type: {
      type: String,
      required: true,
    },
  },
  data: function () {
    const self = this;
    return {
      types: [
        'A',
        'AAAA',
        'CAA',
        'CDNSKEY',
        'CDS',
        'CNAME',
        'DNSKEY',
        'DS',
        'HTTPS',
        'MX',
        'NS',
        'OPENPGPKEY',
        'PTR',
        'SMIMEA',
        'SPF',
        'SRV',
        'SVCB',
        'TLSA',
        'TXT',
        'Subnet'
      ],
      addHandler: ($event) => {
        self.$emit('dirty', $event);
        let value = [].concat(this.value);
        value.push('')
        self.$emit('input', value);
        self.$nextTick(() => self.$refs.inputFields[self.$refs.inputFields.length - 1].focus());
      },
      removeHandler: (index, $event) => {
        self.$emit('dirty', $event);
        let value = [].concat(this.value);
        value.splice(index, 1);
        self.$emit('input', value);
      },
    }
  },
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
