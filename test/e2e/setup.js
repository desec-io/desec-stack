var assert = require('assert');
var schemas = require("./schemas.js");

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

var chakram = require('/usr/local/lib/node_modules/chakram/lib/chakram.js');
var Q = require('q');

var packet = require('dns-packet');
var dgram = require('dgram');
var socket = dgram.createSocket('udp4');
after("tear down udp4 socket", function () { socket.close(); });

chakram.addMethod("body", function (respObj, expected) {
    var body = respObj.body;

    if (arguments.length === 1) {
        this.assert(
            body !== undefined && body !== null,
            'expected body to exist',
            'expected not to exist'
        );
    } else if (expected instanceof RegExp) {
        this.assert(
            expected.test(body),
            'expected body with value ' + body + ' to match regex ' + expected,
            'expected body with value ' + body + ' not to match regex ' + expected
        );
    } else if (typeof(expected) === 'function') {
        expected(body);
    } else {
        this.assert(
            body === expected,
            'expected body with value ' + body + ' to match ' + expected,
            'expected body with value ' + body + ' not to match ' + expected
        );
    }
});

var settings = {
    headers: {},
    followRedirect: false,
    baseUrl: '',
};

chakram.getRequestSettings = function () {
    return settings;
};

chakram.setRequestSettings = function (s) {
    settings = s;
    chakram.setRequestDefaults(settings);
};
chakram.setRequestSettings(settings);

chakram.setBaseUrl = function (url) {
    var s = chakram.getRequestSettings();
    s.baseUrl = url;
    chakram.setRequestSettings(s);
};

chakram.setRequestHeader = function (header, value) {
    var s = chakram.getRequestSettings();
    s.headers[header] = value;
    chakram.setRequestSettings(s);
};

// Make JSON format validators available
chakram.addSchemaFormat(require('tv4-formats'))

/*
 * DNS Resolver Testing
 */

// This structure will hold outstanding requests that
// we're are currently awaiting a response for.
// Note that there is no timeout mechanism; requests
// that (for any reason) do not receive responses will
// rot here indefinitely.
// Format: request id -> promise
var inflight = {};
var nextId = 1;

// Receive messages on our udp4 socket
socket.on('message', function (message) {
  try {
      // decode reply, find promise, remove from inflight and resolve
      var response = packet.decode(message);
      var promise = inflight[response.id];
      delete inflight[response.id];
      if (response.rcode !== 'NOERROR' && response.rcode !== 'NXDOMAIN') {
          promise.reject(response);
      } else {
          promise.resolve(response);
      }
  } catch (e) {
      // ignore faulty packets
  }
});

/**
 * Returns a promise that will eventually be resolved into an object representing nslord's answer for the RR set of
 * given name and type. For information about the object structure, check https://github.com/mafintosh/dns-packet.
 * In case of error, the promise is rejected and the dns-packet is given without further processing.
 * @param name full qualified domain name (no trailing dot)
 * @param type rrset type
 * @returns {promise|*|jQuery.promise|Promise}
 */
chakram.resolve = function (name, type) {
    var deferred = Q.defer();

    var buf = packet.encode({
        type: 'query',
        id: nextId,
        questions: [{
            type: type,
            class: 'IN',
            name: name
        }]
    });

    // FIXME contacting nslord for DNS responses. This can changed to nsmaster as soon as changes to the DNS are applied
    // immediately, i.e. before pdns HTTP responses return to the API.
    socket.send(buf, 0, buf.length, 53, process.env.DESECSTACK_IPV4_REAR_PREFIX16 + '.0.129');
    inflight[nextId] = deferred;
    nextId = (nextId + 1) % 65536;  // We don't care if id's are predictable in our test setting

    return deferred.promise;
};

