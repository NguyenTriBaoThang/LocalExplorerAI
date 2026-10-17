import ts from 'typescript'
import { mkdtemp, readFile, writeFile, rm, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'

// Node 20 does not strip TypeScript. Compile pure helpers into a disposable test directory.
const dir = await mkdtemp(join(tmpdir(), 'local-explorer-trip-tests-'))
try {
  const source = new URL('../src/components/trip/', import.meta.url)
  const files = (await readdir(source)).filter(f => f.endsWith('.ts') && f !== 'landmarkLayer.ts')
  for (const file of files) {
    const input = await readFile(new URL(file, source), 'utf8')
    const output = ts.transpileModule(input, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
      .replace(/(from\s+['"]\.\/[^'"]+?)(?:\.ts)?(['"])/g, '$1.mjs$2')
    await writeFile(join(dir, file.replace(/\.ts$/, '.mjs')), output)
  }
  const result = spawnSync(process.execPath, ['--test', ...files.filter(f => f.endsWith('.test.ts')).map(f => join(dir, f.replace(/\.ts$/, '.mjs')))], { stdio: 'inherit' })
  process.exitCode = result.status ?? 1
} finally { await rm(dir, { recursive: true, force: true }) }
