#!/usr/bin/env bash

set -u -o pipefail

export PATH="/usr/sbin:/usr/bin:/bin:${PATH:-}"

catalog_file="/var/lib/knot/catalog.zone"
zone_dir="/var/lib/knot"

ns_ttl="${DESECSTACK_NSLORD_DEFAULT_TTL:-${DESECSTACK_NSMASTER_DEFAULT_NS_TTL:-3600}}"
soa_ttl="${DESECSTACK_NSLORD_DEFAULT_TTL:-${DESECSTACK_NSMASTER_DEFAULT_SOA_TTL:-3600}}"
soa_mname="${DESECSTACK_NSMASTER_DEFAULT_SOA_RNAME:-get.desec.io.}"
soa_rname="${DESECSTACK_NSMASTER_DEFAULT_SOA_RNAME:-get.desec.io.}"
default_ns_csv="${DESECSTACK_NSLORD_KNOT_DEFAULT_NS:-${DESECSTACK_NS:-}}"
default_ns_csv="${default_ns_csv// /,}"

IFS=',' read -r -a default_ns <<< "${default_ns_csv}"

create_zonefile() {
    local zone="${1%.}"
    local zone_with_dot="${zone}."
    local zonefile="${zone_dir}/${zone}.zone"
    local zonefile_with_dot="${zone_dir}/${zone_with_dot}.zone"
    local soa_serial

    if [[ -f "${zonefile}" && -f "${zonefile_with_dot}" ]]; then
        return
    fi

    soa_serial="$(( $(date +%s) + 120 ))"

    {
        printf "\$ORIGIN %s\n" "${zone_with_dot}"
        printf "@ %s IN SOA %s %s %s 86400 3600 2419200 3600\n" "${soa_ttl}" "${soa_mname}" "${soa_rname}" "${soa_serial}"
        for ns in "${default_ns[@]}"; do
            if [[ -n "${ns}" ]]; then
                if [[ "${ns}" != *. ]]; then
                    ns="${ns}."
                fi
                printf "@ %s IN NS %s\n" "${ns_ttl}" "${ns}"
            fi
        done
    } | tee "${zonefile}" > "${zonefile_with_dot}"

    chown knot:knot "${zonefile}" "${zonefile_with_dot}" || true
    knotc zone-reload "${zone}" || true
}

while true; do
    if [[ -f "${catalog_file}" ]]; then
        while read -r zone; do
            if [[ -n "${zone}" ]]; then
                create_zonefile "${zone}"
            fi
        done < <(awk 'toupper($3)=="PTR"{print $4}' "${catalog_file}")
    fi
    sleep 1
done
