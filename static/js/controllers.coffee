# -*- coding: utf-8 -*-

GroupsCtrl = ($scope, $location, $http) ->
  $scope.groups = []

  $http.get('groups').then (res) ->
    $scope.groups = res.data
    return true

  $scope.byCountDesc = (g) -> -g.count
  $scope.goto = (tag) -> $location.path '/' + encodeURIComponent tag


MediaCtrl = ($scope, $location, $http, $routeParams, $window, Photo) ->
  $scope.photos = []
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
    $('#modal-tagger .tag-input').focus()

  $('#modal-tagger').on 'hidden.bs.modal', ->
    $('#modal-tagger .tag-input').val ''

  $('.tag-form').on 'submit', (e) ->
    el = $(e.target).find('.tag-input').first()
    tag = el.val().toLowerCase().replace /^\s+|\s+$/, ''
    return unless tag.length > 0
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

  $scope.addAndTag = (tag) ->
    for id of activeIds()
      $scope.getPhoto(id).setTag tag
    $scope.showTagger()

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
    recomputeSelected()

  # INDIVIDUAL PHOTO OPERATIONS

  $scope.toggleViewer = ->
    modal = $('#modal-viewer').modal('toggle').first()
    $scope.viewerVisible = 'none' isnt modal.css 'display'

  $scope.contrastPhoto = (gamma, alpha) ->
    return unless $scope.viewerVisible
    $scope.getPhoto().contrast gamma, alpha

  $scope.cropPhoto = (x1, y1, x2, y2) ->
    return unless $scope.viewerVisible
    $scope.getPhoto().crop x1, y1, x2, y2

  $scope.rotatePhoto = (degrees) ->
    return unless $scope.viewerVisible
    $scope.getPhoto().rotate degrees

  $scope.incPhotoYear = (add) ->
    return unless $scope.viewerVisible
    $scope.getPhoto().incrementDate 'year', add

  $scope.incPhotoMonth = (add) ->
    return unless $scope.viewerVisible
    $scope.getPhoto().incrementDate 'month', add

  $scope.incPhotoDay = (add) ->
    return unless $scope.viewerVisible
    $scope.getPhoto().incrementDate 'day', add

  $scope.deletePhoto = ->
    return unless $scope.viewerVisible
    return unless confirm 'Really delete?'
    $scope.getPhoto().delete_ (id) ->
      i = _.indexOf _.pluck($scope.photos, 'id'), id
      if i >= 0
        $scope.cursor-- if $scope.cursor is $scope.photos.length - 1
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

    # NO MODIFIER -- just activate clicked photo.
    $scope.selectedIds = {}
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

  $scope.prevPhoto = (n) ->
    return if $scope.cursor <= 0
    $scope.cursor = Math.max 0, $scope.cursor - n
    $scope.scroll()

  $scope.nextPhoto = (n) ->
    L = $scope.photos.length - 1
    return if $scope.cursor >= L
    $scope.cursor = Math.min L, $scope.cursor + n
    $scope.scroll()

  $scope.getPhoto = (id) ->
    if typeof id is 'undefined' or id is null
      return $scope.photos[$scope.cursor]
    if typeof id is 'string'
      id = parseInt id
    for p in $scope.photos
      if id is p.id
        return p
    null

  $scope.scroll = ->
    y = $("#photo-#{$scope.getPhoto().id}").offset().top - 16
    top = $(window).scrollTop()
    unless top < y < top + $(window).height() - 100
      $('html, body').animate scrollTop: y

  activeIds = ->
    ids = _.extend {}, $scope.selectedIds
    if 0 is _.size ids
      ids[$scope.photos[$scope.cursor].id] = true
    console.log 'active ids', ids
    return ids

  recomputeSelected = ->
    ids = activeIds()
    n = _.size ids
    counts = {}
    for id of ids
      for t in $scope.getPhoto(id).tags
        counts[t] = 0 unless counts[t]
        counts[t]++
    $scope.selectedPhotoTags = _.sortBy (
      {name: t, count: c, limit: n} for t, c of counts
    ), (x) -> -x.count

  $http.get("tags?tags=#{$scope.activeTags.join '|'}").then (res) ->
    $scope.availableTags = res.data
    return true

  $('#thumbs').focus()

  $('.modal').on 'hide.bs.modal', ->
    $('#thumbs').focus()

  # this is an absurd workaround for the fact that tabbing away from an input
  # element does not allow the standard blur handler to return focus to #thumbs
  # (for correct processing of future keydown events). we capture <tab> keydowns
  # and convert them to blur firings manually.
  $('#modal-viewer .tag-input').on 'keydown', (e) ->
    if e.keyCode is 9  # tab
      $(e.target).blur()
      return false
    true

  $('#modal-viewer .tag-input').on 'blur', (e) ->
    $(e.target).val ''
    setTimeout (-> $('#thumbs').focus()), 0

  $scope.loadPhotos 200


angular.module('app.controllers', ['app.services'])
  .controller('GroupsCtrl', GroupsCtrl)
  .controller('MediaCtrl', MediaCtrl)
