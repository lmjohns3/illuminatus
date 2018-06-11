(function() {
  'use strict'

  window.Illuminatus = window.Illuminatus || {};

  Illuminatus.Thumbs = function(config, thumbTemplate, $thumbs, $column) {
    this.config = config;
    this.renderThumb = Handlebars.compile($(thumbTemplate).html());
    this.$thumbs = $thumbs;
    this.$column = $column;
    this.query = null;
    this.scrolling = false;

    $thumbs.parent().scroll(this.handleScroll(this));
  };

  Illuminatus.Thumbs.prototype = {
    setQuery: function(query) {
      if (query === this.query) return;

      this.query = query;
      this.$thumbs.empty();
      this.assets = [];

      this.asset = null;
      this.cursor = null;

      this.loading = false;
      this.exhausted = false;
    },

    incCursor: function(n) { this.setCursor(this.cursor + (n || 1)); },
    decCursor: function(n) { this.setCursor(this.cursor - (n || 1)); },
    setCursor: function(idx) {
      if (this.assets.length === 0) {
        this.asset = null;
        this.cursor = null;
        return;
      }
      if (idx instanceof Illuminatus.Asset)
        idx = this.assets.indexOf(idx);
      if (0 <= idx && idx < this.assets.length) {
        if (this.asset)
          this.asset.setCursor(false);
        this.assets[idx].setCursor(true);
        this.asset = this.assets[idx];
        this.cursor = idx;
        this.scrollToCursor();
      }
    },

    setNarrow: function(narrow) {
      this.$column.toggleClass('narrow', narrow);
      this.scrollToCursor();
    },

    selectAll: function() {
      this.assets.forEach(function (asset) { asset.setSelect(true); });
    },

    clearSelection: function() {
      this.assets.forEach(function (asset) { asset.setSelect(false); });
    },

    eachSelected: function(func) {
      return this.assets.forEach(function (asset, i) {
        if (asset.selected) func(asset, i);
      });
    },

    removeCursor: function() {
      var idx = arguments[0] || this.cursor;
      if (idx < 0 || idx >= this.assets.length) return;
      this.assets[idx].remove();
      this.assets.splice(idx, 1);
      if (this.assets.length === 0)
        this.asset = null;
      if (this.cursor >= idx && this.cursor > 0)
        this.setCursor(this.cursor - 1);
    },

    removeSelected: function() {
      var beforeCursor = 0;
      var remaining = [];
      this.assets.forEach(function(asset, i) {
        if (asset.selected) {
          if (i <= this.cursor)
            beforeCursor++;
          asset.remove();
        } else {
          remaining.push(asset);
        }
      });
      this.assets = remaining;
      if (this.assets.length === 0)
        this.asset = null;
      else
        this.setCursor(Math.max(0, this.cursor - beforeCursor));
    },

    fetch: function(limit, callback) {
      if (this.loading || this.exhausted) return;

      var self = this;
      limit = limit || 10;
      if (limit <= 0) return;

      var doneHandler = function(data) {
        console.log('fetched', data.assets);
        self.loading = false;
        self.exhausted = data.assets.length < limit;
        data.assets.forEach(function (rec) {
          var format = self.config.formats.small_photo_format;
          if (rec.medium === 'audio')
            format = self.config.formats.small_audio_format;
          if (rec.medium === 'video')
            format = self.config.formats.small_video_format;
          self.$thumbs.append(self.renderThumb({
            asset: rec,
            format: format,
            is_audio: rec.medium === 'audio',
            is_photo: rec.medium === 'photo',
            is_video: rec.medium === 'video',
            thumb: rec.path_hash.slice(0, 2) + '/' + rec.path_hash
          }));
          var $thumb = $('#asset-' + rec.id);
          var asset = new Illuminatus.Asset(rec, $thumb);
          self.assets.push(asset);
          $thumb[0].asset = asset;
        });
        if (self.assets.length > 0 && self.cursor === null)
          self.setCursor(0);
        if (callback)
          callback();
        if (!self.exhausted && self.$thumbs.height() < $(window).height())
          self.fetch(limit, callback);
      };

      var url = ('/query/' + this.query +
                 '?offset=' + this.assets.length +
                 '&limit=' + limit);
      //console.log(url);
      this.loading = true;
      $.getJSON(url)
        .done(doneHandler)
        .fail(function() { self.loading = false; });
    },

    handleScroll: function(self) {
      return function() {
        if (self.exhausted || self.loading) return;
        var bottom = self.$thumbs.parent().scrollTop() + $(window).height();
        // compare total vertical pixels ($thumbs.height()) with the bottom-most
        // visible pixel of the thumbs -- fetch more if the bottom is close to the
        // total.
        //console.log('thumbs: bottom', bottom, 'visible of total', self.$thumbs.height());
        if (self.$thumbs.height() - bottom < 200)
          self.fetch();
      };
    },

    scrollToCursor: function() {
      if (this.scrolling || !this.asset) return;

      this.scrolling = true;
      var down = this.asset.$thumb.offset().top - this.$thumbs.offset().top;
      var hidden = this.$thumbs.parent().scrollTop();
      var height = $(window).height();

      //console.log('cursor: down', down, 'hidden', hidden, 'height', height);

      if (down < hidden + 100 || down > hidden + height - 100) {
        var self = this;
        this.$thumbs.parent().animate(
          {scrollTop: down - 150}, 200, 'linear',
          function() { self.scrolling = false; });
      } else {
        this.scrolling = false;
      }
    }
  };
})();
