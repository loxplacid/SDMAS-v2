module.exports = {
  testEnvironment: 'node',
  collectCoverageFrom: [
    '**/di-container.js',
    '**/implementations/**/*.js',
    '!**/node_modules/**'
  ],
  coverageDirectory: 'coverage',
  verbose: true,
  testMatch: ['<rootDir>/tests/**/*.test.js'],
  setupFilesAfterEnv: [],
  reporters: [
    'default',
    'jest-junit'
  ]
};
