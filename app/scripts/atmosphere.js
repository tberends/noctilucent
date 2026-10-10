const MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
const FIELD_INDEX = { TEMP: 0, SKNT: 1, DRCT: 2, RELH: 3, MIXR: 4, THTA: 5 };
const DAY = 86400000;

const SCALES = {
    TEMP: {
        min: -80,
        max: 30,
        unit: "°C",
        stops: [
            [-80, [18, 32, 74]],
            [-50, [32, 78, 140]],
            [-20, [150, 196, 214]],
            [0, [232, 214, 176]],
            [15, [214, 140, 96]],
            [30, [168, 64, 58]]
        ]
    },
    SKNT: {
        min: 0,
        max: 120,
        unit: "kt",
        stops: [
            [0, [12, 20, 36]],
            [20, [40, 78, 112]],
            [50, [150, 196, 214]],
            [90, [236, 242, 246]],
            [120, [255, 252, 245]]
        ]
    },
    RELH: {
        min: 0,
        max: 100,
        unit: "%",
        stops: [
            [0, [92, 74, 52]],
            [40, [70, 96, 112]],
            [70, [46, 110, 150]],
            [100, [214, 236, 248]]
        ]
    },
    MIXR: {
        min: 0,
        max: 12,
        unit: "g/kg",
        stops: [
            [0, [16, 28, 40]],
            [3, [36, 90, 110]],
            [8, [120, 190, 180]],
            [12, [236, 244, 232]]
        ]
    },
    THTA: {
        min: 270,
        max: 450,
        unit: "K",
        stops: [
            [270, [24, 28, 64]],
            [300, [48, 72, 120]],
            [340, [180, 150, 110]],
            [400, [236, 214, 170]],
            [450, [248, 244, 236]]
        ]
    }
};

const PERIODS = {
    "14d": { source: "recent", days: 14 },
    "60d": { source: "recent", days: 60 },
    "1y": { source: "archive", days: 365 },
    all: { source: "archive", days: null }
};

let meta = null;
let recent = null;
let archive = null;
let active = null;
let t0 = 0;
let t1 = 0;
let range0 = 0;
let range1 = 0;
let selected = 0;
let band = null;
let moisture = "RELH";
let dragging = false;

function formatNum(value, digits) {
    if (value == null || !Number.isFinite(Number(value))) return "geen";
    return Number(value).toFixed(digits).replace(".", ",");
}

function formatStamp(ms) {
    const date = new Date(ms);
    const hours = String(date.getUTCHours()).padStart(2, "0");
    const minutes = String(date.getUTCMinutes()).padStart(2, "0");
    return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}, ${hours}:${minutes} UTC`;
}

function formatTick(ms, span) {
    const date = new Date(ms);
    if (span > 800 * DAY) return String(date.getUTCFullYear());
    if (span > 40 * DAY) return `${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
    return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]}`;
}

function dewpoint(temp, humidity) {
    if (!Number.isFinite(temp) || !Number.isFinite(humidity) || humidity <= 0) return null;
    const capped = Math.min(humidity, 100);
    const a = 17.625;
    const b = 243.04;
    const gamma = Math.log(capped / 100) + (a * temp) / (b + temp);
    return (b * gamma) / (a - gamma);
}

function colorAt(stops, min, max, value) {
    const clamped = Math.min(max, Math.max(min, value));
    if (clamped <= stops[0][0]) return stops[0][1];
    for (let i = 1; i < stops.length; i += 1) {
        if (clamped <= stops[i][0]) {
            const [start, from] = stops[i - 1];
            const [end, to] = stops[i];
            const fraction = (clamped - start) / (end - start || 1);
            return from.map((channel, index) => Math.round(channel + (to[index] - channel) * fraction));
        }
    }
    return stops[stops.length - 1][1];
}

function paintScale(id, scale) {
    const host = document.getElementById(id);
    if (!host) return;
    const gradient = scale.stops.map(([value, rgb]) => {
        const percent = ((value - scale.min) / (scale.max - scale.min)) * 100;
        return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]}) ${percent}%`;
    }).join(", ");
    host.innerHTML = `<span>${formatNum(scale.min, 0)}</span><i style="background:linear-gradient(90deg, ${gradient})"></i><span>${formatNum(scale.max, 0)} ${scale.unit}</span>`;
}

