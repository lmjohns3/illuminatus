(function() {
  'use strict'

  window.Illuminatus = window.Illuminatus || {};

  Illuminatus.Tags = function(template, $tags, $column) {
    this.render = Handlebars.compile($(template).html());
    this.$tags = $tags;
    this.tags = [];

    var self = this;
    this.$column = $column;
    this.$column.click(function(e) {
      var width = $(this).outerWidth();
      var border = width - $(this).innerWidth();
      if (width - e.pageX < border)
        self.toggleClosed();
    });
  };

  Illuminatus.Tags.prototype = {
    toggleClosed: function() {
      this.$column.toggleClass('closed');
    },

    setClosed: function(closed) {
      if (closed)
        this.$column.addClass('closed');
      else
        this.$column.removeClass('closed');
    },

    refresh: function() {
      $.getJSON('/config', (function(self) {
        return function(data) {
          self.tags = data.tags;
          self.$tags.empty();
          data.tags.forEach(function(tag) {
            self.$tags.append(self.render(tag));
          });
        };
      })(this));
    }
  };

})();
