import axios from 'axios'
import moment from 'moment'
import React, {useEffect, useReducer, useState} from 'react'
import {BrowserView, MobileView, isBrowser, isMobile} from 'react-device-detect';
import {useParams} from 'react-router-dom'
import Select from 'react-select'
import { useSwipeable } from 'react-swipeable'

import DB from './db'
import Tags from './tags'
import {useKeyPressCallback} from './hooks'


const hrefForTag = (tag, path) => {
  const part = `/${tag}/`;
  return path.indexOf(part) < 0 ? tag : path.replace(part, '/');
}


export default function View() {
  // Get format info for the app.
  const [formats, setFormats] = useState([]);
  useEffect(() => {
    axios('/rest/formats/').then(res => setFormats(res.data));
  }, []);

  // Get assets matching our view query.
  const query = useParams().query
      , [assets, setAssets] = useState([]);
  useEffect(() => {
    axios(`/rest/query/${query}`).then(res => setAssets(res.data));
  }, [query]);

  // Keep track if there is a single asset being viewed.
  const h = window.Location.hash
      , hashCurrent = /#\d+/.test(h) ? parseInt(h.replace('#', '')) : null
      , [current, setCurrent] = useState(hashCurrent);
  useEffect(() => {
    const onKeyDown = ({key}) => {
      if (key === 'Escape') {
        setCurrent(null);
      } else if (current > 0 && (key === 'ArrowLeft' || key === 'ArrowUp')) {
        setCurrent(current - 1);
      } else if (current < assets.length - 1 && (key === 'ArrowRight' || key === 'ArrowDown')) {
        setCurrent(current + 1);
      }
    };
    if (current) {
      window.addEventListener('keydown', onKeyDown);
      return () => window.removeEventListener('keydown', onKeyDown);
    }
  }, [assets, current]);
  useEffect(() => {
    window.location.hash = current ? `#${current}` : '';
  }, [current]);

  // Show either the asset being viewed or thumbnails of all the assets.
  if (current) {
    return <div className='view'>
      <Asset asset={assets[current]} formats={formats} /></div>;
  } else {
    return <div className='browse'>
      <Tags assets={assets} href={hrefForTag} />
      <div className='thumbs'>{assets.map(
          (asset, idx) => <Thumb key={asset.id}
                                 asset={asset}
                                 formats={formats}
                                 handleClick={() => setCurrent(idx)} />
      )}</div>
    </div>;
  }
}


const Thumb = ({asset, formats, handleClick}) => {
  const s = asset.slug
      , ext = formats[asset.medium]['small'].ext
      , isVideo = asset.medium === 'video'
      , source = e => `/asset/small/${s.slice(0, 1)}/${s}.${e}`
      , initialSrc = source(isVideo ? 'png' : ext);
  return <span className='thumb' onClick={handleClick}>
    <img className={asset.medium}
         src={initialSrc}
         onMouseEnter={e => { if (isVideo) e.target.src = source(ext); }}
         onMouseLeave={e => { if (isVideo) e.target.src = initialSrc; }}/>
    {isVideo ? <span className='video-icon'>▶</span> : null}
  </span>;
}


// const handlers = useSwipeable({ onSwiped: (eventData) => eventHandler, ...config })
// return (<div {...handlers}> You can swipe here </div>)

const Asset = ({asset, formats}) => {
  const s = asset.slug
      , ext = formats[asset.medium]['medium'].ext
      , src = `/asset/medium/${s.slice(0, 1)}/${s}.${ext}`;
  const [similar, setSimilar] = useState([]);
  useEffect(() => {
    axios(`/rest/asset/${s}/similar/?hash=DIFF_6&max-diff=0.1`).then(res => setSimilar(res.data));
  }, [asset]);
  return <div className='asset'>
    <Tags assets={[asset]} startVisible={true} href={hrefForTag} />
    {
      asset.medium === 'video' ? <video autoPlay controls><source src={src} /></video> :
      asset.medium === 'audio' ? <audio autoPlay controls><source src={src} /></audio> :
                                 <img src={src} />
    }
    <div className='similar'>{
      similar.map(a => <Thumb key={a.id} asset={a} formats={formats} handleClick={null} />)
    }</div>
    <div className='icon-buttons'>
      <span className='icon-button'><span className='icon'>⚠</span></span>
      <span className='icon-button'><span className='icon'>🖉</span></span>
      <span className='icon-button'><span className='icon' style={{fontSize:'200%'}}>×</span></span>
      <span className='icon-button'><span className='icon'>⮢</span></span>
      <span className='icon-button'><span className='icon'>⮣</span></span>
      <span className='icon-button'><span className='icon'>⤿</span></span>
      <span className='icon-button'><span className='icon'>⤾</span></span>
      <span className='icon-button'><span className='icon'>⬌</span></span>
      <span className='icon-button'><span className='icon'>⬍</span></span>
      <span className='icon-button'><span className='icon'>⮮</span></span>
      <span className='icon-button'><span className='icon'>⮯</span></span>
      <span className='icon-button'><span className='icon'>🗑</span></span>
      <span className='icon-button'><span className='icon'>⛔</span></span>
      <span className='icon-button'><span className='icon'>🚫</span></span>
      <span className='icon-button'><span className='icon'>✏</span></span>
      <span className='icon-button'><span className='icon'>☠</span></span>
    </div>
  </div>;
}
