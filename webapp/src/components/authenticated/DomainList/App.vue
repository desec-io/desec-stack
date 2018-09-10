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
      <v-btn color="primary" depressed @click.native="showNewDomainDialog = true">Create new domain</v-btn>
      <new-domain-dialog
        v-model="showNewDomainDialog"
        :current="() => (domains.length)"
        :limit="5"
        :error="newDomainError"
        @createNewDomain="createNewDomain($event)"
      ></new-domain-dialog>
      <v-dialog v-model="showDomainDetailsDialog" max-width="700px" @keydown.esc="showDomainDetailsDialog = false">
        <v-card>
          <v-card-title>
            <div class="title">Domain details for <b>{{ domainDetailsDialogDomainName }}</b></div>
            <v-spacer></v-spacer>
            <v-icon @click.stop="showDomainDetailsDialog = false">close</v-icon>
          </v-card-title>
          <v-divider></v-divider>
          <v-alert :value="domainDetailsDialogDomainIsNew" type="success">Your domain <b>{{ domainDetailsDialogDomainName }}</b> has been successfully created!</v-alert>
          <v-card-text>
            <p>Please forward the following information to your domain registrar:</p>
            <div class="caption font-weight-medium">NS records</div>
<pre class="mb-3 pa-3">
ns1.desec.io
ns2.desec.io
</pre>
            <v-layout flex align-end>
              <div class="caption font-weight-medium">DS records</div>
              <v-spacer></v-spacer>
              <div v-if="!domainDetailsDialogDScopied">
                <v-icon
                  small
                  @click="true"
                  v-clipboard:copy="domainDetailsDialogDS.join('\n')"
                  v-clipboard:success="() => (domainDetailsDialogDScopied = true)"
                  v-clipboard:error="() => (domainDetailsDialogDScopied = false)"
                >content_copy</v-icon>
              </div>
              <div v-else>copied! <v-icon small>check</v-icon></div>
            </v-layout>
<pre
  class="mb-3 pa-3"
  v-clipboard:copy="domainDetailsDialogDS.join('\n')"
  v-clipboard:success="() => (domainDetailsDialogDScopied = true)"
  v-clipboard:error="() => (domainDetailsDialogDScopied = false)"
>
{{ domainDetailsDialogDS.join('\n') }}
</pre>
            <p>Once your domain registrar processes this information, your deSEC DNS setup will be ready to use.</p>
          </v-card-text>
          <v-card-actions class="pa-3">
            <v-spacer></v-spacer>
            <v-btn color="primary" outline v-if="domainDetailsDialogDomainIsNew" @click.native="showDomainDetailsDialog = false; showNewDomainDialog = true">Create another domain</v-btn>
            <v-btn color="primary" dark depressed @click.native="showDomainDetailsDialog = false">{{ domainDetailsDialogDomainIsNew ? 'Close and edit' : 'Close' }}</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-card-title>

    <v-data-table
      :custom-filter="customFilter"
      :headers="headers"
      :items="domains"
      :must-sort="true"
      :no-data-text="''"
      :pagination.sync="pagination"
      :search="search"
      item-key="name"
      :rows-per-page-items="[10,20,{'text':'All', 'value':-1}]"
      class="elevation-1"
    >
      <template slot="headers" slot-scope="props">
        <tr>
          <th
            v-for="header in props.headers"
            :key="header.text"
            :class="['column sortable', pagination.descending ? 'desc' : 'asc', header.value === pagination.sortBy ? 'active' : '', header.align ? 'text-xs-' + header.align : '']"
            @click="changeSort(header.value)"
          >
            <v-icon small>arrow_upward</v-icon>
            {{ header.text }}
          </th>
          <th class="text-xs-right">
            <!--v-checkbox
              :input-value="props.all"
              :indeterminate="props.indeterminate"
              primary
              hide-details
              @click.native="toggleAll"
            ></v-checkbox-->
          </th>
        </tr>
      </template>
      <template slot="items" slot-scope="props">
        <tr>
          <td>{{ props.item.name }}</td>
          <td>{{ props.item.updated }}</td>
          <td>
            <v-layout align-center justify-end>
              <v-btn @click.stop="openDomainDetailsDialog(props.item.name)" color="grey" flat icon><v-icon>info</v-icon></v-btn>
              <v-btn @click.stop="openDomainDeletionDialog(props.item.name)" class="_delete" flat icon><v-icon>delete</v-icon></v-btn>
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
      <template slot="no-data">
        <div class="py-5 text-xs-center">
          <h2 class="title">Feels so empty here!</h2>
          <p>Create a new domain to get started.</p>
          <v-btn color="primary" depressed @click.stop="showNewDomainDialog = true">Create new domain</v-btn>
        </div>
      </template>
    </v-data-table>
    <confirmation
      v-model="showDomainDeletionDialog"
      info="This operation will cause the domain to disappear from the DNS. It will no longer be reachable from the Internet."
      title="Domain Deletion"
      :callback="deleteDomain"
      :args="[domainDeletionDomainName]"
    >
      <p>Do you really want to delete the domain <b>{{ domainDeletionDomainName }}</b>?</p>
    </confirmation>
  </v-card>
</template>

<script>
import {HTTP} from '../../../http-common'
import Confirmation from '../Confirmation.vue'
import NewDomainDialog from './NewDomainDialog.vue'

export default {
  name: 'DomainList',
  components: {
    NewDomainDialog,
    Confirmation
  },
  data: () => ({
    domainDeletionDomainName: '',
    domainDetailsDialogDomainName: '',
    domainDetailsDialogDS: [],
    domainDetailsDialogDScopied: false,
    domainDetailsDialogDomainIsNew: false,
    newDomainError: '',
    showDomainDeletionDialog: false,
    showDomainDetailsDialog: false,
    showNewDomainDialog: false,
    pagination: {
      sortBy: 'name'
    },
    errors: [],
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
    async createNewDomain (name) {
      this.newDomainError = ''
      try {
        const response = await HTTP.post('domains/', {
          'name': name
        })
        this.domains.push(response.data)
        this.showNewDomainDialog = false
        this.openDomainDetailsDialog(name, true)
      } catch (e) {
        console.log(e)
        /* TODO
        - make the message more human-readable
         */
        this.newDomainError = JSON.stringify(e.response.data)
      }
    },
    async deleteDomain (name) {
      await HTTP.delete('domains/' + name + '/')
      this.domains = this.domains.filter(domain => domain.name !== name)
      this.domainDeletionDomainName = ''
    },
    openDomainDeletionDialog (name) {
      this.domainDeletionDomainName = name
      this.showDomainDeletionDialog = true
    },
    openDomainDetailsDialog (name, showAlert = false) {
      this.domainDetailsDialogDScopied = false
      this.domainDetailsDialogDomainName = name
      this.domainDetailsDialogDomainIsNew = showAlert
      let dsList = this.domains.filter(domain => domain.name === name)[0].keys.map(key => key.ds)
      dsList = dsList.concat.apply([], dsList)
      this.domainDetailsDialogDS = dsList
      this.showDomainDetailsDialog = true
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
  .v-input--checkbox {
    display: inline-flex;
    width: auto;
  }
  button._delete {
    color: #9E9E9E; /* grey */
  }
  button._delete:hover {
    color: #C62828; /* red darken-3 */
  }
</style>
