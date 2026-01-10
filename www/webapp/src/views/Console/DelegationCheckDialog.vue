<template>
  <v-dialog
    v-model="show"
    max-width="700px"
    persistent
    scrollable
    @keydown.esc="close"
  >
    <v-card>
      <v-card-title>
        <div class="text-h6">
          Delegation Check for <b>{{ domain.name }}</b>
        </div>
        <v-spacer />
        <v-icon :icon="mdiClose" @click.stop="close" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pt-4">
        <delegation-status :item="domain" class="mb-4" />
        <div class="text-subtitle-2 mb-2">What to do next</div>
        <ul class="delegation-instructions">
          <li v-for="(item, idx) in instructions" :key="idx">
            {{ item }}
          </li>
        </ul>
      </v-card-text>

      <v-card-actions class="pb-4">
        <v-spacer />
        <v-btn color="primary" variant="text" @click="close">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mdiClose } from '@mdi/js';
import DelegationStatus from '@/components/Field/DelegationStatus.vue';

export default {
  name: 'DelegationCheckDialog',
  components: { DelegationStatus },
  props: {
    domain: {
      type: Object,
      required: true,
    },
    modelValue: {
      type: Boolean,
      default: true,
    },
  },
  data: () => ({
    mdiClose,
  }),
  computed: {
    show: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit('update:modelValue', value);
        this.$emit('input', value);
      },
    },
    instructions() {
      const domain = this.domain || {};
      if (!domain.delegation_checked) {
        return [
          'Please wait a moment and run the check again.',
        ];
      }
      if (domain.is_registered === false) {
        return [
          'Your registrar has not published this domain yet. This can take a few hours.',
          'If you recently registered the domain, wait and retry later.',
        ];
      }
      if (domain.is_delegated == null) {
        return [
          'Set your domain nameservers at your registrar to deSEC.',
          'Use the “Setup instructions” action in the domain list to find the correct nameservers.',
          'After updating, wait a bit and run this check again.',
        ];
      }
      if (domain.is_delegated === false) {
        return [
          'Remove any non-deSEC nameservers at your registrar.',
          'Keep only the deSEC nameservers listed in the setup instructions.',
          'After changes propagate, run this check again.',
        ];
      }
      if (domain.is_secured === true) {
        return [
          'Everything looks good. No further action is required.',
        ];
      }
      if (domain.is_secured === false) {
        return [
          'Update the DS records at your registrar to match deSEC.',
          'Use the “Setup instructions” action to copy the DS records.',
          'After updating, wait a bit and run this check again.',
        ];
      }
      return [
        'Add DS records at your registrar to enable DNSSEC for this domain.',
        'Use the “Setup instructions” action to copy the DS records.',
        'After updating, wait a bit and run this check again.',
      ];
    },
  },
  methods: {
    close() {
      this.show = false;
    },
  },
};
</script>

<style scoped>
.delegation-instructions {
  margin: 0;
  padding-left: 1.25rem;
}
.delegation-instructions li {
  margin-bottom: 0.4rem;
}
</style>
