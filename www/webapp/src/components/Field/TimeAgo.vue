<template>
  <div
      class="my-1 py-5"
      :title="value"
  >
    <span v-text="formattedValue"></span>
  </div>
</template>

<script>
import {formatDistanceToNow} from 'date-fns/formatDistanceToNow';

export default {
  name: 'TimeAgo',
  props: {
    value: {
      default: '',
      type: String,
    },
    defaultText: {
      default: 'never',
      type: String,
    },
  },
  computed: {
    formattedValue() {
      const inputTime = this.value;
      if(!inputTime)
        return this.defaultText

      const parsedTime = new Date(inputTime);
      return formatDistanceToNow(parsedTime, {addSuffix: true});
    }
  }
};
</script>
