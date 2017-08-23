var chakram = require("./../setup.js").chakram;
var expect = chakram.expect;

describe("API", function () {

    var URL = 'https://www/api/v1';

    before(function () {
        chakram.setRequestDefaults({
            headers: {
                'Host': 'desec.' + process.env.DESECSTACK_DOMAIN,
            }
        })
    });

    it("provides an index page", function () {
        var response = chakram.get(URL + '/');
        return expect(response).to.have.status(200);
    });

});
