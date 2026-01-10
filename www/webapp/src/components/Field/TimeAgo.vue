<template>
  <div
      class="my-1 py-5"
      :title="inputValue"
  >
    <span v-text="formattedValue"></span>
  </div>
</template>

<script>
import {formatDistanceToNow} from 'date-fns/formatDistanceToNow';

export default {
  name: 'TimeAgo',
  props: {
    modelValue: {
      default: '',
      type: String,
    },
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
    inputValue() {
      return this.modelValue ?? this.value;
    },
    formattedValue() {
      const inputTime = this.inputValue;
      if(!inputTime)
        return this.defaultText

      const parsedTime = new Date(inputTime);
      return formatDistanceToNow(parsedTime, {addSuffix: true});
    }
  }
};
</script>
