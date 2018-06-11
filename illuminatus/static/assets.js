(function() {
  'use strict'

  window.Illuminatus = window.Illuminatus || {};

  Illuminatus.Asset = function(rec, $thumb) {
    this.rec = rec;
    this.$thumb = $thumb;
    this.selected = false;
    this.cursor = false;
  };

  Illuminatus.Asset.prototype = {
    $ajax: function(method, path, data, callback) {
      console.log('ajax', method, path, data, callback);
      $.ajax({
        url: '/asset/' + this.rec.id + path,
        type: method,
        data: data,
        success: (function(self) {
          return function(data) {
            self.rec = data;
            if (callback) callback();
          };
        })(this)
      });
    },

    toggleSelect: function() { this.setSelect(!this.selected); },

    setSelect: function(selected) {
      this.selected = selected;
      this.$thumb.toggleClass('selected', this.selected);
    },

    setCursor: function(cursor) {
      this.cursor = cursor;
      this.$thumb.toggleClass('cursor', this.cursor);
    },

    remove: function(callback) {
      this.$ajax('DELETE', '/', {}, callback);
    },

    incTag: function(tag, callback) {
      this.$ajax('PUT', '/', {inc_tags: tag}, callback);
    },

    decTag: function(tag, callback) {
      this.$ajax('PUT', '/', {dec_tags: tag}, callback);
    },

    removeTag: function(tag, callback) {
      this.$ajax('PUT', '/', {remove_tags: tag}, callback);
    },

    addFilter: function(filter, data, callback) {
      console.log('+ filter', filter, data);
      this.$ajax('POST', '/filters/' + filter, data, callback);
    },

    removeFilter: function(filter, index, callback) {
      console.log('- filter', filter, index);
      this.$ajax('DELETE', '/filters/' + filter + '/' + index, {}, callback);
    },

    undoLastFilter: function(callback) {
      var filters = this.rec.filters;
      var L = filters.length;
      if (L > 0)
        this.removeFilter(filters[L - 1].filter, L - 1, callback);
    },

    incrementDate: function(increment, callback) {
      this.$ajax('PUT', '/', {stamp: increment}, callback);
    },

    rotate: function(degrees, callback) {
      this.addFilter('rotate', {degrees: degrees}, callback);
    },

    hflip: function(callback) {
      this.addFilter('hflip', {}, callback);
    },

    vflip: function(callback) {
      this.addFilter('vflip', {}, callback);
    },

    autocontrast: function(percent, callback) {
      this.addFilter('autocontrast', {percent: percent}, callback);
    }
  };
})();
