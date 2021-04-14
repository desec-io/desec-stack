var chakram = require("./../setup.js").chakram;
var expect = chakram.expect;
var itPropagatesToTheApi = require("./../setup.js").itPropagatesToTheApi;
var itShowsUpInPdnsAs = require("./../setup.js").itShowsUpInPdnsAs;
var schemas = require("./../schemas.js");
var withCaptcha = require("./../setup.js").withCaptcha;

describe("API Versioning", function () {

    before(function () {
        chakram.setRequestDefaults({
            headers: {
                'Host': 'desec.' + process.env.DESECSTACK_DOMAIN,
            },
            followRedirect: false,
            baseUrl: 'https://www/api',
        })
    });

    [
        'v1',
        'v2',
    ].forEach(function (version) {
        it("maintains the requested version " + version, function() {
            chakram.get('/' + version + '/').then(function (response) {
                expect(response).to.have.schema(schemas.rootNoLogin);
                let regex = new RegExp('https://[^/]+/api/' + version + '/auth/login/', 'g')
                expect(response.body.login).to.match(regex);
                return chakram.wait();
            });
        });
    })

});

describe("API v1", function () {
    this.timeout(3000);

    let publicSuffix = 'dedyn.' + process.env.DESECSTACK_DOMAIN;  // see settings.py

    before(function () {
        chakram.setRequestDefaults({
            headers: {
                'Host': 'desec.' + process.env.DESECSTACK_DOMAIN,
            },
            followRedirect: false,
            baseUrl: 'https://www/api/v1',
        })

        // ensure that the public suffix domain is set up and ready to use
        let email = 'admin@example.com';
        let password = 'admin123!';
        return withCaptcha(function (captcha) {
            return chakram.post('/auth/', {
                    "email": email,
                    "password": password,
                    "captcha": captcha,
                }).then(function (registerResponse) {
                    return chakram.post('/auth/login/', {
                        "email": email,
                        "password": password,
                    }).then(function (loginResponse) {
                        return chakram.post('/domains/', {
                            name: publicSuffix,
                        }, {
                            headers: {'Authorization': 'Token ' + loginResponse.body.token }
                        }); // note that we ignore errors here
                    });
            });
        });
    });

    it("provides an index page", function () {
        return chakram.get('/').then(function (response) {
            expect(response).to.have.schema(schemas.rootNoLogin);
            expect(response.body.login).to.match(/https:\/\/[^\/]+\/api\/v1\/auth\/login\//);
            return chakram.wait();
        });
    });

    it("has HSTS header", function () {
        var response = chakram.get('/');
        expect(response).to.have.header('Strict-Transport-Security', 'max-age=31536000; includeSubdomains; preload');
        return chakram.wait();
    });

    it("has CORS headers", function () {
        return chakram.options('/', {headers: {'Origin': 'http://foo.example' }}).then(function (response) {
            expect(response).to.have.header('access-control-allow-origin', '*');
            expect(response).to.have.header('access-control-allow-headers', /.*authorization.*/);
            return chakram.wait();
        });
    });

    describe("user registration", function () {

        var captcha;

        before(function () {
            return withCaptcha(function (_captcha) {
                captcha = _captcha;
            });
        });

        it("returns a user object", function () {
            var email, password, token;

            email = require("uuid").v4() + '@e2etest.local';
            password = require("uuid").v4();

            var response = chakram.post('/auth/', {
                "email": email,
                "password": password,
                "captcha": captcha,
            });

            return expect(response).to.have.status(202);
        });
    });

    describe("user account", function () {

        var email, password;

        before(function () {

            // register a user that we can work with
            email = require("uuid").v4() + '@e2etest.local';
            password = require("uuid").v4();

            let response = withCaptcha(function (captcha) {
                return chakram.post('/auth/', {
                    "email": email,
                    "password": password,
                    "captcha": captcha,
                });
            });

            return expect(response).to.have.status(202);
        });

        it("returns a token when logging in", function () {
            return chakram.post('/auth/login/', {
                "email": email,
                "password": password,
            }).then(function (loginResponse) {
                expect(loginResponse.body.token).to.match(schemas.TOKEN_REGEX);
            });
        });

        describe("auth/account/ endpoint", function () {
            var email2, password2, token2;

            before(function () {
                // register an independent user to screw around with
                email2 = require("uuid").v4() + '@e2etest.local';
                password2 = require("uuid").v4();

                return withCaptcha(function (captcha) {
                    return chakram.post('/auth/', {
                        "email": email2,
                        "password": password2,
                        "captcha": captcha,
                    }).then(function () {
                        return chakram.post('/auth/login/', {
                            "email": email2,
                            "password": password2,
                        }).then(function (response) {
                            token2 = response.body.token
                        });
                    });
                });
            });

            it("returns JSON of correct schema", function () {
                var response = chakram.get('/auth/account/', {
                    headers: {'Authorization': 'Token ' + token2 }
                });
                expect(response).to.have.status(200);
                expect(response).to.have.schema(schemas.user);
                return chakram.wait();
            });

            it("allows triggering change email process", function () {
                return chakram.post('/auth/account/change-email/', {
                    "email": email2,
                    "password": password2,
                    "new_email": require("uuid").v4() + '@e2etest.local',
                }).then(function (response) {
                    expect(response).to.have.status(202);
                });
            });
        });
    });

    var email = require("uuid").v4() + '@e2etest.local';
    describe("with user account [" + email + "]", function () {

        var apiHomeSchema = {
            properties: {
                domains: {type: "string"},
                tokens: {type: "string"},
                account: {type: "object"},
            },
            required: ["domains", "tokens", "account"]
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

            return withCaptcha(function (captcha) {
                return chakram.post('/auth/', {
                    "email": email,
                    "password": password,
                    "captcha": captcha,
                }).then(function () {
                    return chakram.post('/auth/login/', {
                        "email": email,
                        "password": password,
                    }).then(function (loginResponse) {
                        expect(loginResponse.body.token).to.match(schemas.TOKEN_REGEX);
                        token = loginResponse.body.token;
                        chakram.setRequestHeader('Authorization', 'Token ' + token);
                    });
                });
            });
        });

        describe("(logged in)", function () {

            describe("api 'homepage'", function () {

                var response;

                before(function () {
                    return chakram.get('/').then(function (_response) {
                        response = _response;
                    });
                });

                it('has status 200', function () {
                    return expect(response).to.have.status(200);
                });

                it('looks according to the schema', function () {
                    return expect(response).to.have.schema(apiHomeSchema);
                });

            });

            describe("on domains/ endpoint", function () {

                var domain = 'e2etest-' + require("uuid").v4() + '.' + publicSuffix;
                before(function () {
                    return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
                });

                it("can register a domain name", function () {
                    var response = chakram.get('/domains/' + domain + '/');
                    expect(response).to.have.status(200);
                    expect(response).to.have.schema(schemas.domain);
                    return chakram.wait();
                });

                itShowsUpInPdnsAs('', domain, 'NS', process.env.DESECSTACK_NS.split(/\s+/),  process.env.DESECSTACK_NSLORD_DEFAULT_TTL);

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

                var domain = 'e2etest-' + require("uuid").v4() + '.' + publicSuffix;
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

                    var rrTypes = ['ALIAS', 'SOA', 'RRSIG', 'DNSKEY', 'NSEC3PARAM', 'OPT'];
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
                        )).to.have.status(400);
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

                describe("cannot create RRsets with duplicate record content", function () {
                    it("rejects exact duplicates", function () {
                        return expect(chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            {
                                'subname': 'duplicate-contents', 'type': 'AAAA',
                                'records': ['::1', '::1'], 'ttl': 60
                            }
                        )).to.have.status(400);
                    });

                    it("rejects semantic duplicates", function () {
                        return expect(chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            {
                                'subname': 'duplicate-contents', 'type': 'AAAA',
                                'records': ['::1', '::0001'], 'ttl': 60
                            }
                        )).to.have.status(400);
                    });

                    describe("even in subsequent requests", function () {
                        before(function() {
                            return expect(chakram.post(
                                '/domains/' + domain + '/rrsets/',
                                {
                                    'subname': 'duplicate-contents', 'type': 'AAAA',
                                    'records': ['::1'], 'ttl': 60
                                }
                            )).to.have.status(201);
                        });

                        it("still does not accept a semantic duplicate", function () {
                            return expect(chakram.post(
                                '/domains/' + domain + '/rrsets/',
                                {
                                    'subname': 'duplicate-contents', 'type': 'AAAA',
                                    'records': ['::0001'], 'ttl': 60
                                }
                            )).to.have.status(400);
                        });

                        it("still does not accept a semantic duplicates", function () {
                            return expect(chakram.post(
                                '/domains/' + domain + '/rrsets/',
                                {
                                    'subname': 'duplicate-contents', 'type': 'AAAA',
                                    'records': ['::1', '::0001'], 'ttl': 60
                                }
                            )).to.have.status(400);
                        });
                    })
                });

                describe("can bulk-post an AAAA and an MX record", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [
                                { 'subname': 'ipv6', 'type': 'AAAA', 'records': ['dead::beef'], 'ttl': 3622 },
                                { 'subname': '', 'type': 'MX', 'records': ['10 mail.example.com.', '20 mail.example.net.'], 'ttl': 3633 }
                            ]
                        );
                        expect(response).to.have.status(201);
                        expect(response).to.have.schema(schemas.rrsets);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'ipv6', domain: domain, type: 'AAAA', ttl: 3622, records: ['dead::beef']},
                        {subname: '', domain: domain, type: 'MX', ttl: 3633, records: ['10 mail.example.com.', '20 mail.example.net.']},
                    ]);

                    itShowsUpInPdnsAs('ipv6', domain, 'AAAA', ['dead::beef'], 3622);

                    itShowsUpInPdnsAs('', domain, 'MX', ['10 mail.example.com.', '20 mail.example.net.'], 3633);
                });

                describe("cannot bulk-post with missing or invalid fields", function () {
                    before(function () {
                        // Set an RRset that we'll try to overwrite
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            {'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']}
                        );
                        expect(response).to.have.status(201);

                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [
                                {'subname': 'a.1', 'records': ['dead::beef'], 'ttl': 3622},
                                {'subname': 'b.1', 'ttl': -50, 'type': 'AAAA', 'records': ['dead::beef']},
                                {'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                                {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA'},
                                {'subname': 'd.1', 'ttl': 3650, 'type': 'AAAA'},
                                {'subname': 'd.1', 'ttl': 3650, 'type': 'SOA', 'records': ['get.desec.io. get.desec.io. 2018034419 10800 3600 604800 60']},
                                {'subname': 'd.1', 'ttl': 3650, 'type': 'OPT', 'records': ['9999']},
                                {'subname': 'd.1', 'ttl': 3650, 'type': 'TYPE099', 'records': ['v=spf1 mx -all']},
                            ]
                        );
                        expect(response).to.have.status(400);
                        expect(response).to.have.json([
                            { type: [ 'This field is required.' ] },
                            { ttl: [ 'Ensure this value is greater than or equal to 60.' ] },
                            { subname: [ 'This field is required.' ] },
                            { ttl: [ 'This field is required.' ] },
                            { records: [ 'This field is required.' ] },
                            { type: [ 'You cannot tinker with the SOA RR set. It is managed automatically.' ] },
                            { type: [ 'You cannot tinker with the OPT RR set. It is managed automatically.' ] },
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
                                    expect(response).to.have.json('ttl', 3650);
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
                                {'subname': 'a.2', 'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'c.2', 'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'delete-test', 'ttl': 3650, 'type': 'A', 'records': ['127.1.2.3']},
                                {'subname': 'replace-test-1', 'ttl': 3650, 'type': 'AAAA', 'records': ['::1', '::2']},
                                {'subname': 'replace-test-2', 'ttl': 3650, 'type': 'AAAA', 'records': ['::1', '::2']},
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

                    describe("can be replaced with a CNAME record", function () {
                        before(function () {
                            var response = chakram.put(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'replace-test-1', 'ttl': 3650, 'type': 'AAAA', 'records': []},
                                    {'subname': 'replace-test-1', 'ttl': 3601, 'type': 'CNAME', 'records': ['example.com.']},
                                ]
                            );
                            return expect(response).to.have.status(200);
                        });

                        itPropagatesToTheApi([
                            {subname: 'replace-test-1', domain: domain, type: 'AAAA', records: []},
                            {subname: 'replace-test-1', domain: domain, type: 'CNAME', records: ["example.com."]},
                        ]);

                        itShowsUpInPdnsAs('replace-test-1', domain, 'AAAA', ["example.com"]);
                        itShowsUpInPdnsAs('replace-test-1', domain, 'CNAME', ["example.com"]);
                    });

                    describe("cannot be replaced with a malformed CNAME record", function () {
                        before(function () {
                            var response = chakram.put(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'replace-test-2', 'ttl': 3650, 'type': 'AAAA', 'records': []},
                                    {'subname': 'replace-test-2', 'ttl': 3601, 'type': 'CNAME', 'records': ['no.trailing.dot']},
                                ]
                            );
                            return expect(response).to.have.status(400);
                        });

                        itPropagatesToTheApi([
                            {subname: 'replace-test-2', domain: domain, type: 'AAAA', records: ["::1", "::2"]},
                            {subname: 'replace-test-2', domain: domain, type: 'CNAME', records: []},
                        ]);

                        itShowsUpInPdnsAs('replace-test-2', domain, 'AAAA', ["::1", "::2"]);
                        itShowsUpInPdnsAs('replace-test-2', domain, 'CNAME', []);
                    });

                    describe("cannot bulk-post existing or duplicate RRsets", function () {
                        var response;

                        before(function () {
                            response = chakram.post(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'a.2', 'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                                    {'subname': 'a.2', 'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                                ]
                            );
                            expect(response).to.have.status(400);
                            return chakram.wait();
                        });

                        it("gives the right response", function () {
                            expect(response).to.have.json([
                                {"non_field_errors": ["Same subname and type as in position(s) 1, but must be unique."]},
                                {"non_field_errors": ["Same subname and type as in position(s) 0, but must be unique."]}
                            ]);
                            return chakram.wait();
                        });

                        it("does not touch records in the API", function () {
                            return chakram
                                .get('/domains/' + domain + '/rrsets/a.2.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 3650);
                                    expect(response.body.records).to.have.members(['"foo"']);
                                });
                        });

                        itShowsUpInPdnsAs('a.2', domain, 'TXT', ['"foo"'], 3650);
                    });

                    describe("cannot delete RRsets via bulk-post", function () {
                        var response;

                        before(function () {
                            response = chakram.post(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'c.2', 'ttl': 3640, 'type': 'TXT', 'records': []},
                                ]
                            );
                            return expect(response).to.have.status(400);
                        });

                        it("gives the right response", function () {
                            return expect(response).to.have.json([
                                {'records': ['This field must not be empty when using POST.']},
                            ]);
                        });
                    });
                });

                describe("cannot bulk-post with invalid input", function () {
                    it("gives the right response for invalid type", function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 3650, 'type': 'INVALID', 'records': ['"foo"']}]
                        );
                        return expect(response).to.have.status(400);
                    });

                    it("gives the right response for invalid records", function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 3650, 'type': 'MX', 'records': ['1.2.3.4']}]
                        );
                        return expect(response).to.have.status(400);
                    });

                    it("gives the right response for records contents being null", function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 3650, 'type': 'MX', 'records': ['1.2.3.4', null]}]
                        );
                        return expect(response).to.have.status(400);
                    });
                });

            });

            describe('PUT rrsets/ with fresh domain', function () {

                var domain = 'e2etest-' + require("uuid").v4() + '.' + publicSuffix;
                before(function () {
                    return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
                });

                describe("can overwrite a single existing RRset using PUT", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            { 'subname': 'single', 'type': 'AAAA', 'records': ['bade::fefe'], 'ttl': 3662 }
                        ).then(function () {
                            return chakram.put(
                                '/domains/' + domain + '/rrsets/single.../AAAA/',
                                { 'subname': 'single', 'type': 'AAAA', 'records': ['fefe::bade'], 'ttl': 3631 }
                            );
                        });
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrset);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'single', domain: domain, type: 'AAAA', ttl: 3631, records: ['fefe::bade']},
                    ]);

                    itShowsUpInPdnsAs('single', domain, 'AAAA', ['fefe::bade'], 3631);
                });

                describe("can bulk-put an AAAA and an MX record", function () {
                    before(function () {
                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [
                                { 'subname': 'ipv6', 'type': 'AAAA', 'records': ['dead::beef'], 'ttl': 3622 },
                                { 'subname': '', 'type': 'MX', 'records': ['10 mail.example.com.', '20 mail.example.net.'], 'ttl': 3633 }
                            ]
                        );
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrsets);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'ipv6', domain: domain, type: 'AAAA', ttl: 3622, records: ['dead::beef']},
                        {subname: '', domain: domain, type: 'MX', ttl: 3633, records: ['10 mail.example.com.', '20 mail.example.net.']},
                    ]);

                    itShowsUpInPdnsAs('ipv6', domain, 'AAAA', ['dead::beef'], 3622);

                    itShowsUpInPdnsAs('', domain, 'MX', ['10 mail.example.com.', '20 mail.example.net.'], 3633);
                });

                describe("cannot bulk-put with missing or invalid fields", function () {
                    before(function () {
                        // Set an RRset that we'll try to overwrite
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            {'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']}
                        );
                        expect(response).to.have.status(201);

                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [
                                {'subname': 'a.1', 'records': ['dead::beef'], 'ttl': 3622},
                                {'subname': 'b.1', 'ttl': -50, 'type': 'AAAA', 'records': ['dead::beef']},
                                {'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                                {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA'},
                                {'subname': 'd.1', 'ttl': 3650, 'type': 'AAAA'},
                            ]
                        );
                        expect(response).to.have.status(400);
                        expect(response).to.have.json([
                            { type: [ 'This field is required.' ] },
                            { ttl: [ 'Ensure this value is greater than or equal to 60.' ] },
                            { subname: [ 'This field is required.' ] },
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
                                    expect(response).to.have.json('ttl', 3650);
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
                                {'subname': 'a.2', 'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'b.2', 'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'c.2', 'ttl': 3650, 'type': 'A', 'records': ['1.2.3.4']},
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
                                    {'subname': 'a.2', 'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
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
                                    expect(response).to.have.json('ttl', 3640);
                                    expect(response.body.records).to.have.members(['"bar"']);
                                });
                        });

                        itShowsUpInPdnsAs('a.2', domain, 'TXT', ['"bar"'], 3640);
                    });

                    describe("cannot bulk-put duplicate RRsets", function () {
                        var response;

                        before(function () {
                            response = chakram.put(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'b.2', 'ttl': 3660, 'type': 'TXT', 'records': ['"bar"']},
                                    {'subname': 'b.2', 'ttl': 3660, 'type': 'TXT', 'records': ['"bar"']},
                                ]
                            );
                            return expect(response).to.have.status(400);
                        });

                        it("gives the right response", function () {
                            return expect(response).to.have.json([
                                { 'non_field_errors': [ 'Same subname and type as in position(s) 1, but must be unique.' ] },
                                { 'non_field_errors': [ 'Same subname and type as in position(s) 0, but must be unique.' ] },
                            ]);
                        });

                        it("does not touch records in the API", function () {
                            return chakram
                                .get('/domains/' + domain + '/rrsets/b.2.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 3650);
                                    expect(response.body.records).to.have.members(['"foo"']);
                                });
                        });

                        itShowsUpInPdnsAs('b.2', domain, 'TXT', ['"foo"'], 3650);
                    });

                    describe("can delete RRsets via bulk-put", function () {
                        var response;

                        before(function () {
                            response = chakram.put(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'c.2', 'ttl': 3640, 'type': 'A', 'records': []},
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
                            [{'subname': 'a.2', 'ttl': 3650, 'type': 'INVALID', 'records': ['"foo"']}]
                        );
                        return expect(response).to.have.status(400);
                    });

                    it("gives the right response for invalid records", function () {
                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 3650, 'type': 'MX', 'records': ['1.2.3.4']}]
                        );
                        return expect(response).to.have.status(400);
                    });

                    it("gives the right response for records contents being null", function () {
                        var response = chakram.put(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 3650, 'type': 'MX', 'records': ['1.2.3.4', null]}]
                        );
                        return expect(response).to.have.status(400);
                    });
                });

            });

            describe('PATCH rrsets/ with fresh domain', function () {

                var domain = 'e2etest-' + require("uuid").v4() + '.' + publicSuffix;
                before(function () {
                    return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
                });

                describe("can modify a single existing RRset using PATCH", function () {
                    before(function () {
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            { 'subname': 'single', 'type': 'AAAA', 'records': ['bade::fefe'], 'ttl': 3662 }
                        ).then(function () {
                            return chakram.patch(
                                '/domains/' + domain + '/rrsets/single.../AAAA/',
                                { 'records': ['fefe::bade'], 'ttl': 3631 }
                            );
                        });
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrset);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'single', domain: domain, type: 'AAAA', ttl: 3631, records: ['fefe::bade']},
                    ]);

                    itShowsUpInPdnsAs('single', domain, 'AAAA', ['fefe::bade'], 3631);
                });

                describe("can bulk-patch an AAAA and an MX record", function () {
                    before(function () {
                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [
                                { 'subname': 'ipv6', 'type': 'AAAA', 'records': ['dead::beef'], 'ttl': 3622 },
                                { 'subname': '', 'type': 'MX', 'records': ['10 mail.example.com.', '20 mail.example.net.'], 'ttl': 3633 }
                            ]
                        );
                        expect(response).to.have.status(200);
                        expect(response).to.have.schema(schemas.rrsets);
                        return chakram.wait();
                    });

                    itPropagatesToTheApi([
                        {subname: 'ipv6', domain: domain, type: 'AAAA', ttl: 3622, records: ['dead::beef']},
                        {subname: '', domain: domain, type: 'MX', ttl: 3633, records: ['10 mail.example.com.', '20 mail.example.net.']},
                    ]);

                    itShowsUpInPdnsAs('ipv6', domain, 'AAAA', ['dead::beef'], 3622);

                    itShowsUpInPdnsAs('', domain, 'MX', ['10 mail.example.com.', '20 mail.example.net.'], 3633);
                });

                describe("cannot bulk-patch with missing or invalid fields", function () {
                    before(function () {
                        // Set an RRset that we'll try to overwrite
                        var response = chakram.post(
                            '/domains/' + domain + '/rrsets/',
                            {'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']}
                        );
                        expect(response).to.have.status(201);

                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [
                                {'subname': 'a.1', 'records': ['dead::beef'], 'ttl': 3622},
                                {'subname': 'b.1', 'ttl': -50, 'type': 'AAAA', 'records': ['dead::beef']},
                                {'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                                {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA'},
                                {'subname': 'd.1', 'ttl': 3650, 'type': 'AAAA'},
                            ]
                        );
                        expect(response).to.have.status(400);
                        expect(response).to.have.json([
                            { type: [ 'This field is required.' ] },
                            { ttl: [ 'Ensure this value is greater than or equal to 60.' ] },
                            { subname: [ 'This field is required.' ] },
                            { ttl: ['This field is required.']} ,
                            { records: ['This field is required.']} ,
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
                                    expect(response).to.have.json('ttl', 3650);
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
                                {'subname': 'a.1', 'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'a.2', 'ttl': 3650, 'type': 'A', 'records': ['4.3.2.1']},
                                {'subname': 'a.2', 'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'b.2', 'ttl': 3650, 'type': 'A', 'records': ['5.4.3.2']},
                                {'subname': 'b.2', 'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']},
                                {'subname': 'c.2', 'ttl': 3650, 'type': 'A', 'records': ['1.2.3.4']},
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
                                    {'subname': 'a.2', 'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
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
                                        expect(response).to.have.json('ttl', 3650);
                                        expect(response.body.records).to.have.members(['"bar"']);
                                    }),
                                chakram
                                    .get('/domains/' + domain + '/rrsets/a.2.../TXT/')
                                    .then(function (response) {
                                        expect(response).to.have.status(200);
                                        expect(response).to.have.json('ttl', 3640);
                                        expect(response.body.records).to.have.members(['"bar"']);
                                    }),
                            ]);
                        });

                        itShowsUpInPdnsAs('a.2', domain, 'TXT', ['"bar"'], 3640);
                    });

                    describe("cannot bulk-patch duplicate RRsets", function () {
                        var response;

                        before(function () {
                            response = chakram.patch(
                                '/domains/' + domain + '/rrsets/',
                                [
                                    {'subname': 'b.2', 'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                                    {'subname': 'b.2', 'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                                ]
                            );
                            return expect(response).to.have.status(400);
                        });

                        it("gives the right response", function () {
                            return expect(response).to.have.json([
                                { 'non_field_errors': [ 'Same subname and type as in position(s) 1, but must be unique.' ] },
                                { 'non_field_errors': [ 'Same subname and type as in position(s) 0, but must be unique.' ] },
                            ]);
                        });

                        it("does not touch records in the API", function () {
                            return chakram
                                .get('/domains/' + domain + '/rrsets/b.2.../TXT/')
                                .then(function (response) {
                                    expect(response).to.have.status(200);
                                    expect(response).to.have.json('ttl', 3650);
                                    expect(response.body.records).to.have.members(['"foo"']);
                                });
                        });

                        itShowsUpInPdnsAs('b.2', domain, 'TXT', ['"foo"'], 3650);
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
                });

                describe("cannot bulk-patch with invalid input", function () {
                    it("gives the right response for invalid type", function () {
                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 3650, 'type': 'INVALID', 'records': ['"foo"']}]
                        );
                        return expect(response).to.have.status(400);
                    });

                    it("gives the right response for invalid records", function () {
                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 3650, 'type': 'MX', 'records': ['1.2.3.4']}]
                        );
                        return expect(response).to.have.status(400);
                    });

                    it("gives the right response for records contents being null", function () {
                        var response = chakram.patch(
                            '/domains/' + domain + '/rrsets/',
                            [{'subname': 'a.2', 'ttl': 3650, 'type': 'MX', 'records': ['1.2.3.4', null]}]
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
