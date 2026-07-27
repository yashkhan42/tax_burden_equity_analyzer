import styles from "./visualizations.module.css";
import {
  contributionScale,
  formatRate,
  formatSignedPoints,
  prepareContribution,
} from "./helpers";
import type { ContributionResponse, Reason } from "./types";

interface ReasonRowProps {
  reason: Reason;
  zeroPercent: number;
  lengthPercent: number;
  supporting?: boolean;
}

function ReasonRow({
  reason,
  zeroPercent,
  lengthPercent,
  supporting = false,
}: ReasonRowProps) {
  const raises = reason.points > 0;
  const left = raises ? zeroPercent : zeroPercent - lengthPercent;
  const direction = raises ? "Raises" : "Lowers";

  return (
    <div
      className={`${styles.contributionRow} ${
        supporting ? styles.supportingRow : ""
      }`}
    >
      <p className={styles.reasonText}>{reason.text}</p>
      <div
        className={styles.barArea}
        role="img"
        aria-label={`${direction} the effective rate by ${Math.abs(
          reason.points,
        ).toFixed(1)} percentage points.`}
      >
        <div className={styles.barTrack} aria-hidden="true">
          <span
            className={styles.barZero}
            style={{ left: `${zeroPercent}%` }}
          />
          <span
            className={`${styles.barFill} ${
              raises ? styles.barRaised : styles.barLowered
            } ${styles.mark}`}
            style={{
              left: `${left}%`,
              width: `max(3px, ${lengthPercent}%)`,
            }}
          />
        </div>
        <span
          className={`${styles.points} ${
            raises ? styles.pointsRaised : styles.pointsLowered
          }`}
        >
          {formatSignedPoints(reason.points)}
        </span>
      </div>
    </div>
  );
}

export function ContributionChart(props: ContributionResponse) {
  const prepared = prepareContribution(props);
  const remainderReason: Reason | null =
    prepared.remainder === null
      ? null
      : { text: "Everything else together", points: prepared.remainder };
  const allRows = remainderReason
    ? [...prepared.reasons, remainderReason]
    : prepared.reasons;
  const scale = contributionScale(allRows.map((row) => row.points));
  const raised = prepared.reasons.filter((reason) => reason.points > 0);
  const lowered = prepared.reasons.filter((reason) => reason.points < 0);
  const raisedFirst =
    prepared.reasons.length === 0 || prepared.reasons[0].points >= 0;
  const groups = (
    raisedFirst
      ? [
          { label: "Raised the rate", rows: raised },
          { label: "Lowered the rate", rows: lowered },
        ]
      : [
          { label: "Lowered the rate", rows: lowered },
          { label: "Raised the rate", rows: raised },
        ]
  ).filter((group) => group.rows.length > 0);

  return (
    <section
      className={`${styles.root} ${styles.contribution}`}
      aria-label="What shaped this filer’s rate"
    >
      <p className={styles.summary}>{props.summary}</p>

      <div className={styles.contributionFigures}>
        <div className={styles.figureBlock}>
          <span className={styles.figureLabel}>Typical prediction</span>
          <strong className={styles.figureValue}>
            {formatRate(props.baseline)}
          </strong>
        </div>
        <div className={styles.figureBlock}>
          <span className={styles.figureLabel}>This profile</span>
          <strong className={styles.figureValue}>
            {formatRate(props.predicted)}
          </strong>
        </div>
      </div>
      <p className={styles.unitNote}>
        Each bar shows how many percentage points one characteristic adds or
        subtracts.
      </p>

      {prepared.calm ? (
        <div className={styles.calmState}>
          <p className={styles.calmTitle}>No single reason stands apart.</p>
          <p className={styles.calmCopy}>
            This rate is close to the starting point; the remaining differences
            are too small to present as distinct findings.
          </p>
        </div>
      ) : (
        <div className={styles.reasonGroups}>
          {groups.map((group) => (
            <section className={styles.reasonGroup} key={group.label}>
              <h3 className={styles.reasonHeading}>{group.label}</h3>
              <div className={styles.reasonList}>
                {group.rows.map((reason, index) => (
                  <ReasonRow
                    key={`${reason.text}-${index}`}
                    reason={reason}
                    zeroPercent={scale.zeroPercent}
                    lengthPercent={scale.lengthPercent(reason.points)}
                  />
                ))}
              </div>
            </section>
          ))}

          {remainderReason ? (
            <div className={styles.remainder}>
              <ReasonRow
                reason={remainderReason}
                zeroPercent={scale.zeroPercent}
                lengthPercent={scale.lengthPercent(remainderReason.points)}
                supporting
              />
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