async function loadView(key) {
    const spec = meta[key];
    const response = await fetch(spec.file);
    if (!response.ok) throw new Error(spec.file);
    const buffer = await response.arrayBuffer();
    const nH = meta.heights.length;
    const nT = spec.times.length;
    if (buffer.byteLength !== 6 * nH * nT * 4) {
        throw new Error(`Onverwachte grootte van ${spec.file}`);
    }
    return {
        times: spec.times.map((stamp) => Date.parse(stamp)),
        tropopause: spec.tropopause,
        nH,
        nT,
        buffer,
        heights: meta.heights
    };
}

function fieldValues(view, name) {
    const offset = FIELD_INDEX[name] * view.nH * view.nT;
    return new Float32Array(view.buffer, offset * 4, view.nH * view.nT);
}

function sample(view, name, heightIndex, timeIndex) {
    return fieldValues(view, name)[heightIndex * view.nT + timeIndex];
}

function prepare(canvas, rightMargin, leftMargin = 48) {
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 320;
    const height = canvas.clientHeight || 200;
    const pixelWidth = Math.max(1, Math.round(width * dpr));
    const pixelHeight = Math.max(1, Math.round(height * dpr));
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth;
        canvas.height = pixelHeight;
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const plot = {
        x: leftMargin,
        y: 8,
        w: Math.max(10, width - leftMargin - rightMargin),
        h: Math.max(10, height - 34)
    };
    canvas._box = { ctx, width, height, plot };
    return canvas._box;
}

function yOfHeight(box, heights, meters) {
    const low = heights[0];
    const high = heights[heights.length - 1];
    const fraction = (meters - low) / (high - low || 1);
    return box.plot.y + box.plot.h - fraction * box.plot.h;
}

function xOfIndex(box, index) {
    const columns = Math.max(1, t1 - t0);
    return box.plot.x + ((index - t0 + 0.5) / columns) * box.plot.w;
}

function xEdge(box, index) {
    const columns = Math.max(1, t1 - t0);
    return box.plot.x + ((index - t0) / columns) * box.plot.w;
}

function xOfTime(box, ms) {
    const start = active.times[t0];
    const end = active.times[t1 - 1];
    const fraction = (ms - start) / (end - start || 1);
    return box.plot.x + fraction * box.plot.w;
}

function drawHeightAxis(ctx, box, heights) {
    ctx.save();
    ctx.font = "11px 'Source Sans 3', sans-serif";
    ctx.fillStyle = "#93a4c3";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    const maxMeters = heights[heights.length - 1];
    const step = maxMeters > 20000 ? 10000 : 5000;
    for (let meters = 0; meters <= maxMeters + 1; meters += step) {
        const y = yOfHeight(box, heights, meters);
        if (y < box.plot.y - 1 || y > box.plot.y + box.plot.h + 1) continue;
        ctx.fillText(String(Math.round(meters / 1000)), box.plot.x - 8, y);
        ctx.strokeStyle = "rgba(214, 228, 240, 0.08)";
        ctx.beginPath();
        ctx.moveTo(box.plot.x, y);
        ctx.lineTo(box.plot.x + box.plot.w, y);
        ctx.stroke();
    }
    ctx.restore();
}

function drawTimeAxis(ctx, box) {
    const start = active.times[t0];
    const end = active.times[t1 - 1];
    const span = end - start;
    ctx.save();
    ctx.font = "11px 'Source Sans 3', sans-serif";
    ctx.fillStyle = "#93a4c3";
    ctx.textBaseline = "top";
    const ticks = span > 800 * DAY ? 5 : 4;
    const y = box.plot.y + box.plot.h + 8;
    const plotLeft = box.plot.x;
    const plotRight = box.plot.x + box.plot.w;
    for (let i = 0; i < ticks; i += 1) {
        const label = formatTick(start + (span * i) / (ticks - 1), span);
        const width = ctx.measureText(label).width;
        const atStart = i === 0;
        const atEnd = i === ticks - 1;
        let x = plotLeft + (box.plot.w * i) / (ticks - 1);
        if (atStart) {
            ctx.textAlign = "left";
            x = Math.max(0, Math.min(plotLeft, box.width - width));
        } else if (atEnd) {
            ctx.textAlign = "right";
            x = Math.min(box.width, Math.max(plotRight, width));
        } else {
            ctx.textAlign = "center";
            const half = width / 2;
            x = Math.min(box.width - half, Math.max(half, x));
        }
        ctx.fillText(label, x, y);
    }
    ctx.restore();
}

