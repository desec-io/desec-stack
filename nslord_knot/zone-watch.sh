#!/usr/bin/env bash

set -euo pipefail

export PATH="/usr/sbin:/usr/bin:/bin:${PATH:-}"

import_dir="${DESECSTACK_NSLORD_KNOT_IMPORT_DIR:-/knot-import}"
catalog_file="/var/lib/knot/catalog.zone"
zone_dir="/var/lib/knot"

ns_ttl="${DESECSTACK_NSLORD_DEFAULT_TTL:-${DESECSTACK_NSMASTER_DEFAULT_NS_TTL:-3600}}"
soa_ttl="${DESECSTACK_NSLORD_DEFAULT_TTL:-${DESECSTACK_NSMASTER_DEFAULT_SOA_TTL:-3600}}"
soa_mname="${DESECSTACK_NSMASTER_DEFAULT_SOA_RNAME:-get.desec.io.}"
soa_rname="${DESECSTACK_NSMASTER_DEFAULT_SOA_RNAME:-get.desec.io.}"
default_ns_csv="${DESECSTACK_NSLORD_KNOT_DEFAULT_NS:-${DESECSTACK_NS:-}}"
default_ns_csv="${default_ns_csv// /,}"

IFS=',' read -r -a default_ns <<< "${default_ns_csv}"

key_ready_path() {
    local zone="${1%.}"
    echo "${import_dir}/${zone}/.ready"
}

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

    knotc -c /etc/knot/knot.conf zone-keys-load "${zone}" || true
}

import_keys() {
    [[ -d "${import_dir}" ]] || return
    for zone_dir_path in "${import_dir}"/*; do
        [[ -d "${zone_dir_path}" ]] || continue
        [[ -f "${zone_dir_path}/.import" ]] || continue

        zone="$(basename "${zone_dir_path}")"
        zone="${zone%.}."
        if [[ -f "${catalog_file}" ]] && ! awk 'toupper($3)=="PTR"{print $4}' "${catalog_file}" | grep -qx "${zone}"; then
            continue
        fi
        keep_tag="$(tr -d '[:space:]' < "${zone_dir_path}/.import" || true)"

        import_ok=true
        for keyfile in "${zone_dir_path}"/*.key; do
            [[ -f "${keyfile}" ]] || continue
            if ! keymgr -c /etc/knot/knot.conf "${zone}" import-bind "${keyfile}"; then
                import_ok=false
            fi
        done

        if [[ "${import_ok}" != true ]]; then
            sleep 1
            continue
        fi

        keep_keyid=""
        if [[ -n "${keep_tag}" ]]; then
            keep_keyid="$(keymgr -c /etc/knot/knot.conf "${zone}" list \
                | awk -v tag="${keep_tag}" '$2==tag {print $1; exit}')"
            if [[ -n "${keep_keyid}" ]]; then
                keymgr -c /etc/knot/knot.conf "${zone}" set "${keep_keyid}" \
                    ksk=yes zsk=yes publish=+0 ready=+0 active=+0 || true
            fi
        fi

        knotc -c /etc/knot/knot.conf zone-keys-load "${zone}" || true

        if [[ -n "${keep_tag}" ]]; then
            keymgr -c /etc/knot/knot.conf "${zone}" list | while read -r line; do
                keyid="$(awk '{print $1}' <<< "${line}")"
                tag="$(awk '{print $2}' <<< "${line}")"
                [[ -z "${keyid}" ]] && continue
                [[ -n "${keep_keyid}" && "${keyid}" == "${keep_keyid}" ]] && continue
                [[ "${tag}" == "${keep_tag}" ]] && continue
                keymgr -c /etc/knot/knot.conf "${zone}" delete "${keyid}" || true
            done
            keymgr -c /etc/knot/knot.conf "${zone}" del-all-old || true
            knotc -c /etc/knot/knot.conf zone-keys-load "${zone}" || true
        fi

        touch "$(key_ready_path "${zone}")"
        rm -f "${zone_dir_path}"/*.key "${zone_dir_path}"/*.private "${zone_dir_path}/.import" || true
    done
}

ensure_zone_key() {
    local zone="${1%.}"
    local zone_with_dot="${zone}."

    if keymgr -c /etc/knot/knot.conf "${zone_with_dot}" list | grep -q .; then
        return
    fi

    keymgr -c /etc/knot/knot.conf "${zone_with_dot}" generate \
        algorithm=13 ksk=yes zsk=yes >/dev/null 2>&1 || return

    keyid="$(keymgr -c /etc/knot/knot.conf "${zone_with_dot}" list \
        | awk 'NR==1 {print $1; exit}')"
    if [[ -n "${keyid}" ]]; then
        keymgr -c /etc/knot/knot.conf "${zone_with_dot}" set "${keyid}" \
            ksk=yes zsk=yes publish=+0 ready=+0 active=+0 || true
    fi

    knotc -c /etc/knot/knot.conf zone-keys-load "${zone}" || true
}

process_catalog() {
    [[ -f "${catalog_file}" ]] || return
    while read -r zone; do
        [[ -n "${zone}" ]] || continue
        local zone_base="${zone%.}"
        local ready_file
        ready_file="$(key_ready_path "${zone_base}")"
        if [[ -d "${import_dir}/${zone_base}" && ! -f "${ready_file}" ]]; then
            continue
        fi
        ensure_zone_key "${zone}"
        create_zonefile "${zone}"
    done < <(awk 'toupper($3)=="PTR"{print $4}' "${catalog_file}")
}

while true; do
    import_keys
    process_catalog
    sleep 1
done
