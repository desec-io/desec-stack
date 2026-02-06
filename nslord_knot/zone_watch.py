#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Callable, List, Optional


logger = logging.getLogger("zone_watch")
DEFAULT_PATH = "/usr/sbin:/usr/bin:/bin"


class ZoneWatcher:
    def __init__(
        self,
        *,
        import_dir: str,
        catalog_file: str,
        zone_dir: str,
        ns_ttl: int,
        soa_ttl: int,
        soa_mname: str,
        soa_rname: str,
        default_ns: List[str],
        knot_conf: str = "/etc/knot/knot.conf",
        time_fn: Callable[[], float] = time.time,
        sleep_fn: Callable[[float], None] = time.sleep,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        command_timeout: float = 2.0,
    ):
        self.import_dir = Path(import_dir)
        self.catalog_file = Path(catalog_file)
        self.zone_dir = Path(zone_dir)
        self.ns_ttl = ns_ttl
        self.soa_ttl = soa_ttl
        self.soa_mname = soa_mname
        self.soa_rname = soa_rname
        self.default_ns = default_ns
        self.knot_conf = knot_conf
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn
        self.runner = runner
        self.command_timeout = command_timeout

    def run_cmd(self, args: List[str]) -> subprocess.CompletedProcess:
        try:
            return self.runner(
                args,
                capture_output=True,
                text=True,
                timeout=self.command_timeout,
                env={**os.environ, "PATH": DEFAULT_PATH},
            )
        except FileNotFoundError:
            logger.warning("command not found: %s", " ".join(args))
            return subprocess.CompletedProcess(args, 127, "", "not found")
        except subprocess.TimeoutExpired:
            logger.warning("command timeout: %s", " ".join(args))
            return subprocess.CompletedProcess(args, 1, "", "timeout")

    def key_ready_path(self, zone: str) -> Path:
        zone_base = zone.rstrip(".")
        return self.import_dir / zone_base / ".ready"

    def read_catalog_zones(self) -> List[str]:
        if not self.catalog_file.exists():
            return []
        zones: List[str] = []
        for line in self.catalog_file.read_text(encoding="ascii", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            zone = ""
            if parts[2].upper() == "PTR":
                zone = parts[3]
            elif len(parts) >= 5 and parts[3].upper() == "PTR":
                zone = parts[4]
            else:
                continue
            if not zone.endswith("."):
                zone = f"{zone}."
            zones.append(zone)
        return zones

    def _zonefile_paths(self, zone: str) -> tuple[Path, Path, str]:
        zone_base = zone.rstrip(".")
        zone_with_dot = f"{zone_base}."
        zonefile = self.zone_dir / f"{zone_base}.zone"
        zonefile_with_dot = self.zone_dir / f"{zone_with_dot}.zone"
        return zonefile, zonefile_with_dot, zone_with_dot

    def create_zonefile(self, zone: str) -> None:
        zonefile, zonefile_with_dot, zone_with_dot = self._zonefile_paths(zone)
        if zonefile.exists() and zonefile_with_dot.exists():
            return

        soa_serial = int(self.time_fn()) + 120
        lines = [
            f"$ORIGIN {zone_with_dot}",
            f"@ {self.soa_ttl} IN SOA {self.soa_mname} {self.soa_rname} {soa_serial} 86400 3600 2419200 3600",
        ]
        for ns in self.default_ns:
            ns = ns.strip()
            if not ns:
                continue
            if not ns.endswith("."):
                ns = f"{ns}."
            lines.append(f"@ {self.ns_ttl} IN NS {ns}")
        content = "\n".join(lines) + "\n"

        zonefile.write_text(content, encoding="ascii")
        zonefile_with_dot.write_text(content, encoding="ascii")

        self.run_cmd(["chown", "knot:knot", str(zonefile), str(zonefile_with_dot)])
        self.run_cmd(["knotc", "zone-reload", zone.rstrip(".")])
        self.run_cmd(["knotc", "-c", self.knot_conf, "zone-keys-load", zone.rstrip(".")])

    def import_keys(self) -> None:
        if not self.import_dir.is_dir():
            return

        catalog_zones = set(self.read_catalog_zones())

        for entry in self.import_dir.iterdir():
            if not entry.is_dir():
                continue
            import_marker = entry / ".import"
            if not import_marker.is_file():
                continue

            zone = entry.name.rstrip(".") + "."
            if self.catalog_file.exists() and zone not in catalog_zones:
                continue

            keep_tag = import_marker.read_text(encoding="ascii", errors="ignore").strip()
            import_ok = True
            for keyfile in entry.glob("*.key"):
                result = self.run_cmd(
                    ["keymgr", "-c", self.knot_conf, zone, "import-bind", str(keyfile)]
                )
                if result.returncode != 0:
                    import_ok = False

            if not import_ok:
                logger.warning("import_keys retry zone=%s status=import_failed", zone)
                self.sleep_fn(1)
                continue

            keep_keyid = ""
            if keep_tag:
                result = self.run_cmd(["keymgr", "-c", self.knot_conf, zone, "list"])
                for line in result.stdout.splitlines():
                    fields = line.split()
                    if len(fields) >= 2 and fields[1] == keep_tag:
                        keep_keyid = fields[0]
                        break
                if keep_keyid:
                    self.run_cmd(
                        [
                            "keymgr",
                            "-c",
                            self.knot_conf,
                            zone,
                            "set",
                            keep_keyid,
                            "ksk=yes",
                            "zsk=yes",
                            "publish=+0",
                            "ready=+0",
                            "active=+0",
                        ]
                    )

            self.run_cmd(["knotc", "-c", self.knot_conf, "zone-keys-load", zone])

            if keep_tag:
                result = self.run_cmd(["keymgr", "-c", self.knot_conf, zone, "list"])
                for line in result.stdout.splitlines():
                    fields = line.split()
                    if len(fields) < 2:
                        continue
                    keyid, tag = fields[0], fields[1]
                    if keep_keyid and keyid == keep_keyid:
                        continue
                    if tag == keep_tag:
                        continue
                    self.run_cmd(
                        ["keymgr", "-c", self.knot_conf, zone, "delete", keyid]
                    )
                self.run_cmd(["keymgr", "-c", self.knot_conf, zone, "del-all-old"])
                self.run_cmd(["knotc", "-c", self.knot_conf, "zone-keys-load", zone])

            ready_path = self.key_ready_path(zone)
            ready_path.parent.mkdir(parents=True, exist_ok=True)
            ready_path.touch()
            for keyfile in entry.glob("*.key"):
                try:
                    keyfile.unlink()
                except FileNotFoundError:
                    pass
            for keyfile in entry.glob("*.private"):
                try:
                    keyfile.unlink()
                except FileNotFoundError:
                    pass
            try:
                import_marker.unlink()
            except FileNotFoundError:
                pass

    def ensure_zone_key(self, zone: str) -> bool:
        zone_base = zone.rstrip(".")
        zone_with_dot = f"{zone_base}."
        result = self.run_cmd(["keymgr", "-c", self.knot_conf, zone_with_dot, "list"])
        if result.stdout.strip():
            return True

        result = self.run_cmd(
            [
                "keymgr",
                "-c",
                self.knot_conf,
                zone_with_dot,
                "generate",
                "algorithm=13",
                "ksk=yes",
                "zsk=yes",
            ]
        )
        if result.returncode != 0:
            logger.warning("ensure_zone_key generate failed zone=%s", zone_with_dot)
            return False

        result = self.run_cmd(["keymgr", "-c", self.knot_conf, zone_with_dot, "list"])
        keyid = ""
        for line in result.stdout.splitlines():
            fields = line.split()
            if fields:
                keyid = fields[0]
                break
        if keyid:
            self.run_cmd(
                [
                    "keymgr",
                    "-c",
                    self.knot_conf,
                    zone_with_dot,
                    "set",
                    keyid,
                    "ksk=yes",
                    "zsk=yes",
                    "publish=+0",
                    "ready=+0",
                    "active=+0",
                ]
            )

        self.run_cmd(["knotc", "-c", self.knot_conf, "zone-keys-load", zone_base])
        return True

    def process_catalog(self) -> None:
        zones = self.read_catalog_zones()
        for zone in zones:
            if not zone:
                continue
            zone_base = zone.rstrip(".")
            ready_file = self.key_ready_path(zone_base)
            if (self.import_dir / zone_base).is_dir() and not ready_file.exists():
                continue
            self.ensure_zone_key(zone)
            self.create_zonefile(zone)

    def loop(self) -> None:
        logger.info(
            "zone watcher start catalog=%s import_dir=%s zone_dir=%s",
            self.catalog_file,
            self.import_dir,
            self.zone_dir,
        )
        while True:
            try:
                self.import_keys()
                self.process_catalog()
            except Exception:
                logger.exception("zone watcher loop error")
            self.sleep_fn(1)


def _env_int(name: str, default: str) -> int:
    return int(os.environ.get(name, default))


def main() -> None:
    os.environ["PATH"] = f"{DEFAULT_PATH}:{os.environ.get('PATH', '')}"
    ns_ttl = _env_int(
        "DESECSTACK_NSLORD_DEFAULT_TTL",
        os.environ.get("DESECSTACK_NSMASTER_DEFAULT_NS_TTL", "3600"),
    )
    soa_ttl = _env_int(
        "DESECSTACK_NSLORD_DEFAULT_TTL",
        os.environ.get("DESECSTACK_NSMASTER_DEFAULT_SOA_TTL", "3600"),
    )
    soa_mname = os.environ.get("DESECSTACK_NSMASTER_DEFAULT_SOA_RNAME", "get.desec.io.")
    soa_rname = os.environ.get("DESECSTACK_NSMASTER_DEFAULT_SOA_RNAME", "get.desec.io.")
    default_ns_csv = os.environ.get(
        "DESECSTACK_NSLORD_KNOT_DEFAULT_NS", os.environ.get("DESECSTACK_NS", "")
    )
    default_ns_csv = default_ns_csv.replace(" ", ",")
    default_ns = [ns for ns in default_ns_csv.split(",") if ns]

    level_name = os.environ.get("ZONE_WATCH_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        watcher = ZoneWatcher(
            import_dir=os.environ.get("DESECSTACK_NSLORD_KNOT_IMPORT_DIR", "/knot-import"),
            catalog_file="/var/lib/knot/catalog.zone",
            zone_dir="/var/lib/knot",
            ns_ttl=ns_ttl,
            soa_ttl=soa_ttl,
            soa_mname=soa_mname,
            soa_rname=soa_rname,
            default_ns=default_ns,
        )
        watcher.loop()
    except Exception:
        logger.exception("zone watcher fatal error")


if __name__ == "__main__":
    main()
