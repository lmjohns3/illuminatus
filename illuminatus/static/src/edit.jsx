import moment from 'moment'
import React, {useEffect, useState} from "react"
import ReactCrop from "react-image-crop"
import Select from "react-select"


const Controls = ({asset, close, isEditing, setIsEditing}) => {
  return <div className='controls'>
    <Button name='close' onClick={close} style={{fontSize:'200%'}} icon='×' />
    <Button name='edit' onClick={() => setIsEditing(!isEditing)} icon='🖉' /> 
    {isEditing ? <EditingButtons /> : null}
  </div>;
}


const EditingButtons = () => {
  return <>
    <Button name='magic' icon='☘' />
    <Button name='brightness' icon='☀' />
    <Button name='contrast' icon='◑' />
    <Button name='saturation' icon='▧' />
    <Button name='hue' icon='🖌' />
    <Button name='rotate' icon='↻' />
    <Button name='cw' icon='⤵' />
    <Button name='ccw' icon='⤴' />
    <Button name='hflip' icon='↔' />
    <Button name='vflip' icon='↕' />
    <Button name='delete' icon='🗑' />
    <Button name='crop' icon='✂' />
  </>;
}

// <Button icon='⚠' />
// <Button icon='⮢' />
// <Button icon='⮣' />
// <Button icon='⤿' />
// <Button icon='⤾' />
// <Button icon='⛔' />
// <Button icon='🚫' />
// <Button icon='✏' />
// <Button icon='☠' />


const Button = ({name, icon, onClick, style}) => {
  return <span className='button' title={name} style={style} onClick={onClick}>
    <span className='icon'>{icon}</span>
  </span>;
}


export default Controls

/*
<ReactCrop src={this.state.asset.src} crop={this.state.crop} onChange={newCrop => this.setCrop(newCrop)} />


const FilterTools = ({filters}) => (
    <ul>{filters.map(filter => (
      <li><a data-filter="{filter}" data-index="{index}">
        <span className="dingbat">✘</span> {filter}</a></li>
    ))}</ul>)

const StampTools = ({stamp}) => (
  <ul>
    <li><a id="">Y: {stamp.year}</a></li>
    <li><a id="">M: {stamp.month}</a></li>
    <li><a id="">D: {stamp.day}</a></li>
    <li><a id="">H: {stamp.hour}</a></li>
  </ul>)


    <ul className="toolbar" id="basic-tools">
      <li><span className="dingbat">⚒</span> Edit <EditTools /></li>
      <li><span className="dingbat">🏷</span> Tags <TagTools tags={asset.tags} /></li>
      <li><span className="dingbat">☞</span> Filters <FilterTools filters={asset.filters} /></li>
      <li><span className="dingbat">⏰</span> {asset.stamp.title} <StampTools stamp={asset.stamp} /></li>
      <li><span id="path">{asset.path}</span></li>
    </ul>
    <ul className="toolbar" id="ephemeral-tools">
      <li id="cancel"><span className="dingbat">✘</span> Cancel</li>
      <li id="commit"><span className="dingbat">✔</span> Save</li>
      <li id="range"><input type="range" min="0" max="200" defaultValue="100" step="1"/><span id="range-value"></span></li>
  </div>
</div>);
    }
}



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
*/