/**
 * Returns a promise that will eventually be resolved into an array of strings, representing nslord's answer for the
 * RR set of given name and type. Note that not all record type are supported. Unsupported record types will be given
 * in javascripts default representation, which is most likely an unusable mess.
 * In case of error, the promise is rejected and the dns-packet is given without further processing. For further
 * information on the structure of this object, check https://github.com/mafintosh/dns-packet.
 * @param name full qualified domain name (no trailing dot)
 * @param type rrset type
 * @returns {promise|*|jQuery.promise|Promise}
 */
chakram.resolveStr = function (name, type) {
    var deferred = Q.defer();

    function convert (data, type) {
        switch (type) {
            case 'A': return data;
            case 'AAAA': return data;
            case 'MX': return data.preference + ' ' + data.exchange + '.';
            case 'TXT': return '"' + data + '"';
            // extend as needed
            default: return data.toString();  // uh-oh, messy & ugly
        }
    }

    chakram.resolve(name, type)
        .then(function (respObj) {
            var repr = [];

            // convert to str
            for (var a of respObj.answers) {
                repr.push(convert(a.data, type));
            }

            deferred.resolve(repr);
        })
        .catch(function (error) {
            deferred.reject(error);
        });

    return deferred.promise;
};

/**
 * A chainable property that does nothing. Can be used to increase readability of expectations.
 */
chakram.addProperty("dns", function(){});

/**
 * A shorthand for checking the TTL of an RR set.
 */
chakram.addMethod("ttl", function (respObj, expected) {
    this.assert(respObj.rcode === 'NOERROR', 'expected response to have rcode NOERROR');
    this.assert(respObj.answers.length > 0, 'expected response to have answers');
    this.assert(respObj.answers.every(function(elem) { return elem.ttl === parseInt(expected); }),
        'TTL of at least one answer in the DNS packet didn\'t match expected value of ' + expected + ': ' +
        respObj.answers.map(x => x.ttl));
});

exports.chakram = chakram;

/**
 * A test that checks record contents by querying the API endpoint
 */
function itPropagatesToTheApi(rrsets) {
    return it("propagates to the API", function () {
        promises = rrsets.map(function (rrset) {
            return chakram
                .get('/domains/' + rrset.domain + '/rrsets/' + rrset.subname + '.../' + rrset.type + '/')
                .then(function (response) {
                    if(rrset.records.length) {
                        chakram.expect(response).to.have.status(200);
                        chakram.expect(response).to.have.schema(schemas.rrset);
                        chakram.expect(response.body.records).to.have.members(rrset.records);
                        if (typeof rrset.ttl !== "undefined") {
                            chakram.expect(response).to.have.json('ttl', rrset.ttl);
                        }
                    } else {
                        assert(typeof rrset.ttl == "undefined");
                        chakram.expect(response).to.have.status(404);
                    }
                });
        });
        return chakram.waitFor(promises);
    });
}

/**
 * A test that checks DNS record contents
 */
function itShowsUpInPdnsAs(subname, domain, type, records, ttl) {
    var queryName = (typeof subname == 'undefined' ? '' : subname + '.') + domain;
    return it('shows up correctly in pdns for ' + subname + '|' + domain + '|' + type, function () {
        chakram.expect(chakram.resolveStr(queryName, type)).to.have.lengthOf(records.length);
        chakram.expect(chakram.resolveStr(queryName, type)).to.have.members(records);
        chakram.expect(chakram.resolveStr(queryName, type)).to.have.members(records.reverse());
        if (typeof ttl !== "undefined") {
            chakram.expect(chakram.resolve(queryName, type)).to.have.dns.ttl(ttl);
        }
        return chakram.wait();
    });
}

/**
 * Injects a CAPTCHA with correct solution
 */
function withCaptcha(f) {
    return chakram.post('/captcha/', {}).then(function (response) {
        return f({
            "id": response.body.id,
            "solution": response.body.content,
        });
    });
}

exports.itPropagatesToTheApi = itPropagatesToTheApi;
exports.itShowsUpInPdnsAs = itShowsUpInPdnsAs;
exports.withCaptcha = withCaptcha;
