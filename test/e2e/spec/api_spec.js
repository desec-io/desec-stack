var chakram = require("./../setup.js").chakram;
var expect = chakram.expect;
var itPropagatesToTheApi = require("./../setup.js").itPropagatesToTheApi;
var itShowsUpInPdnsAs = require("./../setup.js").itShowsUpInPdnsAs;
var schemas = require("./../schemas.js");

describe("API", function () {
    this.timeout(3000);

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

            var response = chakram.post('/auth/users/', {
                "email": email,
                "password": password,
            });

            return expect(response).to.have.status(201);
        });

        it("locks new users that look suspicious");
    });

    describe("user account", function () {

        var email, password;

        before(function () {

            // register a user that we can work with
            email = require("uuid").v4() + '@e2etest.local';
            password = require("uuid").v4();

            var response = chakram.post('/auth/users/', {
                "email": email,
                "password": password,
            });

            return expect(response).to.have.status(201);
        });

        it("returns a token when logging in", function () {
            return chakram.post('/auth/token/login/', {
                "email": email,
                "password": password,
            }).then(function (loginResponse) {
                expect(loginResponse.body.auth_token).to.match(schemas.TOKEN_REGEX);
            });
        });

        describe("auth/me/ endpoint", function () {
            var email2, password2, token2;

            before(function () {
                // register an independent user to screw around with
                email2 = require("uuid").v4() + '@e2etest.local';
                password2 = require("uuid").v4();

                return chakram.post('/auth/users/', {
                    "email": email2,
                    "password": password2,
                }).then(function () {
                    return chakram.post('/auth/token/login/', {
                        "email": email2,
                        "password": password2,
                    }).then(function (response) {
                        token2 = response.body.auth_token
                    });
                });
            });

            it("returns JSON of correct schema", function () {
                var response = chakram.get('/auth/me/', {
                    headers: {'Authorization': 'Token ' + token2 }
                });
                expect(response).to.have.status(200);
                expect(response).to.have.schema(schemas.user);
                return chakram.wait();
            });

            it("allows changing email address", function () {
                let email3 = require("uuid").v4() + '@e2etest.local';

                return chakram.put('/auth/me/',
                    {'email': email3},
                    {headers: {'Authorization': 'Token ' + token2}}
                ).then(function (response) {
                    expect(response).to.have.status(200);
                    expect(response).to.have.schema(schemas.user);
                    expect(response.body.email).to.equal(email3);
                });
            });
        });

        describe("token management (djoser)", function () {

            var token1, token2;

            function createTwoTokens() {
                return chakram.waitFor([
                    chakram.post('/auth/token/login/', {
                        "email": email,
                        "password": password,
                    }).then(function (loginResponse) {
                        expect(loginResponse).to.have.status(201);
                        expect(loginResponse.body.auth_token).to.match(schemas.TOKEN_REGEX);
                        token1 = loginResponse.body.auth_token;
                        expect(token1).to.not.equal(token2);
                    }),
                    chakram.post('/auth/token/login/', {
                        "email": email,
                        "password": password,
                    }).then(function (loginResponse) {
                        expect(loginResponse).to.have.status(201);
                        expect(loginResponse.body.auth_token).to.match(schemas.TOKEN_REGEX);
                        token2 = loginResponse.body.auth_token;
                        expect(token2).to.not.equal(token1);
                    })
                ]);
            }

            function deleteToken(token) {
                var response = chakram.post('/auth/token/logout/', null, {
                    headers: {'Authorization': 'Token ' + token}
                });

                return expect(response).to.have.status(204);
            }

            it("can create additional tokens", createTwoTokens);

            describe("additional tokens", function () {

                before(createTwoTokens);

                it("can be used for login (1)", function () {
                    return expect(chakram.get('/domains/', {
                        headers: {'Authorization': 'Token ' + token1 }
                    })).to.have.status(200);
                });

                it("can be used for login (2)", function () {
                    return expect(chakram.get('/domains/', {
                        headers: {'Authorization': 'Token ' + token2 }
                    })).to.have.status(200);
                });

                describe("and one deleted", function () {

                    before(function () {
                        var response = chakram.post('/auth/token/logout/', undefined,
                            { headers: {'Authorization': 'Token ' + token1 } }
                        );

                        return expect(response).to.have.status(204);
                    });

                    it("leaves the other untouched", function () {
                        return expect(chakram.get('/domains/', {
                            headers: {'Authorization': 'Token ' + token2 }
                        })).to.have.status(200);
                    });

                });

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

            return chakram.post('/auth/users/', {
                "email": email,
                "password": password,
            }).then(function () {
                return chakram.post('/auth/token/login/', {
                    "email": email,
                    "password": password,
                }).then(function (loginResponse) {
                    expect(loginResponse.body.auth_token).to.match(schemas.TOKEN_REGEX);
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

            describe("on domains/ endpoint", function () {

                var domain = 'e2etest-' + require("uuid").v4() + '.dedyn.io';
                before(function () {
                    return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
                });

                it("can register a domain name", function () {
                    var response = chakram.get('/domains/' + domain + '/');
                    expect(response).to.have.status(200);
                    expect(response).to.have.schema(schemas.domain);
                    return chakram.wait();
                });

                describe("on rrsets/ endpoint", function () {
                    it("can retrieve RRsets", function () {
                        var response = chakram.get('/domains/' + domain + '/rrsets/');
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrsets);

                        response = chakram.get('/domains/' + domain + '/rrsets/.../NS/');
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrset);

                        response = chakram.get('/domains/' + domain + '/rrsets/@/NS/');
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrset);

                        return chakram.wait();
                    });
                });
            });

            describe('POST rrsets/ with fresh domain', function () {

                var domain = 'e2etest-' + require("uuid").v4() + '.dedyn.io';
                before(function () {
                    return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
                });

                describe("can set an A RRset", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            {'subname': '', 'type': 'A', 'records': ['127.0.0.1'], 'ttl': 60}
                        );
                        expect(response).to.have.status(201);
                        expect(response).to.have.schema(schemas.rrset);
                        expect(response).to.have.json('ttl', 60);
                        expect(response).to.have.json('records', ['127.0.0.1']);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: '', domain: domain, type: 'A', ttl: 60, records: ['127.0.0.1']},
                    ]);

                    itShowsUpInPdnsAs('', domain, 'A', ['127.0.0.1'], 60);
                });

                describe("cannot create RRsets of restricted or dead type", function () {

                    var rrTypes = ['DNAME', 'ALIAS', 'SOA', 'RRSIG', 'DNSKEY', 'NSEC3PARAM', 'OPT'];
                    for (var i = 0; i < rrTypes.length; i++) {
                        var rrType = rrTypes[i];
                        it(rrType, function () {
                            return expect(chakram.post(
                                    '/domains/' + domain + '/rrsets/',
                                    {'subname': 'not-welcome', 'type': rrType, 'records': ['127.0.0.1'], 'ttl': 60}
                                )).to.have.status(400);
                        });
                    }

                });

                it("cannot update RRSets for nonexistent domain name", function () {
                    return expect(chakram.patch(
                            '/domains/nonexistent.e2e.domain/rrsets/',
                            {'subname': '', 'type': 'A', 'records': ['127.0.0.1'], 'ttl': 60}
                        )).to.have.status(404);
                });

                it("cannot create RRSets for nonexistent domain name", function () {
                    return expect(chakram.post(
                            '/domains/nonexistent.e2e.domain/rrsets/',
                            {'subname': '', 'type': 'A', 'records': ['127.0.0.1'], 'ttl': 60}
                        )).to.have.status(404);
                });

                it("cannot set unicode RRsets", function () {
                    return expect(chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            {'subname': '想不出来', 'type': 'A', 'records': ['127.0.0.1'], 'ttl': 60}
                        )).to.have.status(422);
                });

                describe("can set a wildcard AAAA RRset with multiple records", function () {
                    before(function () {
                        return chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            {'subname': '*.foobar', 'type': 'AAAA', 'records': ['::1', 'bade::affe'], 'ttl': 60}
                        );
                    });

                    itPropagatesToTheApi([
                        {subname: '*.foobar', domain: domain, type: 'AAAA', ttl: 60, records: ['::1', 'bade::affe']},
                        {subname: '*.foobar', domain: domain, type: 'AAAA', records: ['bade::affe', '::1']},
                    ]);

                    itShowsUpInPdnsAs('test.foobar', domain, 'AAAA', ['::1', 'bade::affe'], 60);
                });

                describe("can bulk-post an AAAA and an MX record", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [
                                { 'subname': 'ipv6', 'type': 'AAAA', 'records': ['dead::beef'], 'ttl': 22 },
                                { /* implied: 'subname': '', */ 'type': 'MX', 'records': ['10 mail.example.com.', '20 mail.example.net.'], 'ttl': 33 }
                            ]
                        );
                        expect(response).to.have.status(201);
                        expect(response).to.have.schema(schemas.rrsets);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'ipv6', domain: domain, type: 'AAAA', ttl: 22, records: ['dead::beef']},
                        {subname: '', domain: domain, type: 'MX', ttl: 33, records: ['10 mail.example.com.', '20 mail.example.net.']},
                    ]);

                    itShowsUpInPdnsAs('ipv6', domain, 'AAAA', ['dead::beef'], 22);

                    itShowsUpInPdnsAs('', domain, 'MX', ['10 mail.example.com.', '20 mail.example.net.'], 33);
                });

                describe("cannot bulk-post with missing or invalid fields", function () {
                    before(function () {
                        // Set an RRset that we'll try to overwrite
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [{'ttl': 50, 'type': 'TXT', 'records': ['"foo"']}]
                        );
                        expect(response).to.have.status(201);

                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [
                                {'subname': 'a.1', 'records': ['dead::beef'], 'ttl': 22},
                                {'subname': 'b.1', 'ttl': -50, 'type': 'AAAA', 'records': ['dead::beef']},
                                {'ttl': 40, 'type': 'TXT', 'records': ['"bar"']},
                                {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA'},
                                {'subname': 'd.1', 'ttl': 50, 'type': 'AAAA'},
                                {'subname': 'd.1', 'ttl': 50, 'type': 'SOA', 'records': ['ns1.desec.io. peter.desec.io. 2018034419 10800 3600 604800 60']},
                                {'subname': 'd.1', 'ttl': 50, 'type': 'OPT', 'records': ['9999']},
                                {'subname': 'd.1', 'ttl': 50, 'type': 'TYPE099', 'records': ['v=spf1 mx -all']},
                            ]
                        );
                        expect(response).to.have.status(400);
                        expect(response).to.have.json([
                            { type: [ 'This field is required.' ] },
                            { ttl: [ 'Ensure this value is greater than or equal to 1.' ] },
                            {},
                            { ttl: [ 'This field is required.' ] },
                            { records: [ 'This field is required.' ] },
                            { type: [ 'You cannot tinker with the SOA RRset.' ] },
                            { type: [ 'You cannot tinker with the OPT RRset.' ] },
                            { type: [ 'Generic type format is not supported.' ] },
                        ]);

                        return chakram.wait();
                    });

                    it("does not propagate partially to the API", function () {
                        return chakram.waitFor([
                            chakram
                                .get('/domains/' + domain + '/rrsets/b.1.../AAAA/')
                                .then(function (response) {
                                    expect(response).to.have.status(404);
                                }),
                            chakram
                                .get('/domains/' + domain + '/rrsets/.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 50);
                                    expect(response.body.records).to.have.members(['"foo"']);
                                }),
                            ]);
                    });

                    itShowsUpInPdnsAs('b.1', domain, 'AAAA', []);
                });

                context("with a pre-existing RRset", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [
                                {'subname': 'a.2', 'ttl': 50, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'c.2', 'ttl': 50, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'delete-test', 'ttl': 50, 'type': 'A', 'records': ['127.1.2.3']},
                            ]
                        );
                        return expect(response).to.have.status(201);
                    });

                    describe("can delete an RRset", function () {
                        before(function () {
                            var response = chakram.delete('/domains/' + domain + '/rrsets/delete-test.../A/');
                            return expect(response).to.have.status(204);
                        });

                        itPropagatesToTheApi([
                            {subname: 'delete-test', domain: domain, type: 'A', records: []},
                        ]);

                        itShowsUpInPdnsAs('delete-test', domain, 'A', []);
                    });

                    describe("cannot bulk-post existing or duplicate RRsets", function () {
                        var response;

                        before(function () {
                            response = chakram.post(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'a.2', 'ttl': 40, 'type': 'TXT', 'records': ['"bar"']},
                                    {'subname': 'a.2', 'ttl': 40, 'type': 'TXT', 'records': ['"bar"']},
                                ]
                            );
                            expect(response).to.have.status(400);
                            return chakram.wait();
                        });

                        it("gives the right response", function () {
                            expect(response).to.have.json([
                                { '__all__': [ 'R rset with this Domain, Subname and Type already exists.' ] },
                                { '__all__': [ 'RRset repeated with same subname and type.' ] },
                            ]);
                            return chakram.wait();
                        });

                        it("does not touch records in the API", function () {
                            return chakram
                                .get('/domains/' + domain + '/rrsets/a.2.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 50);
                                    expect(response.body.records).to.have.members(['"foo"']);
                                });
                        });

                        itShowsUpInPdnsAs('a.2', domain, 'TXT', ['"foo"'], 50);
                    });

                    describe("cannot delete RRsets via bulk-post", function () {
                        var response;

                        before(function () {
                            response = chakram.post(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'c.2', 'ttl': 40, 'type': 'TXT', 'records': []},
                                ]
                            );
                            return expect(response).to.have.status(400);
                        });

                        it("gives the right response", function () {
                            return expect(response).to.have.json([
                                { '__all__': [ 'R rset with this Domain, Subname and Type already exists.' ] },
                            ]);
                        });
                    });
                });

                describe("cannot bulk-post with invalid input", function () {
                    it("gives the right response for invalid type", function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 50, 'type': 'INVALID', 'records': ['"foo"']}]
                        );
                        return expect(response).to.have.status(422);
                    });

                    it("gives the right response for invalid records", function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 50, 'type': 'MX', 'records': ['1.2.3.4']}]
                        );
                        return expect(response).to.have.status(422);
                    });

                    it("gives the right response for records contents being null", function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 50, 'type': 'MX', 'records': ['1.2.3.4', null]}]
                        );
                        return expect(response).to.have.status(400);
                    });
                });

            });

            describe('PUT rrsets/ with fresh domain', function () {

                var domain = 'e2etest-' + require("uuid").v4() + '.dedyn.io';
                before(function () {
                    return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
                });

                describe("can overwrite a single existing RRset using PUT", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            { 'subname': 'single', 'type': 'AAAA', 'records': ['bade::fefe'], 'ttl': 62 }
                        ).then(function () {
                            return chakram.put(
                                '/domains/' + domain + '/rrsets/single.../AAAA/',
                                { 'records': ['fefe::bade'], 'ttl': 31 }
                            );
                        });
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrset);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'single', domain: domain, type: 'AAAA', ttl: 31, records: ['fefe::bade']},
                    ]);

                    itShowsUpInPdnsAs('single', domain, 'AAAA', ['fefe::bade'], 31);
                });

                describe("can bulk-put an AAAA and an MX record", function () {
                    before(function () {
                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [
                                { 'subname': 'ipv6', 'type': 'AAAA', 'records': ['dead::beef'], 'ttl': 22 },
                                { /* implied: 'subname': '', */ 'type': 'MX', 'records': ['10 mail.example.com.', '20 mail.example.net.'], 'ttl': 33 }
                            ]
                        );
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrsets);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'ipv6', domain: domain, type: 'AAAA', ttl: 22, records: ['dead::beef']},
                        {subname: '', domain: domain, type: 'MX', ttl: 33, records: ['10 mail.example.com.', '20 mail.example.net.']},
                    ]);

                    itShowsUpInPdnsAs('ipv6', domain, 'AAAA', ['dead::beef'], 22);

                    itShowsUpInPdnsAs('', domain, 'MX', ['10 mail.example.com.', '20 mail.example.net.'], 33);
                });

                describe("cannot bulk-put with missing or invalid fields", function () {
                    before(function () {
                        // Set an RRset that we'll try to overwrite
                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [{'ttl': 50, 'type': 'TXT', 'records': ['"foo"']}]
                        );
                        expect(response).to.have.status(200);

                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [
                                {'subname': 'a.1', 'records': ['dead::beef'], 'ttl': 22},
                                {'subname': 'b.1', 'ttl': -50, 'type': 'AAAA', 'records': ['dead::beef']},
                                {'ttl': 40, 'type': 'TXT', 'records': ['"bar"']},
                                {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA'},
                                {'subname': 'd.1', 'ttl': 50, 'type': 'AAAA'},
                            ]
                        );
                        expect(response).to.have.status(400);
                        expect(response).to.have.json([
                            { type: [ 'This field is required.' ] },
                            { ttl: [ 'Ensure this value is greater than or equal to 1.' ] },
                            {},
                            { ttl: [ 'This field is required.' ] },
                            { records: [ 'This field is required.' ] },
                        ]);

                        return chakram.wait();
                    });

                    it("does not propagate partially to the API", function () {
                        return chakram.waitFor([
                            chakram
                                .get('/domains/' + domain + '/rrsets/b.1.../AAAA/')
                                .then(function (response) {
                                    expect(response).to.have.status(404);
                                }),
                            chakram
                                .get('/domains/' + domain + '/rrsets/.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 50);
                                    expect(response.body.records).to.have.members(['"foo"']);
                                }),
                            ]);
                    });

                    itShowsUpInPdnsAs('b.1', domain, 'AAAA', []);
                });

                context("with a pre-existing RRset", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [
                                {'subname': 'a.2', 'ttl': 50, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'b.2', 'ttl': 50, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'c.2', 'ttl': 50, 'type': 'A', 'records': ['1.2.3.4']},
                            ]
                        );
                        expect(response).to.have.status(201);
                        return chakram.wait();
                    });

                    describe("can bulk-put existing RRsets", function () {
                        var response;

                        before(function () {
                            response = chakram.put(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'a.2', 'ttl': 40, 'type': 'TXT', 'records': ['"bar"']},
                                ]
                            );
                            expect(response).to.have.status(200);
                            expect(response).to.have.schema(schemas.rrsets);
                            return chakram.wait();
                        });

                        it("does modify records in the API", function () {
                            return chakram
                                .get('/domains/' + domain + '/rrsets/a.2.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 40);
                                    expect(response.body.records).to.have.members(['"bar"']);
                                });
                        });

                        itShowsUpInPdnsAs('a.2', domain, 'TXT', ['"bar"'], 40);
                    });

                    describe("cannot bulk-put duplicate RRsets", function () {
                        var response;

                        before(function () {
                            response = chakram.put(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'b.2', 'ttl': 60, 'type': 'TXT', 'records': ['"bar"']},
                                    {'subname': 'b.2', 'ttl': 60, 'type': 'TXT', 'records': ['"bar"']},
                                ]
                            );
                            return expect(response).to.have.status(400);
                        });

                        it("gives the right response", function () {
                            return expect(response).to.have.json([
                                { },
                                { '__all__': [ 'RRset repeated with same subname and type.' ] },
                            ]);
                        });

                        it("does not touch records in the API", function () {
                            return chakram
                                .get('/domains/' + domain + '/rrsets/b.2.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 50);
                                    expect(response.body.records).to.have.members(['"foo"']);
                                });
                        });

                        itShowsUpInPdnsAs('b.2', domain, 'TXT', ['"foo"'], 50);
                    });

                    describe("can delete RRsets via bulk-put", function () {
                        var response;

                        before(function () {
                            response = chakram.put(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'c.2', 'ttl': 40, 'type': 'A', 'records': []},
                                ]
                            );
                            return expect(response).to.have.status(200);
                        });

                        it("gives the right response", function () {
                            var response = chakram.get('/domains/' + domain + '/rrsets/c.2.../A/');
                            return expect(response).to.have.status(404);
                        });
                    });
                });

                describe("cannot bulk-put with invalid input", function () {
                    it("gives the right response for invalid type", function () {
                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 50, 'type': 'INVALID', 'records': ['"foo"']}]
                        );
                        return expect(response).to.have.status(422);
                    });

                    it("gives the right response for invalid records", function () {
                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 50, 'type': 'MX', 'records': ['1.2.3.4']}]
                        );
                        return expect(response).to.have.status(422);
                    });

                    it("gives the right response for records contents being null", function () {
                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 50, 'type': 'MX', 'records': ['1.2.3.4', null]}]
                        );
                        return expect(response).to.have.status(400);
                    });
                });

            });

            describe('PATCH rrsets/ with fresh domain', function () {

                var domain = 'e2etest-' + require("uuid").v4() + '.dedyn.io';
                before(function () {
                    return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
                });

                describe("can modify a single existing RRset using PATCH", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            { 'subname': 'single', 'type': 'AAAA', 'records': ['bade::fefe'], 'ttl': 62 }
                        ).then(function () {
                            return chakram.patch(
                                '/domains/' + domain + '/rrsets/single.../AAAA/',
                                { 'records': ['fefe::bade'], 'ttl': 31 }
                            );
                        });
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrset);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'single', domain: domain, type: 'AAAA', ttl: 31, records: ['fefe::bade']},
                    ]);

                    itShowsUpInPdnsAs('single', domain, 'AAAA', ['fefe::bade'], 31);
                });

                describe("can bulk-patch an AAAA and an MX record", function () {
                    before(function () {
                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [
                                { 'subname': 'ipv6', 'type': 'AAAA', 'records': ['dead::beef'], 'ttl': 22 },
                                { /* implied: 'subname': '', */ 'type': 'MX', 'records': ['10 mail.example.com.', '20 mail.example.net.'], 'ttl': 33 }
                            ]
                        );
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrsets);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'ipv6', domain: domain, type: 'AAAA', ttl: 22, records: ['dead::beef']},
                        {subname: '', domain: domain, type: 'MX', ttl: 33, records: ['10 mail.example.com.', '20 mail.example.net.']},
                    ]);

                    itShowsUpInPdnsAs('ipv6', domain, 'AAAA', ['dead::beef'], 22);

                    itShowsUpInPdnsAs('', domain, 'MX', ['10 mail.example.com.', '20 mail.example.net.'], 33);
                });

                describe("cannot bulk-patch with missing or invalid fields", function () {
                    before(function () {
                        // Set an RRset that we'll try to overwrite
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [{'ttl': 50, 'type': 'TXT', 'records': ['"foo"']}]
                        );
                        expect(response).to.have.status(201);

                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [
                                {'subname': 'a.1', 'records': ['dead::beef'], 'ttl': 22},
                                {'subname': 'b.1', 'ttl': -50, 'type': 'AAAA', 'records': ['dead::beef']},
                                {'ttl': 40, 'type': 'TXT', 'records': ['"bar"']},
                                {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA'},
                                {'subname': 'd.1', 'ttl': 50, 'type': 'AAAA'},
                            ]
                        );
                        expect(response).to.have.status(400);
                        expect(response).to.have.json([
                            { type: [ 'This field is required.' ] },
                            { ttl: [ 'Ensure this value is greater than or equal to 1.' ] },
                            {},
                            {},
                            {},
                        ]);

                        return chakram.wait();
                    });

                    it("does not propagate partially to the API", function () {
                        return chakram.waitFor([
                            chakram
                                .get('/domains/' + domain + '/rrsets/b.1.../AAAA/')
                                .then(function (response) {
                                    expect(response).to.have.status(404);
                                }),
                            chakram
                                .get('/domains/' + domain + '/rrsets/.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 50);
                                    expect(response.body.records).to.have.members(['"foo"']);
                                }),
                            ]);
                    });

                    itShowsUpInPdnsAs('b.1', domain, 'AAAA', []);
                });

                context("with a pre-existing RRset", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [
                                {'subname': 'a.1', 'ttl': 50, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'a.2', 'ttl': 50, 'type': 'A', 'records': ['4.3.2.1']},
                                {'subname': 'a.2', 'ttl': 50, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'b.2', 'ttl': 50, 'type': 'A', 'records': ['5.4.3.2']},
                                {'subname': 'b.2', 'ttl': 50, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'c.2', 'ttl': 50, 'type': 'A', 'records': ['1.2.3.4']},
                            ]
                        );
                        return expect(response).to.have.status(201);
                    });

                    describe("can bulk-patch existing RRsets", function () {
                        var response;

                        before(function () {
                            response = chakram.patch(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'a.1', 'type': 'TXT', 'records': ['"bar"']},
                                    {'subname': 'a.2', 'ttl': 40, 'type': 'TXT', 'records': ['"bar"']},
                                ]
                            );
                            expect(response).to.have.status(200);
                            expect(response).to.have.schema(schemas.rrsets);
                            return chakram.wait();
                        });

                        it("does modify records in the API", function () {
                            return chakram.waitFor([
                                chakram
                                    .get('/domains/' + domain + '/rrsets/a.1.../TXT/')
                                    .then(function (response) {
                                        expect(response).to.have.status(200);
                                        expect(response).to.have.json('ttl', 50);
                                        expect(response.body.records).to.have.members(['"bar"']);
                                    }),
                                chakram
                                    .get('/domains/' + domain + '/rrsets/a.2.../TXT/')
                                    .then(function (response) {
                                        expect(response).to.have.status(200);
                                        expect(response).to.have.json('ttl', 40);
                                        expect(response.body.records).to.have.members(['"bar"']);
                                    }),
                            ]);
                        });

                        itShowsUpInPdnsAs('a.2', domain, 'TXT', ['"bar"'], 40);
                    });

                    describe("cannot bulk-patch duplicate RRsets", function () {
                        var response;

                        before(function () {
                            response = chakram.patch(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'b.2', 'ttl': 40, 'type': 'TXT', 'records': ['"bar"']},
                                    {'subname': 'b.2', 'ttl': 40, 'type': 'TXT', 'records': ['"bar"']},
                                ]
                            );
                            return expect(response).to.have.status(400);
                        });

                        it("gives the right response", function () {
                            return expect(response).to.have.json([
                                {},
                                { '__all__': [ 'RRset repeated with same subname and type.' ] },
                            ]);
                        });

                        it("does not touch records in the API", function () {
                            return chakram
                                .get('/domains/' + domain + '/rrsets/b.2.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 50);
                                    expect(response.body.records).to.have.members(['"foo"']);
                                });
                        });

                        itShowsUpInPdnsAs('b.2', domain, 'TXT', ['"foo"'], 50);
                    });

                    describe("can delete RRsets via bulk-patch", function () {
                        var response;

                        before(function () {
                            response = chakram.patch(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'c.2', 'type': 'A', 'records': []},
                                ]
                            );
                            return expect(response).to.have.status(200);
                        });

                        it("gives the right response", function () {
                            var response = chakram.get('/domains/' + domain + '/rrsets/c.2.../A/');
                            return expect(response).to.have.status(404);
                        });
                    });

                    describe("accepts missing fields for no-op requests via bulk-patch", function () {
                        var response;

                        before(function () {
                            response = chakram.patch(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'a.2', 'type': 'A', 'records': ['6.6.6.6']}, // existing RRset; TTL not needed
                                    {'subname': 'b.2', 'type': 'A', 'ttl': 40}, // existing RRset; records not needed
                                    {'subname': 'x.2', 'type': 'A', 'records': []}, // non-existent, no-op
                                    {'subname': 'x.2', 'type': 'AAAA'}, // non-existent, no-op
                                    {'subname': 'x.2', 'type': 'TXT', 'ttl': 32}, // non-existent, no-op
                                ]
                            );
                            return expect(response).to.have.status(200);
                        });

                        it("gives the right response", function () {
                            var response = chakram.get('/domains/' + domain + '/rrsets/b.2.../A/');
                            expect(response).to.have.status(200);
                            expect(response).to.have.json('ttl', 40);
                            return chakram.wait();
                        });
                    });

                    describe("catches invalid type for no-op request via bulk-patch", function () {
                        it("gives the right response", function () {
                            return chakram.patch(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'x.2', 'type': 'AAA'}, // non-existent, no-op, but invalid type
                                ]
                            ).then(function (respObj) {
                                expect(respObj).to.have.status(422);
                                expect(respObj.body.detail).to.match(/IN AAA: unknown type given$/);
                                return chakram.wait();
                            });
                        });
                    });
                });

                describe("cannot bulk-patch with invalid input", function () {
                    it("gives the right response for invalid type", function () {
                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 50, 'type': 'INVALID', 'records': ['"foo"']}]
                        );
                        return expect(response).to.have.status(422);
                    });

                    it("gives the right response for invalid records", function () {
                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 50, 'type': 'MX', 'records': ['1.2.3.4']}]
                        );
                        return expect(response).to.have.status(422);
                    });

                    it("gives the right response for records contents being null", function () {
                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 50, 'type': 'MX', 'records': ['1.2.3.4', null]}]
                        );
                        return expect(response).to.have.status(400);
                    });
                });

            });

            describe("auth/tokens/ endpoint", function () {

                var tokenId;
                var tokenValue;

                function createTokenWithName () {
                    var tokenname = "e2e-token-" + require("uuid").v4();
                    return chakram.post('/auth/tokens/', { name: tokenname }).then(function (response) {
                        expect(response).to.have.status(201);
                        expect(response).to.have.json('name', tokenname);
                        tokenId = response.body['id'];
                    });
                }

                function createToken () {
                    return chakram.post('/auth/tokens/').then(function (response) {
                        expect(response).to.have.status(201);
                        tokenId = response.body['id'];
                        tokenValue = response.body['value'];
                    });
                }

                it("can create tokens", createToken);

                it("can create tokens with name", createTokenWithName)

                describe("with tokens", function () {
                    before(createToken)

                    it("a list of tokens can be retrieved", function () {
                        var response = chakram.get('/auth/tokens/');
                        return expect(response).to.have.schema(schemas.tokens);
                    });

                    describe("can delete token", function () {

                        before( function () {
                            var response = chakram.delete('/auth/tokens/' + tokenId + '/');
                            return expect(response).to.have.status(204);
                        });

                        it("deactivates the token", function () {
                            return expect(chakram.get('/auth/tokens/', {
                                headers: {'Authorization': 'Token ' + tokenValue }
                            })).to.have.status(401);
                        });

                    });

                    it("deleting nonexistent tokens yields 204", function () {
                        var response = chakram.delete('/auth/tokens/wedonthavethisid/');
                        return expect(response).to.have.status(204);
                    });

                });

            })

        });

    });

});
