import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useLanguage } from "../i18n.jsx";

// The dashboard. Four headline numbers are stat tiles, not a chart - a handful of
// totals has no shape worth plotting. The rates are meters, because each is one ratio
// against a limit. Only the two rankings and the daily activity are real charts, and
// they are bars in a single hue: the length already carries the magnitude, so colouring
// each bar differently would say the same thing twice.
//
// "Answered" and "not answered" use the reserved status green and red, and both ship
// with an icon and a word, so the colour never carries the meaning on its own.

function Tile({ label, value, note, tone = "neutral", icon }) {
  return (
    <div className={`tile tone-${tone}`}>
      <div className="tile-top">
        <span className="tile-label">{label}</span>
        {icon}
      </div>
      <strong className="tile-value">{value}</strong>
      {note && <span className="tile-note">{note}</span>}
    </div>
  );
}

function Meter({ label, rate, note }) {
  const percent = rate === null ? 0 : Math.round(rate * 100);
  return (
    <div className="meter">
      <div className="meter-head">
        <span>{label}</span>
        <strong>{rate === null ? "—" : `${percent}%`}</strong>
      </div>
      <div
        className="meter-track"
        role="meter"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div className="meter-fill" style={{ width: `${percent}%` }} />
      </div>
      {note && <span className="meter-note">{note}</span>}
    </div>
  );
}

