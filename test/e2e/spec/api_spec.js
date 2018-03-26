var chakram = require("./../setup.js").chakram;
var expect = chakram.expect;

describe("API", function () {

    before(function () {
        chakram.setRequestDefaults({
            headers: {
                'Host': 'desec.' + process.env.DESECSTACK_DOMAIN,
            },
            followRedirect: false,
            baseUrl: 'https://www/api/v1',
        })
    });

    it("provides an index page", function () {
        var response = chakram.get('/');
        return expect(response).to.have.status(200);
    });

    describe("user registration", function () {

        it("returns a user object", function () {
            var email, password, token;

            email = require("uuid").v4() + '@e2etest.local';
            password = require("uuid").v4();

            var response = chakram.post('/auth/users/create/', {
                "email": email,
                "password": password,
            });

            return expect(response).to.have.status(201);
        });

    });

    describe("user login", function () {

        var email, password, token;

        before(function () {

            // register a user that we can work with
            email = require("uuid").v4() + '@e2etest.local';
            password = require("uuid").v4();

            var response = chakram.post('/auth/users/create/', {
                "email": email,
                "password": password,
            });

            return expect(response).to.have.status(201);
        });

        it("returns a token", function () {
            return chakram.post('/auth/token/create/', {
                "email": email,
                "password": password,
            }).then(function (loginResponse) {
                expect(loginResponse.body.auth_token).to.match(/^[a-z0-9]{40}$/);
                token = loginResponse.body.auth_token;
            });
        });

    });

    var email = require("uuid").v4() + '@e2etest.local';
    describe("with user account [" + email + "]", function () {

        var apiHomeSchema = {
            properties: {
                domains: {type: "string"},
                logout: {type: "string"},
                user: {type: "string"},
            },
            required: ["domains", "logout", "user"]
        };

        var password, token;

        before(function () {
            chakram.setRequestSettings({
                headers: {
                    'Host': 'desec.' + process.env.DESECSTACK_DOMAIN,
                },
                followRedirect: false,
                baseUrl: 'https://www/api/v1',
            });

            // register a user that we can login and work with
            password = require("uuid").v4();

            return chakram.post('/auth/users/create/', {
                "email": email,
                "password": password,
            }).then(function () {
                return chakram.post('/auth/token/create/', {
                    "email": email,
                    "password": password,
                }).then(function (loginResponse) {
                    expect(loginResponse.body.auth_token).to.match(/^[a-z0-9]{40}$/);
                    token = loginResponse.body.auth_token;
                    chakram.setRequestHeader('Authorization', 'Token ' + token);
                });
            });
        });

        describe("(logged in)", function () {

            describe("api 'homepage'", function () {

                var response;

                before(function () {
                    response = chakram.get('/');
                });

                it('has status 200', function () {
                    return expect(response).to.have.status(200);
                });

                it('looks according to the schema', function () {
                    return expect(response).to.have.schema(apiHomeSchema);
                });

            });

            describe("domains endpoint", function () {

                it("can register a domain name", function () {
                    var domain = 'e2etest-' + require("uuid").v4() + '.dedyn.io';
                    return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
                });

            });

            describe("a domain endpoint", function () {

                var domain;

                before(function () {
                    domain = 'e2etest-' + require("uuid").v4() + '.dedyn.io';
                    return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
                });

                it("can set an IPv4 address", function () {
                    return expect(chakram.post(
                        '/domains/' + domain + '/rrsets/',
                        {
                            'subname': '',
                            'type': 'A',
                            'records': ['127.0.0.1'],
                            'ttl': 60,
                        }
                    )).to.have.status(201);
                });

                it("can set an IPv6 address", function () {
                    return expect(chakram.post(
                        '/domains/' + domain + '/rrsets/',
                        {
                            'subname': '',
                            'type': 'AAAA',
                            'records': ['::1'],
                            'ttl': 60,
                        }
                    )).to.have.status(201);
                });

            });

        });

    });

});
