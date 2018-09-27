<template>
  <tr>
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
      <ul>
        <li v-for="record in rrset.records" :key="record">{{ record }}</li>
      </ul>
    </td>
    <td>
      <v-form v-model="valid">
        {{ rrset.ttl }}
        {{ valid }}
        <v-text-field v-model="rrset.ttl" required></v-text-field>
      </v-form>
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
export default {
  name: 'RRset',
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
    valid: false,
    types: ['A', 'AAAA', 'MX']
  }),
  computed: {
    left () {
      return this.limit - this.current()
    }
  }
}
</script>

<style>
</style>
