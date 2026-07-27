import styles from "./visualizations.module.css";
import { formatPointMagnitude, twinGeometry } from "./helpers";
import type { TwinAttribute, TwinResponse, TwinSide } from "./types";

interface TwinCardProps {
  side: TwinSide;
  changedLabel: string;
  shared: TwinAttribute[];
  rowCount: number;
  cardLabel: string;
}

function AttributeRow({
  label,
  value,
  changed = false,
}: TwinAttribute & { changed?: boolean }) {
  return (
    <div
      className={`${styles.twinRow} ${changed ? styles.changedRow : ""}`}
    >
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function TwinCard({
  side,
  changedLabel,
  shared,
  rowCount,
  cardLabel,
}: TwinCardProps) {
  return (
    <dl
      className={styles.twinCard}
      style={{ gridRow: `span ${rowCount}` }}
      aria-label={`${cardLabel}: ${side.label}, effective rate ${side.display}`}
    >
      <AttributeRow label={changedLabel} value={side.label} changed />
      {shared.map((attribute, index) => (
        <AttributeRow
          key={`${attribute.label}-${index}`}
          label={attribute.label}
          value={attribute.value}
        />
      ))}
      <div className={`${styles.twinRow} ${styles.rateRow}`}>
        <dt className={styles.figureLabel}>Effective rate</dt>
        <dd>
          <strong className={styles.twinRate}>{side.display}</strong>
        </dd>
      </div>
    </dl>
  );
}

export function TwinComparison(props: TwinResponse) {
  const geometry = twinGeometry(props);
  const rowCount = props.shared.length + 2;
  const plotLeft = 40;
  const plotWidth = 720;
  const toX = (percent: number) => plotLeft + (percent / 100) * plotWidth;
  const firstX = toX(geometry.firstPercent);
  const secondX = toX(geometry.secondPercent);
  const zeroX = toX(geometry.zeroPercent);
  const collapsedX = toX(geometry.collapsedPercent);
  const lowX = Math.min(firstX, secondX);
  const highX = Math.max(firstX, secondX);

  const stateNote = geometry.essentiallySame
    ? "The printed rates are the same to one decimal place."
    : geometry.crossesZero
      ? "One side pays tax; the other is paid."
      : geometry.bothNegative
        ? "Both rates are below zero."
        : geometry.eitherExactlyZero
          ? "One rate is exactly zero."
          : null;

  return (
    <section
      className={`${styles.root} ${styles.twin}`}
      aria-label="Twin comparison"
    >
      <p className={styles.summary}>{props.summary}</p>

      <div className={styles.twinCards}>
        <TwinCard
          side={props.a}
          changedLabel={props.changedLabel}
          shared={props.shared}
          rowCount={rowCount}
          cardLabel="Described filer"
        />
        <TwinCard
          side={props.b}
          changedLabel={props.changedLabel}
          shared={props.shared}
          rowCount={rowCount}
          cardLabel="Comparison filer"
        />
      </div>

      <div className={styles.gapBlock}>
        <p className={styles.gapLabel}>Difference in effective rate</p>
        {geometry.essentiallySame ? (
          <p className={styles.sameRate}>Essentially the same rate</p>
        ) : (
          <p className={styles.gapValue}>
            <strong>{formatPointMagnitude(props.gapPoints)}</strong>
            <span>points</span>
          </p>
        )}

        <figure className={styles.dumbbell}>
          <svg
            className={styles.dumbbellSvg}
            viewBox="0 0 800 108"
            role="img"
            aria-label={`${props.summary} ${props.a.label}: ${props.a.display}. ${props.b.label}: ${props.b.display}.`}
          >
            <title>Distance between the two effective rates</title>
            <desc>
              The scale includes zero. The connector shows the difference
              caused by changing {props.changed}.
            </desc>
            <line
              className={styles.dumbbellAxis}
              x1={plotLeft}
              x2={plotLeft + plotWidth}
              y1={50}
              y2={50}
            />
            <line
              className={styles.dumbbellZero}
              x1={zeroX}
              x2={zeroX}
              y1={30}
              y2={70}
            />
            <text
              className={styles.dumbbellZeroLabel}
              x={zeroX}
              y={88}
              textAnchor="middle"
            >
              0
            </text>

            {geometry.essentiallySame ? (
              <circle
                className={`${styles.dumbbellDotSecond} ${styles.mark}`}
                cx={collapsedX}
                cy={50}
                r={5}
              />
            ) : (
              <>
                <line
                  className={`${styles.dumbbellConnector} ${styles.mark}`}
                  x1={lowX}
                  x2={highX}
                  y1={50}
                  y2={50}
                />
                <circle
                  className={`${styles.dumbbellDotFirst} ${styles.mark}`}
                  cx={firstX}
                  cy={50}
                  r={5}
                />
                <circle
                  className={`${styles.dumbbellDotSecond} ${styles.mark}`}
                  cx={secondX}
                  cy={50}
                  r={5}
                />
              </>
            )}
          </svg>
        </figure>

        {stateNote ? <p className={styles.stateNote}>{stateNote}</p> : null}
        {props.gapMoney && !geometry.essentiallySame ? (
          <p className={styles.moneyNote}>{props.gapMoney}</p>
        ) : null}
        <p className={styles.comparisonNote}>{props.comparisonNote}</p>
      </div>
    </section>
  );
}
