// Short labels for the school filter and the cards; the API sends full names.
const SHORT_NAMES: Record<string, string> = {
  MG: "Management",
  YC: "Yale College",
  GS: "Graduate School",
  MD: "Medicine",
  PH: "Public Health",
  FS: "Environment",
  DI: "Divinity",
  MU: "Music",
  NR: "Nursing",
  AC: "Architecture",
  AT: "Art",
  DR: "Drama",
  GB: "Global Affairs",
  PA: "Physician Associate",
};

export function schoolLabel(code: string, fallback = ""): string {
  return SHORT_NAMES[code] ?? (fallback || code);
}
