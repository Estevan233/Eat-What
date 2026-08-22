import { describe, expect, it } from 'vitest'

import * as constitutionConstants from '@/constants/constitution'
import source from './constitution.vue?raw'

describe('constitution questionnaire fallback', () => {
  it('keeps all nine questions available when the remote question request fails', () => {
    const localQuestions = Reflect.get(
      constitutionConstants,
      'CONSTITUTION_QUESTIONS',
    )

    expect(localQuestions).toHaveLength(9)
    expect(localQuestions.map((question: { id: number }) => question.id)).toEqual([
      1, 2, 3, 4, 5, 6, 7, 8, 9,
    ])
    expect(source).toContain('questions.value = [...CONSTITUTION_QUESTIONS]')
    expect(source).not.toContain('questions.value = []')
  })
})
