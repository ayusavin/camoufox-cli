/** Config: read/write ~/.camoufox-cli/config.json */

import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";

export const CONFIG_DIR = path.join(os.homedir(), ".camoufox-cli");
export const CONFIG_PATH = path.join(CONFIG_DIR, "config.json");
export const EXTENSIONS_DIR = path.join(CONFIG_DIR, "extensions");
export const CAPSOLVER_XPI_PATH = path.join(EXTENSIONS_DIR, "capsolver.xpi");

export interface CliConfig {
  capsolver_api_key?: string;
  capsolver_extension_id?: string;
}

export function readConfig(): CliConfig {
  try {
    if (fs.existsSync(CONFIG_PATH))
      return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
  } catch {}
  return {};
}

export function writeConfig(config: CliConfig): void {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));
}

export function hasCapsolverXpi(): boolean {
  return fs.existsSync(CAPSOLVER_XPI_PATH);
}
