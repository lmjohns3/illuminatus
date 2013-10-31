angular.module('app', [
  'app.controllers'
  'app.directives'
  'app.filters'
  'app.services'
]).config ($routeProvider, $locationProvider) ->
  $routeProvider
    .when('/', templateUrl: 'static/views/groups.html', controller: 'GroupsCtrl')
    .when('/:tags', templateUrl: 'static/views/media.html', controller: 'MediaCtrl')
    .otherwise(redirectTo: '/')
  $locationProvider.html5Mode false


angular.element(document).ready ->
  angular.bootstrap document, ['app']