function BarList({ rows, labelOf, valueOf, tipOf }) {
  const most = Math.max(...rows.map(valueOf), 1);
  return (
    <ol className="bars">
      {rows.map((row, index) => (
        <li className="bar-row" key={index}>
          <div className="bar-label" title={labelOf(row)}>
            {labelOf(row)}
          </div>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${Math.max((valueOf(row) / most) * 100, 3)}%` }}
            />
            <span className="bar-tip">{tipOf(row)}</span>
          </div>
          <div className="bar-value">{valueOf(row)}</div>
        </li>
      ))}
    </ol>
  );
}

// Two series - answered and not answered - so this is a stacked bar with a legend,
// horizontal because the department names are long. The two segments use the reserved
// status colours and are separated by a 2px gap of the card surface, so where one ends
// and the next begins is never in doubt. Each one is also labelled in the tooltip, so
// the colour is not carrying the distinction on its own.
function Departments({ rows, strings }) {
  const most = Math.max(...rows.map((row) => row.questions), 1);
  return (
    <>
      <div className="legend">
        <span className="legend-item">
          <span className="legend-swatch is-good" />
          {strings.legendAnswered}
        </span>
        <span className="legend-item">
          <span className="legend-swatch is-critical" />
          {strings.legendRefused}
        </span>
      </div>
      <ol className="bars">
        {rows.map((row) => (
          <li className="bar-row" key={row.department}>
            <div className="bar-label">
              {strings.department[row.department] || row.department}
            </div>
            <div className="bar-track">
              <div className="stack" style={{ width: `${(row.questions / most) * 100}%` }}>
                {row.answered > 0 && (
                  <div
                    className="stack-part is-good"
                    style={{ flexGrow: row.answered }}
                    title={strings.legendAnswered}
                  />
                )}
                {row.refused > 0 && (
                  <div
                    className="stack-part is-critical"
                    style={{ flexGrow: row.refused }}
                    title={strings.legendRefused}
                  />
                )}
              </div>
              <span className="bar-tip">
                {strings.ofDepartment(row.answered, row.refused)}
              </span>
            </div>
            <div className="bar-value">{row.questions}</div>
          </li>
        ))}
      </ol>
    </>
  );
}

export default function Dashboard() {
  const { strings } = useLanguage();
  const [data, setData] = useState(null);
  const [problem, setProblem] = useState(null);

  useEffect(() => {
    api.stats().then(setData).catch((error) => setProblem(error.message));
  }, []);

  if (problem) return <div className="error">{problem}</div>;
  if (!data) return <div className="dash-loading" />;

  const nothingYet = data.questions === 0;
  const busiest = Math.max(...data.activity.map((day) => day.count), 1);
  // Just the day of the month. Fourteen labels of "13/10" were what stopped the columns
  // shrinking; the full date is in the tooltip, where there is room for it.
  const shortDay = (day) => day.slice(8);

  return (
    <div className="dash">
      <header className="dash-head">
        <h2>{strings.statsTitle}</h2>
        <p>{strings.statsSubtitle}</p>
      </header>

      {nothingYet ? (
        <p className="dash-empty">{strings.noData}</p>
      ) : (
        <>
          <section className="tiles">
            <Tile
              label={strings.statQuestions}
              value={data.questions}
              note={strings.statConversations(data.conversations)}
              icon={
                <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
                  <path d="M3 4h10v7H7l-3 2.5V11H3z" fill="none" stroke="currentColor"
                        strokeWidth="1.4" strokeLinejoin="round" />
                </svg>
              }
            />
            <Tile
              label={strings.statAnswered}
              value={data.answered}
              tone="good"
              note={`${Math.round((data.answered / data.questions) * 100)}% ${strings.ofQuestions}`}
              icon={
                <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
                  <path d="M3 8.5l3.2 3L13 5" fill="none" stroke="currentColor"
                        strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              }
            />
            <Tile
              label={strings.statRefused}
              value={data.refused}
              tone="critical"
              note={`${Math.round((data.refused / data.questions) * 100)}% ${strings.ofQuestions}`}
              icon={
                <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
                  <circle cx="8" cy="8" r="5.4" fill="none" stroke="currentColor"
                          strokeWidth="1.4" />
                  <path d="M8 5.2v4.1M8 11.1v.1" stroke="currentColor" strokeWidth="1.5"
                        strokeLinecap="round" />
                </svg>
              }
            />
            <Tile
              label={strings.statCitation}
              value={data.with_citation}
              note={
                data.citation_rate === 1
                  ? strings.perfect
                  : `${Math.round((data.citation_rate || 0) * 100)}% ${strings.ofAnswers}`
              }
              icon={
                <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
                  <path d="M4 3h8v10l-4-2.4L4 13z" fill="none" stroke="currentColor"
                        strokeWidth="1.4" strokeLinejoin="round" />
                </svg>
              }
            />
          </section>

          <section className="meters">
            <Meter label={strings.answerRate} rate={data.answer_rate} />
            <Meter label={strings.citationRate} rate={data.citation_rate} />
            <Meter
              label={strings.helpfulRate}
              rate={data.helpful_rate}
              note={data.rated > 0 ? strings.ratedOf(data.rated) : strings.noRatings}
            />
          </section>

          <section className="card">
            <h3>{strings.activity}</h3>
            <p className="card-note">{strings.activityNote}</p>
            <div className="columns">
              {data.activity.map((day) => (
                <div className="column" key={day.day}>
                  <div className="column-track">
                    <div
                      className="column-fill"
                      style={{ height: `${(day.count / busiest) * 100}%` }}
                    />
                    <span className="column-tip">
                      {strings.questionsOn(day.count, day.day.slice(5).replace("-", "/"))}
                    </span>
                  </div>
                  <span className="column-label">{shortDay(day.day)}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="card">
            <h3>{strings.byDepartment}</h3>
            <p className="card-note">{strings.byDepartmentNote}</p>
            {data.departments.length === 0 ? (
              <p className="card-empty">—</p>
            ) : (
              <Departments rows={data.departments} strings={strings} />
            )}
          </section>

          <div className="dash-columns">
            <section className="card">
              <h3>{strings.topQuestions}</h3>
              <p className="card-note">{strings.topQuestionsNote}</p>
              <BarList
                rows={data.top_questions}
                labelOf={(row) => row.question}
                valueOf={(row) => row.count}
                tipOf={(row) => strings.times(row.count)}
              />
            </section>

            <section className="card">
              <h3>{strings.citedFiles}</h3>
              <p className="card-note">&nbsp;</p>
              <BarList
                rows={data.cited_files}
                labelOf={(row) => row.file}
                valueOf={(row) => row.count}
                tipOf={(row) => strings.times(row.count)}
              />
            </section>
          </div>

          {data.disliked > 0 && (
            <div className="dash-columns">
              <section className="card">
                <h3>{strings.reasonsTitle}</h3>
                <p className="card-note">{strings.reasonsNote}</p>
                <ol className="bars">
                  {data.reasons.map((row) => (
                    <li className="bar-row" key={row.reason}>
                      <div className="bar-label" title={strings.reason[row.reason]}>
                        {strings.reason[row.reason] || row.reason}
                      </div>
                      <div className="bar-track">
                        <div
                          className="bar-fill is-bad"
                          style={{ width: `${Math.max(row.share * 100, 3)}%` }}
                        />
                        <span className="bar-tip">
                          {row.count} · {Math.round(row.share * 100)}%
                        </span>
                      </div>
                      <div className="bar-value">{Math.round(row.share * 100)}%</div>
                    </li>
                  ))}
                </ol>
              </section>

              <section className="card">
                <h3>{strings.flaggedTitle}</h3>
                <p className="card-note">{strings.flaggedNote}</p>
                <ul className="flagged">
                  {data.flagged.map((row, index) => (
                    <li key={index}>
                      <span className="flagged-question">{row.question}</span>
                      <span className="flagged-reason">
                        {strings.reason[row.reason] || row.reason}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          )}

          <section className="card">
            <h3>{strings.unanswered}</h3>
            <p className="card-note">{strings.unansweredNote}</p>
            {data.refused_questions.length === 0 ? (
              <p className="card-empty">—</p>
            ) : (
              <ul className="refused-list">
                {data.refused_questions.map((row, index) => (
                  <li key={index}>
                    <span className="refused-mark" aria-hidden="true" />
                    <span className="refused-question">{row.question}</span>
                    <time>{row.asked_at.slice(0, 10)}</time>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
