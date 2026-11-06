import pytest
from engine.linux_battery import LinuxBatterySampler
from engine.models import BatterySnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path, value):
    """Write a sysfs-style single-value file."""
    path.write_text(str(value))


def _make_bat(tmp_path, fields: dict, name="BAT0", with_type=True):
    bat = tmp_path / name
    bat.mkdir()
    if with_type:
        # B8: real sysfs always exposes a `type` file. Emit it by default so
        # the type-based detection path is what most tests exercise.
        _write(bat / "type", "Battery")
    for k, v in fields.items():
        _write(bat / k, v)
    return bat


def _make_ac(tmp_path, online="0", name="AC", with_type=True):
    ac = tmp_path / name
    ac.mkdir()
    if with_type:
        _write(ac / "type", "Mains")
    if online is not None:
        _write(ac / "online", online)
    return ac


# ---------------------------------------------------------------------------
# Existing tests (kept, extended)
# ---------------------------------------------------------------------------

def test_battery_sampler_happy_path(tmp_path):
    _make_bat(
        tmp_path,
        {
            "capacity": "85",
            "status": "Discharging",
            "power_now": "10000000",           # µW -> 10 W
            "energy_now": "50000000",          # µWh -> 50 Wh
            "energy_full": "50000000",         # 50 Wh
            "energy_full_design": "60000000",  # 60 Wh
        },
    )
    _make_ac(tmp_path, online="0")

    snapshot = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snapshot is not None
    assert snapshot.capacity == 85
    assert snapshot.online is False
    assert snapshot.status == "Discharging"
    assert snapshot.power_watts == pytest.approx(10.0)
    # 50 Wh / 10 W = 5 h — now guaranteed to be populated (see B1)
    assert snapshot.hours_left == pytest.approx(5.0)
    assert snapshot.health_percent == pytest.approx(83.3, abs=0.1)


def test_battery_charge_fallback(tmp_path):
    _make_bat(
        tmp_path,
        {
            "capacity": "75",
            "status": "Discharging",
            "charge_now": "3000000",          # µAh -> 3 Ah
            "current_now": "1000000",         # µA  -> 1 A
            "charge_full": "4000000",         # 4 Ah
            "charge_full_design": "5000000",  # 5 Ah
            # NOTE: no voltage_now -> B3 cannot derive watts.
        },
    )
    _make_ac(tmp_path, online="0")

    snapshot = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snapshot is not None
    assert snapshot.capacity == 75
    assert snapshot.status == "Discharging"
    assert snapshot.hours_left == pytest.approx(3.0, abs=0.01)   # 3 Ah / 1 A
    assert snapshot.health_percent == pytest.approx(80.0, abs=0.1)
    # B3: without voltage_now there's nothing to derive watts from.
    assert snapshot.power_watts is None


def test_linux_desktop_fallback_no_battery(tmp_path):
    """Only an AC adapter exists (e.g. a desktop) -> no snapshot."""
    _make_ac(tmp_path, online="1")

    assert LinuxBatterySampler(
        sys_path=str(tmp_path)
    ).get_battery_snapshot() is None


def test_linux_desktop_fallback_empty_dir(tmp_path):
    """No power_supply entries at all -> no snapshot."""
    assert LinuxBatterySampler(
        sys_path=str(tmp_path)
    ).get_battery_snapshot() is None


# ---------------------------------------------------------------------------
# B1: hours_left is gated on status == "Discharging", not on `online`
# ---------------------------------------------------------------------------

def test_b1_charging_status_suppresses_hours_left_despite_online_false(tmp_path):
    """USB-C quirk: status=Charging while AC reports online=0."""
    _make_bat(
        tmp_path,
        {
            "status": "Charging",
            "power_now": "5000000",       # 5 W
            "energy_now": "50000000",     # 50 Wh
        },
    )
    _make_ac(tmp_path, online="0")        # AC file lies

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.status == "Charging"
    assert snap.online is False
    assert snap.hours_left is None


