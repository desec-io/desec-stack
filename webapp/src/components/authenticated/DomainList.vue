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
      <v-dialog v-model="dialog" max-width="500px" @keydown.esc="dialog = false">
        <v-btn slot="activator" color="primary" dark>Create new domain</v-btn>
        <v-card>
          <v-form @submit.prevent="createNewDomain">
            <v-card-title>
              <span class="title">Create a New Domain</span>
              <v-spacer></v-spacer>
              <v-icon @click="dialog = false">close</v-icon>
            </v-card-title>
            <v-divider></v-divider>
            <v-card-text>
              <p>You have {{ 5 - domains.length }} of 5 domains left in your plan. <a>Upgrade now!</a></p>
              <v-text-field v-model="dialogDomainName" label="Enter domain name" hint="example.com" required></v-text-field>
            </v-card-text>
            <v-card-actions>
              <v-spacer></v-spacer>
              <v-btn color="primary" outline @click.native="dialog = false">Cancel</v-btn>
              <v-btn color="primary" depressed type="submit">Create</v-btn>
              <v-spacer></v-spacer>
            </v-card-actions>
          </v-form>
        </v-card>
      </v-dialog>
      <v-dialog v-model="domainDetailsDialog" max-width="700px" @keydown.esc="domainDetailsDialog = false">
        <v-btn slot="activator" color="primary" dark>DS</v-btn>
        <v-card>
          <v-card-title>
            <div class="title">Domain details</div>
            <v-spacer></v-spacer>
            <v-icon @click="domainDetailsDialog = false">close</v-icon>
          </v-card-title>
          <v-alert :value="true" type="success">Your domain <b>{{ 'example.com' }}</b> has been successfully created!</v-alert>
          <v-divider></v-divider>
          <v-card-text>
            <p>Please forward the following information to your domain registrar:</p>
            <!--
            TODO
            - on click, copy text to clipboard
            -->
            <div class="caption font-weight-medium">NS records</div>
<pre class="mb-3 pa-3">
ns1.desec.io
ns2.desec.io
</pre>
            <div class="caption font-weight-medium">DS records</div>
<pre class="mb-3 pa-3">
6454 8 2 5CBA665A006F6487625C6218522F09BD3673C25FA10F25CB18459AA10DF1F520
6454 8 1 24396E17E36D031F71C354B06A979A67A01F503E
</pre>
            <p>Once your domain registrar processes this information, your deSEC DNS setup will be ready to use.</p>
          </v-card-text>
          <v-card-actions class="pa-3">
            <v-spacer></v-spacer>
            <v-btn xs12 color="primary" outline @click.native="domainDetailsDialog = false; dialog = true">Create another domain</v-btn>
            <v-btn xs12 color="primary" dark depressed @click.native="domainDetailsDialog = false">Close and edit</v-btn>
          </v-card-actions>
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
      <div><v-btn color="secondary" @click="domains = []"><v-icon>delete</v-icon> Clear all domains</v-btn></div>
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
import {HTTP} from '../../http-common'

export default {
  name: 'DomainList',
  data: () => ({
    dialog: false,
    dialogDomainName: '',
    domainDetailsDialog: false,
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
  .caption {
    text-transform: uppercase;
  }
  pre {
    background: lightgray;
    overflow: auto;
  }
  button {
    min-width: 230px;
  }
</style>
