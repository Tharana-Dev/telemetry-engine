import pytest
from engine.linux_battery import LinuxBatterySampler
from engine.models import BatterySnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path, value):
    """Write a sysfs-style single-value file."""
    path.write_text(str(value))


def _make_bat(tmp_path, fields: dict, name="BAT0"):
    bat = tmp_path / name
    bat.mkdir()
    for k, v in fields.items():
        _write(bat / k, v)
    return bat


def _make_ac(tmp_path, online="0", name="AC"):
    ac = tmp_path / name
    ac.mkdir()
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
        },
    )
    _make_ac(tmp_path, online="0")

    snapshot = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snapshot is not None
    assert snapshot.capacity == 75
    assert snapshot.status == "Discharging"
    assert snapshot.hours_left == pytest.approx(3.0, abs=0.01)   # 3 Ah / 1 A
    assert snapshot.health_percent == pytest.approx(80.0, abs=0.1)
    # B9: charge-based path never derives watts (no voltage file read).
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
    """USB-C quirk: status=Charging while AC reports online=0.

    Pre-B1 code gated on `not online`, so it would compute hours_left here
    (i.e. show "3h 20m remaining" on a charging battery). The gate must be
    on `status`, not `online`.
    """
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
    assert snap.online is False           # we read the AC file verbatim
    # Would be 10.0 pre-B1; must be None now.
    assert snap.hours_left is None


@pytest.mark.parametrize("status", ["Full", "Not charging", "Unknown"])
def test_b1_non_discharging_statuses_have_no_hours_left(tmp_path, status):
    """Any status other than 'Discharging' must suppress hours_left."""
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
    """Dual edge of B1: status=Discharging but AC says online=1.

    Pre-B1 code gated on `not online`, so it would *skip* hours_left here.
    The gate is on status, so we now compute it — `online` is orthogonal.
    """
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
    """B1 applies to the charge-based fallback path too."""
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

    # Pre-B1 (not online) would be 3.0 h; must be None.
    assert snap.hours_left is None


# ---------------------------------------------------------------------------
# B2: negative power / current is treated as magnitude
# ---------------------------------------------------------------------------

def test_b2_negative_power_now_reports_positive_watts(tmp_path):
    """Some drivers emit negative power_now while discharging."""
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
    # Pre-B2: `power_watts > 0` guard fails on -10 -> hours_left stayed None.
    assert snap.hours_left == pytest.approx(5.0)


def test_b2_negative_current_in_charge_fallback(tmp_path):
    """Charge path: current_now < 0 must still yield positive hours."""
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
    """Energy path, no power_now: current*voltage may be negative; abs() it."""
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
# B9: missing data -> None, not 0 / 100.0 sentinels
# ---------------------------------------------------------------------------

def test_b9_missing_capacity_returns_none(tmp_path):
    _make_bat(tmp_path, {"status": "Discharging"})
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap is not None
    assert snap.capacity is None


def test_b9_missing_power_data_returns_none_power_watts(tmp_path):
    """energy_now present, but no power_now / current_now -> power is None."""
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
    """Charge path but no charge_now -> hours_left must be None, not 0."""
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
    """No energy_* and no charge_* pairs -> health is None, not 100.0."""
    _make_bat(tmp_path, {"status": "Discharging"})
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.health_percent is None


def test_b9_health_uses_charge_pair_when_energy_pair_missing(tmp_path):
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "charge_full": "4000000",        # 4 Ah
            "charge_full_design": "5000000", # 5 Ah
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.health_percent == pytest.approx(80.0, abs=0.1)


def test_b9_health_none_when_only_one_of_pair_present(tmp_path):
    """energy_full present but energy_full_design missing, no charge pair.

    Documents current behaviour: the partial energy pair is discarded and,
    with no charge pair to fall back to, health is None.
    """
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
    """A garbage 'capacity' value is not a crash — it's a missing value."""
    _make_bat(
        tmp_path,
        {
            "status": "Discharging",
            "capacity": "eighty",         # not an int
        },
    )
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.capacity is None


# ---------------------------------------------------------------------------
# Online inference when no AC adapter is exposed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "status, expected_online",
    [
        ("Charging", True),
        ("Full", True),
        ("Discharging", False),
        ("Not charging", False),
        ("Unknown", False),
    ],
)
def test_no_ac_folder_infers_online_from_status(tmp_path, status, expected_online):
    _make_bat(tmp_path, {"status": status})
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


def test_nonexistent_sys_path_returns_none(tmp_path):
    assert LinuxBatterySampler(
        sys_path=str(tmp_path / "does_not_exist")
    ).get_battery_snapshot() is None


# ---------------------------------------------------------------------------
# Health clamp & zero design capacity
# ---------------------------------------------------------------------------

def test_health_clamped_to_100_when_full_exceeds_design(tmp_path):
    """Driver rounding can make full > design; report 100, not 120."""
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
    """Guards the `edesign > 0` divide-by-zero check."""
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
    """energy path without power_now must derive watts from I*V."""
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
    """power_watts == 0 would divide-by-zero; guard must yield None."""
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
    """50 Wh / 7 W = 7.142857… -> 7.14."""
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


def test_missing_status_falls_back_to_unknown(tmp_path):
    _make_bat(tmp_path, {"capacity": "50"})
    _make_ac(tmp_path, online="0")

    snap = LinuxBatterySampler(sys_path=str(tmp_path)).get_battery_snapshot()

    assert snap.status == "Unknown"
    assert snap.hours_left is None