function drawHeat(canvas, fieldName) {
    const scale = SCALES[fieldName];
    const box = prepare(canvas, 12);
    const { ctx, plot } = box;
    const columns = t1 - t0;
    const rows = active.nH;
    const values = fieldValues(active, fieldName);
    const offscreen = document.createElement("canvas");
    offscreen.width = columns;
    offscreen.height = rows;
    const imageCtx = offscreen.getContext("2d");
    const image = imageCtx.createImageData(columns, rows);
    for (let heightIndex = 0; heightIndex < rows; heightIndex += 1) {
        const imageRow = rows - 1 - heightIndex;
        for (let timeIndex = t0; timeIndex < t1; timeIndex += 1) {
            const value = values[heightIndex * active.nT + timeIndex];
            const offset = (imageRow * columns + (timeIndex - t0)) * 4;
            if (!Number.isFinite(value)) continue;
            const [red, green, blue] = colorAt(scale.stops, scale.min, scale.max, value);
            image.data[offset] = red;
            image.data[offset + 1] = green;
            image.data[offset + 2] = blue;
            image.data[offset + 3] = 255;
        }
    }
    imageCtx.putImageData(image, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(offscreen, plot.x, plot.y, plot.w, plot.h);
    drawHeightAxis(ctx, box, active.heights);
    drawTimeAxis(ctx, box);
    return box;
}

function drawTropopause(box) {
    const { ctx, plot } = box;
    ctx.save();
    ctx.beginPath();
    ctx.rect(plot.x, plot.y, plot.w, plot.h);
    ctx.clip();
    ctx.strokeStyle = "rgba(247, 244, 239, 0.9)";
    ctx.lineWidth = 1.4;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    let open = false;
    for (let timeIndex = t0; timeIndex < t1; timeIndex += 1) {
        const height = active.tropopause[timeIndex];
        if (height == null || !Number.isFinite(height)) {
            open = false;
            continue;
        }
        const x = xOfIndex(box, timeIndex);
        const y = yOfHeight(box, active.heights, height);
        if (!open) {
            ctx.moveTo(x, y);
            open = true;
        } else {
            ctx.lineTo(x, y);
        }
    }
    ctx.stroke();
    ctx.restore();
}

function drawBarb(ctx, x, y, fromDeg, knots) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate((fromDeg * Math.PI) / 180);
    ctx.strokeStyle = "rgba(244, 247, 251, 0.88)";
    ctx.fillStyle = "rgba(244, 247, 251, 0.88)";
    ctx.lineWidth = 1;
    if (knots < 2.5) {
        ctx.beginPath();
        ctx.arc(0, 0, 2.2, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
        return;
    }
    const staff = 16;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -staff);
    ctx.stroke();
    let remaining = Math.round(knots / 5) * 5;
    let feather = -staff;
    while (remaining >= 50 && feather < -2) {
        ctx.beginPath();
        ctx.moveTo(0, feather);
        ctx.lineTo(7, feather + 3);
        ctx.lineTo(0, feather + 6);
        ctx.closePath();
        ctx.fill();
        feather += 6;
        remaining -= 50;
    }
    while (remaining >= 10 && feather < -1) {
        ctx.beginPath();
        ctx.moveTo(0, feather);
        ctx.lineTo(7, feather + 3.5);
        ctx.stroke();
        feather += 3.2;
        remaining -= 10;
    }
    if (remaining >= 5 && feather < -1) {
        ctx.beginPath();
        ctx.moveTo(0, feather);
        ctx.lineTo(4, feather + 2);
        ctx.stroke();
    }
    ctx.restore();
}

