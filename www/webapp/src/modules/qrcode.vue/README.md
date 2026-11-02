# qrcode.vue (vendored)

`dist/qrcode.vue.esm.js` is the prebuilt ES module of
[qrcode.vue](https://github.com/scopewu/qrcode.vue) v1.7.0, a Vue 2
component (MIT License, see `LICENSE`). The webapp uses it through
`src/components/QrcodeVue.vue`, which adapts it to Vue 3.

The module is part of this repository so that changes to the code that
renders TOTP secrets as QR codes go through our own review. To update it,
replace the file with a reviewed build, and adjust the version above.
