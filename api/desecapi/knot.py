"""
Thin wrapper around libknot's control socket for managing zones on nsmaster (Knot DNS).

Replaces the nsmaster-facing functions that previously used the PowerDNS HTTP API:

  Old (pdns.py, server=NSMASTER)       New (knot.py)
  ─────────────────────────────────    ──────────────────────────────────────────
  create_zone_master(name)             create_zone(name)
  delete_zone_master(name)             delete_zone(name)
  axfr_to_master(zone)                 retrieve_zone(name)
  get_serials()                        get_serials()
  update_catalog / construct_catalog   (removed — Knot updates catalog automatically)
"""

import os

from libknot.control import KnotCtl, KnotCtlType

SOCKET_PATH = os.environ.get("DESECSTACK_NSMASTER_SOCKET", "/run/knot/knot.sock")
SLAVE_TEMPLATE = "slave"  # must match template id in knot.conf


def _ctl() -> KnotCtl:
    """Return a connected KnotCtl instance (caller must close it)."""
    ctl = KnotCtl()
    ctl.connect(SOCKET_PATH)
    return ctl


def create_zone(name: str) -> None:
    """Register a new slave zone on nsmaster."""
    name = name.rstrip(".") + "."
    ctl = _ctl()
    try:
        ctl.send_block(cmd="conf-begin")
        ctl.receive_block()
        ctl.send_block(cmd="conf-set", section="zone", identifier=name)
        ctl.receive_block()
        ctl.send_block(
            cmd="conf-set",
            section="zone",
            identifier=name,
            item="template",
            data=SLAVE_TEMPLATE,
        )
        ctl.receive_block()
        ctl.send_block(cmd="conf-commit")
        ctl.receive_block()
    finally:
        ctl.send(KnotCtlType.END)
        ctl.close()


def delete_zone(name: str) -> None:
    """Remove a slave zone from nsmaster."""
    name = name.rstrip(".") + "."
    ctl = _ctl()
    try:
        ctl.send_block(cmd="conf-begin")
        ctl.receive_block()
        ctl.send_block(cmd="conf-unset", section="zone", identifier=name)
        ctl.receive_block()
        ctl.send_block(cmd="conf-commit")
        ctl.receive_block()
    finally:
        ctl.send(KnotCtlType.END)
        ctl.close()


def retrieve_zone(name: str) -> None:
    """Trigger an AXFR/IXFR retrieval from nslord for the given zone."""
    name = name.rstrip(".") + "."
    ctl = _ctl()
    try:
        ctl.send_block(cmd="zone-retransfer", zone=name)
        ctl.receive_block()
    finally:
        ctl.send(KnotCtlType.END)
        ctl.close()


def get_serials() -> dict[str, int]:
    """Return {zone_name: serial} for all zones known to nsmaster."""
    ctl = _ctl()
    try:
        ctl.send_block(cmd="zone-status")
        data = ctl.receive_block()
        return {
            zone: int(info.get("serial", 0))
            for zone, info in data.items()
            if info.get("serial")
        }
    finally:
        ctl.send(KnotCtlType.END)
        ctl.close()
