import { describe, expect, it } from "vitest";
import { toCsv } from "@/lib/csv-export";

describe("toCsv", () => {
  it("builds a header row from column definitions, in order", () => {
    const csv = toCsv([{ name: "Acme", count: 3 }], [
      { key: "name", header: "Company" },
      { key: "count", header: "Count" },
    ]);
    expect(csv.split("\r\n")[0]).toBe("Company,Count");
  });

  it("renders one data row per input row", () => {
    const csv = toCsv(
      [
        { name: "Acme", count: 3 },
        { name: "Globex", count: 5 },
      ],
      [
        { key: "name", header: "Company" },
        { key: "count", header: "Count" },
      ],
    );
    const lines = csv.split("\r\n");
    expect(lines).toEqual(["Company,Count", "Acme,3", "Globex,5"]);
  });

  it("escapes values containing commas, quotes or newlines", () => {
    const csv = toCsv([{ note: 'Has, a comma and "quotes"' }], [{ key: "note", header: "Note" }]);
    expect(csv.split("\r\n")[1]).toBe('"Has, a comma and ""quotes"""');
  });

  it("joins array values with a semicolon", () => {
    const csv = toCsv([{ skills: ["Python", "SQL"] }], [{ key: "skills", header: "Skills" }]);
    expect(csv.split("\r\n")[1]).toBe("Python; SQL");
  });

  it("renders null/undefined as an empty cell", () => {
    const csv = toCsv([{ value: null }], [{ key: "value", header: "Value" }]);
    expect(csv.split("\r\n")[1]).toBe("");
  });

  it("returns just the header for an empty row set", () => {
    const csv = toCsv([], [{ key: "name", header: "Company" }]);
    expect(csv).toBe("Company");
  });
});
