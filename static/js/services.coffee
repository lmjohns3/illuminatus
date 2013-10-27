# http://stackoverflow.com/questions/12719782/angularjs-customizing-resource

PhotoFactory = ($http) ->
  ->
    parse = (msg) ->
      if msg.response then msg.response else msg

    class Photo
      constructor: (value) ->
        angular.copy parse(value or {}), @
        @when = moment @stamp
        @img = "#{@thumb}#"

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

      incrementDate: (field, add) ->
        if add
          @when.add field, 1
        else
          @when.subtract field, 1
        @meta.stamp = @when.format()
        @save()

      save: ->
        data = meta: @meta
        $http(method: 'POST', url: "/photo/#{@id}", data: data).then (res) =>
          console.log 'saved', @id, res
          @meta = res.data.meta
          @stamp = res.data.stamp
          @tags = res.data.tags
          @when = moment @stamp

      contrast: (gamma, alpha) ->
        data = gamma: gamma, alpha: alpha
        $http(method: 'POST', url: "/photo/#{@id}/contrast", data: data).then (res) =>
          console.log 'contrast', @id, data, res
          @img = "#{@thumb}##{new Date().getTime()}"

      rotate: (degrees) ->
        data = degrees: degrees
        $http(method: 'POST', url: "/photo/#{@id}/rotate", data: data).then (res) =>
          console.log 'rotate', @id, data, res
          @img = "#{@thumb}##{new Date().getTime()}"

      crop: (x1, y1, x2, y2) ->
        data = x1: x1, y1: y1, x2: x2, y2: y2
        $http(method: 'POST', url: "/photo/#{@id}/crop", data: data).then (res) =>
          console.log 'crop', @id, data, res
          @img = "#{@thumb}##{new Date().getTime()}"

      delete_: (callback) ->
        $http(method: 'DELETE', url: "/photo/#{@id}").then (res) => callback @id

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
