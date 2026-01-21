<template>
  <tr>
    <td
      v-for="(field, index) in fields"
      :key="index"
      style="vertical-align: top"
    >
      <v-text-field
        ref="input"
        :hint="hints[index]"
        :persistent-hint="'mnemonics' in field"
        v-model="field.value"
        :label="hideLabel ? '' : field.label"
        :class="hideLabel ? 'pt-0' : ''"
        :disabled="disabled"
        :readonly="readonly"
        :placeholder="required && !field.optional ? ' ' : '(optional)'"
        :hide-details="!('mnemonics' in field) && !fieldInvalid(index)"
        :error="fieldInvalid(index)"
        :error-messages="fieldErrorMessages(index)"
        :append-inner-icon="index == fields.length-1 && !readonly && !disabled ? appendIcon : ''"
        @click:append-inner="$emit('remove', $event)"
        @update:modelValue="inputHandler()"
        @paste.prevent="pasteHandler($event)"
        @keydown="keydownHandler(index, $event)"
        @keyup="(e) => $emit('keyup', e)"
      />
      {{ errorMessages.join(' ') }}
    </td>
  </tr>
</template>

<script>
import { useVuelidate } from '@vuelidate/core';
import { helpers, requiredUnless } from '@vuelidate/validators';

export default {
  name: 'RecordItem',
  setup() {
    return { v$: useVuelidate(null, null, { $autoDirty: true }) };
  },
  props: {
    content: {
      type: String,
      required: true,
    },
    errorMessages: {
      type: Array,
      default: () => [],
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    readonly: {
      type: Boolean,
      default: false,
    },
    required: {
      type: Boolean,
      default: true,
    },
    hideLabel: {
      type: Boolean,
      default: false,
    },
    appendIcon: {
      type: String,
      required: false,
    },
  },
  data: () => ({
    errors: {
      required: ' ',
    },
    fields: [
      { label: 'Value', validations: {} },
    ],
    value: '',
  }),
  computed: {
    hints: function () {
      return this.fields.map(field => ('mnemonics' in field && field.mnemonics[field.value]) || "");
    },
  },
  watch: {
    content: function () {
      this.update(this.content);
    }
  },
  beforeMount() {
    // Initialize per-field value storage
    this.fields.forEach((field, /*i*/) => {
      field.value = '';
      field.hint = '';
    });
  },
  mounted() {
    // Set up mirror system
    this.fields.forEach((field, i) => {
      function createMirror(template) {
        const style = window.getComputedStyle(template);
        const mirror = document.createElement("div");
        mirror.style.border = style.getPropertyValue('border');
        mirror.style.fontSize = style.getPropertyValue('font-size');
        mirror.style.fontFamily = style.getPropertyValue('font-family');
        mirror.style.fontWeight = style.getPropertyValue('font-weight');
        mirror.style.fontStyle = style.getPropertyValue('font-style');
        mirror.style.fontFeatureSettings = style.getPropertyValue('font-feature-settings');
        mirror.style.fontKerning = style.getPropertyValue('font-kerning');
        mirror.style.fontStretch = style.getPropertyValue('font-stretch');
        mirror.style.fontVariant = style.getPropertyValue('font-variant');
        mirror.style.fontVariantCaps = style.getPropertyValue('font-variant-caps');
        mirror.style.fontVariantLigatures = style.getPropertyValue('font-variant-ligatures');
        mirror.style.fontVariantNumeric = style.getPropertyValue('font-variant-numeric');
        mirror.style.letterSpacing = style.getPropertyValue('letter-spacing');
        mirror.style.padding = style.getPropertyValue('padding');
        mirror.style.transformOrigin = style.getPropertyValue('transform-origin');
        mirror.style.textTransform = style.getPropertyValue('text-transform');
        mirror.style.whiteSpace = style.getPropertyValue('white-space');
        mirror.style.marginRight = '1ch';
        mirror.style.height = '0';
        mirror.style.visibility = 'hidden';
        return mirror;
      }
      const el = this.$refs.input[i].$el;
      let mirror;
      let hint = el.getElementsByClassName("v-messages__message")[0];
      if(hint) {
        mirror = createMirror(hint);
        mirror.className = 'mirror-hint'
        el.after(mirror);
      }
      mirror = createMirror(el);
      mirror.style.paddingTop = '0px';
      mirror.style.whiteSpace = 'pre';
      mirror.className = 'mirror-input'
      el.after(mirror);
      let label = el.getElementsByClassName("v-label")[0];
      if(label) {
        mirror = createMirror(label);
        mirror.style.transform = 'translateY(-18px) scale(0.75)';
        mirror.className = 'mirror-label'
        el.after(mirror);
      }
    });

    // Update internal and graphical representation
    this.update(this.content);
  },
  validations() {
    const withMessages = (validators) => {
      if (!validators) {
        return {};
      }
      return Object.entries(validators).reduce((acc, [name, validator]) => {
        const message = this.errors?.[name];
        acc[name] = message ? helpers.withMessage(message, validator) : validator;
        return acc;
      }, {});
    };

    const validations = {
      fields: {
        $each: {
          value: this.required ? withMessages({ required: requiredUnless('optional') }) : {},
        },
      },
    };

    validations.fields = this.fields.reduce(
      (acc, field, index) => {
        acc[index] = { value: withMessages(field.validations) };
        return acc;
      },
      validations.fields,
    );

    return validations;
  },
  methods: {
    fieldInvalid(index) {
      const valueState = this.v$?.fields?.[index]?.value || this.v$?.fields?.$each?.[index]?.value;
      return !!valueState?.$invalid;
    },
    fieldErrorMessages(index) {
      const valueState = this.v$?.fields?.[index]?.value || this.v$?.fields?.$each?.[index]?.value;
      if (!valueState) {
        return [];
      }
      if (Array.isArray(valueState.$errors) && valueState.$errors.length) {
        const resolveMessage = (err) => {
          const message = err.$message;
          if (typeof message === 'function') {
            return message();
          }
          if (message && typeof message === 'object' && 'value' in message) {
            return message.value;
          }
          if (message) {
            return message;
          }
          const key = err.$validator || err.$params?.type || err.$params?.name;
          return this.errors?.[key] || 'Invalid input.';
        };
        return valueState.$errors.map(resolveMessage);
      }
      if (valueState.$invalid) {
        return ['Invalid input.'];
      }
      return [];
    },
    focus() {
      this.$refs.input[0].focus();
    },
    async update(value, caretPosition) {
      await this.$nextTick();

      // Right-trim if the cursor position is not after the last character
      let trimmed = value.replace(/ +$/g, '');
      const n = (trimmed.match(/ /g) || []).length;
      const diff = Math.max(0, (this.fields.length - 1) - n);
      trimmed += ' '.repeat(diff);
      if (caretPosition < trimmed.length) {
        value = trimmed;
      }

      // Only emit update event if there's news
      const dirty = (value !== this.value);
      if (dirty) {
        this.value = value;
        this.$emit('update:content', this.value);
      }

      // Always update fields as left-side fields with empty neighbor might have a trailing space
      // This case does not change the record value, but the field representation needs an update
      this.updateFields();

      if (caretPosition !== undefined) {
        await this.setPosition(caretPosition);
      }
    },
    positionAfterDelimiter(index) {
      const ref = this.getInputEl(index);
      if (!ref) {
        return false;
      }
      return index > 0 && ref.selectionStart === 0 && ref.selectionEnd === 0;
    },
    positionBeforeDelimiter(index) {
      const ref = this.getInputEl(index);
      return index < this.fields.length - 1 && ref && ref.selectionStart === this.fields[index].value.length;
    },
    keydownHandler(index, event) {
      switch (event.key) {
        case "Backspace":
          this.backspaceHandler(index, event);
          break;
        case " ":
          this.spaceHandler(index, event);
          break;
        case "End":
          this.endHandler(event);
          break;
        case "Home":
          this.homeHandler(event);
          break;
        case "ArrowLeft":
          this.leftHandler(index, event);
          break;
        case "ArrowRight":
          this.rightHandler(index, event);
          break;
        case "Delete":
          this.deleteHandler(index, event);
          break;
      }
    },
    spaceHandler(index, event) {
      if (!this.positionBeforeDelimiter(index)) {
        return;
      }

      const length = this.fields.slice(index + 1)
        .map(field => field.value.length)
        .reduce((acc, curr) => acc + curr, 0);

      if (length === 0 || this.fields[this.fields.length - 1].value.length > 0) {
        return this.rightHandler(index, event);
      }
    },
    backspaceHandler(index, event) {
      if (!this.positionAfterDelimiter(index)) {
        return;
      }

      event.preventDefault();
      const pos = this.getPosition();
      this.update(this.value.slice(0, pos - 1) + this.value.slice(pos), pos - 1);
    },
    deleteHandler(index, event) {
      if (!this.positionBeforeDelimiter(index)) {
        return;
      }

      event.preventDefault();
      const pos = this.getPosition();
      this.update(this.value.slice(0, pos) + this.value.slice(pos + 1), pos);
    },
    leftHandler(index, event) {
      if (!this.positionAfterDelimiter(index)) {
        return;
      }

      event.preventDefault();
      this.setPosition(this.getPosition() - 1);
    },
    rightHandler(index, event) {
      if (!this.positionBeforeDelimiter(index)) {
        return;
      }

      event.preventDefault();
      this.setPosition(this.getPosition() + 1);
    },
    endHandler(event) {
      if (event.shiftKey) {
        return;
      }
      event.preventDefault();
      this.setPosition(this.value.length);
    },
    homeHandler(event) {
      if (event.shiftKey) {
        return;
      }
      event.preventDefault();
      this.setPosition(0);
    },
    inputHandler() {
      this.$emit('dirty');
      this.v$?.$touch();
      const pos = this.getPosition();
      const value = this.fields.map(field => field.value).join(' ');
      this.update(value, pos);
    },
    pasteHandler(e) {
      const clipboardData = e.clipboardData.getData('text');
      let value = this.fields.map(field => field.value).join(' ');
      const selectionStart = this.getPosition();
      const selectionEnd = selectionStart + this.getSelectionWidth();
      if (clipboardData.includes("\n")) {
        e.data = [ value, selectionStart, selectionEnd, clipboardData ];
        return;
      } else {
        e.stopPropagation();
      }

      // number of field gaps covered by this paste, minus 1 (given by number of spaces in the clipboard text, bounded
      // from above by the number of fields (minus 1) at or to the right of the caret position
      const nBeforeCaret = (value.slice(0, selectionStart).match(/ /g) || []).length
      const n = Math.min((clipboardData.match(/ /g) || []).length, this.fields.length - 1 - nBeforeCaret);

      // Insert clipboard text and remove up to n spaces form the right
      value = value.slice(0, selectionStart) + clipboardData + value.slice(selectionEnd);
      value = value.replace(new RegExp(` {0,${n}}$`,'g'), '');
      this.update(value, selectionStart + clipboardData.length);
    },
    async setPosition(pos) {
      await this.$nextTick();
      let i = 0;
      while (pos > this.fields[i].value.length && i + 1 < this.fields.length) {
        pos -= this.fields[i].value.length + 1;
        i++;
      }

      const input = this.getInputEl(i);
      if (!input) {
        return;
      }
      input.focus();
      await this.$nextTick();
      input.setSelectionRange(pos, pos);
    },
    async select(i) {
      await this.$nextTick();
      const input = this.getInputEl(i);
      if (!input) {
        return;
      }
      input.focus();
      await this.$nextTick();
      input.select();  // for some reason this doesn't seem to work
      //console.log(this.$refs.input[i].$refs.input.selectionStart, this.$refs.input[i].$refs.input.selectionEnd);
      //window.setTimeout(() => console.log(this.$refs.input[i].$refs.input.selectionStart, this.$refs.input[i].$refs.input.selectionEnd), 1000);
    },
    getPosition() {
      const refs = this.$refs.input;
      const dirty = refs.findIndex((ref, index) => this.getInputEl(index) === document.activeElement);
      let selectionStart = this.getInputEl(dirty).selectionStart;
      for (let i = 0; i < dirty; i++) {
        selectionStart += this.getInputEl(i).value.length + 1;
      }
      return selectionStart;
    },
    getSelectionWidth() {
      const refs = this.$refs.input;
      const dirty = refs.findIndex((ref, index) => this.getInputEl(index) === document.activeElement);
      const input = this.getInputEl(dirty);
      return input.selectionEnd - input.selectionStart;
    },
    getInputEl(index) {
      const field = this.$refs.input[index];
      if (!field) {
        return null;
      }
      if (field.$refs && field.$refs.input) {
        return field.$refs.input;
      }
      return field.$el.querySelector('input');
    },
    updateFields() {
      let values = this.value.split(' ');
      const last = values.slice(this.fields.length - 1).join(' ');
      values = values.slice(0, this.fields.length - 1);
      values = values.concat([last]);
      // Make sure to reset trailing fields if value does not have enough spaces
      this.fields.forEach((foo, i) => {
        this.fields[i].value = values[i] || '';
        const el = this.$refs.input[i].$el.parentNode;
        let mirror;
        mirror = el.getElementsByClassName("mirror-label")[0];
        if (mirror) {
          mirror.textContent = el.getElementsByTagName("label")[0].textContent;
        }
        mirror = el.getElementsByClassName("mirror-input")[0];
        if (mirror) {
          mirror.textContent = this.fields[i].value;
        }
        mirror = el.getElementsByClassName("mirror-hint")[0];
        if (mirror) {
          this.$nextTick(() => {
            try {
              mirror.textContent = el.getElementsByClassName("v-messages__message")[0].textContent;
            } catch {
              mirror.textContent = ' ';
            }
          });
        }
      });
    },
  },
};
</script>
