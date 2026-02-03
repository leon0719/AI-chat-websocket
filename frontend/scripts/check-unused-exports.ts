#!/usr/bin/env bun
import { readdirSync, readFileSync, statSync } from "node:fs";
import { basename, dirname, extname, join, relative } from "node:path";

const SRC_DIR = "./src";
const EXTENSIONS = [".ts", ".tsx"];
const IGNORED_DIRS = ["node_modules", ".next", "out", ".git"];

interface ExportInfo {
  name: string;
  file: string;
  line: number;
  type: "function" | "const" | "type" | "interface" | "class" | "enum";
}

interface UnusedExportInfo extends ExportInfo {
  importPath: string | null;
  reExportedIn: string | null;
  reason: string;
}

function getSourceFiles(dir: string): string[] {
  const files: string[] = [];

  const items = readdirSync(dir);
  for (const item of items) {
    const fullPath = join(dir, item);

    if (IGNORED_DIRS.includes(item)) continue;

    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      files.push(...getSourceFiles(fullPath));
    } else if (EXTENSIONS.includes(extname(item))) {
      files.push(fullPath);
    }
  }

  return files;
}

const EXPORT_PATTERNS = [
  { regex: /^export\s+function\s+(\w+)/m, type: "function" as const },
  { regex: /^export\s+async\s+function\s+(\w+)/m, type: "function" as const },
  { regex: /^export\s+const\s+(\w+)\s*=/m, type: "const" as const },
  { regex: /^export\s+let\s+(\w+)\s*=/m, type: "const" as const },
  { regex: /^export\s+type\s+(\w+)/m, type: "type" as const },
  { regex: /^export\s+interface\s+(\w+)/m, type: "interface" as const },
  { regex: /^export\s+class\s+(\w+)/m, type: "class" as const },
  { regex: /^export\s+enum\s+(\w+)/m, type: "enum" as const },
];

function extractExports(filePath: string, content: string): ExportInfo[] {
  const exports: ExportInfo[] = [];
  const lines = content.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    for (const { regex, type } of EXPORT_PATTERNS) {
      const match = line.match(regex);
      if (match) {
        exports.push({ name: match[1], file: filePath, line: i + 1, type });
      }
    }
  }

  return exports;
}

const ALWAYS_USED_PATTERNS = [
  /^use[A-Z]/, // React hooks
  /Provider$/, // Context providers
  /^default$/, // default exports
];

// Next.js special exports (used by framework, not imported)
const NEXTJS_SPECIAL_EXPORTS = new Set([
  // App Router metadata
  "generateStaticParams",
  "generateMetadata",
  "metadata",
  "viewport",
  "generateViewport",
  // Route segment config
  "revalidate",
  "dynamic",
  "dynamicParams",
  "fetchCache",
  "runtime",
  "preferredRegion",
  "maxDuration",
  // Route handlers
  "GET",
  "POST",
  "PUT",
  "DELETE",
  "PATCH",
  "HEAD",
  "OPTIONS",
]);

function isAlwaysUsed(name: string): boolean {
  if (NEXTJS_SPECIAL_EXPORTS.has(name)) return true;
  return ALWAYS_USED_PATTERNS.some((pattern) => pattern.test(name));
}

function checkNamedImport(content: string, name: string): boolean {
  const patterns = [
    new RegExp(`import\\s*\\{[^}]*\\b${name}\\b[^}]*\\}\\s*from`),
    new RegExp(`import\\s*\\{[^}]*\\b${name}\\s+as\\s+\\w+[^}]*\\}\\s*from`),
    new RegExp(`import\\s+\\w+\\s*,\\s*\\{[^}]*\\b${name}\\b[^}]*\\}\\s*from`),
  ];

  return patterns.some((pattern) => pattern.test(content));
}

