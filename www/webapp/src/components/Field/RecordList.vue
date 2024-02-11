<template>
  <div>
    <div style="overflow: auto hidden; padding-bottom: 1px; width: 100%">
      <table style="border-spacing: 0; width: 100%">
        <component
                :is="getRecordComponentName(type)"
                v-for="(item, index) in value"
                :key="index"
                :content="item"
                :error-messages="errorMessages[index] ? errorMessages[index].content : []"
                :hide-label="index > 0"
                :append-icon="value.length > 1 ? mdiClose : ''"
                :disabled="disabled"
                :readonly="readonly"
                :required="required"
                ref="inputFields"
                @update:content="$set(value, index, $event)"
                @input.native="$emit('dirty', $event)"
                @remove="(e) => removeHandler(index, e)"
                @keyup="(e) => $emit('keyup', e)"
        />
      </table>
    </div>
    <v-btn
            @click="addHandler"
            class="px-0 text-none"
            color="grey"
            small
            text
            v-if="!readonly && !disabled"
            aria-label="Add another value"
    ><v-icon>{{ mdiPlus }}</v-icon> add another value</v-btn>
  </div>
</template>

<script>
import RecordItem from './RecordItem.vue';
import RecordA from './RecordA.vue';
import RecordAAAA from './RecordAAAA.vue';
import RecordCAA from './RecordCAA.vue';
import RecordCDNSKEY from './RecordCDNSKEY.vue';
import RecordCDS from './RecordCDS.vue';
import RecordCNAME from './RecordCNAME.vue';
import RecordDNSKEY from './RecordDNSKEY.vue';
import RecordDS from './RecordDS.vue';
import RecordHTTPS from './RecordHTTPS.vue';
import RecordMX from './RecordMX.vue';
import RecordNS from './RecordNS.vue';
import RecordOPENPGPKEY from './RecordOPENPGPKEY.vue';
import RecordPTR from './RecordPTR.vue';
import RecordSMIMEA from './RecordSMIMEA.vue';
import RecordSRV from './RecordSRV.vue';
import RecordSVCB from './RecordSVCB.vue';
import RecordTLSA from './RecordTLSA.vue';
import RecordTXT from './RecordTXT.vue';
import RecordSubnet from './RecordSubnet.vue';
import {mdiClose, mdiPlus} from "@mdi/js";

export default {
  name: 'RecordList',
  components: {
    RecordItem,
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
      mdiClose,
      mdiPlus,
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
      const prefixComponentName = 'Record';
      const genericComponentName = prefixComponentName + 'Item';
      const specificComponentName = prefixComponentName + type;
      if (this.types.includes(type) && specificComponentName in this.$options.components) {
        return specificComponentName;
      }
      return genericComponentName;
    },
  },
};
</script>
<style scoped>
table ::v-deep td:last-child {
  padding-right: 4px;
}
</style>
