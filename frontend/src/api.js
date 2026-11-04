const KEY = 'zh_token'

export function getToken() {
  try { return sessionStorage.getItem(KEY) || '' } catch { return '' }
}
export function setToken(t) {
  try { t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY) } catch { /* storage unavailable */ }
}

async function raw(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (form) {
    payload = form // the browser sets the multipart boundary itself
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const res = await fetch(`/api${path}`, { method, headers, body: payload })
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      const d = j.detail
      msg = Array.isArray(d) ? d.map((e) => e.msg).join('; ') : d || msg
    } catch { /* non-JSON error */ }
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  return res
}

export async function api(path, opts) {
  return (await raw(path, opts)).json()
}

export async function download(path, filename) {
  const res = await raw(path)
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const money = (cents, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency, minimumFractionDigits: cents % 100 ? 2 : 0 }).format(cents / 100)

export const amount = (n, currency = 'USD') => {
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(n)
  } catch {
    return `${n} ${currency}`
  }
}
