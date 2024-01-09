<template>
  <div>
    <div class="text-center" v-if="!success">
        <generic-password
            v-model="payload.new_password"
            :autofocus="true"
            :new="true"
            :standalone="true"
            tabindex="1"
        />
        <v-btn
                depressed
                color="primary"
                type="submit"
                :disabled="working || !valid"
                :loading="working"
                tabindex="2"
        >Submit</v-btn>
    </div>
    <v-alert type="success" v-else>
      <p>{{ this.response.data.detail }}</p>
    </v-alert>
  </div>
</template>

<script>
  import GenericActionHandler from "./GenericActionHandler.vue"
  import GenericPassword from "@/components/Field/GenericPassword.vue";

  export default {
    name: 'ResetPasswordActionHandler',
    components: {GenericPassword},
    extends: GenericActionHandler,
  };
</script>
