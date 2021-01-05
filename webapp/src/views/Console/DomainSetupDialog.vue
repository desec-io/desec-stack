<template>
  <v-dialog
    v-model="show"
    max-width="700px"
    persistent
    @keydown.esc="close"
  >
    <v-card>
      <v-card-title>
        <div class="title">
          Setup Instructions for <b>{{ domain }}</b>
        </div>
        <v-spacer/>
        <v-icon @click.stop="close">
          mdi-close
        </v-icon>
      </v-card-title>
      <v-divider/>

      <domain-setup v-bind="$attrs"></domain-setup>

      <v-divider/>
      <v-card-actions>
        <v-spacer/>
        <v-btn flat @click.stop="close">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import DomainSetup from "@/views/DomainSetup";

export default {
  name: 'DomainSetupPage',
  components: { DomainSetup },
  props: {
    'domain': {
      type: String,
      required: true,
    }
  },
  data: () => ({
    value: {
      type: Boolean,
      default: true,
    },
  }),
  computed: {
    show: {
      get() {
        return this.value
      },
      set(value) {
         this.$emit('input', value)
      }
    }
  },
  methods: {
    close() {
      this.show = false;
    }
  },
};
</script>
