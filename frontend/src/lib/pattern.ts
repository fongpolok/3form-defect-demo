// Same stripe-toggle math as backend/app/lighting/pattern.py (itself a port
// of the old app's LightUI.setPattern()) — reimplemented here so the
// full-screen projector window can animate at 60fps without a network
// round trip per frame. Keep the two in sync if you change the algorithm.
export interface PatternParams {
  width: number; // stripe width, px
  rotation: number; // degrees
  shift: number; // px
  intensity: number; // 0-255
}

export function drawPattern(ctx: CanvasRenderingContext2D, w: number, h: number, params: PatternParams) {
  const { width: stripeWidth, rotation, shift, intensity } = params;
  const light = `rgb(${intensity},${intensity},${intensity})`;
  const dark = `rgb(${255 - intensity},${255 - intensity},${255 - intensity})`;

  ctx.save();
  ctx.clearRect(0, 0, w, h);
  ctx.translate(w / 2, h / 2);
  ctx.rotate((rotation * Math.PI) / 180);
  ctx.translate(-w / 2, -h / 2);

  // Oversize so rotated corners are still covered.
  const diag = Math.ceil(Math.sqrt(w * w + h * h));
  const startX = (w - diag) / 2;
  const startY = (h - diag) / 2;

  let count: number;
  let whiteRegion: boolean;
  if (shift === 0) {
    count = 0;
    whiteRegion = false;
  } else if (shift <= stripeWidth) {
    count = stripeWidth - shift;
    whiteRegion = true;
  } else {
    count = stripeWidth - (shift - stripeWidth);
    whiteRegion = false;
  }

  for (let x = 0; x < diag; x++) {
    if (count === stripeWidth) {
      whiteRegion = !whiteRegion;
      count = 0;
    }
    count++;
    ctx.fillStyle = whiteRegion ? light : dark;
    ctx.fillRect(startX + x, startY, 1, diag);
  }

  ctx.restore();
}
