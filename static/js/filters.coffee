angular.module('app.filters', [])
  .filter('interpolate', ['version', (version) -> (t) -> String(t).replace(/\%VERSION\%/mg, version)])
