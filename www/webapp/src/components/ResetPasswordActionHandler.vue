<template>
  <div>
    <div class="text-center" v-if="!success">
        <v-text-field
                v-model="payload.new_password"
                :append-icon="show ? mdiEyeOff : mdiEye"
                label="New password"
                required
                :disabled="working"
                :rules="[rules.required, rules.min]"
                :type="show ? 'text' : 'password'"
                hint="At least 8 characters"
                autocomplete="new-password"
                @click:append="show = !show"
                tabindex="1"
        ></v-text-field>
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
  import {mdiEye, mdiEyeOff} from "@mdi/js";

  export default {
    name: 'ResetPasswordActionHandler',
    extends: GenericActionHandler,
    data: () => ({
      mdiEyeOff: mdiEyeOff,
      mdiEye: mdiEye,
      rules: {
        required: value => !!value || 'Required.',
        min: v => (v !== undefined && v.length >= 8) || 'Min 8 characters',
      },
      show: false,
    }),
  };
</script>
