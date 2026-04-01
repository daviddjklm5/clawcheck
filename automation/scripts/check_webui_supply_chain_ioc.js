#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const BLOCKED_AXIOS_VERSIONS = new Set(["1.14.1", "0.30.4"]);
const SUSPICIOUS_PACKAGES = new Set(["plain-crypto-js"]);

function parseArgs(argv) {
  const options = {
    webuiDir: path.resolve(__dirname, "..", "..", "webui"),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const current = argv[i];
    if (current === "--webui-dir") {
      const next = argv[i + 1];
      if (!next) {
        throw new Error("Missing value for --webui-dir");
      }
      options.webuiDir = path.resolve(next);
      i += 1;
    }
  }

  return options;
}

function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    throw new Error(`Failed to parse JSON: ${filePath}\n${error.message}`);
  }
}

function versionLooksBlockedAxios(version) {
  const normalized = String(version || "").trim();
  return BLOCKED_AXIOS_VERSIONS.has(normalized);
}

function extractLeafPackageName(lockPackagePath) {
  if (!lockPackagePath) {
    return "";
  }

  const normalized = String(lockPackagePath).replace(/\\/g, "/");
  const marker = "node_modules/";
  const index = normalized.lastIndexOf(marker);
  if (index < 0) {
    return "";
  }
  return normalized.slice(index + marker.length);
}

function scanPackageJsonMap(mapValue, sectionName, violations, packageKeyPrefix = "") {
  if (!mapValue || typeof mapValue !== "object" || Array.isArray(mapValue)) {
    return;
  }

  for (const [key, value] of Object.entries(mapValue)) {
    const packageKey = packageKeyPrefix ? `${packageKeyPrefix}.${key}` : key;

    if (SUSPICIOUS_PACKAGES.has(key)) {
      violations.push({
        where: `package.json:${sectionName}`,
        detail: `Found suspicious package '${key}' (declared as '${packageKey}')`,
      });
    }

    if (key === "axios") {
      const spec = typeof value === "string" ? value : JSON.stringify(value);
      for (const blocked of BLOCKED_AXIOS_VERSIONS) {
        if (String(spec).includes(blocked)) {
          violations.push({
            where: `package.json:${sectionName}`,
            detail: `Found blocked axios spec '${spec}' (contains ${blocked})`,
          });
        }
      }
    }

    if (value && typeof value === "object" && !Array.isArray(value)) {
      scanPackageJsonMap(value, sectionName, violations, packageKey);
    }
  }
}

function scanNestedDependencies(dependencies, sourceLabel, violations, lineage = []) {
  if (!dependencies || typeof dependencies !== "object" || Array.isArray(dependencies)) {
    return;
  }

  for (const [packageName, node] of Object.entries(dependencies)) {
    const packageLineage = [...lineage, packageName].join(" > ");
    let version = "";
    if (node && typeof node === "object" && !Array.isArray(node) && typeof node.version === "string") {
      version = node.version.trim();
    } else if (typeof node === "string") {
      version = node.trim();
    }

    if (packageName === "axios" && versionLooksBlockedAxios(version)) {
      violations.push({
        where: sourceLabel,
        detail: `Found blocked axios version '${version}' at '${packageLineage}'`,
      });
    }

    if (SUSPICIOUS_PACKAGES.has(packageName)) {
      const versionLabel = version || "unknown";
      violations.push({
        where: sourceLabel,
        detail: `Found suspicious package '${packageName}@${versionLabel}' at '${packageLineage}'`,
      });
    }

    if (node && typeof node === "object" && !Array.isArray(node) && node.dependencies) {
      scanNestedDependencies(node.dependencies, sourceLabel, violations, [...lineage, packageName]);
    }
  }
}

function run() {
  const { webuiDir } = parseArgs(process.argv.slice(2));
  const packageJsonPath = path.join(webuiDir, "package.json");
  const packageLockPath = path.join(webuiDir, "package-lock.json");

  if (!fs.existsSync(packageJsonPath)) {
    throw new Error(`package.json not found: ${packageJsonPath}`);
  }
  if (!fs.existsSync(packageLockPath)) {
    throw new Error(`package-lock.json not found: ${packageLockPath}`);
  }

  const packageJson = readJson(packageJsonPath);
  const packageLock = readJson(packageLockPath);
  const violations = [];

  scanPackageJsonMap(packageJson.dependencies, "dependencies", violations);
  scanPackageJsonMap(packageJson.devDependencies, "devDependencies", violations);
  scanPackageJsonMap(packageJson.optionalDependencies, "optionalDependencies", violations);
  scanPackageJsonMap(packageJson.peerDependencies, "peerDependencies", violations);
  scanPackageJsonMap(packageJson.overrides, "overrides", violations);
  scanPackageJsonMap(packageJson.resolutions, "resolutions", violations);

  const lockPackages = packageLock.packages;
  if (lockPackages && typeof lockPackages === "object" && !Array.isArray(lockPackages)) {
    for (const [lockPackagePath, meta] of Object.entries(lockPackages)) {
      if (!meta || typeof meta !== "object" || Array.isArray(meta)) {
        continue;
      }

      const packageName = typeof meta.name === "string" && meta.name
        ? meta.name
        : extractLeafPackageName(lockPackagePath);
      const version = typeof meta.version === "string" ? meta.version.trim() : "";
      const lockLabel = `package-lock.json:packages['${lockPackagePath}']`;

      if (packageName === "axios" && versionLooksBlockedAxios(version)) {
        violations.push({
          where: lockLabel,
          detail: `Found blocked axios version '${version}'`,
        });
      }

      if (SUSPICIOUS_PACKAGES.has(packageName)) {
        const versionLabel = version || "unknown";
        violations.push({
          where: lockLabel,
          detail: `Found suspicious package '${packageName}@${versionLabel}'`,
        });
      }
    }
  }

  scanNestedDependencies(packageLock.dependencies, "package-lock.json:dependencies", violations);

  if (violations.length > 0) {
    console.error("[supply-chain-check] BLOCKED indicators detected:");
    for (const violation of violations) {
      console.error(`- ${violation.where}: ${violation.detail}`);
    }
    process.exit(1);
  }

  console.log("[supply-chain-check] OK: no blocked Axios IOC found in package.json/package-lock.json");
}

try {
  run();
} catch (error) {
  console.error(`[supply-chain-check] ERROR: ${error.message}`);
  process.exit(1);
}
