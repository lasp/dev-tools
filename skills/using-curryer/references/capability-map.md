# What curryer provides, and the SPICE mistakes to catch

Verified against curryer 0e6f2658 (main) on 2026-10-03.

The map drifts. Before flagging a reimplementation, confirm the function exists in the curryer
the repository pins.

## Do not reimplement

Downstream code that hand-rolls one of these, or a second copy inside curryer, is a finding that
names the curryer function to use.

- **Coordinate transforms:** `compute.spatial.ecef_to_geodetic`, `geodetic_to_ecef`.
- **Ray and ellipsoid intersection:** `compute.spatial.ray_intersect_ellipsoid`,
  `instrument_intersect_ellipsoid`, `compute_ellipsoid_intersection`.
- **Pointing vectors:** `compute.spatial.pixel_vectors`,
  `get_instrument_kernel_pointing_vectors`, `instrument_pointing_state`;
  `compute.pointing.PointingData.get_pointing`.
- **Geolocation:** `compute.spatial.Geolocate`, `SpatialQueries`, `terrain_correct`.
- **Angles:** `compute.spatial.calc_azimuth`, `calc_zenith`, `surface_angles`, `spice_angles`.
- **Field of view and occultation:** `compute.pointing.check_fov`, `check_occult`,
  `boresight_dot_object`, `calc_cosine`.
- **Observer and solar geometry:** `compute.geometry.sc_radius`, `subobserver_point`,
  `earth_sun_distance`, `colatitude`, `GeometryData`, which computes the fields
  `compute.geometry_fields.GeometryField` names one at a time; `compute.ephemeris.SolarDistAndDoppler`.
- **Elevation and terrain:** `compute.elevation.Elevation`, `ElevationRegion`.
- **A mission's cadence:** `compute.abstract.AbstractMissionData`, constructed with a cadence,
  then `get_times(ugps_range)`. A new mission data class subclasses it rather than repeating
  the orchestration.
- **Time:** `spicetime.adapt()` and the `SpiceTime` array.
- **Constants:** `compute.constants`, such as `WGS84_SEMI_MAJOR_AXIS_KM`.

## SPICE mistakes

Each is a correctness finding unless it says otherwise.

- **A direct `import spiceypy`** or `from spiceypy import ...` instead of `curryer.spicierpy`,
  which silently bypasses curryer's vectorized overrides.
- **A Python loop over scalar SPICE calls** where a vectorized `spicierpy` override exists: an
  efficiency finding, not a correctness one.
- **Ad hoc epochs:** time arithmetic by hand instead of `spicetime.adapt()`. curryer's internal
  time is uGPS, int64 microseconds since 1980-01-06.
- **Constants written out** (Earth radii, GM, the astronomical unit) instead of
  `compute.constants`.
- **Kernel paths over 80 characters:** SPICE rejects them, and curryer routes them through
  `kernels/path_utils.py`. Handling a long path by hand is a bug.
- **`.dict()` on a Pydantic v2 model** such as `correction.verification.VerificationResult`,
  where `.model_dump()` is the call, or its `aggregate_stats` (an `xr.Dataset`) left in JSON
  output.
- **Units, frames and corrections:** km against m, degrees against radians, J2000 (inertial)
  against ITRF93 (Earth-fixed), and a missing light-time or aberration correction (`LT+S`) where
  the physics needs one.