function checkSameFileUsage(content: string, name: string, exportLine: number): boolean {
  const lines = content.split("\n");

  for (let i = 0; i < lines.length; i++) {
    if (i + 1 === exportLine) continue;

    const line = lines[i];
    // Skip import lines
    if (line.trimStart().startsWith("import ")) continue;

    // Check for usage patterns
    const usagePatterns = [
      new RegExp(`\\b${name}\\b\\s*\\(`), // Function call: name(
      new RegExp(`\\(\\s*${name}\\s*[,)]`), // Function argument: func(name) or func(name, ...)
      new RegExp(`,\\s*${name}\\s*[,)]`), // Function argument after comma: func(x, name)
      new RegExp(`\\b${name}\\b\\s*<`), // Generic: name<
      new RegExp(`styled\\(\\s*${name}\\s*[,)]`), // styled(name) or styled(name, {
      new RegExp(`extends\\s+${name}\\b`), // extends name
      new RegExp(`:\\s*${name}\\b`), // Type annotation: : name
      new RegExp(`<[^>]*\\b${name}\\b[^>]*>`), // Generic param: <..., name, ...>
      new RegExp(`<${name}[>/\\s]`), // JSX: <name> or <name/> or <name prop
      new RegExp(`\\.${name}\\b`), // Property access: obj.name
      new RegExp(`\\[${name}\\]`), // Index access: obj[name]
      new RegExp(`\\|\\s*${name}\\b`), // Union type: | name
      new RegExp(`${name}\\s*\\|`), // Union type: name |
      new RegExp(`&\\s*${name}\\b`), // Intersection: & name
      new RegExp(`${name}\\s*&`), // Intersection: name &
      new RegExp(`${name}\\[\\]`), // Array type: name[]
      new RegExp(`=\\s*${name}\\b`), // Assignment: = name
      new RegExp(`z\\.array\\(\\s*${name}\\s*\\)`), // Zod: z.array(name)
      new RegExp(`z\\.union\\(\\s*\\[[^\\]]*${name}[^\\]]*\\]\\s*\\)`), // Zod: z.union([..., name, ...])
    ];

    for (const pattern of usagePatterns) {
      if (pattern.test(line)) {
        return true;
      }
    }
  }

  return false;
}

interface ReExportResult {
  found: boolean;
  reExportFile: string | null;
  importPath: string | null;
}

function checkReExport(
  exportFile: string,
  name: string,
  allContents: Map<string, string>,
): ReExportResult {
  const exportDir = dirname(exportFile);

  // Check index.ts in the same directory
  const indexFiles = ["index.ts", "index.tsx"];
  for (const indexFile of indexFiles) {
    const indexPath = join(exportDir, indexFile);
    const indexContent = allContents.get(indexPath);

    if (indexContent) {
      // Check for re-export patterns (including export type {})
      const reExportPatterns = [
        new RegExp(`export\\s*(type\\s*)?\\{[^}]*\\b${name}\\b[^}]*\\}\\s*from`),
        /export\s*\*\s*from/,
      ];

      if (reExportPatterns.some((p) => p.test(indexContent))) {
        // Check if this index file's exports are used elsewhere
        const indexRelPath = relative(SRC_DIR, exportDir).replace(/\\/g, "/");
        const importPath = `@/${indexRelPath}`;

        for (const [filePath, content] of allContents) {
          if (filePath === indexPath || filePath === exportFile) continue;

          const importPatterns = [`from "${importPath}"`, `from '${importPath}'`];

          const hasImport = importPatterns.some((p) => content.includes(p));
          if (hasImport && content.includes(name)) {
            return { found: true, reExportFile: indexPath, importPath };
          }
        }

        // Found in index but not imported
        return { found: false, reExportFile: indexPath, importPath };
      }
    }
  }

  // Also check parent directory's index file
  const parentDir = dirname(exportDir);
  for (const indexFile of indexFiles) {
    const parentIndexPath = join(parentDir, indexFile);
    const parentIndexContent = allContents.get(parentIndexPath);

    if (parentIndexContent) {
      const reExportPatterns = [
        new RegExp(`export\\s*(type\\s*)?\\{[^}]*\\b${name}\\b[^}]*\\}\\s*from`),
        /export\s*\*\s*from/,
      ];

      if (reExportPatterns.some((p) => p.test(parentIndexContent))) {
        const parentRelPath = relative(SRC_DIR, parentDir).replace(/\\/g, "/");
        const importPath = `@/${parentRelPath}`;

        for (const [filePath, content] of allContents) {
          if (filePath === parentIndexPath || filePath === exportFile) continue;

          const importPatterns = [`from "${importPath}"`, `from '${importPath}'`];

          const hasImport = importPatterns.some((p) => content.includes(p));
          if (hasImport && content.includes(name)) {
            return { found: true, reExportFile: parentIndexPath, importPath };
          }
        }

        return { found: false, reExportFile: parentIndexPath, importPath };
      }
    }
  }

  return { found: false, reExportFile: null, importPath: null };
}

function checkIndexFileUsage(
  exportFile: string,
  name: string,
  allContents: Map<string, string>,
): boolean {
  if (!exportFile.endsWith("index.ts") && !exportFile.endsWith("index.tsx")) {
    return false;
  }

  const parentDir = exportFile.replace(/\/index\.(ts|tsx)$/, "");
  const indexRelPath = relative(SRC_DIR, parentDir).replace(/\\/g, "/");

  for (const [filePath, content] of allContents) {
    if (filePath === exportFile) continue;

    const importPatterns = [
      `from "${parentDir}"`,
      `from '${parentDir}'`,
      `from "@/${indexRelPath}"`,
      `from '@/${indexRelPath}'`,
    ];

    const hasImportFromDir = importPatterns.some((p) => content.includes(p));
    if (hasImportFromDir && content.includes(name)) {
      return true;
    }
  }

  return false;
}

