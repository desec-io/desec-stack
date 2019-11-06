module.exports = {
  configureWebpack: {
    devServer: {
      disableHostCheck: true,
      sockHost: 'desec.example.dedyn.io',    // TODO use env
      public: 'https://desec.example.dedyn.io/app/',    // TODO use env
      // sockPath: "/app/sockjs-node",
    },
  },
  publicPath: '/app/',
};
