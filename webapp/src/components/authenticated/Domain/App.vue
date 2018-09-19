<template>
  <v-card>
    <v-card-title>
      <div class="headline">{{ $route.params.name }}</div>
    </v-card-title>

    <v-toolbar>
      <v-btn color="primary" depressed>Add record</v-btn>
      <v-text-field
        v-model="search"
        append-icon="search"
        label="Search subname or value"
        single-line
        hide-details
      ></v-text-field>
      <v-spacer></v-spacer>
      <v-toolbar-items>
        <v-btn flat>Import</v-btn>
        <v-btn flat>Export all</v-btn>
      </v-toolbar-items>
    </v-toolbar>

    <v-data-table
      :custom-filter="customFilter"
      :headers="headers"
      :items="rrsets"
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
          <td>{{ props.item.type }}</td>
          <td>{{ props.item.subname }}</td>
          <td>{{ props.item.records }}</td>
          <td>{{ props.item.ttl }}</td>
          <td>
            <v-layout align-center justify-end>
              <v-btn color="grey" flat icon><v-icon>edit</v-icon></v-btn>
              <v-btn @click.stop="openRRsetDeletionDialog(props.item)" class="_delete" flat icon><v-icon>delete</v-icon></v-btn>
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
          <v-btn color="primary" depressed>Add record</v-btn>
        </div>
      </template>
    </v-data-table>
    <div>
      <h2>dev</h2>
      <v-btn color="primary" depressed @click.native="router.replace({name: 'DomainList'})">back</v-btn>
    </div>

    <domain-details-dialog
      v-model="showDomainDetailsDialog"
      :name="domainDetailsDialogDomainName"
      :ds="domainDetailsDialogDS"
    ></domain-details-dialog>
    <confirmation
      v-model="showRRsetDeletionDialog"
      title="Record Deletion"
      :callback="deleteRRset"
      :args="[rrsetDeletionSubname, rrsetDeletionType]"
    >
      <p>Do you really want to delete the <b>{{ rrsetDeletionType }}</b> record on <b>{{ rrsetDeletionName }}</b>?</p>
    </confirmation>
  </v-card>
</template>

<script>
import {HTTP} from '../../../utils'
import router from '../../../router'
import Confirmation from '../Confirmation'
import DomainDetailsDialog from '../DomainList/DomainDetailsDialog'

export default {
  name: 'Domain',
  components: {
    DomainDetailsDialog,
    Confirmation
  },
  data: () => ({
    rrsetDeletionName: '',
    rrsetDeletionSubname: '',
    rrsetDeletionType: '',
    domainDetailsDialogDomainName: '',
    domainDetailsDialogDS: [],
    domainDetailsDialogDomainIsNew: false,
    showRRsetDeletionDialog: false,
    showDomainDetailsDialog: false,
    pagination: {
      sortBy: 'name'
    },
    errors: [],
    search: '',
    headers: [
      { text: 'Type', value: 'type', align: 'left' },
      { text: 'Subname', value: 'subname', align: 'left' },
      { text: 'Value', value: 'records', align: 'left' },
      { text: 'TTL', value: 'ttl', align: 'left' },
      { }
    ],
    rrsets: [],
    loading: true
  }),
  async mounted () {
    try {
      const response = await HTTP.get('domains/' + this.$route.params.name + '/rrsets/')
      let rrsets = response.data.filter(rrset => !(rrset.subname === '' && rrset.type === 'NS'))
      this.rrsets = rrsets
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
      return items.filter(row => filter(row['subname'], search) || filter(row['records'], search))
    },
    async deleteRRset (subname, type) {
      console.log('delete ' + 'domains/' + this.$route.params.name + '/rrsets/...' + subname + '/' + type + '/')
      await HTTP.delete('domains/' + this.$route.params.name + '/rrsets/...' + subname + '/' + type + '/')
      this.rrsets = this.rrsets.filter(rrset => !(rrset.subname === subname && rrset.type === type))
      this.rrsetDeletionName = ''
      this.rrsetDeletionSubname = ''
      this.rrsetDeletionType = ''
    },
    openRRsetDeletionDialog (rrset) {
      this.rrsetDeletionName = rrset.name.slice(0, -1)
      this.rrsetDeletionSubname = rrset.subname
      this.rrsetDeletionType = rrset.type
      this.showRRsetDeletionDialog = true
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
    router () {
      return router
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
