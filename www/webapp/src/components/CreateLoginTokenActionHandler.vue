<script>
  import GenericActionHandler from "./GenericActionHandler"
  import {HTTP} from "../utils";

  export default {
    name: 'CreateLoginTokenActionHandler',
    extends: GenericActionHandler,
    data: () => ({
      auto_submit: true,
    }),
    watch: {
      success(value) {
        if(value) {
          HTTP.defaults.headers.common.Authorization = `Token ${value.token}`;
          this.$store.commit('login', value);
          if (this.useSessionStorage) {
            sessionStorage.setItem('token', JSON.stringify(value));
          }
          this.$router.replace({ name: 'domains' });
        }
      }
    }
  };
</script>
