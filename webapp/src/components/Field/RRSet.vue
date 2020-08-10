<template>
  <div>
    <component
            :is="getRecordComponentName(type)"
            v-for="(item, index) in valueMap"
            :key="item.id"
            :content="item.content"
            :error-messages="errorMessages[index] ? errorMessages[index].content : []"
            :hide-label="index > 0"
            :append-icon="value.length > 1 ? 'mdi-close' : ''"
            ref="inputFields"
            @update:content="$set(value, index, $event)"
            @remove="(e) => removeHandler(index, e)"
            @keyup="(e) => $emit('keyup', e)"
    />
    <v-btn
            @click="addHandler"
            class="px-0 text-none"
            color="grey"
            small
            text
    ><v-icon>mdi-plus</v-icon> add another value</v-btn>
    <!--div><code style="white-space: normal">{{ value }}</code></div-->
  </div>
</template>

<script>
import Record from './Record.vue';
import RecordA from './RecordA.vue';
import RecordAAAA from './RecordAAAA.vue';
import RecordCNAME from './RecordCNAME.vue';
import RecordNS from './RecordNS.vue';
import RecordMX from './RecordMX.vue';
import RecordSRV from './RecordSRV.vue';
import RecordTXT from './RecordTXT.vue';

export default {
  name: 'RRSet',
  components: {
    Record,
    RecordA,
    RecordAAAA,
    RecordCNAME,
    RecordMX,
    RecordNS,
    RecordSRV,
    RecordTXT,
  },
  props: {
    errorMessages: {
      type: Array,
      default: () => [],
    },
    value: {
      type: Array,
      required: true,
    },
    type: {
      type: String,
      required: true,
    },
  },
  data: function () {
    const self = this;
    return {
      removals: 0,
      types: ['A', 'AAAA', 'MX', 'NS', 'CNAME', 'TXT', 'SPF', 'CAA', 'TLSA', 'OPENPGPKEY', 'PTR', 'SRV', 'DS'],
      addHandler: () => {
        self.value.push('');
        self.$nextTick(() => self.$refs.inputFields[self.$refs.inputFields.length - 1].focus());
      },
      removeHandler: (index) => {
        self.value.splice(index, 1);
        self.removals++;
      },
    }
  },
  computed: {
    // This is necessary to allow rerendering the list after record deletion. Otherwise, VueJS confuses record indexes.
    valueMap: function () {
      return this.value.map((v, k) => ({content: v, id: `${k}_${this.removals}`}));
    },
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
