# Link Planner — methods, validation, limits

**Sun**: Meeus, *Astronomical Algorithms* ch.25 low-precision theory (~0.01°). **Moon**: ch.47 truncated ELP series (58 longitude/distance terms, 30 latitude terms + additive terms). **Frame**: lunar pole tilted 1.54242° to the ecliptic, node at the lunar orbit's mean ascending node Ω, prime meridian along mean Earth direction (mean rotation angle F+180° from the node); optical libration emerges from the true Moon direction. Physical libration (~0.03°) omitted. UTC treated as TT (~69 s).
**Site geometry**: body-fixed site normal; elevation/azimuth of Moon→Sun and site→Earth vectors in km (so Earth/Sun parallax from the surface is included). Sun visible if upper limb (centre + semidiameter) > mask; Earth visible if centre > mask.

## Validation (automated, `tests/test_all.py`)
- Meeus ch.47 example (1992-04-12 0h TD): longitude matches to 0.00001°, latitude 0.0005°, distance within 9 km.
- Meeus ch.53 optical libration: l′ −1.206°, b′ +4.194° reproduced.
- 2026-11-09 new moon (almanac ≈07:02 UTC) reproduced within minutes; 2026-08-12 total solar eclipse elongation < 1°.
- Libration over 2026 stays within ±7.9° (lon) and ±6.8° (lat).
- Pole physics: Sun stays within ~1.5° of the horizon; Earth visible roughly half of the libration cycle.
These checks validate the ephemeris and frame, **not** terrain, illumination maps or radio performance.

## Not done (next steps)
LOLA DEM horizon masks; SPICE kernels (de440 + lunar PCK) as the reference ephemeris; link-budget model; NASA SVS illumination cross-check.
