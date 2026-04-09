// ColourScale — Task 3.1

export interface ColourStop {
  value: number;
  colour: string;
}

export interface ColourScale {
  getColour(score: number): string;
  min: number;
  max: number;
  stops: ColourStop[];
}

// Brewer YlGn 5-stop sequential ramp: light yellow → dark green
const RAMP: string[] = ['#ffffb2', '#addd8e', '#78c679', '#31a354', '#006837'];
const MIDPOINT_COLOUR = '#78c679'; // index 2 of 5-stop ramp

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
}

function rgbToHex(r: number, g: number, b: number): string {
  return (
    '#' +
    [r, g, b]
      .map((v) => Math.round(v).toString(16).padStart(2, '0'))
      .join('')
  );
}

/** Interpolate across the RAMP using a normalised value in [0, 1]. */
function interpolateRamp(t: number): string {
  // Clamp
  const clamped = Math.max(0, Math.min(1, t));
  const maxIdx = RAMP.length - 1;
  const scaled = clamped * maxIdx;
  const lo = Math.floor(scaled);
  const hi = Math.min(lo + 1, maxIdx);
  const frac = scaled - lo;

  const [r0, g0, b0] = hexToRgb(RAMP[lo]);
  const [r1, g1, b1] = hexToRgb(RAMP[hi]);

  return rgbToHex(r0 + (r1 - r0) * frac, g0 + (g1 - g0) * frac, b0 + (b1 - b0) * frac);
}

export function buildColourScale(scores: number[]): ColourScale {
  if (scores.length === 0) {
    // Empty input — degenerate: return midpoint colour for everything
    return {
      min: 0,
      max: 0,
      stops: [{ value: 0, colour: MIDPOINT_COLOUR }],
      getColour: () => MIDPOINT_COLOUR,
    };
  }

  const min = Math.min(...scores);
  const max = Math.max(...scores);

  // Degenerate case: all scores equal
  if (min === max) {
    return {
      min,
      max,
      stops: [{ value: min, colour: MIDPOINT_COLOUR }],
      getColour: () => MIDPOINT_COLOUR,
    };
  }

  // Build 5 evenly-spaced stops between min and max
  const stops: ColourStop[] = RAMP.map((colour, i) => ({
    value: min + (i / (RAMP.length - 1)) * (max - min),
    colour,
  }));

  function getColour(score: number): string {
    const t = (score - min) / (max - min);
    return interpolateRamp(t);
  }

  return { min, max, stops, getColour };
}
