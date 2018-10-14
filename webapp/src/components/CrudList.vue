<template>
  <v-card>

    <!-- Error Snackbar -->
    <v-snackbar
      v-model="snackbar"
      color="error"
      multi-line
      :timeout=5000
      vertical
    >
      {{ errors[errors.length - 1] }}
      <v-btn
        dark
        flat
        @click="snackbar = false"
      >
        Close
      </v-btn>
    </v-snackbar>

    <!-- Headline & Toolbar, Including New Form -->
    <v-toolbar flat color="white">
      <v-toolbar-title>{{ headlines.table }}</v-toolbar-title>
      <v-spacer></v-spacer>
      <v-text-field
        v-model="search"
        append-icon="search"
        label="Search"
        single-line
        hide-details
      ></v-text-field>
      <v-dialog v-if="createable" v-model="createDialog" max-width="500px" persistent @keydown.esc="close">
        <v-btn slot="activator" color="primary" dark class="mb-2" :disabled="working">{{ headlines.create }}</v-btn>
        <v-card>
          <v-form v-on:submit.prevent="save()">
            <v-card-title>
              <span class="headline">{{ headlines.create }}</span>
              <v-spacer></v-spacer>
              <v-icon @click.stop="close">close</v-icon>
            </v-card-title>
            <v-divider></v-divider>
            <v-progress-linear v-if="createDialogWorking" height="2" :indeterminate="true"></v-progress-linear>

            <v-alert :value="createDialogError" type="error">{{ errors[errors.length - 1] }}</v-alert>

            <v-card-text v-if="createDialog"> <!-- v-if required here to make autofocus below working for the 2nd+ times, cf stackoverflow.com/a/51476992 -->
              <p>{{ texts.create() }}</p>

              <!-- New Form -->
              <v-text-field
                v-for="(c, id) in columns"
                :key="id"
                v-if="!c.readonly"
                v-model="createDialogItem[c.value]"
                :label="c.textCreate || c.text"
                :error-messages="c.createErrors"
                autofocus
              ></v-text-field>
            </v-card-text>

            <v-card-actions>
              <v-spacer></v-spacer>
              <v-btn color="primary" class="grow" outline @click.native="close" :disabled="createDialogWorking">Cancel</v-btn>
              <v-btn type="submit" color="primary" class="grow" depressed :loading="createDialogWorking">Save</v-btn>
            </v-card-actions>
          </v-form>
        </v-card>
      </v-dialog>
    </v-toolbar>

    <!-- The Actual Table -->
    <v-data-table
      :headers="headers"
      :items="rows"
      :search="search"
      :custom-filter="filterRows"
      :loading="working || createDialogWorking || destroyDialogWorking"
      hide-actions
      class="elevation-1"
    >
      <!-- row template -->
      <template slot="items" slot-scope="props">
        <td v-for="(c, id) in columns" :key="id">
          <span v-if="c.datatype=='timeago'" :title="props.item[c.value]">{{ timeAgo.format(new Date(props.item[c.value])) }}</span>
          <span v-else-if="c.datatype=='code'"><code>{{ props.item[c.value] }}</code></span>
          <span v-else>{{ props.item[c.value] }}</span>
        </td>
        <td>
          <v-layout align-center justify-end>
            <v-btn
              v-for="action in actions"
              v-bind:key="action.key"
              color="grey" flat icon
              @click.stop="action.go(props.item)"
              >
              <v-icon>{{action.icon}}</v-icon>
            </v-btn>
            <v-btn
              v-if="destroyable"
              color="grey" class="hover-red" flat icon
              @click.stop="destroyAsk(props.item)"
            >
              <v-icon>delete</v-icon>
            </v-btn>
          </v-layout>
        </td>
      </template>
      <template slot="no-data">
        <div v-if="working" class="py-5 text-xs-center">
          <p>fetching data ...</p>
        </div>
        <div v-else class="py-5 text-xs-center">
          <h2 class="title">Feels so empty here!</h2>
          <p>No data yet.</p>
        </div>
      </template>
    </v-data-table>

    <!-- Delete Dialog -->
    <v-dialog v-model="destroyDialog" max-width="500px" persistent>
      <v-card>
        <v-form v-on:submit.prevent="destroy(destroyDialogItem)">
          <v-card-title>
            <span class="headline">{{ headlines.destroy }}</span>
          </v-card-title>

          <v-divider></v-divider>
          <v-progress-linear v-if="destroyDialogWorking" height="2" :indeterminate="true"></v-progress-linear>

          <v-alert :value="texts.destroyWarning(destroyDialogItem)" type="info">{{ texts.destroyWarning(destroyDialogItem) }}</v-alert>
          <v-alert :value="destroyDialogError" type="error">{{ errors[errors.length - 1] }}</v-alert>

          <v-card-text>
            {{ texts.destroy(destroyDialogItem) }}
          </v-card-text>

          <v-card-actions>
            <v-spacer></v-spacer>
            <v-btn color="primary" class="grow" outline @click.native="destroyClose" :disabled="destroyDialogWorking">Cancel</v-btn>
            <v-btn color="primary" class="grow" dark depressed type="submit" :loading="destroyDialogWorking">Delete</v-btn>
          </v-card-actions>
        </v-form>
      </v-card>
    </v-dialog>

  </v-card>
