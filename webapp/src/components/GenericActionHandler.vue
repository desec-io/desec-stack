<template>
  <div>
    <div class="text-center" v-if="working">
      <v-progress-circular align="center" indeterminate></v-progress-circular>
    </div>
    <v-alert type="success" v-if="success">
      <p>{{ this.response.data.detail }}</p>
    </v-alert>
  </div>
</template>

<script>
  export default {
    name: 'GenericActionHandler',
    data: () => ({
      auto_submit: false,
    }),
    async created() {
      this.auto_submit = this.auto_submit || this.$options.name == 'GenericActionHandler'
      if(this.auto_submit) {
        this.$emit('autosubmit')
      }
    },
    props: {
      payload: Object,
      response: Object,
      valid: Boolean,
      working: Boolean,
    },
    computed: {
      success: function () {
        return this.response.status >= 200 && this.response.status < 300
      }
    },
  };
</script>
