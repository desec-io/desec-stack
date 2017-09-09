var chakram = require("./../setup.js").chakram;
var expect = chakram.expect;

describe("dyndns service", function () {

    var apiHomeSchema = {
        properties: {
            domains: {type: "string"},
            logout: {type: "string"},
            user: {type: "string"},
        },
        required: ["domains", "logout", "user"]
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

        var password, token;

        before(function () {
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

        var domain = 'e2etest-' + require("uuid").v4() + '.dedyn.io';
        describe("and domain [" + domain + "]", function () {

            before(function () {
                chakram.setRequestHeader('Authorization', 'Token ' + token);
                return expect(chakram.post('/domains/', {'name': domain})).to.have.status(201);
            });

            describe("dyndns12 endpoint with basic auth", function () {

                var apiAccessConfig;

                before(function () {
                    apiAccessConfig = {
                        headers: {
                            Host: 'desec.' + process.env.DESECSTACK_DOMAIN,
                            Authorization: 'Token ' + token,
                        }
                    };
                    chakram.setRequestHeader('Host', 'update.dedyn.' + process.env.DESECSTACK_DOMAIN);
                    chakram.setRequestHeader('Authorization', 'Basic ' + require('btoa')(domain + ':' + token));
                    chakram.setRequestHeader('Accept', '*/*');
                    chakram.setBaseUrl('https://www');
                });

                describe("updates without any arguments", function () {

                    before(function () {
                        var response = chakram.get('/'); // TODO also try other URLs
                        expect(response).to.have.body('good');
                        expect(response).to.have.status(200);
                        return chakram.wait();
                    });

                    it('propagate to the API', function () {
                        var response = chakram.get('/api/v1/domains/' + domain + '/rrsets/.../A/', apiAccessConfig);
                        return expect(response).to.have.json('records', [process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.127']);
                    });

                    it('propagate to pdns', function () {
                        expect(chakram.resolve(domain, 'A')).to.have.members([process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.127']);
                        expect(chakram.resolve(domain, 'AAAA')).to.be.empty;
                        return chakram.wait();
                    });

                });

                describe("v4 updates by query parameter", function () {

                    before(function () {
                        var response = chakram.get('/update/?ip=1.2.3.4');
                        expect(response).to.have.body('good');
                        expect(response).to.have.status(200);
                        return chakram.wait();
                    });

                    it('propagate to the API', function () {
                        var response = chakram.get('/api/v1/domains/' + domain + '/rrsets/.../A/', apiAccessConfig);
                        return expect(response).to.have.json('records', ['1.2.3.4']);
                    });

                    it('propagate to pdns', function () {
                        expect(chakram.resolve(domain, 'A')).to.have.members(['1.2.3.4']);
                        expect(chakram.resolve(domain, 'AAAA')).to.be.empty;
                        return chakram.wait();
                    });

                    describe("removes v4 address with empty query param", function () {

                        before(function () {
                            var response = chakram.get('/update/?ip=&ipv6=bade::affe');
                            expect(response).to.have.body('good');
                            expect(response).to.have.status(200);
                            return chakram.wait();
                        });

                        it('propagate to the API (v4)', function () {
                            var response = chakram.get('/api/v1/domains/' + domain + '/rrsets/.../A/', apiAccessConfig);
                            return expect(response).to.have.status(404);
                        });

                        it('propagate to the API (v6)', function () {
                            var response = chakram.get('/api/v1/domains/' + domain + '/rrsets/.../AAAA/', apiAccessConfig);
                            return expect(response).to.have.json('records', ['bade::affe']);
                        });

                        it('propagate to pdns', function () {
                            expect(chakram.resolve(domain, 'A')).to.be.empty;
                            expect(chakram.resolve(domain, 'AAAA')).to.have.members(['bade::affe']);
                            return chakram.wait();
                        });

                    });

                });

                describe("v6 updates by query parameter", function () {

                    before(function () {
                        var response = chakram.get('/update/?ipv6=dead::beef');
                        expect(response).to.have.body('good');
                        expect(response).to.have.status(200);
                        return chakram.wait();
                    });

                    it('propagate to the API', function () {
                        var response = chakram.get('/api/v1/domains/' + domain + '/rrsets/.../AAAA/', apiAccessConfig);
                        return expect(response).to.have.json('records', ['dead::beef']);
                    });

                    it('propagate to pdns', function () {
                        expect(chakram.resolve(domain, 'AAAA')).to.have.members(['dead::beef']);
                        expect(chakram.resolve(domain, 'A')).to.have.members([process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.127']);  // taken from the v4 connection
                        return chakram.wait();
                    });

                    describe("removes v6 address with empty query param", function () {

                        before(function () {
                            var response = chakram.get('/update/?ip=1.3.3.7&ipv6=');
                            expect(response).to.have.body('good');
                            expect(response).to.have.status(200);
                            return chakram.wait();
                        });

                        it('propagate to the API (v4)', function () {
                            var response = chakram.get('/api/v1/domains/' + domain + '/rrsets/.../A/', apiAccessConfig);
                            return expect(response).to.have.json('records', ['1.3.3.7']);
                        });

                        it('propagate to the API (v6)', function () {
                            var response = chakram.get('/api/v1/domains/' + domain + '/rrsets/.../AAAA/', apiAccessConfig);
                            return expect(response).to.have.status(404);
                        });

                        it('propagate to pdns', function () {
                            expect(chakram.resolve(domain, 'A')).to.have.members(['1.3.3.7']);
                            expect(chakram.resolve(domain, 'AAAA')).to.be.empty;
                            return chakram.wait();
                        });

                    });

                });

                describe("v4 and v6 updates by query parameter", function () {

                    before(function () {
                        var response = chakram.get('/update/?ip=192.168.1.1&ipv6=::1');
                        expect(response).to.have.body('good');
                        expect(response).to.have.status(200);
                        return chakram.wait();
                    });

                    it('propagate to the API', function () {
                        var response = chakram.get('/api/v1/domains/' + domain + '/rrsets/.../A/', apiAccessConfig);
                        expect(response).to.have.json('records', ['192.168.1.1']);
                        response = chakram.get('/api/v1/domains/' + domain + '/rrsets/.../AAAA/', apiAccessConfig);
                        expect(response).to.have.json('records', ['::1']);
                        return chakram.wait();
                    });

                    it('propagate to pdns', function () {
                        expect(chakram.resolve(domain, 'AAAA')).to.have.members(['::1']);
                        expect(chakram.resolve(domain, 'A')).to.have.members(['192.168.1.1']);
                        return chakram.wait();
                    });

                });

            });

        });

    });

});
