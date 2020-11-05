import axios from 'axios'
import moment from 'moment'
import React, {useEffect, useState} from 'react'
import {Link, useHistory, useParams} from 'react-router-dom'
import CreatableSelect from 'react-select/creatable'
import ReactCrop from 'react-image-crop'

import {countAssetTags, Tags} from './tags'
import {Breadcrumbs, Button, ConfigContext} from './utils'

import './edit.styl'
import 'react-image-crop/dist/ReactCrop.css'


const FilterTools = ({filters}) => (<ul className='filters'>
  {filters.map((f, i) => <li key={i}><span>{f}</span><span className='remove'>🗑</span></li>)}
</ul>)


const StampTools = ({stamp}) => (<ul className='stamp'>
  <li>Y: {stamp.year()}</li>
  <li>M: {stamp.month()}</li>
  <li>D: {stamp.day()}</li>
  <li>H: {stamp.hour()}</li>
</ul>)


const Tool = ({name, icon, iconWhenActive, activeTool, onClick}) => {
  const isActive = activeTool === null || activeTool === name;
  return <Button name={name}
                 icon={isActive ? (iconWhenActive || icon) : icon}
                 disabled={!isActive}
                 onClick={onClick} />;
}


const Edit = () => {
  const slug = useParams().slug
      , hist = useHistory()
      , stopEditing = () => hist.replace(`/view/${asset.slug}/`)
      , url = `/rest/asset/${slug}/`
      , [asset, setAsset] = useState({medium: 'photo', tags: [], slug})
      , [activeTool, setActiveTool] = useState(null)
      , [crop, setCrop] = useState({unit: '%', width: 80, height: 80, x: 10, y: 10});

  useEffect(() => { axios(url).then(res => setAsset(res.data)); }, [slug]);

  const addTag = ({value}, {action}) => {
    if (action === 'create-option' || action === 'select-option') {
      axios.put(url, {add_tags: value}).then(res => setAsset(res.data));
    }
  };

  const removeTag = name => {
    axios.put(url, {remove_tags: name}).then(res => setAsset(res.data));
  };

  useEffect(() => {
    const handler = ev => {
      if (ev.code === 'Escape') {
        stopEditing();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return <>
    <Breadcrumbs className='edit'>
      <Link to={`/view/${slug}/`}>{slug.slice(0, 12)}</Link>
      <span className='divider'>»</span>
      Edit
    </Breadcrumbs>
    <div className='edit asset'><ConfigContext.Consumer>{
     ({formats}) => {
       const ext = formats[asset.medium]['full'].ext
           , src = `/asset/full/${asset.slug.slice(0, 1)}/${asset.slug}.${ext}`;
       if (asset.medium === 'video')
         return <video key={asset.id} autoPlay controls><source src={src} /></video>;
       if (asset.medium === 'audio')
         return <audio key={asset.id} autoPlay controls><source src={src} /></audio>;
       if (crop)
         return <ReactCrop src={src} crop={crop} onChange={(_, crop) => setCrop(crop)} />;
       return <img src={src} />;
    }}</ConfigContext.Consumer></div>
    {countAssetTags([asset]).map(
      group => <Tags key={group.icon} icon={group.icon} tags={group.tags}
                     className='edit'
                     clickHandler={tag => () => removeTag(tag.name)} />
    )}
    <div className='edit tags'>
      <span className='icon'></span>
      <ul><li><ConfigContext.Consumer>{
        ({tags}) => <CreatableSelect className='tag-select'
                                     options={tags.map(t => ({label: t.name, value: t.name}))}
                                     onChange={addTag}
                                     autoFocus={true}
                                     placeholder='Add tag...' />
      }</ConfigContext.Consumer></li></ul>
    </div>
    <div className='tools'>
      <Button name='exit' icon='⨉' onClick={stopEditing}/>
      <span className='spacer' />
      <Button name='delete' icon='🗑' />
      <span className='spacer' />
      <Tool name='crop' icon='✂' iconWhenActive={'⨉'} activeTool={activeTool} />
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
    <FilterTools filters={asset.filters || []} />
    <StampTools stamp={moment(asset.stamp || null)} />
  </>;
}


export default Edit

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
      <li id='cancel'><span className='dingbat'>✘</span> Cancel</li>
      <li id='commit'><span className='dingbat'>✔</span> Save</li>
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
