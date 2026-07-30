import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

const root = process.cwd();
const dist = path.join(root, "dist");

await rm(dist, { recursive: true, force: true });
await mkdir(path.join(dist, "server"), { recursive: true });
await mkdir(path.join(dist, "client"), { recursive: true });
await mkdir(path.join(dist, ".openai"), { recursive: true });

await cp(path.join(root, "index.html"), path.join(dist, "client", "index.html"));
await cp(path.join(root, ".openai", "hosting.json"), path.join(dist, ".openai", "hosting.json"));

const trackedDataFiles = execFileSync("git", ["ls-files", "data"], { cwd: root, encoding: "utf8" })
  .split("\n")
  .filter(Boolean);

for (const file of trackedDataFiles) {
  await mkdir(path.dirname(path.join(dist, "client", file)), { recursive: true });
  await cp(path.join(root, file), path.join(dist, "client", file));
}

if (existsSync(path.join(root, "public"))) {
  await cp(path.join(root, "public"), path.join(dist, "client"), { recursive: true });
}

const worker = `
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let response = await env.ASSETS.fetch(request);

    if (response.status === 404 && !url.pathname.includes(".")) {
      response = await env.ASSETS.fetch(new Request(new URL("/index.html", url), request));
    }

    return response;
  }
};
`;

await writeFile(path.join(dist, "server", "index.js"), worker.trimStart());
