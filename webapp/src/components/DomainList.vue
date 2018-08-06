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
      <v-dialog v-model="dialog" persistent max-width="500px">
        <v-btn slot="activator" color="primary" dark>Create new domain</v-btn>
        <v-card>
          <v-form @submit="createNewDomain()">
            <v-card-title>
              <span class="headline">Create a New Domain</span>
            </v-card-title>
            <v-card-text>
              <v-container grid-list-md>
                <v-layout wrap>
                  <v-flex xs12>
                    <p>You have {{ 5 - domains.length }} of 5 domains left in your plan. <a>Upgrade now!</a></p>
                  </v-flex>
                  <v-flex xs12>
                    <v-text-field v-model="dialogDomainName" label="Enter domain name" hint="example.com" required></v-text-field>
                  </v-flex>
                </v-layout>
              </v-container>
            </v-card-text>
            <v-card-actions>
              <v-spacer></v-spacer>
              <v-btn color="blue darken-1" flat @click.native="dialog = false">Cancel</v-btn>
              <v-btn color="blue darken-1" dark type="submit">Create</v-btn>
              <v-spacer></v-spacer>
            </v-card-actions>
          </v-form>
        </v-card>
      </v-dialog>
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
          <v-btn color="primary" dark @click.stop="dialog = true">Create new domain</v-btn>
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
    dialog: false,
    dialogDomainName: '',
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
      const response = await HTTP.get('domains/')
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
    async createNewDomain () {
      try {
        console.log(this.dialogDomainName)
        const response = await HTTP.post('domains/', {
          'name': this.dialogDomainName
        })
        this.domains.push(response.data)
        this.dialog = false
        this.dialogDomainName = ''
      } catch (e) {
        console.log(e)
        this.errors.push(e)
      }
    }
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
