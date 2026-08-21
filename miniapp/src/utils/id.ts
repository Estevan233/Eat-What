export function createRequestId(prefix = 'req'): string {
  const randomPart = () => Math.random().toString(36).slice(2, 10)
  return [prefix, Date.now().toString(36), randomPart(), randomPart()]
    .join('-')
    .slice(0, 64)
}
