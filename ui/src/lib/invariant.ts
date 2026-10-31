export const invariant: (
  condition: unknown,
  message: string,
) => asserts condition = (condition, message) => {
  if (!condition) {
    throw new Error(`Invariant failed: ${message}`);
  }
};
