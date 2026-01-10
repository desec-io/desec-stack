<script>
  import GenericActionHandler from "./GenericActionHandler.vue"

  export default {
    name: 'CreateTOTPActionHandler',
    extends: GenericActionHandler,
    data: () => ({
      auto_submit: true,
    }),
    watch: {
      success(value) {
        if(value) {
          sessionStorage.setItem('totpVerifyData', JSON.stringify(this.response.data));
          this.$router.push({ name: 'TOTPVerify', query: { name: this.response.data.name }});
        }
      }
    }
  };
</script>
