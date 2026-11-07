# Units in the widgets tables

Last updated by the data team.

## Decision

Every column that holds a physical quantity carries its unit in its name, in SI, as `<quantity>_<unit>`, for example `flux_w_m2` or `wavelength_nm`. A reader never converts units silently: a column whose name lacks a unit is refused at load.

## Why

Two releases shipped irradiance in the wrong unit because the loader guessed. Naming the unit makes the guess unnecessary and a review can see it.

## Scope

The loaders in `widgets/` and every table they write. Plots and notebooks are out of scope.
