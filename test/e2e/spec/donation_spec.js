var chakram = require("./../setup.js").chakram;
var expect = chakram.expect;

describe("dyndns service", function () {

    // ('name', 'iban', 'bic', 'amount', 'message', 'email')
    var apiDonationSchema = {
        properties: {
            name: {type: "string"},
            iban: {type: "string"},
            bic: {type: "string"},
            amount: {type: "string"},
            message: {type: "string"},
            email: {type: "string"},
        },
        required: ["name", "iban", "bic", "amount"]
    };

    before(function () {
        chakram.setRequestSettings({
            headers: {
                'Host': 'desec.' + process.env.DESECSTACK_DOMAIN,
            },
            followRedirect: false,
            baseUrl: 'https://www/api/v1',
        });
    });

    describe("donating", function () {

        describe("without message and IBAN containing spaces", function () {

            var response;
            var iban = "DE89 3704 0044 0532 0130 00";

            before(function() {
                response = chakram.post('/donation/', {
                    "name": "Drama Queen",
                    "iban": iban,
                    "bic": "MARKDEF1100",
                    "amount": "3.14",
                    "email": "drama@queen.world",
                });
            });

            it("goes through", function () {
               return expect(response).to.have.status(201);
            });

            it("follows donation schema", function () {
                return expect(response).to.have.schema(apiDonationSchema);
            });

            it("does not return the full iban", function () {
                return response.then(function (donationResponse) {
                    expect(donationResponse.body.iban).to.not.contain(iban);
                });
            });

        });

        it("does not require an email address", function () {
            var email, password, token;

            var response = chakram.post('/donation/', {
                "name": "Drama Queen",
                "iban": "DE89370400440532013000",
                "bic": "MARKDEF1100",
                "amount": "3.14",
            });

            return expect(response).to.have.status(201);
        });

        // TODO it(sends emails)

    });

});
