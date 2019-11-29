module.exports = {
  configureWebpack: {
    devServer: {
      disableHostCheck: true,
      sockHost: 'desec.' + process.env.DESECSTACK_DOMAIN,
      public: 'https://desec.' + process.env.DESECSTACK_DOMAIN + '/app/',
    },
  },
  publicPath: '/app/',
};
