from pathlib import Path

from nslord_knot.zone_watch import ZoneWatcher


class DummyRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, args, capture_output=True, text=True, **kwargs):
        self.calls.append(list(args))

        class Result:
            returncode = 0
            stdout = ""

        return Result()


def _watcher(tmp_path: Path, runner=None):
    return ZoneWatcher(
        import_dir=str(tmp_path / "import"),
        catalog_file=str(tmp_path / "catalog.zone"),
        zone_dir=str(tmp_path / "zones"),
        ns_ttl=3600,
        soa_ttl=3600,
        soa_mname="ns1.example.",
        soa_rname="hostmaster.example.",
        default_ns=["ns1.example.", "ns2.example."],
        runner=runner or DummyRunner(),
        time_fn=lambda: 1000,
        sleep_fn=lambda *_: None,
    )


def test_read_catalog_zones_parses_ptr(tmp_path):
    catalog = tmp_path / "catalog.zone"
    catalog.write_text(
        "\n".join(
            [
                "; comment",
                "abc.zones 0 IN PTR zone1.test.",
                "def.zones 0 IN PTR zone2.test",
                "ignored 0 IN TXT hello",
            ]
        ),
        encoding="ascii",
    )
    watcher = _watcher(tmp_path)
    zones = watcher.read_catalog_zones()
    assert zones == ["zone1.test.", "zone2.test."]


def test_create_zonefile_writes_both_files(tmp_path):
    (tmp_path / "zones").mkdir(parents=True)
    watcher = _watcher(tmp_path)
    watcher.create_zonefile("example.test.")

    zonefile = tmp_path / "zones" / "example.test.zone"
    zonefile_with_dot = tmp_path / "zones" / "example.test..zone"
    assert zonefile.exists()
    assert zonefile_with_dot.exists()
    content = zonefile.read_text(encoding="ascii")
    assert "$ORIGIN example.test." in content
    assert "SOA ns1.example. hostmaster.example. 1120" in content
    assert "IN NS ns1.example." in content
    assert "IN NS ns2.example." in content


def test_process_catalog_skips_key_not_ready(tmp_path):
    runner = DummyRunner()
    watcher = _watcher(tmp_path, runner=runner)

    (tmp_path / "zones").mkdir(parents=True)
    import_dir = tmp_path / "import"
    import_dir.mkdir()
    (import_dir / "zone1.test").mkdir()
    catalog = tmp_path / "catalog.zone"
    catalog.write_text(
        "abc.zones 0 IN PTR zone1.test.\nxyz.zones 0 IN PTR zone2.test.\n",
        encoding="ascii",
    )

    called = {"ensure": [], "create": []}

    def ensure_zone_key(zone):
        called["ensure"].append(zone)
        return True

    def create_zonefile(zone):
        called["create"].append(zone)

    watcher.ensure_zone_key = ensure_zone_key
    watcher.create_zonefile = create_zonefile

    watcher.process_catalog()

    assert called["ensure"] == ["zone2.test."]
    assert called["create"] == ["zone2.test."]