@pytest.mark.parametrize("status", ["Full", "Not charging", "Unknown"])
def test_b1_non_discharging_statuses_have_no_hours_left(tmp_path, status):
    _make_bat(
        tmp_path,
        {
            "status": status,
            "power_now": "5000000",
            "energy_now": "50000000",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.status == status
    assert snap.hours_left is None


def test_b1_discharging_status_still_computes_hours_left_when_online(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "power_now": "10000000",      # 10 W
            "energy_now": "50000000",     # 50 Wh
        },
    )
    _make_ac(tmp_path, online="1")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.online is True
    assert snap.status == "Discharging"
    assert snap.hours_left == pytest.approx(5.0)


def test_b1_charge_fallback_respects_status_gate(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Charging",
            "charge_now": "3000000",      # 3 Ah
            "current_now": "1000000",     # 1 A
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.hours_left is None


# ---------------------------------------------------------------------------
# B2: negative power / current is treated as magnitude
# ---------------------------------------------------------------------------

def test_b2_negative_power_now_reports_positive_watts(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "power_now": "-10000000",     # -10 W
            "energy_now": "50000000",     # 50 Wh
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.power_watts == pytest.approx(10.0)
    assert snap.hours_left == pytest.approx(5.0)


def test_b2_negative_current_in_charge_fallback(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "charge_now": "3000000",       # 3 Ah
            "current_now": "-1000000",     # -1 A
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.hours_left == pytest.approx(3.0)


def test_b2_negative_current_with_voltage_derives_positive_watts(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "energy_now": "50000000",        # 50 Wh
            "current_now": "-1000000",       # -1 A
            "voltage_now": "12000000",       # 12 V
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.power_watts == pytest.approx(12.0)
    assert snap.hours_left == pytest.approx(round(50 / 12, 2))


# ---------------------------------------------------------------------------
# B3: charge-based path derives watts from I*V when voltage_now exists
# ---------------------------------------------------------------------------

def test_b3_charge_fallback_derives_watts_from_voltage(tmp_path):
    """Charge battery with voltage_now -> power_watts is populated, not None."""
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "charge_now": "3000000",       # 3 Ah
            "current_now": "1000000",      # 1 A
            "voltage_now": "12000000",     # 12 V
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    # B3: 1 A * 12 V = 12 W
    assert snap.power_watts == pytest.approx(12.0)
    # hours_left still comes from charge/current, not from watts
    assert snap.hours_left == pytest.approx(3.0)


def test_b3_charge_fallback_negative_current_with_voltage_abs_watts(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "charge_now": "3000000",
            "current_now": "-1000000",     # -1 A
            "voltage_now": "12000000",     # 12 V
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.power_watts == pytest.approx(12.0)


def test_b3_charge_fallback_without_voltage_still_none(tmp_path):
    """Sanity: B3 only fires when voltage_now is present."""
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "charge_now": "3000000",
            "current_now": "1000000",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.power_watts is None


# ---------------------------------------------------------------------------
# B4: "Not charging" (charge limit) counts as online without an AC folder
# ---------------------------------------------------------------------------

def test_b4_not_charging_counts_as_online_when_no_ac_folder(tmp_path):
    """A battery-limited laptop on wall power: status='Not charging', no AC."""
    _make_bat(tmp_path, {"status": "Not charging"})
    # No AC directory.

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.status == "Not charging"
    assert snap.online is True     # B4: was False before


# ---------------------------------------------------------------------------
# B6 (refactored contract): unreadable / non-listable sys_path now raises
# ---------------------------------------------------------------------------

def test_b6_permission_error_on_listdir_raises(tmp_path, monkeypatch):
    """Fatal: unreadable sys_path must bubble PermissionError to the caller."""
    import os as _os

    def boom(path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(_os, "listdir", boom)

    with pytest.raises(PermissionError):
        LinuxBatterySampler(sys_path=str(tmp_path))


# ---------------------------------------------------------------------------
# B7: unreadable AC "online" file falls back to status inference
# ---------------------------------------------------------------------------

def test_b7_ac_online_unreadable_falls_back_to_status(tmp_path):
    """AC folder present but the 'online' file is missing -> infer from status."""
    _make_bat(tmp_path, {"status": "Charging"})
    _make_ac(tmp_path, online=None)   # no online file written

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    # Before B7: None == "1" -> online=False while charging.
    assert snap.online is True
    assert snap.status == "Charging"


def test_b7_ac_online_unreadable_not_charging_infers_online(tmp_path):
    """Same fallback, charge-limit case: should be online via B4/B7."""
    _make_bat(tmp_path, {"status": "Not charging"})
    _make_ac(tmp_path, online=None)

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.online is True


def test_b7_ac_online_unreadable_discharging_infers_offline(tmp_path):
    _make_bat(tmp_path, {"status": "Discharging"})
    _make_ac(tmp_path, online=None)

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.online is False


# ---------------------------------------------------------------------------
# Refactored contract: online is None when neither source can be read
# ---------------------------------------------------------------------------

def test_online_is_none_when_ac_missing_and_status_missing(tmp_path):
    """Partial error: no AC folder, no status file -> honest None."""
    _make_bat(tmp_path, {})   # battery exists but no status file
    # No AC directory.

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap is not None
    assert snap.status is None
    assert snap.online is None


# ---------------------------------------------------------------------------
# B8: detection via the `type` file, with name-based fallback
# ---------------------------------------------------------------------------

def test_b8_usb_c_folder_detected_via_type_file(tmp_path):
    """USB-C charger folder name (ucsi-source-psy-*) doesn't match AC*; type does."""
    _make_bat(tmp_path, {"status": "Charging"})
    _make_ac(tmp_path, online="1", name="ucsi-source-psy-USBC0001", with_type=True)

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.online is True


def test_b8_adp_folder_detected_via_name_fallback(tmp_path):
    """No `type` file anywhere -> name fallback still finds ADP*."""
    _make_bat(tmp_path, {"status": "Charging"}, with_type=False)
    _make_ac(tmp_path, online="1", name="ADP1", with_type=False)

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.online is True


def test_b8_battery_folder_without_bat_prefix_detected_via_type(tmp_path):
    """A `type=Battery` folder not named BAT* is still picked up."""
    _make_bat(tmp_path, {"capacity": "42", "status": "Discharging"}, name="CMB1")
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap is not None
    assert snap.capacity == 42


def test_b8_type_file_takes_precedence_over_name(tmp_path):
    """A folder named BAT0 whose type says 'Mains' is not treated as a battery."""
    mains = tmp_path / "BAT0"
    mains.mkdir()
    _write(mains / "type", "Mains")
    _write(mains / "online", "1")

    # A real battery elsewhere so a snapshot is still returned.
    _make_bat(tmp_path, {"capacity": "77", "status": "Discharging"}, name="CMB0")
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap is not None
    assert snap.capacity == 77    # came from CMB0, not the mislabeled BAT0


# ---------------------------------------------------------------------------
# B9: missing data -> None, not 0 / 100.0 sentinels
# ---------------------------------------------------------------------------

def test_b9_missing_capacity_returns_none(tmp_path):
    _make_bat(tmp_path, {"status": "Discharging"})
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap is not None
    assert snap.capacity is None


def test_b9_missing_power_data_returns_none_power_watts(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "energy_now": "50000000",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.power_watts is None
    assert snap.hours_left is None


def test_b9_missing_hours_left_data_returns_none(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "current_now": "1000000",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.hours_left is None


def test_b9_missing_health_data_returns_none(tmp_path):
    _make_bat(tmp_path, {"status": "Discharging"})
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.health_percent is None


def test_b9_health_uses_charge_pair_when_energy_pair_missing(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "charge_full": "4000000",
            "charge_full_design": "5000000",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.health_percent == pytest.approx(80.0, abs=0.1)


def test_b9_health_none_when_only_one_of_pair_present(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "energy_full": "50000000",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.health_percent is None


def test_b9_non_numeric_field_treated_as_missing(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "capacity": "eighty",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.capacity is None


# ---------------------------------------------------------------------------
# Online inference when no AC adapter is exposed (updated for B4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "status, expected_online",
    [
        ("Charging", True),
        ("Full", True),
        ("Discharging", False),
        ("Not charging", True),   # B4: was False before
        ("Unknown", False),
    ],
)
def test_no_ac_folder_infers_online_from_status(tmp_path, status, expected_online):
    _make_bat(tmp_path, {"status": status}, with_type=False)
    # No AC directory created.

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.online is expected_online


# ---------------------------------------------------------------------------
# Multiple entries / weird directory layouts
# ---------------------------------------------------------------------------

def test_multiple_batteries_picks_first_sorted(tmp_path):
    """BAT0 wins over BAT1 — sorting, not directory order."""
    _make_bat(tmp_path, {"capacity": "10", "status": "Discharging"}, name="BAT1")
    _make_bat(tmp_path, {"capacity": "90", "status": "Discharging"}, name="BAT0")
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.capacity == 90


def test_multiple_acs_picks_first_sorted(tmp_path):
    _make_bat(tmp_path, {"status": "Discharging"})
    _make_ac(tmp_path, online="1", name="AC1")
    _make_ac(tmp_path, online="0", name="AC0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.online is False   # AC0 (sorted first) has online=0


def test_nonexistent_sys_path_raises(tmp_path):
    """Fatal: missing sys_path now bubbles FileNotFoundError (was: return None)."""
    with pytest.raises(FileNotFoundError):
        LinuxBatterySampler(sys_path=str(tmp_path / "does_not_exist"))


# ---------------------------------------------------------------------------
# Health clamp & zero design capacity
# ---------------------------------------------------------------------------

def test_health_clamped_to_100_when_full_exceeds_design(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "energy_full": "60000000",
            "energy_full_design": "50000000",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.health_percent == 100.0


def test_health_none_when_design_capacity_is_zero(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "energy_full": "50000000",
            "energy_full_design": "0",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.health_percent is None


# ---------------------------------------------------------------------------
# Assorted edges
# ---------------------------------------------------------------------------

def test_power_derived_from_current_and_voltage_when_power_now_missing(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "energy_now": "50000000",       # 50 Wh
            "current_now": "1000000",       # 1 A
            "voltage_now": "12000000",      # 12 V
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.power_watts == pytest.approx(12.0)
    assert snap.hours_left == pytest.approx(round(50 / 12, 2))


def test_zero_power_now_yields_none_hours_left(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "power_now": "0",
            "energy_now": "50000000",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.power_watts == 0.0
    assert snap.hours_left is None


def test_zero_current_in_charge_fallback_yields_none_hours_left(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "charge_now": "3000000",
            "current_now": "0",
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.hours_left is None


def test_hours_left_rounded_to_two_decimals(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "power_now": "7000000",        # 7 W
            "energy_now": "50000000",      # 50 Wh
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.hours_left == 7.14


def test_missing_status_is_none(tmp_path):
    """Partial error: missing status file -> None (was: 'Unknown' fallback)."""
    _make_bat(tmp_path, {"capacity": "50"})
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.status is None
    assert snap.hours_left is None