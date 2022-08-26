<script>
  import GenericActionHandler from "./GenericActionHandler"

  export default {
    name: 'CreateTOTPActionHandler',
    extends: GenericActionHandler,
    data: () => ({
      auto_submit: true,
    }),
    watch: {
      success(value) {
        if(value) {
          let params = {
            data: this.response.data,
            name: this.response.data.name,
          };
          this.$router.push({ name: 'TOTPVerify', params: params});
        }
      }
    }
  };
</script>
