<template>
  <!--v-textarea
    :label="label"
    :disabled="disabled || readonly"
    :error-messages="errorMessages"
    :value="value"
    :type="type || ''"
    :placeholder="required ? '' : '(optional)'"
    :hint="hint"
    persistent-hint
    :required="required"
    :rules="[v => !required || !!v || 'Required.']"
    @input="changed('input', $event)"
    @input.native="$emit('dirty', $event)"
    @keyup="changed('keyup', $event)"
  /-->
  <v-container>
    <h1 v-if="value.covered_names.length > 0">
      Protects TLS connections to <code>{{ value.covered_names[0] }}:{{ value.port }}/{{ value.protocol }}</code>
      <span v-if="value.covered_names.length > 1">and {{ value.covered_names.length - 1}} others</span>
    </h1>
    <h1 v-else>
      Defunct Identity for <code>{{ value.subject_names[0] }}:{{ value.port }}/{{ value.protocol }}</code>
      <span v-if="value.subject_names.length > 1">and {{ value.subject_names.length - 1}} others</span>
    </h1>
    <div>
      <v-alert type="warning">
        Warning: the following names are covered by the given certificate but are not available in your deSEC account:
        <ul>
          <li v-for="v in names_not_covered" :key="v"><code>{{v}}:{{ value.port }}/{{ value.protocol }}</code></li>
        </ul>
        Make these domains available in your deSEC account, then re-add this certificate to fix the problem.
      </v-alert>
      <p v-if="value.covered_names.length > 0">
        Protected domain names:
      </p>
      <ul>
        <li v-for="v in value.covered_names" :key="v"><code>{{v}}:{{ value.port }}/{{ value.protocol }}</code></li>
      </ul>
      <p/>
      <p v-if="value.covered_names.length > 0">
        TLSA-aware clients will verify that the contents of the TLSA record matches
        <b v-if="value.tlsa_matching_type == 0"></b>
        <b v-if="value.tlsa_matching_type == 1"> the SHA-256 hash of the</b>
        <b v-if="value.tlsa_matching_type == 2"> the SHA-512 hash of the</b>

        <b v-if="value.tlsa_selector == 0"> full certificate</b>
        <b v-if="value.tlsa_selector == 1"> public key of the certificate</b>

        <b v-if="value.tlsa_certificate_usage == 0"> of the issuing CA</b>
        <b v-if="value.tlsa_certificate_usage == 1"> presented by the server</b>
        <b v-if="value.tlsa_certificate_usage == 2"> of the issuing CA</b>
        <b v-if="value.tlsa_certificate_usage == 3"> presented by the server</b>

        <b v-if="value.tlsa_certificate_usage <= 1"> and that the certificate validates against the trust store</b>.
      </p>
      <!-- TODO use dialog to show certificate and fingerprint info -->
<!--      <p>-->
<!--        This identity was generated using an SSL certificate with fingerprint <code>{{ value.fingerprint }}</code>-->
<!--        at {{ value.created }}.-->
<!--      </p>-->
    </div>
  </v-container>
</template>

<script>
export default {
  name: 'TLSAIdentity',
  props: {
    disabled: {
      type: Boolean,
      required: false,
    },
    errorMessages: {
      type: [String, Array],
      default: () => [],
    },
    hint: {
      type: String,
      default: '',
    },
    label: {
      type: String,
      required: false,
    },
    readonly: {
      type: Boolean,
      required: false,
    },
    required: {
      type: Boolean,
      default: false,
    },
    value: {
      type: [String, Number],
      required: false,
    },
    type: {
      type: String,
      required: false,
    },
  },
  computed: {
    names_not_covered: function () {
      let that = this;
      return this.value.subject_names.filter(name => !that.value.covered_names.includes(name));
    }
  },
  methods: {
    changed(event, e) {
      this.$emit(event, e);
      this.$emit('dirty');
    },
  },
};
</script>

<style>
</style>