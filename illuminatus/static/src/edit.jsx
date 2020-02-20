import React, {Component} from "react"
import {Link, useParams} from "react-router-dom"
import ReactCrop from "react-image-crop"
import Select from "react-select"
import axios from "axios"

class Edit extends Component {
    render() {
        return <div className="edit">EDIT {useParams().id}</div>
    }
}

export default Edit

/*(function() {
  'use strict';

  var KEYS = {
    tab: 9, enter: 13, escape: 27, space: 32,
    insert: 45, delete: 46, backspace: 8,
    pageup: 33, pagedown: 34, end: 35, home: 36,
    left: 37, up: 38, right: 39, down: 40,
    '0': 48, '1': 49, '2': 50, '3': 51, '4': 52,
    '5': 53, '6': 54, '7': 55, '8': 56, '9': 57,
    a: 65, b: 66, c: 67, d: 68, e: 69, f: 70, g: 71, h: 72, i: 73,
    j: 74, k: 75, l: 76, m: 77, n: 78, o: 79, p: 80, q: 81, r: 82,
    s: 83, t: 84, u: 85, v: 86, w: 87, x: 88, y: 89, z: 90,
    '=': 187, '-': 189, '`': 192, '[': 219, ']': 221
  };

  var tags = null;
  var config = null;
  var thumbs = null;
  var editor = null;

  var showExportDialog = function() {
    $.featherlight('text', {
      afterOpen: function(e) {
        var query = thumbs.query;
        var name = query.replace(/\W+/g, '-');
        var selected = thumbs.selected();
        if (selected.length > 0) {
          var ids = [];
          selected.forEach(function(ids) { asset.push('id:' + asset.rec.id); });
          query = ids.join('|');
          name = name + '-' + ids.length;
        }
        var render = Handlebars.compile($('#export-template').html());
        $('div.featherlight-inner').html(
          render({query: query, name: 'export-' + name}));
      }});
  };

  var ensureEditor = function() {
    if (!editor)
      editor = new Illuminatus.Editor(
        config, '#editor-template', $('#editor'), $('#editor-column'));
    editor.edit(thumbs.asset);
    tags.setClosed(true);
  };

  Illuminatus.Editor = function(config, template, $target, $column) {
    this.config = config;
    this.template = Handlebars.compile($(template).html());
    this.$target = $target;
    this.$column = $column;

    var self = this;
    this.$column.on('input', 'input[type=range]', function(e) {
      var mod = 'filter';
      var value = this.value + '%';
      var filter = self.isRanging;
      if (self.isRanging === 'saturation') {
        filter = 'saturate';
      } else if (self.isRanging === 'hue') {
        value = this.value + 'deg';
        filter = 'hue-rotate';
      } else if (self.isRanging === 'rotate') {
        mod = 'transform';
        value = this.value + 'deg';
      }
      $('#workspace img').css(mod, filter + '(' + value + ')');
      $('#range-value').html(value);
    });

    this.isTagging = null;
    this.isRanging = null;
    this.isCropping = null;
    this.$crop = null;

    this.asset = null;
  };

  Illuminatus.Editor.prototype = {
    edit: function(asset) {
      location.hash = '#edit:' + thumbs.query + '=' + thumbs.assets.indexOf(asset);
      this.asset = asset;
      this.render();
      this.$column.removeClass('closed');
      thumbs.setNarrow(true);
    },

    hide: function() {
      location.hash = '#thumbs:' + thumbs.query;
      this.$column.addClass('closed');
      thumbs.setNarrow(false);
      this.asset = null;
    },

    render: function() {
      var when = moment(this.asset.rec.stamp);
      var format = this.config.formats.large_photo_format;
      if (this.asset.rec.medium === 'audio')
        format = this.config.formats.large_audio_format;
      if (this.asset.rec.medium === 'video')
        format = this.config.formats.large_video_format;
      this.$target.html(this.template({
        format: format,
        asset: this.asset.rec,
        is_audio: this.asset.rec.medium === 'audio',
        is_photo: this.asset.rec.medium === 'photo',
        is_video: this.asset.rec.medium === 'video',
        thumb: this.asset.rec.path_hash.slice(0, 2) + '/' + this.asset.rec.path_hash,
        uniq: moment().format(),
        stamp: {
          title: when.format('DD MMM'),
          year: when.format('YYYY'),
          month: when.format('MM'),
          day: when.format('DD'),
          hour: when.format('ha')
        }
      }));
      if (this.isTagging)
        this.startTagging();
    },

    renderCallback: function() {
      var self = this;
      return function() { self.render(); };
    },

    remove: function() {
      if (!this.asset) return;
      thumbs.remove(this.asset);
      if (thumbs.asset)
        this.edit(thumbs.asset);
    },

    cancel: function() {
      if (this.isTagging) {
        this.isTagging = null;
        this.$target.toggleClass('tagging', false);
      }
      if (this.isCropping) {
        this.isCropping = null;
        this.$target.toggleClass('cropping', false);
        if (this.$crop) this.$crop.destroy();
        this.$crop = null;
        $('#workspace img').attr('style', '');
      }
      if (this.isRanging) {
        this.isRanging = null;
        this.$target.toggleClass('ranging', false);
        $('#workspace img').css({filter: 'none', transform: 'none'});
      }
    },

    commit: function() {
      if (this.isTagging) {
        this.asset.incTag($('#tag-input')[0].value, this.renderCallback());
      }
      if (this.isCropping) {
        var $img = $('#workspace img');
        var width = $img.width();
        var height = $img.height();
        var box = this.$crop.ui.selection.last;
        this.asset.addFilter(
          'crop',
          {x1: box.x / width,
           y1: box.y / height,
           x2: box.x2 / width,
           y2: box.y2 / height},
          this.renderCallback());
        this.cancel();
      }
      if (this.isRanging) {
        var value = $('#range').find('input[type=range]')[0].value;
        var filter = this.isRanging;
        var data = {};
        if (filter === 'rotate' || filter === 'hue')
          data.degrees = value;
        else
          data.percent = value;
        this.asset.addFilter(filter, data, this.renderCallback());
        this.cancel();
      }
    },

    startCrop: function() {
      if (this.$crop)
        this.$crop.destroy();

      var $img = $('#workspace img');
      var width = $img.width();
      var height = $img.height();
      var self = this;

      $img.Jcrop({
        boxHeight: height,
        boxWidth: width,
        keySupport: false,
        setSelect: [20, 20, width - 20, height - 20],
        bgOpacity: 0.8,
        allowSelect: true
      }, function() {
        self.isCropping = true;
        self.$target.toggleClass('cropping', true);
        self.$crop = this;
      });
    },

    startRange: function(attribute) {
      this.isRanging = attribute;
      this.$target.toggleClass('ranging', true);
      var attrs = {min: 0, max: 200, value: 100};
      if (attribute === 'hue')
        attrs = {min: 0, max: 360, value: 0};
      if (attribute === 'rotate')
        attrs = {min: -180, max: 180, value: 0};
      $('#range').find('input[type=range]').attr(attrs).trigger('input');
    },

    startTagging: function() {
      this.isTagging = true;
      this.$target.toggleClass('tagging', true);
      $('#tag-input')[0].value = '';
      $('#tag-input').focus();
    }
  };

  var handleKeydown = function(e) {
    // enter   - show editor
    // bksp    - delete current image
    // down, j - move to next image
    // up, k   - move to previous image
    // pgdown  - move 10 images forward
    // pgup    - move 10 images back
    // s       - toggle star tag
    // x       - toggle select
    // E       - export selected
    // A       - select all
    //
    // In Edit Mode:
    // escape - hide editor
    // c      - start cropping
    // z      - undo most recent change
    // !      - apply autocontrast
    // t      - focus tag input
    // ]/[    - rotate 90 deg cw/ccw
    // }/{    - rotate 1 deg cw/ccw
    // p/P    - increment/decrement year
    // o/O    - increment/decrement month
    // i/I    - increment/decrement day
    // u/U    - increment/decrement hour

    //console.log(e);

    if (e.ctrlKey || e.altKey || e.metaKey) return;

    var key = e.keyCode;

    if ($(e.target).is('input, textarea') &&
        (key !== KEYS.enter) && (key !== KEYS.escape))
      return;

    e.preventDefault();

    if (key === KEYS.escape) {
      if (editor) {
        if (editor.isCropping || editor.isRanging || editor.isTagging) {
          editor.cancel();
        } else {
          editor.hide();
          editor = null;
        }
      }
    }

    if (key === KEYS.enter) {
      if (editor) {
        if (editor.isCropping || editor.isRanging || editor.isTagging) {
          editor.commit();
        } else {
          editor.edit(thumbs.asset);
        }
      } else {
        ensureEditor();
      }
    }

    if (key === KEYS.e && e.shiftKey)
      showExportDialog();

    if (key === KEYS.j || key === KEYS.right || key === KEYS.down) {
      thumbs.incCursor();
      if (editor)
        editor.edit(thumbs.asset);
    }


    if (key === KEYS.k || key === KEYS.left || key === KEYS.up) {
      thumbs.decCursor();
      if (editor)
        editor.edit(thumbs.asset);
    }

    if (key === KEYS.pagedown) {
      thumbs.incCursor(10);
      if (editor)
        editor.edit(thumbs.asset);
    }

    if (key === KEYS.pageup) {
      thumbs.decCursor(10);
      if (editor)
        editor.edit(thumbs.asset);
    }

    if (key === KEYS.a && e.shiftKey)
      thumbs.selectAll();

    if (key === KEYS.x)
      if (thumbs.asset)
        thumbs.asset.toggleSelect();

    if (key === KEYS.backspace || key === KEYS.delete) {
      if (confirm('Really delete "' + thumbs.asset.rec.path + '"?')) {
        thumbs.remove();
        if (editor)
          editor.edit(thumbs.asset);
      }
    }

    if (key === KEYS.t) {
      ensureEditor();
      editor.startTagging();
    }

    if (editor) {
      if (key === KEYS['['])
        editor.asset.rotate(e.shiftKey ? -1 : -90, editor.renderCallback());
      if (key === KEYS[']'])
        editor.asset.rotate(e.shiftKey ? 1 : 90, editor.renderCallback());

      if (key === KEYS.p)
        editor.asset.incrementDate((e.shiftKey ? '+' : '-') + '1y', editor.renderCallback());
      if (key === KEYS.o)
        editor.asset.incrementDate((e.shiftKey ? '+' : '-') + '1m', editor.renderCallback());
      if (key === KEYS.i)
        editor.asset.incrementDate((e.shiftKey ? '+' : '-') + '1d', editor.renderCallback());
      if (key === KEYS.u)
        editor.asset.incrementDate((e.shiftKey ? '+' : '-') + '1h', editor.renderCallback());

      if (key === KEYS['1'] && e.shiftKey)  // !
        editor.asset.autocontrast(1, editor.renderCallback());

      if (key === KEYS.z)
        editor.asset.undoLastFilter(editor.renderCallback());

      if (key === KEYS.c)
        editor.startCrop();
    }
  };

  $(document).keydown(handleKeydown);

  $('#editor').on('click', '#magic', function(e) {
    editor.asset.autocontrast(1, editor.renderCallback()); });

  $('#editor').on('click', '#brightness', function(e) { editor.startRange('brightness'); });
  $('#editor').on('click', '#contrast', function(e) { editor.startRange('contrast'); });
  $('#editor').on('click', '#saturation', function(e) { editor.startRange('saturation'); });
  $('#editor').on('click', '#hue', function(e) { editor.startRange('hue'); });

  $('#editor').on('click', '#rotate', function(e) { editor.startRange('rotate'); });
  $('#editor').on('click', '#rotate-ccw-90', function(e) {
    editor.asset.rotate(-90, editor.renderCallback()); });
  $('#editor').on('click', '#rotate-cw-90', function(e) {
    editor.asset.rotate(90, editor.renderCallback()); });
  $('#editor').on('click', '#hflip', function(e) {
    editor.asset.hflip(editor.renderCallback()); });
  $('#editor').on('click', '#vflip', function(e) {
    editor.asset.vflip(editor.renderCallback()); });

  $('#editor').on('click', '#crop', function(e) { editor.startCrop(); });

  $('#editor').on('click', '#cancel', function(e) { editor.cancel(); });
  $('#editor').on('click', '#commit', function(e) { editor.commit(); });

  $('#editor').on('click', '#filters a', function(e) {
    editor.asset.removeFilter($(this).data('filter'),
                             $(this).data('index'),
                             editor.renderCallback());
  })

  $('#editor').on('mouseenter', '#tags-tab', function(e) { editor.startTagging(); });
  $('#editor').on('mouseleave', '#tags-tab', function(e) { editor.cancel(); });

  $('#thumbs').on('click', '.thumb', function(e) {
    var asset = $(e.target).closest('li')[0].asset;
    if (e.ctrlKey || e.metaKey || e.altKey) {
      asset.toggleSelect();
    } else {
      thumbs.clearSelection();
      thumbs.setCursor(asset);
      if (editor)
        editor.edit(thumbs.asset);
    };
  });

  $(document).on('submit', '#export', function(e) { $.featherlight.close(); });

  var app = {
    routes: [
      {
        pattern: /#thumbs.(.+)/,
        render: function(match) {
          tags.refresh();
          thumbs.setQuery(match[1]);
          thumbs.fetch();
        }
      },

      {
        pattern: /#edit.(.+)=([0-9]+)/,
        render: function(match) {
          var n = parseInt(match[2]);
          tags.refresh();
          thumbs.setQuery(match[1]);
          thumbs.fetch(n + 10 - thumbs.assets.length, function() {
            thumbs.setCursor(n);
            ensureEditor();
          });
        }
      }
    ],

    handleRouteChange: function() {
      var hasMatch = false;
      for (var i = 0; i < app.routes.length; i++) {
        var view = app.routes[i];
        var match = view.pattern.exec(location.hash);
        if (match) {
          view.render(match);
          hasMatch = true;
          break;
        }
      }
      if (!hasMatch)
        location.hash = 'thumbs:' + moment().year();
    },

    init: function() {
      addEventListener('hashchange', function() {
        app.handleRouteChange();
      });

      $.getJSON('/config', function(data) {
        config = data;
        thumbs = new Illuminatus.Thumbs(
          data, '#thumb-template', $('#thumbs'), $('#thumbs-column'));
        tags = new Illuminatus.Tags(
          '#tag-template', $('#tags'), $('#tags-column'));
        if (!location.hash) {
          location.hash = 'thumbs:' + moment().year();
        } else {
          app.handleRouteChange();
        }
      });
    }
  };

  window.app = app;

})();

$(app.init);
*/
