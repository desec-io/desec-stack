<!--
TODO
- table header: align left
- When selecting, then searching, selected items can disappear while still being selected. User actions then performed must not be confusing.
-->

<template>
  <v-card>
    <v-card-title>
      <div class="headline">Your domains</div>
      <v-spacer></v-spacer>
      <v-text-field
        v-model="search"
        append-icon="search"
        label="Search"
        single-line
        hide-details
      ></v-text-field>
      <v-btn color="primary" @click="createNewDomain()">Create new domain</v-btn>
    </v-card-title>

    <v-data-table
      v-model="selected"
      :custom-filter="customFilter"
      :headers="headers"
      :items="domains"
      :must-sort="true"
      :no-data-text="''"
      :pagination.sync="pagination"
      :search="search"
      item-key="name"
      :rows-per-page-items="[10,20,{'text':'All', 'value':-1}]"
      select-all
      class="elevation-1"
    >
      <template slot="headers" slot-scope="props">
        <tr>
          <th
            v-for="header in props.headers"
            :key="header.text"
            :class="['column sortable', pagination.descending ? 'desc' : 'asc', header.value === pagination.sortBy ? 'active' : '']"
            @click="changeSort(header.value)"
          >
            <v-icon small>arrow_upward</v-icon>
            {{ header.text }}
          </th>
          <th>
            <v-checkbox
              :input-value="props.all"
              :indeterminate="props.indeterminate"
              primary
              hide-details
              @click.native="toggleAll"
            ></v-checkbox>
          </th>
        </tr>
      </template>
      <template slot="items" slot-scope="props">
        <tr :active="props.selected" @click="props.selected = !props.selected">
          <td>{{ props.item.name }}</td>
          <td>{{ props.item.updated }}</td>
          <td>
            <v-checkbox
              :input-value="props.selected"
              primary
              hide-details
            ></v-checkbox>
          </td>
        </tr>
      </template>
      <template slot="no-data">
        <div class="py-5 text-xs-center">
          <h2 class="title">Feels so empty here!</h2>
          <p>Create a new domain to get started.</p>
          <v-btn color="primary" @click="createNewDomain()">Create new domain</v-btn>
        </div>
      </template>
    </v-data-table>
    <div>
      <h1>dev stuff</h1>
      <div><v-btn color="secondary" @click="domains = []"><v-icon left>mdi_delete</v-icon> Clear all domains</v-btn></div>
      <p>{{ selected }}</p>
      <v-alert :value="errors && errors.length" type="error">
        <li v-for="error of errors" :key="error">
          <b>{{ error.message }}</b>
          {{ error }}
        </li>
      </v-alert>
    </div>
  </v-card>
</template>

<script>
import {HTTP} from '../http-common'

export default {
  name: 'DomainList',
  data: () => ({
    pagination: {
      sortBy: 'name'
    },
    errors: [],
    selected: [],
    search: '',
    headers: [
      { text: 'Name', value: 'name', align: 'left' },
      { text: 'Updated', value: 'updated', align: 'left' }
    ],
    domains: [
    ]
  }),
  async mounted () {
    try {
      const response = await HTTP.get('domains')
      this.domains = response.data
    } catch (e) {
      this.errors.push(e)
    }
  },
  methods: {
    toggleAll () {
      if (this.selected.length) this.selected = []
      else this.selected = this.domains.slice()
    },
    changeSort (column) {
      if (this.pagination.sortBy === column) {
        this.pagination.descending = !this.pagination.descending
      } else {
        this.pagination.sortBy = column
        this.pagination.descending = false
      }
    },
    customFilter (items, search, filter) {
      search = search.toString().toLowerCase()
      return items.filter(row => filter(row['name'], search))
    },
    createNewDomain () {
      this.domains.push({
        name: Math.random().toString(36).substring(7) + '.invalid',
        updated: new Date().toISOString()
      })
    }
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
