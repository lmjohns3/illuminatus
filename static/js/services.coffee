# http://stackoverflow.com/questions/12719782/angularjs-customizing-resource

PhotoFactory = ($http) ->
  ->
    parse = (msg) ->
      if msg.response then msg.response else msg

    class Photo
      constructor: (value) ->
        angular.copy parse(value or {}), @

      toggleTag: (tag) ->
        i = @tagIndex tag
        if i >= 0
          @meta.user_tags.splice i, 1
        else
          @meta.user_tags.push tag
        @save()

      tagIndex: (tag) ->
        _.indexOf @meta.user_tags, tag

      hasTag: (tag) ->
        0 <= @tagIndex tag

      setTag: (tag) ->
        unless @hasTag tag
          @meta.user_tags.push tag
          @save()

      clearTag: (tag) ->
        i = @tagIndex tag
        if i >= 0
          @meta.user_tags.splice i, 1
          @save()

      save: ->
        id = @id
        data = meta: @meta
        $http(method: 'POST', url: "/photo/#{id}", data: data).then (res) =>
          console.log 'saved', id, res
          @meta = res.data.meta
          @stamp = res.data.stamp
          @tags = res.data.tags

      contrastBrightness: (data) ->
        $http(method: 'POST', url: "/photo/#{id}/cb", data: data).then (res) =>
          console.log 'contrast/brightness', id, data, res

      rotate: (data) ->
        $http(method: 'POST', url: "/photo/#{id}/ro", data: data).then (res) =>
          console.log 'rorate', id, data, res

      crop: (data) ->
        $http(method: 'POST', url: "/photo/#{id}/cr", data: data).then (res) =>
          console.log 'crop', id, data, res

    Photo.query = (query, callback) ->
      value = []
      url = '/photo?'
      if query.tags.length > 0
        url += "tags=#{query.tags}&"
      if query.offset > 0
        url += "offset=#{query.offset}&"
      if query.limit > 0
        url += "limit=#{query.limit}&"
      $http.get(url).then (res) ->
        for p in res.data
          value.push new Photo(p)
        callback value
      return value

    return Photo


angular.module('app.services', [])
  .factory('Photo', PhotoFactory)
