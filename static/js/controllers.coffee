# -*- coding: utf-8 -*-

STAR = '★'


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
  $scope.editing = false
  $scope.tagged = _.select $routeParams.tags.split('|'), (t) -> t.length > 0
  $scope.selected = []
  $scope.tags = []

  $scope.go = (tag) ->
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
    photos = Photo.query q, ->
      for p in photos
        $scope.photos.push p
      if $scope.cursorIndex < 0
        $scope.cursorIndex = 0
        $scope.photo = $scope.photos[0]
        $scope.cursorId = $scope.photo.id
      if photos.length < n
        $scope.exhausted = true
      $scope.loading = false

  $scope.starPhoto = (id) ->
    p = $scope.getPhoto(id)
    i = _.indexOf p.meta.user_tags, STAR
    if i >= 0
      p.meta.user_tags.splice i, 1
    else
      p.meta.user_tags.push STAR
    p.$save id: p.id

  $scope.rotatePhoto = (degrees, id) ->
    editPhoto(id)
    $scope.getPhoto(id).$rotate rotate: degrees

  $scope.selectPhoto = (id) ->
    id = $scope.getPhoto(id).id
    i = _.indexOf $scope.selected, id
    if i >= 0
      $scope.selected.splice i, 1
    else
      $scope.selected.push id

  $scope.editPhoto = (id) ->
    $scope.focusPhoto id
    $scope.editing = true

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

