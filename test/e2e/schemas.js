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
        name: { type: "string" },
        owner: { type: "string" },
    },
    required: ["name", "owner", "keys"]
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
        value: { type: "string" },
        name: { type: "string" },
        created: { type: "string" },
        id: { type: "integer" },
    },
    required: ["value", "name", "created", "id"]
};

exports.tokens = {
    type: "array",
    items: exports.token
};

exports.TOKEN_REGEX = /^[A-Za-z0-9+/]{28}$/
