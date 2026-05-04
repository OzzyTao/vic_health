import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

describe('test infrastructure', () => {
  it('vitest runs', () => {
    expect(1 + 1).toBe(2)
  })

  it('fast-check runs', () => {
    fc.assert(
      fc.property(fc.integer(), fc.integer(), (a, b) => {
        expect(a + b).toBe(b + a)
      })
    )
  })
})
