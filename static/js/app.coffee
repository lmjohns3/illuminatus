angular.module('app', [
  'app.controllers'
  'app.directives'
  'app.filters'
  'app.services'
]).config ($routeProvider, $locationProvider) ->
  $routeProvider
    .when('/', templateUrl: 'static/views/index.html', controller: 'IndexCtrl')
    .when('/:tags', templateUrl: 'static/views/photos.html', controller: 'PhotosCtrl')
    .otherwise(redirectTo: '/')
  $locationProvider.html5Mode false


angular.element(document).ready ->
  angular.bootstrap document, ['app']
