---
status: accepted
---

# Keep learned corrections transparent and separate from recovery boost

Weather compensation combines a base outdoor curve, a learned correction, and a
temporary recovery boost. Keep these contributions separately visible so users
can distinguish an unsuitable base curve from a transient room deficit.

Boost uses each eligible room's deficit, trend, and reported activation; the
largest valid need determines the capped common boost. Persistent deficit alone
does not justify repeated escalation. A suspected response fault follows the
notification and learning-suspension policy in ADR 0001.

Learning can trial higher or lower point corrections using accumulated valid
observations. A lower target must preserve comfort in every eligible zone; an
upward trial must demonstrate improvement. Boost, changed setpoints/conditions,
and invalid observations interrupt a trial and restore validated corrections.
Boost does not become a learned correction and takes priority over trials.

The user can select the base curve alone, learning with applied corrections,
or frozen validated corrections, and can reset learning without losing the base
curve. Validated corrections and experience persist; an interrupted trial is not
resumed after restart. Missing runtime is not valid observation time.

## Curve points

The user chooses 2–50 evenly spaced points across an outdoor interval. Each point
has a base value, correction, and accumulated experience. Assign observations
to the nearest point using midpoint boundaries; ties go to the colder outdoor
point. Calculate targets by linear interpolation of corrected neighboring points.
Observation attribution and interpolation influence are distinct.

The corrected heating curve cannot request less supply temperature as outdoor
temperature becomes colder; flat segments are allowed. Limit local corrections
that would violate this property and expose the reason. Final supply limits
also bound boost.

Outside the configured interval, extrapolate the corrected end segment within
supply limits. Suspend learning there; boost and monitoring remain available
when their own requirements hold. Expose the out-of-range condition.

Editing a base point resets its correction and experience. Changing point count
or outdoor interval resets all learning. Explain this before saving.

These decisions preserve interpretability and reversible adjustment. They do not
establish universal calibration values. Current settings and monitoring behavior
are described in [Supply control](../features/supply-control.md).
