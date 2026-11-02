// REQ-P08-S04-019: no screen may use diagnostic wording.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const FORBIDDEN = /\b(heal(s|ed|ing)?|deteriorat\w*|improving|worsening|treatment response|prognosis|clinical recommendation)\b/i;
const ALLOWED = ["Not a clinical assessment of healing, prognosis or treatment response."];
const ROOTS = ["app", "components", "lib"];

function* files(directory) {
  for (const name of readdirSync(directory)) {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (/\.(tsx?|css)$/.test(name)) yield path;
  }
}

let failures = 0;
for (const root of ROOTS) {
  for (const path of files(root)) {
    readFileSync(path, "utf8")
      .split("\n")
      .forEach((line, index) => {
        const text = ALLOWED.reduce((value, phrase) => value.replace(phrase, ""), line);
        if (FORBIDDEN.test(text)) {
          console.error(`${path}:${index + 1}: ${line.trim()}`);
          failures += 1;
        }
      });
  }
}

if (failures) process.exit(1);
console.log("Wording check passed.");