function drawBarbs(box) {
    const { ctx, plot } = box;
    const speed = fieldValues(active, "SKNT");
    const direction = fieldValues(active, "DRCT");
    ctx.save();
    ctx.beginPath();
    ctx.rect(plot.x, plot.y, plot.w, plot.h);
    ctx.clip();
    const xStep = plot.w < 520 ? 34 : 42;
    const yStep = 28;
    for (let x = plot.x + xStep / 2; x < plot.x + plot.w; x += xStep) {
        for (let y = plot.y + yStep / 2; y < plot.y + plot.h; y += yStep) {
            const fractionX = (x - plot.x) / plot.w;
            const fractionY = 1 - (y - plot.y) / plot.h;
            const timeIndex = Math.min(t1 - 1, t0 + Math.floor(fractionX * (t1 - t0)));
            const heightIndex = Math.min(active.nH - 1, Math.round(fractionY * (active.nH - 1)));
            const knots = speed[heightIndex * active.nT + timeIndex];
            const degrees = direction[heightIndex * active.nT + timeIndex];
            if (!Number.isFinite(knots) || !Number.isFinite(degrees)) continue;
            drawBarb(ctx, x, y, degrees, knots);
        }
    }
    ctx.restore();
}

function pointsInView(times, values) {
    const start = active.times[t0];
    const end = active.times[t1 - 1];
    const points = [];
    for (let i = 0; i < times.length; i += 1) {
        const time = times[i];
        const value = values[i];
        if (time < start || time > end || value == null || !Number.isFinite(value)) continue;
        points.push([time, value]);
    }
    return points;
}

function strokeSeries(ctx, points, xOf, yOf, color, dash) {
    if (!points.length) return;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.6;
    ctx.setLineDash(dash);
    ctx.beginPath();
    let previous = null;
    points.forEach(([time, value]) => {
        const x = xOf(time);
        const y = yOf(value);
        if (previous == null || time - previous > 36 * 3600000) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        previous = time;
    });
    ctx.stroke();
    ctx.restore();
}

function extent(values, floor, ceiling) {
    let min = Infinity;
    let max = -Infinity;
    values.forEach((value) => {
        if (value < min) min = value;
        if (value > max) max = value;
    });
    if (!Number.isFinite(min)) return [floor, ceiling];
    return [Math.min(floor, min), Math.max(ceiling, max)];
}

function niceStep(rough) {
    if (!(rough > 0)) return 1;
    const power = 10 ** Math.floor(Math.log10(rough));
    const fraction = rough / power;
    const nice = fraction < 1.5 ? 1 : fraction < 3.5 ? 2 : fraction < 7.5 ? 5 : 10;
    return nice * power;
}

function niceTicks(min, max) {
    if (!(max > min)) return [min];
    const step = niceStep((max - min) / 4);
    const start = Math.ceil(min / step) * step;
    const ticks = [];
    for (let value = start; value <= max + step * 0.01; value += step) ticks.push(value);
    return ticks;
}

let soundingScale = null;

function soundingAxis(view) {
    if (soundingScale && soundingScale.view === view) return soundingScale;
    const temp = fieldValues(view, "TEMP");
    const humidity = fieldValues(view, "RELH");
    let lo = Infinity;
    let hi = -Infinity;
    for (let index = 0; index < temp.length; index += 1) {
        const warm = temp[index];
        if (Number.isFinite(warm)) {
            if (warm < lo) lo = warm;
            if (warm > hi) hi = warm;
        }
        const cold = dewpoint(warm, humidity[index]);
        if (cold != null) {
            if (cold < lo) lo = cold;
            if (cold > hi) hi = cold;
        }
    }
    if (!Number.isFinite(lo)) {
        lo = -120;
        hi = 30;
    }
    const min = Math.floor(lo / 40) * 40;
    const max = Math.ceil(hi / 10) * 10;
    const step = 40;
    const ticks = [min];
    for (let value = min + step; value < max - 12; value += step) ticks.push(value);
    if (ticks[ticks.length - 1] !== max) ticks.push(max);
    soundingScale = { view, min, max, ticks };
    return soundingScale;
}

function drawLineChart(canvas, layers, rightMargin) {
    if (typeof canvas === "string") canvas = document.getElementById(canvas);
    const box = prepare(canvas, rightMargin);
    const { ctx, plot } = box;
    ctx.save();
    ctx.beginPath();
    ctx.rect(plot.x, plot.y, plot.w, plot.h);
    ctx.clip();
    layers.forEach((layer) => {
        const points = pointsInView(meta.indices.times, meta.indices[layer.key]);
        strokeSeries(ctx, points, (time) => xOfTime(box, time), layer.yOf, layer.color, layer.dash);
    });
    ctx.restore();
    drawTimeAxis(ctx, box);
    return box;
}

