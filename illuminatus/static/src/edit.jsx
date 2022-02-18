import moment from 'moment'
import React, {useEffect, useState} from 'react'
import {Link, useHistory, useParams} from 'react-router-dom'
import ReactCrop from 'react-image-crop'

import {TagGroups, TagSelect} from './tags'
import {Breadcrumbs, Button, Related} from './utils'

import './edit.styl'
import 'react-image-crop/dist/ReactCrop.css'


const Tool = ({name, icon, iconWhenActive, activeTool, onClick}) => (
  <Button name={name}
          icon={activeTool === name ? (iconWhenActive || icon) : icon}
          disabled={activeTool !== null && activeTool !== name}
          onClick={onClick} />
)


const Edit = ({refresh}) => {
  const slug = useParams().slug
      , hist = useHistory()
      , stopEditing = () => hist.replace(`/view/${asset.slug}/`)
      , src = `/asset/${slug}/read/full/`
      , defaultAsset = {medium: 'photo', tags: [], slug}
      , [asset, setAsset] = useState(defaultAsset)
      , [activeTool, setActiveTool] = useState(null)
      , [crop, setCrop] = useState(null);

  useEffect(() => {
    setAsset(defaultAsset);
    fetch(`/asset/${slug}/`).then(res => res.json()).then(setAsset);
  }, [slug]);

  useEffect(() => {
    const handler = ev => {
      if (ev.code === 'Escape') stopEditing();
      const input = document.querySelector('.tag-select input');
      if (input && input.matches(':focus')) return;
      if (ev.code === 'KeyT') { ev.preventDefault(); input.focus(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [slug]);

  const deleteAsset = () => {
    if (window.confirm('Really delete?')) {
      fetch(`/asset/${slug}/`, {method: 'delete'}).then(() => hist.go(-1));
    }
  };

  return <>
    <Breadcrumbs className='edit'>
      <Link to={`/view/${slug}/`}>{slug.slice(0, 12)}</Link>
      <span className='divider'>»</span>
      Edit
    </Breadcrumbs>

    <div className='edit asset'>{
      asset.medium === 'video' ? <video key={asset.id} controls><source src={src} /></video> :
      asset.medium === 'audio' ? <audio key={asset.id} controls><source src={src} /></audio> :
      crop ? <ReactCrop src={src} crop={crop} onChange={(_, crop) => setCrop(crop)} /> :
      <img src={src} />
    }</div>
    <TagGroups className='edit' assets={asset.id ? [asset] : []} hideEditable={true}
               clickHandler={tag => () => removeTag(tag.name)} />
    <TagSelect className='edit' assets={asset.id ? [asset] : []} />
    <div className='edit tools'>
      <Button name='exit' icon='✕' onClick={stopEditing}/>
      <span className='spacer' />
      <Button name='delete' icon='🗑' onClick={deleteAsset} />
      <span className='spacer' />
      <Tool name='crop'
            icon='✂'
            iconWhenActive={'✕'}
            activeTool={activeTool}
            onClick={() => {
              setActiveTool('crop');
              setCrop({unit: '%', width: 80, height: 80, x: 10, y: 10});
            }}/>
      <span className='spacer' />
      <Tool name='vflip' icon='↕' activeTool={activeTool} />
      <Tool name='hflip' icon='↔' activeTool={activeTool} />
      <Tool name='ccw' icon='⤷' activeTool={activeTool} />
      <Tool name='cw' icon='⤶' activeTool={activeTool} />
      <Tool name='rotate' icon='⟳' activeTool={activeTool} />
      <span className='spacer' />
      <Tool name='contrast' icon='◑' activeTool={activeTool} />
      <Tool name='brightness' icon='☀' activeTool={activeTool} />
      <Tool name='saturation' icon='▧' activeTool={activeTool} />
      <Tool name='hue' icon='🎨' activeTool={activeTool} />
      <span className='spacer' />
      <Tool name='magic' icon='🪄'  activeTool={activeTool} />
    </div>
    <ul className='edit filters'>
      {(asset.filters || []).map(
        (f, i) => <li key={i}><span>{f}</span><span className='remove'>🗑</span></li>)}
    </ul>
    <Related asset={asset} how='tag' title='Related' className='edit' />
    <Related asset={asset} how='content' title='Duplicates' className='edit' />
  </>;
}


export default Edit

// ✓✕
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

/*

    <ul className='toolbar' id='ephemeral-tools'>
      <li id='cancel'><span className='dingbat'>✕</span> Cancel</li>
      <li id='commit'><span className='dingbat'>✓</span> Save</li>
      <li id='range'><input type='range' min='0' max='200' defaultValue='100' step='1'/><span id='range-value'></span></li>
  </div>

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
*/
