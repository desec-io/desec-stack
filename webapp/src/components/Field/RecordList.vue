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
    ><v-icon>mdi-plus</v-icon> add another value</v-btn>
    <!--div><code style="white-space: normal">{{ value }}</code></div-->
  </div>
</template>

<script>
import Record from './Record.vue';
import RecordA from './Record/A.vue';
import RecordAAAA from './Record/AAAA.vue';
import RecordCNAME from './Record/CNAME.vue';
import RecordNS from './Record/NS.vue';
import RecordMX from './Record/MX.vue';
import RecordSRV from './Record/SRV.vue';
import RecordTXT from './Record/TXT.vue';

export default {
  name: 'RecordList',
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
      addHandler: ($event) => {
        self.$emit('dirty', $event);
        self.value.push('');  /* eslint-disable-line vue/no-mutating-props */
        self.$nextTick(() => self.$refs.inputFields[self.$refs.inputFields.length - 1].focus());
      },
      removeHandler: (index, $event) => {
        self.$emit('dirty', $event);
        self.value.splice(index, 1);  /* eslint-disable-line vue/no-mutating-props */
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