function drawK() {
    const points = pointsInView(meta.indices.times, meta.indices.k);
    const values = points.map((point) => point[1]);
    const [min, max] = extent(values, -10, 40);
    const yOf = (value) => {
        const box = document.getElementById("k-field")._box;
        const fraction = (value - min) / (max - min || 1);
        return box.plot.y + box.plot.h - fraction * box.plot.h;
    };
    const box = drawLineChart("k-field", [{
        key: "k",
        color: "#e6c27a",
        dash: [],
        yOf
    }], 12);
    const ticks = niceTicks(min, max);
    box.ctx.font = "11px 'Source Sans 3', sans-serif";
    box.ctx.fillStyle = "#93a4c3";
    box.ctx.textAlign = "right";
    box.ctx.textBaseline = "middle";
    ticks.forEach((tick) => {
        box.ctx.fillText(formatNum(tick, 0), box.plot.x - 8, yOf(tick));
    });
}

function drawCape() {
    const leftKeys = ["cape", "mucape"];
    const rightKeys = ["lifted", "virtualLifted"];
    const leftValues = [];
    const rightValues = [];
    leftKeys.forEach((key) => {
        pointsInView(meta.indices.times, meta.indices[key]).forEach((point) => leftValues.push(point[1]));
    });
    rightKeys.forEach((key) => {
        pointsInView(meta.indices.times, meta.indices[key]).forEach((point) => rightValues.push(point[1]));
    });
    const leftMax = extent(leftValues, 0, 500)[1];
    const [rightMin, rightMax] = extent(rightValues, -8, 8);
    const yLeft = (value) => {
        const box = document.getElementById("cape-field")._box;
        return box.plot.y + box.plot.h - (value / leftMax) * box.plot.h;
    };
    const yRight = (value) => {
        const box = document.getElementById("cape-field")._box;
        const fraction = (value - rightMin) / (rightMax - rightMin || 1);
        return box.plot.y + box.plot.h - fraction * box.plot.h;
    };
    const box = drawLineChart("cape-field", [
        { key: "cape", color: "#e7a08a", dash: [], yOf: yLeft },
        { key: "mucape", color: "#f3d2c4", dash: [2, 3], yOf: yLeft },
        { key: "lifted", color: "#8eb7e8", dash: [], yOf: yRight },
        { key: "virtualLifted", color: "#d5e6f8", dash: [2, 3], yOf: yRight }
    ], 46);
    box.ctx.font = "11px 'Source Sans 3', sans-serif";
    box.ctx.textBaseline = "middle";
    box.ctx.fillStyle = "#e7a08a";
    box.ctx.textAlign = "right";
    niceTicks(0, leftMax).forEach((tick) => {
        box.ctx.fillText(formatNum(tick, 0), box.plot.x - 8, yLeft(tick));
    });
    box.ctx.fillStyle = "#8eb7e8";
    box.ctx.textAlign = "left";
    niceTicks(rightMin, rightMax).forEach((tick) => {
        box.ctx.fillText(formatNum(tick, 0), box.plot.x + box.plot.w + 8, yRight(tick));
    });
}

