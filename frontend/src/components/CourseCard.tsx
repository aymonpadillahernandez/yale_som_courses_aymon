import { useState } from "react";
import type { Course } from "../api";
import { schoolLabel } from "../schools";

function clean(value: string | number | undefined): string {
  return String(value ?? "").trim();
}

export default function CourseCard({ course, showSchool }: { course: Course; showSchool: boolean }) {
  const [open, setOpen] = useState(false);

  const title = clean(course["Course Title"]) || "Untitled course";
  const number = clean(course["Course Number"]);
  const category = clean(course["Course Category"]);
  const schoolCode = clean(course["School Code"]) || "MG";
  const school = schoolLabel(schoolCode, clean(course.School));
  const isSom = schoolCode === "MG";
  const faculty = clean(course["Faculty 1"]);
  const emails = clean(course["Faculty 1 Email"])
    .split(";")
    .map((e) => e.trim())
    .filter(Boolean);
  const daytimes = clean(course.Daytimes);
  const room = clean(course.Room);
  const units = clean(course.Units);
  const sections = Number(course.Sections ?? 1);
  const session = clean(course["Course Session"]);
  const bid = clean(course["Bid Or Permission"]);
  const sameAs = clean(course["Same As"]);
  const description = clean(course["Course Description"]);
  const bio = clean(course.faculty_bio);
  const syllabus = clean(course.Syllabus) || clean(course["Old Syllabus"]);
  const sourceUrl = clean(course["Source URL"]);

  return (
    <article className="card">
      <header className="card-head">
        <div className="card-heading">
          {(number || showSchool) && (
            <p className="card-number">
              {number}
              {showSchool && <span className="card-school">{school}</span>}
            </p>
          )}
          <h3 className="card-title">{title}</h3>
        </div>
        {category && <span className="badge">{category}</span>}
      </header>

      <dl className="card-facts">
        <div>
          <dt>Faculty</dt>
          <dd>{faculty || "Not listed"}</dd>
        </div>
        <div>
          <dt>Meets</dt>
          <dd>{daytimes || "Not listed"}</dd>
        </div>
        {(isSom || room) && (
          <div>
            <dt>Room</dt>
            <dd>{room || "Not listed"}</dd>
          </div>
        )}
        <div>
          <dt>{isSom ? "Units" : "Credits"}</dt>
          <dd>{units || "Not listed"}</dd>
        </div>
        {!isSom && sections > 1 && (
          <div>
            <dt>Sections</dt>
            <dd>{sections}</dd>
          </div>
        )}
      </dl>

      {description ? (
        <p className={open ? "card-desc" : "card-desc card-desc-clamped"}>{description}</p>
      ) : (
        <p className="card-desc card-desc-empty">No description listed.</p>
      )}

      {open && (
        <div className="card-extra">
          {bio && (
            <section>
              <h4>About {faculty || "the instructor"}</h4>
              <p>{bio}</p>
            </section>
          )}
          {(session || bid || sameAs || !showSchool) && (
            <dl className="card-facts">
              {!showSchool && (
                <div>
                  <dt>School</dt>
                  <dd>{school}</dd>
                </div>
              )}
              {sameAs && (
                <div>
                  <dt>Also listed as</dt>
                  <dd>{sameAs}</dd>
                </div>
              )}
              {session && (
                <div>
                  <dt>Session</dt>
                  <dd>{session}</dd>
                </div>
              )}
              {bid && (
                <div>
                  <dt>Enrolment</dt>
                  <dd>{bid}</dd>
                </div>
              )}
            </dl>
          )}
          {emails.length > 0 && (
            <p className="card-email">
              {emails.map((email, i) => (
                <span key={email}>
                  {i > 0 && ", "}
                  <a href={`mailto:${email}`}>{email}</a>
                </span>
              ))}
            </p>
          )}
        </div>
      )}

      <footer className="card-foot">
        <button type="button" className="link-button" onClick={() => setOpen(!open)}>
          {open ? "Show less" : "Show more"}
        </button>
        {syllabus && (
          <a className="link-button" href={syllabus} target="_blank" rel="noreferrer">
            Syllabus
          </a>
        )}
        {sourceUrl && (
          <a className="link-button" href={sourceUrl} target="_blank" rel="noreferrer">
            Yale Course Search
          </a>
        )}
      </footer>
    </article>
  );
}
