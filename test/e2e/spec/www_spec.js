var chakram = require("./../setup.js").chakram;
var expect = chakram.expect;

// obviously, I took this shamelessly and without further verification from stack overflow
// https://stackoverflow.com/a/17871737
var REGEX_IPV6_ADDRESS = /(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))/;

describe("www/nginx", function () {

    before(function () {
        var s = chakram.getRequestSettings();
        s.followRedirect = false;
        s.baseUrl = '';
        chakram.setRequestSettings(s);
    });

    describe("dedyn host", function () {

        before(function () {
            chakram.setRequestHeader('Host', 'dedyn.' + process.env.DESECSTACK_DOMAIN);
        });

        it("redirects to the desec host", function () {

            [
                'https://' + process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.128/',
                'http://' + process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.128/',
                'https://[' + process.env.DESECSTACK_IPV6_ADDRESS + ']/',
                'http://[' + process.env.DESECSTACK_IPV6_ADDRESS + ']/',
            ].forEach(function (url) {
                var response = chakram.get(url);
                expect(response).to.have.status(301);
                expect(response).to.have.header('Location', 'https://desec.' + process.env.DESECSTACK_DOMAIN + '/');
            });

            return chakram.wait();
        });

    });

    describe("checkip.dedyn host", function () {

        before(function () {
            chakram.setRequestHeader('Host', 'checkip.dedyn.' + process.env.DESECSTACK_DOMAIN);
        });

        describe("contacted through SSL/TLS", function () {

            it('returns the ipv4 address when contacted through ipv4', function () {
                var response = chakram.get('https://' + process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.128/');
                return expect(response).to.have.body(process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.127');
            });

            it('returns an ipv6 address when contacted through ipv6', function () {
                var response = chakram.get('https://[' + process.env.DESECSTACK_IPV6_ADDRESS + ']/');

                // it's hard to find out which IPv6 address we actually expect here
                // and as we are inside the docker network anyway (that is, we are
                // topologically not in the same place as the end user), it's hard
                // if the correct address is returned. Hence, we will stick to some
                // simple tests.
                expect(response).to.have.body(REGEX_IPV6_ADDRESS);
                return chakram.wait();
            });

        });

        describe("contacted without encryption", function () {

            it('redirects to SSL/TLS when contacted through ipv4', function () {
                var response = chakram.get('http://' + process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.128/');
                expect(response).to.have.status(301);
                expect(response).to.have.header('Location', 'https://checkip.dedyn.' + process.env.DESECSTACK_DOMAIN + '/');
                return chakram.wait();
            });

            it('redirects to SSL/TLS when contacted through ipv6', function () {
                var response = chakram.get('http://[' + process.env.DESECSTACK_IPV6_ADDRESS + ']/');
                expect(response).to.have.status(301);
                expect(response).to.have.header('Location', 'https://checkip.dedyn.' + process.env.DESECSTACK_DOMAIN + '/');
                return chakram.wait();
            });

        });

    });

    describe("checkipv4.dedyn host", function () {

        before(function () {
            chakram.setRequestHeader('Host', 'checkipv4.dedyn.' + process.env.DESECSTACK_DOMAIN);
        });

        it('returns the ipv4 address when contacted through ipv4', function () {
            var response = chakram.get('https://' + process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.128/');
            return expect(response).to.have.body(process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.127');
        });

        it('redirects to SSL/TLS when concated without encryption', function () {
            var response = chakram.get('http://' + process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.128/');
            expect(response).to.have.status(301);
            expect(response).to.have.header('Location', 'https://checkipv4.dedyn.' + process.env.DESECSTACK_DOMAIN + '/');
            return chakram.wait();
        });

        it('closes the connection when contacted through ipv6', function () {
            var response = chakram.get('https://[' + process.env.DESECSTACK_IPV6_ADDRESS + ']/');
            return expect(response).to.not.have.a.body();
        });

    });

    describe("checkipv6.dedyn host", function () {

        before(function () {
            chakram.setRequestHeader('Host', 'checkipv6.dedyn.' + process.env.DESECSTACK_DOMAIN);
        });

        it('closes the connection when contacted through ipv4', function () {
            var response = chakram.get('https://' + process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.128/');
            return expect(response).to.not.have.a.body();
        });

        it('redirects to SSL/TLS when concated without encryption', function () {
            var response = chakram.get('http://[' + process.env.DESECSTACK_IPV6_ADDRESS + ']/');
            expect(response).to.have.status(301);
            expect(response).to.have.header('Location', 'https://checkipv6.dedyn.' + process.env.DESECSTACK_DOMAIN + '/');
            return chakram.wait();
        });

        it('returns an ipv6 address when contacted through ipv6', function () {
            var response = chakram.get('https://[' + process.env.DESECSTACK_IPV6_ADDRESS + ']/');

            // it's hard to find out which IPv6 address we actually expect here
            // and as we are inside the docker network anyway (that is, we are
            // topologically not in the same place as the end user), it's hard
            // if the correct address is returned. Hence, we will stick to some
            // simple tests.
            expect(response).to.have.body(REGEX_IPV6_ADDRESS);
            return chakram.wait();
        });

    });

    describe("desec host", function () {

        before(function () {
            chakram.setRequestHeader('Host', 'desec.' + process.env.DESECSTACK_DOMAIN);
        });

        it.skip("is alive", function () {  // disabled as we receive 503 while webapp is being built
            var response = chakram.get('https://www/');
            return expect(response).to.have.status(200);
        });

        it("has security headers", function () {
            var response = chakram.get('https://www/');
            expect(response).to.have.header('Strict-Transport-Security', 'max-age=31536000; includeSubdomains; preload');
            expect(response).to.have.header('Content-Security-Policy', "default-src 'self'; frame-src 'none'; connect-src 'self'; font-src 'self'; img-src 'self' data:; media-src data:; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; base-uri 'self'; frame-ancestors 'none'; block-all-mixed-content; form-action 'none';");
            expect(response).to.have.header('X-Frame-Options', 'deny');
            expect(response).to.have.header('X-Content-Type-Options', 'nosniff');
            expect(response).to.have.header('Referrer-Policy', 'strict-origin-when-cross-origin');
            expect(response).to.have.header('X-XSS-Protection', '1; mode=block');
            return chakram.wait();
        });

    });

});
