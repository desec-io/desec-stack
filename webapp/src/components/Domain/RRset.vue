<template>
  <tr class="rrset">
    <td>
      <v-combobox
        v-model="rrset.type"
        :items="types"
      ></v-combobox>
    </td>
    <td>
      <v-text-field v-model="rrset.subname" placeholder="(empty)"></v-text-field>
    </td>
    <td>
      <pre>{{ rrset.records }}</pre>
      <component
        :is="getRecordComponentName(rrset.type)"
        v-for="(record, index) in rrset.records"
        :key="index"
        :content="record"
        :clearable="rrset.records.length > 1"
        @update:content="$set(rrset.records, index, $event)"
      ></component>
    </td>
    <td>
        <v-text-field
          v-model="rrset.ttl"
          type="number"
          :hide-details="!$v.rrset.ttl.$invalid"
          :error="$v.rrset.ttl.$invalid"
          :error-messages="errors"
        ></v-text-field>
    </td>
    <td>
      <v-layout align-center justify-end>
        {{ rrset.records.length }}/{{ current() }}
        <v-btn color="grey" flat icon><v-icon>edit</v-icon></v-btn>
        <v-btn @click.stop="openRRsetDeletionDialog(rrset)" class="_delete" flat icon><v-icon>delete</v-icon></v-btn>
        <!--v-checkbox
          :input-value="props.selected"
          primary
          hide-details
          class="shrink"
        ></v-checkbox-->
      </v-layout>
    </td>
  </tr>
</template>

<script>
import Record from './Record'
import RecordA from './RecordA'
import RecordCNAME from './RecordCNAME'
import RecordMX from './RecordMX'
import RecordSRV from './RecordSRV'

import { required, integer, minValue } from 'vuelidate/lib/validators'

const MinTTL = 10

export default {
  name: 'RRset',
  components: {
    Record,
    RecordA,
    RecordCNAME: RecordCNAME,
    RecordMX: RecordMX,
    RecordSRV: RecordSRV
  },
  props: {
    current: {
      type: Function,
      required: true
    },
    limit: {
      type: Number,
      required: true
    },
    rrset: {
      type: Object,
      required: true
    }
  },
  data: () => ({
    errorDict: {
      required: 'This field is required.',
      integer: 'TTL must be an integer.',
      minValue: 'The minimum value is ' + MinTTL + '.'
    },
    types: ['A', 'AAAA', 'MX', 'CNAME', 'TXT', 'SPF', 'CAA', 'TLSA', 'OPENPGPKEY', 'PTR', 'SRV', 'DS', 'DNSKEY']
  }),
  methods: {
    getRecordComponentName (type) {
      let genericComponentName = 'Record'
      let specificComponentName = genericComponentName + type
      if (this.types.includes(type) && specificComponentName in this.$options.components) {
        return specificComponentName
      }
      return genericComponentName
    }
  },
  validations: {
    rrset: {
      ttl: {
        required,
        integer,
        minValue: minValue(MinTTL)
      }
    }
  },
  computed: {
    errors () {
      return Object.entries(this.errorDict).filter(entry => !this.$v.rrset.ttl[entry[0]]).map(entry => entry[1])
    },
    left () {
      return this.limit - this.current()
    }
  }
}
</script>

<style>
/* TODO should be scoped, but scoped CSS doesn't work for some reason */
.rrset td {
  vertical-align: top;
}
</style>
