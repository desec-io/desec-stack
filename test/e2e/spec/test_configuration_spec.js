var chakram = require('./../setup.js').chakram;
var expect = chakram.expect;

describe("test configuration", function () {

    it("has a hostname", function () {
        return expect(process.env.DESECSTACK_DOMAIN).to.exist;
    });

    it("knows the ipv4 prefix", function () {
        return expect(process.env.DESECSTACK_IPV4_REAR_PREFIX16).to.exist;
    });

    it("knows the ipv6 address of www", function () {
        return expect(process.env.DESECSTACK_IPV6_ADDRESS).to.exist;
    });

});
