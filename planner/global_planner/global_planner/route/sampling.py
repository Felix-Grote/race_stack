"""
Sample points along a lap curve, and refit a curve through moved samples.

anchors:    section starts and any extra q given, sampled exactly at their q.
grid:       the remaining samples, spread evenly by distance along the curve.
"""
from collections.abc import Sequence
from dataclasses import dataclass
import math

from .curve import Curve, CurvePoint
from .errors import LapError
from .geometry import XY
from .lap import LapCurve


@dataclass(frozen=True)
class LapSample(CurvePoint):
    """A curve point with its lap progress q and the speed limit in force there."""

    q: float
    speed_limit_mps: float


def _lap_sample(lap: LapCurve, s: float, segment: int, t: float, q: float) -> LapSample:
    """Build the LapSample at (segment, t), checking q lies in the piece's owner."""
    cubic = lap.curve.segments[segment]
    tangent, curvature = cubic.frame(t)

    section = lap.route.sections[lap.section_index(q)]
    if lap.curve.owners[segment] != section.uid:
        raise LapError('q lies in a section that does not own its piece')

    return LapSample(s, segment, t, cubic.evaluate(t), tangent, curvature,
                     section.uid, q=q, speed_limit_mps=section.max_speed_mps)


def sample_at_station(lap: LapCurve, s: float) -> LapSample:
    """Return the LapSample at curve distance s."""
    segment, t = lap.curve.locate(s)

    # The inverse may round t to 1 just before a knot. Keep q inside this
    # piece's half-open interval; exact knots go through sample_at_progress.
    q = max(lap.q[segment], min(lap.progress(segment, t),
            math.nextafter(lap.q[segment + 1], lap.q[segment])))

    return _lap_sample(lap, lap.curve.wrap(s), segment, t, q)


def sample_at_progress(lap: LapCurve, q: float) -> LapSample:
    """Return the LapSample at lap progress q, without a round trip through s."""
    if not math.isfinite(q) or not 0 <= q < lap.period:
        raise LapError('q outside [0, lap length)')

    segment, t = lap.parameter_at_progress(q)
    return _lap_sample(lap, lap.curve.station(segment, t), segment, t, q)


def sample_lap(lap: LapCurve, spacing: float,
               extra_anchors: Sequence[float] = ()) -> tuple[LapSample, ...]:
    """
    Return samples every `spacing` metres plus every anchor, sorted by s.

    extra_anchors:  more q to sample exactly, e.g. where the line enters and leaves a
                    portal's reach (zones.reach_boundaries).
    """
    if not math.isfinite(spacing) or spacing <= 0:
        raise LapError('spacing must be positive')

    count = math.ceil(lap.curve.length / spacing)
    if count > lap.curve.policy.max_samples:
        raise LapError('too many samples for this spacing')

    anchors = set(lap.route.section_bounds[:-1])
    anchors.update(q % lap.period for q in extra_anchors)

    """
    Keep anchors exact and keep the uniform grid, but drop a grid point
    within half a spacing of an anchor (around the lap): a point a hair
    away from an anchor leaves the optimizer a near-zero gap.
    """
    anchored = tuple(sample_at_progress(lap, q) for q in sorted(anchors))
    length = lap.curve.length
    stations = [length * i / count for i in range(count)
                if all(lap.curve.separation(length * i / count, v.s) >= spacing / 2
                       for v in anchored)]
    result = tuple(sorted(anchored + tuple(sample_at_station(lap, s) for s in stations),
                          key=lambda v: v.s))
    if any(a.s >= b.s for a, b in zip(result, result[1:])):
        raise LapError('two samples closer than the curve resolution')

    if any(a.q >= b.q for a, b in zip(result, result[1:])):
        raise LapError('samples out of q order')

    return result


def refit_lap(lap: LapCurve, samples: Sequence[LapSample], xy: Sequence[XY]) -> LapCurve:
    """
    Fit a new lap curve through moved points, keeping each sample's q and owner.

    The spline runs by chord length between the moved points, not by q: points that moved
    unevenly would otherwise make it wiggle or loop. q stays each knot's lap progress.
    """
    samples, xy = tuple(samples), tuple(xy)
    if len(samples) != len(xy) or not samples:
        raise LapError('one moved point per sample required')

    q = tuple(v.q for v in samples) + (lap.period,)
    owners = tuple(v.section_uid for v in samples)

    return LapCurve(lap.route, Curve.interpolate(xy, owners, policy=lap.curve.policy), q)
