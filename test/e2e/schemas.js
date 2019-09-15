// For format specs, see https://json-schema.org/latest/json-schema-validation.html#rfc.section.7.3

exports.rootNoLogin = {
    properties: {
        login: { type: "string" },
        register: { type: "string" },
    }
};

exports.user = {
    properties: {
        created: {
            type: "string",
            format: "date-time"
        },
        email: {
            type: "string",
            format: "email"
        },
        id: { type: "integer" },
        limit_domains: { type: "integer" },
    },
    required: ["created", "email", "id", "limit_domains"]
};

exports.domain = {
    properties: {
        keys: {
            type: "array",
            items: {
                properties: {
                    dnskey:  { type: "string" },
                    ds: {
                        type: "array",
                        items: { type: "string" },
                        minItems: 1
                    },
                    flags:  { type: "integer" },
                    keytype:  { type: "string" },
                }
            },
            minItems: 1
        },
        name: {
            type: "string",
            format: "hostname"
        },
        created: {
            type: "string",
            format: "date-time"
        },
        published: {
            type: "string",
            format: "date-time"
        },
    },
    required: ["name", "keys", "created", "published"]
};

exports.rrset = {
    properties: {
        domain: { type: "string" },
        subname: { type: "string" },
        name: { type: "string" },
        records: {
            type: "array",
            items: { type: "string" },
            minItems: 1
        },
        ttl: {
            type: "integer",
            minimum: 1
        },
        type: { type: "string" },
    },
    required: ["domain", "subname", "name", "records", "ttl", "type"]
};

exports.rrsets = {
    type: "array",
    items: exports.rrset
};

exports.token = {
    properties: {
        auth_token: { type: "string" },
        name: { type: "string" },
        created: { type: "string" },
        id: { type: "integer" },
    },
    required: ["auth_token", "name", "created", "id"]
};

exports.tokens = {
    type: "array",
    items: exports.token
};

exports.TOKEN_REGEX = /^[A-Za-z0-9\.\-]{28}$/
