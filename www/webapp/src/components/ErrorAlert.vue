<template>
  <v-alert :value="!!(errors && errors.length)" type="error" style="overflow: auto;">
    <div v-if="errors.length > 1">
      <li v-for="(error, idx) of errors" :key="idx" >
        {{ error }}
      </li>
    </div>
    <div v-else-if="errors.length == 1">
      {{ errors[0] }}
    </div>
  </v-alert>
</template>

<script>
export default {
  name: 'ErrorAlert',
  props: {
    errors: {type: Array},
  },
};
</script>
