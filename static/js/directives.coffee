KEYS =
  backspace: 8, tab: 9, enter: 13, esc: 27, space: 32, pageup: 33, pagedown: 34,
  end: 35, home: 36, left: 37, up: 38, right: 39, down: 40, insert: 45,
  delete: 46, a: 65, b: 66, c: 67, d: 68, e: 69, f: 70, g: 71, h: 72, i: 73,
  j: 74, k: 75, l: 76, m: 77, n: 78, o: 79, p: 80, q: 81, r: 82, s: 83, t: 84,
  u: 85, v: 86, w: 87, x: 88, y: 89, z: 90, '[': 219, ']': 221,


keypress = ($parse) ->
  link: (scope, elem, attrs) ->
    routes = {}
    for ks, v of scope.$eval attrs.lmjKeypress
      action = $parse v
      for k in "#{ks}".split ' '
        shiftKey = ctrlKey = metaKey = false
        if k.match /^[CSM]-/
          mod = k[0]
          k = k[2...]
          ctrlKey = true if mod is 'C'
          metaKey = true if mod is 'M'
          shiftKey = true if mod is 'S'
        k = KEYS[k] or parseInt k, 10
        routes[[k, ctrlKey, metaKey, shiftKey]] = action

    handler = (e) ->
      console.log e
      fn = routes[[e.keyCode, e.ctrlKey, e.metaKey, e.shiftKey]]
      if fn
        scope.$apply -> fn scope
        e.preventDefault()
        return false

    elem.on 'keydown', handler
    scope.$on '$destroy', ->
      elem.off 'keydown', handler


# inspired by http://binarymuse.github.io/ngInfiniteScroll/
scroll = ($rootScope, $window, $timeout) ->
  link: (scope, elem, attrs) ->
    $window = angular.element $window

    disabled = false
    if attrs.lmjScrollDisabled?
      scope.$watch attrs.lmjScrollDisabled, (value) ->
        disabled = not not value

    exhausted = false
    if attrs.lmjScrollExhausted?
      scope.$watch attrs.lmjScrollExhausted, (value) ->
        exhausted = not not value
        if exhausted
          $window.off 'scroll', handler

    handler = ->
      return if disabled

      bottom = $window.height() + $window.scrollTop()
      return unless bottom >= $(document).height() - 200

      if $rootScope.$$phase
        scope.$eval attrs.lmjScroll
      else
        scope.$apply attrs.lmjScroll

    $window.on 'scroll', handler
    scope.$on '$destroy', ->
      $window.off 'scroll', handler


angular.module('app.directives', [])
  .directive('lmjKeypress', keypress)
  .directive('lmjScroll', scroll)
