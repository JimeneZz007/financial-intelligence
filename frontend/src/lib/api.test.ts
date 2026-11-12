import { describe, expect, it, vi } from 'vitest'

import { ApiError, apiGet, apiUrl, buildQuery } from './api'

describe('buildQuery', () => {
  it('repeats array parameters and skips empty values', () => {
    expect(
      buildQuery({ start: '2025-01', business_unit: ['RET', 'ECM'], category: null, group_by: undefined, text: '' }),
    ).toBe('?start=2025-01&business_unit=RET&business_unit=ECM')
  })

  it('returns an empty string when there is nothing to send', () => {
    expect(buildQuery({ business_unit: [] })).toBe('')
  })

  it('serialises booleans and numbers', () => {
    expect(buildQuery({ include_immaterial: false, page: 2 })).toBe('?include_immaterial=false&page=2')
  })

  it('builds versioned API URLs', () => {
    expect(apiUrl('/kpis/summary', { compare: 'previous_year' })).toBe('/api/v1/kpis/summary?compare=previous_year')
  })
})

describe('apiGet', () => {
  const respond = (body: unknown, status: number) =>
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status })))

  it('returns the parsed body on success', async () => {
    respond({ status: 'ok' }, 200)
    await expect(apiGet('/health')).resolves.toEqual({ status: 'ok' })
  })

  it('surfaces the message the API sends for a rejected filter', async () => {
    respond({ detail: 'Unknown business unit(s): XXX. Valid codes: RET, ECM, WHS, COR' }, 422)
    await expect(apiGet('/kpis/summary')).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      message: 'Unknown business unit(s): XXX. Valid codes: RET, ECM, WHS, COR',
    })
  })

  it('flattens validation errors into one readable sentence', async () => {
    respond({ detail: [{ loc: ['query', 'start'], msg: "String should match pattern '^\\d{4}-'" }] }, 422)
    await expect(apiGet('/kpis/summary')).rejects.toThrow("start: String should match pattern '^\\d{4}-'")
  })

  it('falls back to a generic message when the body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>Bad gateway</html>', { status: 502 })))
    await expect(apiGet('/health')).rejects.toThrow('The request failed (HTTP 502).')
  })

  it('reports an unreachable API without leaking the low-level error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    const error = await apiGet('/health').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
    expect((error as ApiError).message).toMatch(/unreachable/i)
  })
})
