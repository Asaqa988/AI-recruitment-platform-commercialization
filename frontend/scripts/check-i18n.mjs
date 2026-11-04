// Fails when the two languages differ in shape, or when a component reads a key that does not exist.
import { readdirSync, readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..', 'src')
const { translations } = await import(pathToFileURL(join(root, 'i18n.js')).href)

const shape = (v) => (typeof v === 'function' ? 'fn' : Array.isArray(v) ? v.map(shape) : v && typeof v === 'object'
  ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, shape(v[k])])) : 'str')
const problems = []
const a = JSON.stringify(shape(translations.en)), b = JSON.stringify(shape(translations.ar))
if (a !== b) {
  const walk = (x, y, path) => {
    if (typeof x !== 'object' || typeof y !== 'object' || !x || !y) { if (x !== y) problems.push(`shape differs at ${path}`); return }
    for (const k of new Set([...Object.keys(x), ...Object.keys(y)])) {
      if (!(k in x)) problems.push(`missing in en: ${path}.${k}`)
      else if (!(k in y)) problems.push(`missing in ar: ${path}.${k}`)
      else walk(x[k], y[k], `${path}.${k}`)
    }
  }
  walk(JSON.parse(a), JSON.parse(b), 't')
}

const files = []
const scan = (d) => readdirSync(d, { withFileTypes: true }).forEach((e) => (e.isDirectory() ? scan(join(d, e.name)) : /\.jsx?$/.test(e.name) && files.push(join(d, e.name))))
scan(root)
for (const f of files) {
  const src = readFileSync(f, 'utf8')
  for (const m of src.matchAll(/\bt\.([a-zA-Z0-9]+)\.([a-zA-Z0-9]+)/g)) {
    const [, g, k] = m
    if (!(translations.en[g] && k in translations.en[g])) problems.push(`${f.replace(root, 'src')}: t.${g}.${k} is not defined`)
  }
}
if (problems.length) { console.error([...new Set(problems)].join('\n')); process.exit(1) }
console.log('i18n ok')