function checkDirectFileUsage(
  exportFile: string,
  name: string,
  allContents: Map<string, string>,
): boolean {
  const exportFileRelative = relative(SRC_DIR, exportFile)
    .replace(/\\/g, "/")
    .replace(/\.(ts|tsx)$/, "");

  const exportFileName = basename(exportFile).replace(/\.(ts|tsx)$/, "");
  const exportDirName = basename(dirname(exportFile));

  for (const [filePath, content] of allContents) {
    if (filePath === exportFile) continue;

    // Check various import path patterns
    const hasImportFromFile =
      content.includes(`from "@/${exportFileRelative}"`) ||
      content.includes(`from '@/${exportFileRelative}'`) ||
      content.includes(`from "./${exportFileName}"`) ||
      content.includes(`from './${exportFileName}'`) ||
      content.includes(`from "../${exportFileName}"`) ||
      content.includes(`from '../${exportFileName}'`) ||
      content.includes(`from "../${exportDirName}/${exportFileName}"`) ||
      content.includes(`from '../${exportDirName}/${exportFileName}'`) ||
      content.includes(`from "../../${exportDirName}/${exportFileName}"`) ||
      content.includes(`from '../../${exportDirName}/${exportFileName}'`);

    if (hasImportFromFile && new RegExp(`\\b${name}\\b`).test(content)) {
      return true;
    }
  }

  return false;
}

function getImportPath(exportFile: string): string {
  const relPath = relative(SRC_DIR, exportFile)
    .replace(/\\/g, "/")
    .replace(/\.(ts|tsx)$/, "");
  return `@/${relPath}`;
}

interface UsageCheckResult {
  isUsed: boolean;
  reExportFile: string | null;
  importPath: string | null;
  reason: string;
}

function checkExportUsage(
  exportInfo: ExportInfo,
  allContents: Map<string, string>,
): UsageCheckResult {
  const { name, file: exportFile, line: exportLine } = exportInfo;
  const content = allContents.get(exportFile) || "";

  if (isAlwaysUsed(name)) {
    return { isUsed: true, reExportFile: null, importPath: null, reason: "" };
  }

  // Check same file usage (styled inheritance, function calls, etc.)
  if (checkSameFileUsage(content, name, exportLine)) {
    return { isUsed: true, reExportFile: null, importPath: null, reason: "" };
  }

  // Check named imports in other files
  for (const [filePath, fileContent] of allContents) {
    if (filePath === exportFile) continue;
    if (checkNamedImport(fileContent, name)) {
      return { isUsed: true, reExportFile: null, importPath: null, reason: "" };
    }
  }

  // Check re-exports through index files
  const reExportResult = checkReExport(exportFile, name, allContents);
  if (reExportResult.found) {
    return { isUsed: true, reExportFile: null, importPath: null, reason: "" };
  }

  // Check index file usage
  if (checkIndexFileUsage(exportFile, name, allContents)) {
    return { isUsed: true, reExportFile: null, importPath: null, reason: "" };
  }

  // Check direct file imports
  if (checkDirectFileUsage(exportFile, name, allContents)) {
    return { isUsed: true, reExportFile: null, importPath: null, reason: "" };
  }

  // Determine reason for being unused
  let reason: string;
  if (reExportResult.reExportFile) {
    const relReExport = relative(process.cwd(), reExportResult.reExportFile);
    reason = `已在 ${relReExport} 中 re-export，但從未被 import`;
  } else {
    reason = "已 export 但從未被 import";
  }

  return {
    isUsed: false,
    reExportFile: reExportResult.reExportFile,
    importPath: reExportResult.importPath || getImportPath(exportFile),
    reason,
  };
}

function printUnusedExports(unusedExports: UnusedExportInfo[]): void {
  const grouped: Record<string, UnusedExportInfo[]> = {};

  for (const exp of unusedExports) {
    const relPath = relative(process.cwd(), exp.file);
    if (!grouped[relPath]) {
      grouped[relPath] = [];
    }
    grouped[relPath].push(exp);
  }

  for (const [file, exports] of Object.entries(grouped)) {
    console.log(`\n📄 ${file}`);
    console.log("─".repeat(60));

    for (const exp of exports) {
      console.log(`   ├─ [${exp.type}] ${exp.name}`);
      console.log(`   │     行號: ${exp.line}`);
      console.log(`   │     Import 路徑: ${exp.importPath || "N/A"}`);
      if (exp.reExportedIn) {
        const relReExport = relative(process.cwd(), exp.reExportedIn);
        console.log(`   │     Re-export 位置: ${relReExport}`);
      }
      console.log(`   │     狀態: ${exp.reason}`);
      console.log(`   │`);
    }
  }
  console.log("");
}

