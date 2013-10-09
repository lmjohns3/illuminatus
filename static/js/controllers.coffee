# -*- coding: utf-8 -*-

IndexCtrl = ($scope, $location, $http) ->
  $scope.tags = []

  $scope.byCountDesc = (g) -> -g.count

  $http.get('tags').then (res) ->
    $scope.tags = res.data
    return true

  $scope.go = (tag) ->
    $location.path '/' + tag

  $scope.random = -> Math.random()


PhotosCtrl = ($scope, $location, $http, $routeParams, $window, Photo) ->
  $scope.photo = null
  $scope.photos = []
  $scope.cursorIndex = -1
  $scope.cursorId = -1
  $scope.loading = false
  $scope.exhausted = false
  $scope.tagging = false
  $scope.tagged = _.select $routeParams.tags.split('|'), (t) -> t.length > 0
  $scope.selected = []
  $scope.tags = []

  $scope.view = (tag) ->
    i = _.indexOf $scope.tagged, tag
    if i >= 0
      $scope.tagged.splice i, 1
    else
      $scope.tagged.push tag
    $location.path '/' + $scope.tagged.join '|'

  $scope.loadPhotos = (n = 32) ->
    return if $scope.exhausted
    return if $scope.loading
    $scope.loading = true
    q = offset: $scope.photos.length, limit: n, tags: $scope.tagged.join '|'
    photos = Photo().query q, ->
      console.log photos
      for p in photos
        $scope.photos.push p
      if $scope.cursorIndex < 0
        $scope.cursorIndex = 0
        $scope.photo = $scope.photos[0]
        $scope.cursorId = $scope.photo.id
      if photos.length < n
        $scope.exhausted = true
      $scope.loading = false

  # GROUP PHOTO OPERATIONS

  $scope.contrastBrightnessSelected = (gamma, alpha) ->
    for id in $scope.selected
      $scope.getPhoto(id).contrastBrightness gamma: gamma, alpha: alpha

  $scope.tagSelected = (add: [], remove: []) ->
    # get a set of ids to work with.
    ids = [].concat $scope.selected
    if ids.length is 0
      ids.push $scope.cursorId

    for id in ids
      p = $scope.getPhoto id
      p.setTag(t) for t in add
      p.clearTag(t) for t in remove

  # INDIVIDUAL PHOTO OPERATIONS

  $scope.rotatePhoto = (degrees) ->
    $scope.getPhoto().rotate rotate: degrees

  $scope.cropPhoto = (x1, y1, x2, y2) ->
    $scope.getPhoto().crop x1: x1, y1: y1, x2: x2, y2: y2

  # EVENT HANDLING

  $scope.handleClick = (id, $event) ->
    if $event.ctrlKey or $event.metaKey or $event.altKey
      $scope.togglePhoto id
    else if $event.shiftKey
      # TODO
    else
      $scope.selected = [id]
      $scope.focusPhoto id
    return true

  $scope.togglePhoto = (id) ->
    id = $scope.getPhoto(id).id
    i = _.indexOf $scope.selected, id
    if i >= 0
      $scope.selected.splice i, 1
    else
      $scope.selected.push id

  $scope.focusPhoto = (id) ->
    for p, i in $scope.photos
      if p.id is id
        $scope.cursorIndex = i
        $scope.cursorId = id
        $scope.photo = $scope.getPhoto()
        break

  $scope.prevPhoto = ->
    return if $scope.cursorIndex <= 0
    $scope.cursorIndex--
    $scope.scroll()

  $scope.prevPage = ->
    return if $scope.cursorIndex <= 0
    $scope.cursorIndex = Math.max 0, $scope.cursorIndex - 16
    $scope.scroll()

  $scope.nextPhoto = ->
    return if $scope.cursorIndex >= $scope.photos.length - 1
    $scope.cursorIndex++
    $scope.scroll()

  $scope.nextPage = ->
    L = $scope.photos.length - 1
    return if $scope.cursorIndex >= L
    $scope.cursorIndex = Math.min L, $scope.cursorIndex + 16
    $scope.scroll()

  $scope.getPhoto = (id) ->
    if typeof id is 'undefined' or id is null
      return $scope.photos[$scope.cursorIndex]
    for p in $scope.photos
      if p.id is id
        return p
    null

  $scope.scroll = ->
    $scope.photo = $scope.getPhoto()
    $scope.cursorId = $scope.photo.id
    y = $("#photo-#{$scope.cursorId}").offset().top - 16
    top = $(window).scrollTop()
    unless top < y < top + $(window).height() - 100
      $('html, body').animate scrollTop: y

  $http.get("tags?tags=#{$scope.tagged.join '|'}").then (res) ->
    $scope.tags = res.data
    return true

  $('#thumbs').focus()

  $scope.loadPhotos 100


angular.module('app.controllers', ['app.services'])
  .controller('IndexCtrl', IndexCtrl)
  .controller('PhotosCtrl', PhotosCtrl)

