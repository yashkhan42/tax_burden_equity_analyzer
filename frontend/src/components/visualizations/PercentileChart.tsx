import styles from "./visualizations.module.css";
import {
  clamp,
  formatAxisNumber,
  preparePercentileBins,
} from "./helpers";
import type { PercentileResponse } from "./types";

const WIDTH = 880;
const HEIGHT = 276;
const MARGIN = { top: 28, right: 20, bottom: 62, left: 20 };
const ZERO_EDGE = 0.95;

function ticksFor(domain: [number, number]): number[] {
  const [minimum, maximum] = domain;
  const roughCount = Math.max(0, Math.floor(maximum / 10) - Math.ceil(minimum / 10));
  const step = roughCount > 9 ? 20 : 10;
  const ticks: number[] = [];
  for (
    let value = Math.ceil(minimum / step) * step;
    value <= maximum;
    value += step
  ) {
    ticks.push(value);
  }
  if (minimum < 0 && maximum > 0 && !ticks.includes(0)) ticks.push(0);
  return ticks.sort((left, right) => left - right);
}

export function PercentileChart(props: PercentileResponse) {
  const {
    markerRate,
    displayRate,
    percentile,
    belowCount,
    bins,
    binWidth,
    shareExactlyZero,
    shareNegative,
    domain,
    summary,
  } = props;

  const [domainMinimum, domainMaximum] = domain;
  const domainSpan = Math.max(domainMaximum - domainMinimum, 1);
  const plotWidth = WIDTH - MARGIN.left - MARGIN.right;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const plotBottom = MARGIN.top + plotHeight;
  const x = (value: number) =>
    MARGIN.left + ((value - domainMinimum) / domainSpan) * plotWidth;

  const prepared = preparePercentileBins(
    bins,
    binWidth,
    shareExactlyZero,
  );
  const tallest = Math.max(
    shareExactlyZero,
    ...prepared.map((bin) => bin.share),
    0.01,
  );
  const headroom = tallest * 1.35;
  const y = (share: number) =>
    MARGIN.top + plotHeight - (share / headroom) * plotHeight;

  const marker = clamp(markerRate, domainMinimum, domainMaximum);
  const markerOnZero = Math.abs(markerRate) <= ZERO_EDGE;
  const zeroTop = y(shareExactlyZero);
  const markerX = x(marker);
  const labelOnLeft = markerX > WIDTH - 130;
  const negativeCount = Math.round(shareNegative * 100);
  const zeroCount = Math.round(shareExactlyZero * 100);

  return (
    <figure className={`${styles.root} ${styles.percentile}`}>
      <div className={styles.chartScroller}>
        <svg
          className={styles.percentileSvg}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={`${summary} The displayed rate is ${displayRate}. It is above about ${belowCount} in every 100 reference filers.`}
        >
        <title>Where this filer sits among the survey examples</title>
        <desc>
          Bars show the spread of predicted effective rates in the comparison
          group. Rates below zero and rates of exactly zero are shown
          separately. This filer is marked at {displayRate}, around percentile{" "}
          {Math.round(percentile)}.
        </desc>

        <rect
          className={styles.negativeRegion}
          x={x(domainMinimum)}
          y={MARGIN.top}
          width={Math.max(0, x(-ZERO_EDGE) - x(domainMinimum))}
          height={plotHeight}
        />

        <text
          className={styles.chartAnnotation}
          x={x(domainMinimum) + 12}
          y={MARGIN.top + 18}
        >
          Rates below zero
        </text>
        <text
          className={styles.chartAnnotationMuted}
          x={x(domainMinimum) + 12}
          y={MARGIN.top + 36}
        >
          About {negativeCount} in 100 got more back than they paid
        </text>

        {prepared.map((bin) => {
          const barX = x(bin.start);
          const barTop = y(bin.share);
          return (
            <rect
              key={`${bin.start}-${bin.end}-${bin.exactZero}`}
              className={`${styles.distributionBar} ${styles.mark}`}
              x={barX}
              y={barTop}
              width={Math.max(1, x(bin.end) - barX)}
              height={Math.max(0, plotBottom - barTop)}
            />
          );
        })}

        <line
          className={styles.axisLine}
          x1={MARGIN.left}
          x2={WIDTH - MARGIN.right}
          y1={plotBottom}
          y2={plotBottom}
        />

        {ticksFor(domain).map((tick) => (
          <g className={styles.axisTick} key={tick}>
            <line
              className={tick === 0 ? styles.zeroTick : styles.tickLine}
              x1={x(tick)}
              x2={x(tick)}
              y1={plotBottom}
              y2={plotBottom + 7}
            />
            <text
              className={styles.tickText}
              x={x(tick)}
              y={plotBottom + 23}
              textAnchor="middle"
            >
              {formatAxisNumber(tick)}
            </text>
          </g>
        ))}

        {shareExactlyZero > 0 ? (
          <>
            <text
              className={styles.zeroLabel}
              x={x(0)}
              y={Math.max(MARGIN.top + 18, zeroTop - 26)}
              textAnchor="middle"
            >
              Owed exactly nothing
            </text>
            <text
              className={styles.chartAnnotationMuted}
              x={x(0)}
              y={Math.max(MARGIN.top + 34, zeroTop - 10)}
              textAnchor="middle"
            >
              About {zeroCount} in 100
            </text>
          </>
        ) : null}

        <line
          className={`${styles.markerLine} ${styles.mark}`}
          x1={markerX}
          x2={markerX}
          y1={MARGIN.top + 4}
          y2={markerOnZero ? Math.max(MARGIN.top + 8, zeroTop - 5) : plotBottom}
        />
        <circle
          className={`${styles.markerDot} ${styles.mark}`}
          cx={markerX}
          cy={MARGIN.top + 4}
          r={5}
        />
        <text
          className={styles.markerLabel}
          x={markerX + (labelOnLeft ? -9 : 9)}
          y={MARGIN.top + 9}
          textAnchor={labelOnLeft ? "end" : "start"}
        >
          This profile · {displayRate}
        </text>

        <text
          className={styles.axisTitle}
          x={MARGIN.left + plotWidth / 2}
          y={HEIGHT - 8}
          textAnchor="middle"
        >
          Effective federal tax rate, percent of income
        </text>
        </svg>
      </div>

      <figcaption className={styles.summary}>{summary}</figcaption>
    </figure>
  );
}