function printStatistics(
  allExports: ExportInfo[],
  usedExports: ExportInfo[],
  unusedExports: UnusedExportInfo[],
): void {
  console.log("═".repeat(60));
  console.log("📊 統計摘要");
  console.log("═".repeat(60));
  console.log(`   總導出數: ${allExports.length}`);
  console.log(`   使用中: ${usedExports.length}`);
  console.log(`   未使用: ${unusedExports.length}`);
  const usageRate = (usedExports.length / allExports.length) * 100;
  console.log(`   使用率: ${usageRate.toFixed(1)}%\n`);

  const typeStats: Record<string, { used: number; unused: number }> = {};
  for (const exp of allExports) {
    if (!typeStats[exp.type]) {
      typeStats[exp.type] = { used: 0, unused: 0 };
    }
  }
  for (const exp of usedExports) {
    typeStats[exp.type].used++;
  }
  for (const exp of unusedExports) {
    typeStats[exp.type].unused++;
  }

  console.log("📈 按類型統計:");
  for (const [type, stats] of Object.entries(typeStats)) {
    const total = stats.used + stats.unused;
    const bar = "█".repeat(Math.round((stats.used / total) * 20));
    const emptyBar = "░".repeat(20 - bar.length);
    console.log(`   ${type.padEnd(12)} ${bar}${emptyBar} ${stats.used}/${total}`);
  }
  console.log("");
}

function printSuggestedActions(unusedExports: UnusedExportInfo[]): void {
  if (unusedExports.length === 0) return;

  console.log("═".repeat(60));
  console.log("💡 建議操作");
  console.log("═".repeat(60));

  // Group by re-export file
  const reExportGroups: Record<string, UnusedExportInfo[]> = {};
  const noReExport: UnusedExportInfo[] = [];

  for (const exp of unusedExports) {
    if (exp.reExportedIn) {
      const key = relative(process.cwd(), exp.reExportedIn);
      if (!reExportGroups[key]) {
        reExportGroups[key] = [];
      }
      reExportGroups[key].push(exp);
    } else {
      noReExport.push(exp);
    }
  }

  if (Object.keys(reExportGroups).length > 0) {
    console.log("\n🔄 從 index.ts 移除 re-export:");
    for (const [indexFile, exports] of Object.entries(reExportGroups)) {
      console.log(`   ${indexFile}:`);
      for (const exp of exports) {
        console.log(`     - 移除 "${exp.name}"`);
      }
    }
  }

  if (noReExport.length > 0) {
    console.log("\n🗑️  可直接刪除的導出:");
    for (const exp of noReExport) {
      const relFile = relative(process.cwd(), exp.file);
      console.log(`   ${relFile}: 刪除 "${exp.name}" (line ${exp.line})`);
    }
  }

  console.log("");
}

async function main() {
  console.log("═".repeat(60));
  console.log("🔍 檢查未使用的導出 (exports)");
  console.log("═".repeat(60));

  const sourceFiles = getSourceFiles(SRC_DIR);
  console.log(`\n📁 掃描 ${sourceFiles.length} 個原始碼檔案`);

  const allContents = new Map<string, string>();
  const allExports: ExportInfo[] = [];

  for (const file of sourceFiles) {
    const content = readFileSync(file, "utf-8");
    allContents.set(file, content);
    allExports.push(...extractExports(file, content));
  }

  console.log(`📦 發現 ${allExports.length} 個導出`);

  const unusedExports: UnusedExportInfo[] = [];
  const usedExports: ExportInfo[] = [];

  for (const exportInfo of allExports) {
    const result = checkExportUsage(exportInfo, allContents);
    if (result.isUsed) {
      usedExports.push(exportInfo);
    } else {
      unusedExports.push({
        ...exportInfo,
        importPath: result.importPath,
        reExportedIn: result.reExportFile,
        reason: result.reason,
      });
    }
  }

  if (unusedExports.length === 0) {
    console.log("\n✅ 所有導出都有被使用！\n");
  } else {
    console.log(`\n⚠️  發現 ${unusedExports.length} 個可能未使用的導出:`);
    printUnusedExports(unusedExports);
  }

  printStatistics(allExports, usedExports, unusedExports);
  printSuggestedActions(unusedExports);

  process.exit(unusedExports.length > 0 ? 1 : 0);
}

main().catch(console.error);