</template>

<script>
import {HTTP, timeAgo} from '@/utils'

// safely access deeply nested objects
const safeget = (path, object) =>
  path.reduce((xs, x) =>
    (xs && xs[x]) ? xs[x] : null, object)

export default {
  name: 'Domain',
  components: {
  },
  data: () => ({
    createDialog: false,
    createDialogWorking: false,
    createDialogIndex: -1,
    createDialogItem: {},
    createDialogError: false,
    destroyDialog: false,
    destroyDialogWorking: false,
    destroyDialogItem: {},
    destroyDialogIndex: -1,
    destroyDialogError: false,
    working: false,
    errors: [],
    snackbar: false,
    search: '',
    rows: [],
    /* to be overwritten */
    // features
    createable: true,
    updatable: false,
    destroyable: true,
    // optics
    headlines: {
      table: 'Crud List',
      create: 'New Object',
      destroy: 'Delete Object'
    },
    texts: {
      create: () => ('Create a new object.'),
      destroy: () => ('Delete an object permanently. This operation can likely not be undone.')
    },
    columns: {},
    actions: [],
    // resource
    paths: {
      list: 'needs/to/be/overwritten/',
      create: 'needs/to/be/overwritten/',
      delete: 'needs/to/be/overwritten/'
    },
    // object
    defaultObject: {},
    // callbacks
    preload: () => (undefined),
    postload: () => (undefined),
    precreate: () => (undefined),
    postcreate: () => (undefined),
    preupdate: () => (undefined),
    postupdate: () => (undefined),
    predelete: () => (undefined),
    postdelete: () => (undefined)
  }),
  async mounted () {
    this.createDialogItem = Object.assign({}, this.createDialogItem)
    try {
      this.working = true
      this.preload()
      this.rows = (await HTTP.get(this.paths.list)).data
      this.postload()
    } catch (e) {
      this.error(e)
      this.postload(e)
    }
    this.working = false
  },
  methods: {
    /***
     * Ask the user to delete the given item.
     * @param item
     */
    async destroyAsk (item) {
      this.destroyDialogIndex = this.rows.indexOf(item)
      this.destroyDialogItem = item
      this.destroyDialog = true
    },
    /***
     * Delete an item from table and server.
     * Errors are handeled by calling the error function.
     * On success, the destroy dialog will be closed (if opened)
     * @param item
     */
    async destroy (item) {
      this.destroyDialogWorking = true
      this.destroyDialogError = null
      try {
        const url = this.resourcePath(this.paths.delete, item)
        this.predelete()
        await HTTP.delete(url)
        this.rows.splice(this.rows.indexOf(item), 1)
        this.postdelete()
        this.destroyClose()
      } catch (e) {
        this.error(e)
        this.postdelete(e)
      }
      this.destroyDialogWorking = false
    },
    /***
     * Closes the destroy dialog and cleans up.
     */
    async destroyClose () {
      this.destroyDialogIndex = -1
      this.destroyDialogItem = {}
      this.destroyDialog = false
      this.destroyDialogError = null
    },
    /***
     * Save an edited or new item in table and server.
     * The item is given by this.dialogIndex and this.dialogItem.
     * Errors are handeled by calling the error function.
     */
    async save () {
      this.createDialogWorking = true
      this.createDialogError = false
      for (let c in this.columns) {
        this.columns[c].createErrors = []
      }
      if (this.createDialogIndex > -1) {
        // TODO implement edit object
      } else {
        // new item
        try {
          this.precreate()
          const url = this.resourcePath(this.paths.create, this.createDialogItem)
          this.rows.push((await HTTP.post(url, this.createDialogItem)).data)
          this.postcreate(this.rows[this.rows.length - 1])
          this.close()
        } catch (e) {
          this.error(e)
          this.postcreate(e)
        }
      }
      this.createDialogWorking = false
    },
    /***
     * Close the dialog and clean up state.
     */
    close () {
      this.createDialog = false
      this.createDialogItem = Object.assign({}, this.defaultItem)
      this.createDialogIndex = -1
      this.createDialogError = false
      for (let c in this.columns) {
        this.columns[c].createErrors = []
      }
    },
    /***
     * Handle the error e by displaying it to the user.
     * @param e
     */
    error (e) {
      if (safeget(['response', 'data', 'detail'], e)) {
        e = e.response.data.detail
      } else if (safeget(['response', 'data'], e)) {
        e = safeget(['response', 'data'], e)
      }
      if (!safeget(['response'], e) && safeget(['request'], e)) {
        e = 'Cannot reach server at ' + (HTTP.baseURL ? HTTP.baseURL : window.location.hostname) + '. Are you offline?'
      }
      this.errors.push(e)
      if (this.destroyDialog) {
        this.destroyDialogError = e
      } else if (this.createDialog) {
        // see if e contains field-specific errors
        if (Object.keys(e).every((key) => this.columns.hasOwnProperty(key))) {
          // assume we obtained field-specific error(s),
          // so let's assign them to the input fields
          for (let c in e) {
            this.columns[c].createErrors = e[c]
          }
        } else {
          this.createDialogError = true
        }
      } else {
        this.snackbar = true
      }
    },
    /***
     * Converts a URL template with parameters into a URL.
     * All colon-prefixed placeholders (e.g., ":name") in p
     * are replaced with a value if obj contains a property
     * with the corresponding name.
     *
     * @param p URL template, like /api/users/:id/posts/
     * @param obj An object to take values from, like { id: 23, text: 'foo' }
     * @returns URL, like /api/users/23/posts/
     */
    resourcePath (p, obj) {
      for (const property in obj) {
        if (obj.hasOwnProperty(property)) {
          p = p.replace(':' + property, obj[property])
        }
      }
      return p
    },
    filterRows1 (items, search, filter) {
      search = search.toString().toLowerCase()
      return items.filter(row => filter(row['name'], search))
    },
    filterRows (items, search, filter) {
      search = search.toString().toLowerCase()
      return items.filter((row) => (
        Object.keys(this.columns).some(c => (this.columns[c].searchable && filter(row[c], search)))
      ))
    }
  },
  computed: {
    timeAgo () {
      return timeAgo
    },
    headers () {
      let h = Object.assign({}, this.columns) // copy cols (a shallow copy is sufficient here)
      h.actions = {
        text: 'Actions',
        sortable: false,
        align: 'right'
      }
      return Object.values(h) // data table expects an array
    }
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
