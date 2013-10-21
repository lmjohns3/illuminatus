# -*- coding: utf-8 -*-

IndexCtrl = ($scope, $location, $http) ->
  $scope.groups = []

  $http.get('groups').then (res) ->
    $scope.groups = res.data
    return true

  $scope.byCountDesc = (g) -> -g.count
  $scope.goto = (tag) -> $location.path '/' + encodeURIComponent tag


PhotosCtrl = ($scope, $location, $http, $routeParams, $window, Photo) ->
  $scope.photos = []
  $scope.photoIds = {}
  $scope.loading = false
  $scope.exhausted = false

  $scope.cursor = -1
  $scope.selectedIds = {}
  $scope.selectedPhotoTags = []

  $scope.availableTags = []
  $scope.activeTags = _.select (
    decodeURIComponent(x) for x in $routeParams.tags.split('|')),
    (t) -> t.length > 0

  # REQUESTING DATA

  $scope.goto = (tag) ->
    i = _.indexOf $scope.activeTags, tag
    if i >= 0
      $scope.activeTags.splice i, 1
    else
      $scope.activeTags.push tag
    $location.path '/' + (encodeURIComponent(x) for x in $scope.activeTags).join '|'

  $scope.loadPhotos = (n = 32) ->
    return if $scope.exhausted
    return if $scope.loading
    $scope.loading = true
    q = offset: $scope.photos.length, limit: n, tags: $scope.activeTags.join '|'
    Photo().query q, (photos) ->
      for p in photos
        $scope.photoIds[p.id] = $scope.photos.length
        $scope.photos.push p
      if $scope.cursor < 0
        $scope.cursor = 0
        recomputeSelected()
      $scope.exhausted = photos.length < n
      $scope.loading = false

  # TAGGING OPERATIONS

  $scope.showTagger = ->
    if $scope.viewerVisible
      $('#modal-viewer .tag-input').focus()
    else
      $('#modal-tagger').modal('show')

  $('#modal-tagger').on 'shown.bs.modal', ->
    $('#modal-tagger .tag-input').val ''
    $('#modal-tagger .tag-input').focus()

  $('#modal-tagger').on 'hidden.bs.modal', ->
    $('#modal-tagger .tag-input').val ''

  $('.tag-input').on 'change', (e) ->
    el = $(e.target)
    tag = el.val().toLowerCase()
    for id of activeIds()
      $scope.getPhoto(id).setTag tag
    el.val ''
    recomputeSelected()

  $scope.dirnameBasename = (s) ->
    return s unless s
    i = s.lastIndexOf '/'
    return s if i < 0
    j = s[0...i].lastIndexOf '/'
    return s if j <= 0
    return "...#{s.substring j}"

  $scope.smartTag = (tag, index) ->
    tag = $scope.selectedPhotoTags[index]
    if tag.count is tag.limit
      op = 'clearTag'
      tag.count = 0
    else
      op = 'setTag'
      tag.count = tag.limit
    for id of activeIds()
      $scope.getPhoto(id)[op] tag.name

  # GROUP PHOTO OPERATIONS

  # INDIVIDUAL PHOTO OPERATIONS

  $scope.toggleViewer = ->
    modal = $('#modal-viewer').modal('toggle').first()
    $scope.viewerVisible = 'none' isnt modal.css 'display'

  $scope.imageWidth = ->
    62 + $('#modal-viewer img').width()

  $scope.contrastPhoto = (gamma, alpha) ->
    $scope.getPhoto().contrast gamma: gamma, alpha: alpha
    #image.src = "/static/img/#{p.thumb_path}##{new Date().getTime()}"

  $scope.cropPhoto = (x1, y1, x2, y2) ->
    p = $scope.getPhoto()
    p.crop x1: x1, y1: y1, x2: x2, y2: y2
    #image.src = "/static/img/#{p.thumb_path}##{new Date().getTime()}"

  $scope.deletePhoto = ->
    return unless confirm 'Really delete?'
    $scope.getPhoto().remove (id) ->
      i = _.indexOf _.pluck($scope.photos, 'id'), id
      if i >= 0
        if cursor is $scope.photos.length - 1
          cursor--
        $scope.photos.splice i, 1

  # EVENT HANDLING

  $scope.handleClick = (id, index, $event) ->
    # CTRL/META/ALT -- toggle selected state of clicked photo.
    if $event.ctrlKey or $event.metaKey or $event.altKey
      $scope.togglePhoto id
      return true

    # SHIFT -- select all photos between current cursor and clicked photo.
    if $event.shiftKey
      i = $scope.cursor
      [i, index] = [index, i] if i > index
      while i != index
        $scope.selectedIds[$scope.photos[i].id] = true
        i++
      $scope.selectedIds[id] = true
      return true

    # NO MODIFIER -- select clicked photo.
    $scope.selectedIds = {}
    $scope.selectedIds[id] = true
    $scope.cursor = index

    recomputeSelected()

    return true

  $scope.togglePhoto = (id) ->
    id = $scope.getPhoto(id).id
    if $scope.selectedIds[id]
      delete $scope.selectedIds[id]
    else
      $scope.selectedIds[id] = true
    recomputeSelected()

  $scope.prevPhoto = ->
    return if $scope.cursor <= 0
    $scope.cursor--
    $scope.scroll()

  $scope.prevPage = ->
    return if $scope.cursor <= 0
    $scope.cursor = Math.max 0, $scope.cursor - 16
    $scope.scroll()

  $scope.nextPhoto = ->
    return if $scope.cursor >= $scope.photos.length - 1
    $scope.cursor++
    $scope.scroll()

  $scope.nextPage = ->
    L = $scope.photos.length - 1
    return if $scope.cursor >= L
    $scope.cursor = Math.min L, $scope.cursor + 16
    $scope.scroll()

  $scope.getPhoto = (id) ->
    if typeof id is 'undefined' or id is null
      return $scope.photos[$scope.cursor]
    $scope.photos[$scope.photoIds[id]]

  $scope.scroll = ->
    y = $("#photo-#{$scope.getPhoto().id}").offset().top - 16
    top = $(window).scrollTop()
    unless top < y < top + $(window).height() - 100
      $('html, body').animate scrollTop: y

  activeIds = ->
    ids = _.extend {}, $scope.selectedIds
    if 0 is _.size ids
      ids[$scope.photos[$scope.cursor].id] = true
    return ids

  recomputeSelected = ->
    ids = activeIds()
    counts = {}
    for id of ids
        for t in $scope.getPhoto(id).tags
          counts[t] = 0 unless counts[t]
          counts[t]++
    n = _.size ids
    $scope.selectedPhotoTags = _.sortBy (
      {name: t, count: c, limit: n} for t, c of counts
    ), (x) -> -x.count

  $http.get("tags?tags=#{$scope.activeTags.join '|'}").then (res) ->
    $scope.availableTags = res.data
    return true

  $('#thumbs').focus()
  $('.modal').on 'hide.bs.modal', -> $('#thumbs').focus()
  $('#modal-viewer .tag-input').on 'blur', -> $('#thumbs').focus()

  $scope.loadPhotos 200


angular.module('app.controllers', ['app.services'])
  .controller('IndexCtrl', IndexCtrl)
  .controller('PhotosCtrl', PhotosCtrl)

