const path = require("path");
const os = require("os");
const { promises: fs } = require("fs");
const execa = require("execa");

describe("interactivecls.js – config command", () => {
  test("writes a default experiment JSON file", async () => {
    // 1. Make a temp directory
    const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "cli-"));
    const outFile = path.join(tmp, "exp.json");
    const script  = path.resolve(__dirname, "../interactivecls.js");

    // 2. Run the CLI
    const { stdout } = await execa("node", [script, "config", outFile, "--output"]);

    // 3. Expect confirmation text
    expect(stdout).toMatch(/written/i);

    // 4. Read & parse the file
    const data = JSON.parse(await fs.readFile(outFile, "utf8"));

    // 5. Assert basic structure
    expect(Array.isArray(data.sets)).toBe(true);
    expect(data.sets.length).toBeGreaterThan(0);
  });
});