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
    </v-card-title>

    <v-data-table
      :custom-filter="customFilter"
      :headers="headers"
      :items="domains"
      :must-sort="true"
      :loading="loading"
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
          <!--th class="text-xs-right">
            <v-checkbox
              :input-value="props.all"
              :indeterminate="props.indeterminate"
              primary
              hide-details
              @click.native="toggleAll"
            ></v-checkbox>
          </th-->
        </tr>
      </template>
      <template slot="items" slot-scope="props">
        <tr>
          <td>{{ props.item.name }}</td>
          <td><span :title="props.item.published">{{ timeAgo.format(new Date(props.item.published)) }}</span></td>
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
        <div v-if="loading" class="py-5 text-xs-center">
          <p>fetching data ...</p>
        </div>
        <div v-else class="py-5 text-xs-center">
          <h2 class="title">Feels so empty here!</h2>
          <p>Create a new domain to get started.</p>
          <v-btn color="primary" depressed @click.stop="showNewDomainDialog = true">Create new domain</v-btn>
        </div>
      </template>
    </v-data-table>

    <new-domain-dialog
      v-model="showNewDomainDialog"
      :current="() => (domains.length)"
      :limit="5"
      :error="newDomainError"
      @createNewDomain="createNewDomain($event)"
    ></new-domain-dialog>
    <domain-details-dialog
      v-model="showDomainDetailsDialog"
      :name="domainDetailsDialogDomainName"
      :is-new="domainDetailsDialogDomainIsNew"
      :ds="domainDetailsDialogDS"
      @createAnotherDomain="showDomainDetailsDialog = false; showNewDomainDialog = true"
    ></domain-details-dialog>
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
import {HTTP, timeAgo} from '../../../utils'
import Confirmation from '../Confirmation'
import NewDomainDialog from './NewDomainDialog'
import DomainDetailsDialog from './DomainDetailsDialog'

export default {
  name: 'DomainList',
  components: {
    DomainDetailsDialog,
    NewDomainDialog,
    Confirmation
  },
  data: () => ({
    domainDeletionDomainName: '',
    domainDetailsDialogDomainName: '',
    domainDetailsDialogDS: [],
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
      { text: 'Published', value: 'published', align: 'left' },
      { }
    ],
    domains: [],
    loading: true
  }),
  async mounted () {
    try {
      const response = await HTTP.get('domains/')
      this.domains = response.data
      this.loading = false
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
      this.domainDetailsDialogDomainName = name
      this.domainDetailsDialogDomainIsNew = showAlert
      let dsList = this.domains.filter(domain => domain.name === name)[0].keys.map(key => key.ds)
      dsList = dsList.concat.apply([], dsList)
      this.domainDetailsDialogDS = dsList
      this.showDomainDetailsDialog = true
    }
  },
  computed: {
    timeAgo () {
      return timeAgo
    }
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
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
