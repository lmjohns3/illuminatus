# http://stackoverflow.com/questions/12719782/angularjs-customizing-resource

photo = ($http) ->
  ->
    parse = (msg) ->
      if msg.response then msg.response else msg

    Photo = (value) ->
      angular.copy parse value or {}, @

    Photo.$get = (id) ->
      value = if @ instanceof Photo then @ else new Photo()
      $http(method: 'GET', url: "/photo/#{id}").then (res) ->
        angular.copy(parse(res.data), value) if res.data
      return value

    Photo.prototype.$get = (id) -> Photo.$get.call @, id

    Photo.query = ->
      value = []
      $http(method: 'GET', url: '/photo/').then (res) ->
        for p in res.objects
          value.push new Photo(p)
      return value


Photo = ($resource) ->
  $resource 'photo/:id', {}, rotate: method: 'POST'


angular.module('app.services', ['ngResource'])
  .factory('Photo', Photo)
