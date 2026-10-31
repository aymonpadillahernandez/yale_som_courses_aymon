import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { fetchCourses, fetchSchools, type Course, type School } from "./api";
import { schoolLabel } from "./schools";
import CourseCard from "./components/CourseCard";
import ChatPanel from "./components/ChatPanel";

const PAGE_SIZE = 48;
const SOM = "MG";

export default function App() {
  const [schools, setSchools] = useState<School[]>([]);
  const [term, setTerm] = useState("");
  const [total, setTotal] = useState(0);

  const [school, setSchool] = useState("All");
  const [category, setCategory] = useState("All");
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");

  const [courses, setCourses] = useState<Course[]>([]);
  const [count, setCount] = useState(0);
  const [loadedKey, setLoadedKey] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(0);

  useEffect(() => {
    fetchSchools()
      .then((data) => {
        setSchools(data.schools);
        setTerm(data.term);
        setTotal(data.total);
      })
      .catch(() => {
        // The course request below reports the outage; the filters just stay empty.
      });
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  // Any filter change reloads page one; stale responses are dropped by request id.
  const filterKey = JSON.stringify([debounced, school, category]);
  const loading = loadedKey !== filterKey;
  useEffect(() => {
    const id = ++request.current;
    fetchCourses({ q: debounced, school, category, offset: 0, limit: PAGE_SIZE })
      .then((data) => {
        if (id !== request.current) return;
        setCourses(data.courses);
        setCount(data.count);
        setError("");
      })
      .catch((err: unknown) => {
        if (id !== request.current) return;
        const detail = err instanceof Error ? err.message : String(err);
        setError(`Could not load courses (${detail}). The server may be waking up; refresh in a minute.`);
      })
      .finally(() => {
        if (id === request.current) setLoadedKey(filterKey);
      });
  }, [debounced, school, category, filterKey]);

  function loadMore() {
    const id = request.current;
    setLoadingMore(true);
    fetchCourses({ q: debounced, school, category, offset: courses.length, limit: PAGE_SIZE })
      .then((data) => {
        if (id !== request.current) return;
        setCourses((prev) => [...prev, ...data.courses]);
      })
      .catch((err: unknown) => {
        const detail = err instanceof Error ? err.message : String(err);
        setError(`Could not load more courses (${detail}).`);
      })
      .finally(() => setLoadingMore(false));
  }

  // Management first (it is home), then the rest alphabetically.
  const orderedSchools = useMemo(
    () =>
      [...schools].sort((a, b) => {
        if (a.code === SOM || b.code === SOM) return a.code === SOM ? -1 : 1;
        return schoolLabel(a.code, a.name).localeCompare(schoolLabel(b.code, b.name));
      }),
    [schools],
  );

  const categories = useMemo(() => {
    const pool = school === "All" ? schools : schools.filter((s) => s.code === school);
    const found = new Set(pool.flatMap((s) => s.categories));
    return Array.from(found).sort();
  }, [schools, school]);

  function pickSchool(code: string) {
    setSchool(code);
    setCategory("All");
  }

  const selected = schools.find((s) => s.code === school);
  const scopeLabel = selected ? schoolLabel(selected.code, selected.name) : "all schools";

  return (
    <div className="shell">
      <header className="masthead">
        <div className="masthead-inner">
          <p className="eyebrow">Yale University{term ? ` · ${term}` : ""}</p>
          <h1>Course explorer</h1>
          <p className="lede">
            {total ? `${total.toLocaleString()} courses` : "Courses"} across every Yale school. Pick a
            school, search, then ask the assistant what the listing does not say.
          </p>
        </div>
      </header>

      <main className="layout">
        <section className="catalog" aria-label="Course catalog">
          {schools.length > 0 && (
            <nav className="schools" aria-label="Filter by school">
              <button
                type="button"
                className={school === "All" ? "school-chip school-chip-on" : "school-chip"}
                aria-pressed={school === "All"}
                onClick={() => pickSchool("All")}
              >
                All schools <span>{total.toLocaleString()}</span>
              </button>
              {orderedSchools.map((s) => (
                <button
                  key={s.code}
                  type="button"
                  title={s.name}
                  className={school === s.code ? "school-chip school-chip-on" : "school-chip"}
                  aria-pressed={school === s.code}
                  onClick={() => pickSchool(s.code)}
                >
                  {schoolLabel(s.code, s.name)} <span>{s.count.toLocaleString()}</span>
                </button>
              ))}
            </nav>
          )}

          <div className="controls">
            <div className="field">
              <label className="sr-only" htmlFor="course-search">
                Search courses
              </label>
              <input
                id="course-search"
                type="search"
                value={query}
                placeholder={`Search ${scopeLabel} by title, number, faculty or topic`}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            {categories.length > 1 && (
              <div className="field field-narrow">
                <label className="sr-only" htmlFor="course-category">
                  Filter by subject
                </label>
                <select
                  id="course-category"
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                >
                  <option value="All">All subjects</option>
                  {categories.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <p className="result-count" aria-live="polite">
            {loading
              ? "Loading catalog…"
              : `Showing ${courses.length.toLocaleString()} of ${count.toLocaleString()} courses in ${scopeLabel}`}
          </p>

          {error && <p className="banner banner-error">{error}</p>}

          {!loading && !error && courses.length === 0 && (
            <p className="banner">No courses match that search. Try fewer words or another school.</p>
          )}

          <div className={loading ? "grid grid-loading" : "grid"}>
            {courses.map((course) => (
              <CourseCard
                key={`${course["School Code"]}-${course["Course ID"]}-${course.Section}`}
                course={course}
                showSchool={school === "All"}
              />
            ))}
          </div>

          {!loading && courses.length < count && (
            <div className="more">
              <button type="button" onClick={loadMore} disabled={loadingMore}>
                {loadingMore
                  ? "Loading…"
                  : `Show ${Math.min(PAGE_SIZE, count - courses.length)} more`}
              </button>
            </div>
          )}
        </section>

        <aside className="rail">
          <ChatPanel />
        </aside>
      </main>
    </div>
  );
}