function drawProfile() {
    const canvas = document.getElementById("profile");
    const box = prepare(canvas, 4, 26);
    const { ctx, plot } = box;
    const temperature = [];
    const dew = [];
    for (let heightIndex = 0; heightIndex < active.nH; heightIndex += 1) {
        const temp = sample(active, "TEMP", heightIndex, selected);
        const humidity = sample(active, "RELH", heightIndex, selected);
        temperature.push(temp);
        dew.push(dewpoint(temp, humidity));
    }
    const axis = soundingAxis(active);
    const { min, max } = axis;
    const xOf = (value) => plot.x + ((value - min) / (max - min)) * plot.w;
    const stroke = (series, color) => {
        ctx.save();
        ctx.beginPath();
        ctx.rect(plot.x, plot.y, plot.w, plot.h);
        ctx.clip();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        let open = false;
        series.forEach((value, heightIndex) => {
            if (!Number.isFinite(value)) {
                open = false;
                return;
            }
            const x = xOf(value);
            const y = yOfHeight(box, active.heights, active.heights[heightIndex]);
            if (!open) {
                ctx.moveTo(x, y);
                open = true;
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();
        ctx.restore();
    };
    drawHeightAxis(ctx, box, active.heights);
    stroke(temperature, "#f2d3b0");
    stroke(dew, "#8eb7e8");
    ctx.font = "11px 'Source Sans 3', sans-serif";
    ctx.fillStyle = "#93a4c3";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const ticks = axis.ticks;
    ticks.forEach((tick, index) => {
        const atStart = index === 0;
        const atEnd = index === ticks.length - 1;
        ctx.textAlign = atStart ? "left" : atEnd ? "right" : "center";
        const x = atStart ? plot.x : atEnd ? plot.x + plot.w : xOf(tick);
        ctx.fillText(formatNum(tick, 0), x, plot.y + plot.h + 8);
    });
    ctx.textAlign = "left";
    ctx.fillStyle = "#f2d3b0";
    ctx.fillText("Temperatuur", plot.x, plot.y + 4);
    ctx.fillStyle = "#8eb7e8";
    ctx.fillText("Dauwpunt", plot.x + 88, plot.y + 4);

    const surfaceTemp = temperature[0];
    const surfaceDew = dew[0];
    const wind = sample(active, "SKNT", 0, selected);
    const direction = sample(active, "DRCT", 0, selected);
    const tropopause = active.tropopause[selected];
    document.getElementById("profile-time").textContent = formatStamp(active.times[selected]);
    document.getElementById("profile-meta").innerHTML = `
        <div><dt>Temperatuur</dt><dd>${formatNum(surfaceTemp, 1)} °C</dd></div>
        <div><dt>Dauwpunt</dt><dd>${formatNum(surfaceDew, 1)} °C</dd></div>
        <div><dt>Wind</dt><dd>${formatNum(direction, 0)}° · ${formatNum(wind, 0)} kt</dd></div>
        <div><dt>Tropopauze</dt><dd>${tropopause == null ? "geen" : `${formatNum(tropopause / 1000, 1)} km`}</dd></div>
    `;
}

function drawCursors() {
    document.querySelectorAll(".plot").forEach((plot) => {
        const field = plot.querySelector(".field");
        const cursor = plot.querySelector(".cursor");
        if (!field._box) return;
        const box = prepare(cursor, field.id === "cape-field" ? 46 : 12);
        const x = xOfIndex(field._box, selected);
        box.ctx.strokeStyle = "rgba(247, 244, 239, 0.9)";
        box.ctx.lineWidth = 1;
        box.ctx.beginPath();
        box.ctx.moveTo(x, field._box.plot.y);
        box.ctx.lineTo(x, field._box.plot.y + field._box.plot.h);
        box.ctx.stroke();
        if (!band) return;
        const left = xEdge(field._box, Math.min(band.a, band.b));
        const right = xEdge(field._box, Math.max(band.a, band.b) + 1);
        box.ctx.fillStyle = "rgba(159, 214, 255, 0.18)";
        box.ctx.fillRect(left, field._box.plot.y, Math.max(2, right - left), field._box.plot.h);
    });
}

function updateReadout() {
    const temp = sample(active, "TEMP", 0, selected);
    const wind = sample(active, "SKNT", 0, selected);
    document.getElementById("readout").textContent =
        `${formatStamp(active.times[selected])} · ${formatNum(temp, 1)} °C · ${formatNum(wind, 0)} kt`;
}

function drawFields() {
    if (!active) return;
    const tempBox = drawHeat(document.getElementById("temp-field"), "TEMP");
    drawTropopause(tempBox);
    const windBox = drawHeat(document.getElementById("wind-field"), "SKNT");
    drawBarbs(windBox);
    drawHeat(document.getElementById("moist-field"), moisture);
    drawHeat(document.getElementById("theta-field"), "THTA");
    drawK();
    drawCape();
    paintScale("scale-temp", SCALES.TEMP);
    paintScale("scale-wind", SCALES.SKNT);
    paintScale("scale-moist", SCALES[moisture]);
    paintScale("scale-theta", SCALES.THTA);
    drawProfile();
    drawCursors();
    updateReadout();
}

function selectIndex(index) {
    const next = Math.max(t0, Math.min(t1 - 1, index));
    if (next === selected) return;
    selected = next;
    drawProfile();
    drawCursors();
    updateReadout();
}

function indexFromCanvas(canvas, clientX) {
    const rect = canvas.getBoundingClientRect();
    const plot = canvas._box.plot;
    const fraction = (clientX - rect.left - plot.x) / plot.w;
    const columns = t1 - t0;
    return t0 + Math.floor(Math.min(0.999, Math.max(0, fraction)) * columns);
}

function fillHero() {
    const latest = meta.latest;
    document.getElementById("station-label").textContent = `${meta.place} · ${meta.station}`;
    document.getElementById("hero-place").textContent = `Station ${meta.station}, ${meta.place}`;
    const time = document.getElementById("latest-time");
    time.dateTime = latest.time;
    time.textContent = formatStamp(Date.parse(latest.time));
    document.getElementById("hero-temp").textContent = `${formatNum(latest.temp, 1)} °C`;
    document.getElementById("hero-dew").textContent = `${formatNum(latest.dewpoint, 1)} °C`;
    document.getElementById("hero-wind").textContent = `${formatNum(latest.windDir, 0)}° · ${formatNum(latest.windSpeed, 0)} kt`;
    document.getElementById("hero-trop").textContent = latest.tropopause == null
        ? "geen"
        : `${formatNum(latest.tropopause / 1000, 1)} km`;
    document.getElementById("hero-k").textContent = formatNum(latest.kIndex, 1);
    document.getElementById("hero-cape").textContent = latest.mucape == null
        ? "geen"
        : `${formatNum(latest.mucape, 0)} J/kg`;
}

async function applyPeriod(id) {
    const period = PERIODS[id];
    document.querySelectorAll("[data-period]").forEach((button) => {
        button.setAttribute("aria-pressed", button.dataset.period === id ? "true" : "false");
    });
    if (period.source === "archive" && !archive) {
        document.getElementById("status").textContent = "Archief laden…";
        archive = await loadView("archive");
        document.getElementById("status").textContent = "";
    }
    active = period.source === "recent" ? recent : archive;
    const end = active.times[active.times.length - 1];
    const startMs = period.days == null ? active.times[0] : end - period.days * DAY;
    let start = active.times.findIndex((time) => time >= startMs);
    if (start < 0) start = active.times.length - 1;
    range0 = start;
    range1 = active.nT;
    t0 = range0;
    t1 = range1;
    selected = t1 - 1;
    band = null;
    drawFields();
}

function setView(start, end) {
    const full = range1 - range0;
    let lo = Math.max(range0, Math.min(start, end));
    let hi = Math.min(range1, Math.max(start, end));
    if (hi - lo < 4) {
        const mid = Math.round((lo + hi) / 2);
        lo = Math.max(range0, mid - 2);
        hi = Math.min(range1, lo + 4);
        lo = Math.max(range0, hi - 4);
    }
    if (hi - lo >= full && lo === range0) {
        t0 = range0;
        t1 = range1;
    } else {
        t0 = lo;
        t1 = hi;
    }
    if (selected < t0 || selected >= t1) selected = t1 - 1;
    band = null;
    drawFields();
}

function zoomBy(factor, anchor) {
    const span = Math.max(1, t1 - t0);
    let next = Math.round(span * factor);
    next = Math.max(4, Math.min(range1 - range0, next));
    const fraction = (anchor - t0) / span;
    let start = Math.round(anchor - fraction * next);
    if (start < range0) start = range0;
    if (start + next > range1) start = range1 - next;
    t0 = start;
    t1 = start + next;
    if (selected < t0 || selected >= t1) selected = Math.min(t1 - 1, Math.max(t0, anchor));
    drawFields();
}

function bindCharts() {
    const charts = document.getElementById("charts");
    charts.tabIndex = 0;
    let drag = null;
    charts.addEventListener("pointerdown", (event) => {
        const canvas = event.target.closest("canvas.field");
        if (!canvas || !canvas._box) return;
        if (event.pointerType === "mouse") {
            drag = {
                x: event.clientX,
                index: indexFromCanvas(canvas, event.clientX),
                canvas,
                moved: false
            };
            charts.setPointerCapture(event.pointerId);
            return;
        }
        dragging = true;
        selectIndex(indexFromCanvas(canvas, event.clientX));
    });
    charts.addEventListener("pointermove", (event) => {
        if (drag) {
            const index = indexFromCanvas(drag.canvas, event.clientX);
            if (Math.abs(event.clientX - drag.x) > 12) {
                drag.moved = true;
                band = { a: drag.index, b: index };
                drawCursors();
            }
            return;
        }
        const canvas = event.target.closest("canvas.field");
        if (!canvas || !canvas._box) return;
        if (event.pointerType === "touch" && !dragging) return;
        selectIndex(indexFromCanvas(canvas, event.clientX));
    });
    window.addEventListener("pointerup", () => {
        if (drag) {
            if (drag.moved && band) {
                const lo = Math.min(band.a, band.b);
                const hi = Math.max(band.a, band.b) + 1;
                setView(lo, hi);
            } else {
                selectIndex(drag.index);
            }
            drag = null;
            band = null;
            drawCursors();
        }
        dragging = false;
    });
    charts.addEventListener("dblclick", (event) => {
        if (!event.target.closest("canvas.field")) return;
        t0 = range0;
        t1 = range1;
        band = null;
        drawFields();
    });
    charts.addEventListener("wheel", (event) => {
        if (!event.ctrlKey && !event.metaKey) return;
        const canvas = event.target.closest("canvas.field");
        if (!canvas || !canvas._box || !active) return;
        event.preventDefault();
        const anchor = indexFromCanvas(canvas, event.clientX);
        zoomBy(event.deltaY > 0 ? 1.4 : 1 / 1.4, anchor);
    }, { passive: false });
    charts.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft") {
            selectIndex(selected - 1);
            event.preventDefault();
        } else if (event.key === "ArrowRight") {
            selectIndex(selected + 1);
            event.preventDefault();
        }
    });
    document.querySelectorAll("[data-period]").forEach((button) => {
        button.addEventListener("click", () => {
            applyPeriod(button.dataset.period).catch(showError);
        });
    });
    document.querySelectorAll("[data-moisture]").forEach((button) => {
        button.addEventListener("click", () => {
            moisture = button.dataset.moisture;
            document.querySelectorAll("[data-moisture]").forEach((item) => {
                item.setAttribute("aria-pressed", item === button ? "true" : "false");
            });
            drawHeat(document.getElementById("moist-field"), moisture);
            paintScale("scale-moist", SCALES[moisture]);
            drawCursors();
        });
    });
    const observer = new ResizeObserver(() => {
        if (active) drawFields();
    });
    observer.observe(document.querySelector(".charts"));
    observer.observe(document.getElementById("profile"));
    const about = document.querySelector(".about-layout");
    if (about) {
        const aboutObserver = new ResizeObserver(() => fitPortrait());
        aboutObserver.observe(about);
        fitPortrait();
    }
}

function fitPortrait() {
    const layout = document.querySelector(".about-layout");
    const copy = document.querySelector(".about-copy");
    const frame = document.querySelector(".portrait-frame");
    if (!layout || !copy || !frame) return;
    const gap = parseFloat(getComputedStyle(layout).columnGap) || 0;
    let side = 0;
    for (let pass = 0; pass < 6; pass += 1) {
        const next = Math.round(copy.getBoundingClientRect().height);
        const limit = Math.max(120, layout.clientWidth - gap - 200);
        const fitted = Math.max(120, Math.min(next, limit));
        if (Math.abs(fitted - side) < 2) break;
        side = fitted;
        frame.style.width = `${side}px`;
    }
}

function showError(error) {
    console.error(error);
    document.getElementById("status").textContent = "De meetgegevens zijn niet geladen.";
}

async function start() {
    const response = await fetch("app/data/meta.json");
    if (!response.ok) throw new Error("meta.json");
    meta = await response.json();
    fillHero();
    recent = await loadView("recent");
    bindCharts();
    await applyPeriod("60d");
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(() => {
            if (active) drawFields();
            fitPortrait();
        });
    }
}

start().catch(showError);
