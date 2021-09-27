<template>
  <ul>
    <li v-for="d in value" v-bind:key="d">
      <router-link :to="{name: 'domain', params: {'domain': d}}">{{ d }}</router-link>
    </li>
  </ul>
</template>

<script>
export default {
  name: 'MultilineText',
  props: {
    label: {
      type: String,
      required: false,
    },
    value: {
      type: [Array],
      required: true,
    },
  },
};
</script>

<style>
</style>
