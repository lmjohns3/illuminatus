import axios from 'axios'
import moment from 'moment'
import React, {useEffect, useReducer, useState} from 'react'
import {BrowserView, MobileView, isBrowser, isMobile} from 'react-device-detect';
import {useHistory, useParams} from 'react-router-dom'
import Select from 'react-select'
import { useSwipeable } from 'react-swipeable'

import DB from './db'
import Tags from './tags'


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
  const h = window.location.hash
      , hashCurrent = /#\d+/.test(h) ? parseInt(h.replace('#', '')) : null
      , history = useHistory()
      , [current, setCurrent] = useState(hashCurrent);
  const view = idx => { setCurrent(idx); history.replace(idx ? `#${idx}` : '#'); };
  useEffect(() => {
    const onKeyDown = ({key}) => {
      if (key === 'Escape') {
        view(null);
      } else if (current > 0 && (key === 'ArrowLeft' || key === 'ArrowUp')) {
        view(current - 1);
      } else if (current < assets.length - 1 && (key === 'ArrowRight' || key === 'ArrowDown')) {
        view(current + 1);
      }
    };
    if (current) {
      window.addEventListener('keydown', onKeyDown);
      return () => window.removeEventListener('keydown', onKeyDown);
    }
  }, [assets, current]);

  // Track the scroll state on the thumbs view. Gets set when a thumb gets a click.
  const [thumbsScroll, setThumbsScroll] = useState(0);
  useEffect(() => { if (!current) window.scrollTo(0, thumbsScroll); }, [current]);

  // Show either the asset being viewed or thumbnails of all the assets.
  if (current && 0 <= current && current < assets.length) {
    return <div className='view'>
      <Asset asset={assets[current]} formats={formats} close={() => view(null)} />
    </div>;
  } else {
    return <div className='browse'>
      <Tags assets={assets} href={hrefForTag} />
      <div className='thumbs'>{assets.map(
          (asset, idx) => <Thumb key={asset.id}
                                 asset={asset}
                                 formats={formats}
                                 handleClick={() => {
                                   setThumbsScroll(window.scrollY);
                                   view(idx);
                                 }} />
      )}</div>
    </div>;
  }
}


const Thumb = ({asset, formats, handleClick}) => {
  const ext = formats[asset.medium]['small'].ext
      , isVideo = asset.medium === 'video'
      , source = e => `/asset/small/${asset.slug.slice(0, 1)}/${asset.slug}.${e}`
      , initialSrc = source(isVideo ? 'png' : ext);
  return <span className='thumb' title={asset.slug} onClick={handleClick}>
    <img className={asset.medium}
         src={initialSrc}
         title={asset.slug}
         onMouseEnter={({target}) => { if (isVideo) target.src = source(ext); }}
         onMouseLeave={({target}) => { if (isVideo) target.src = initialSrc; }}/>
    {isVideo ? <span className='video-icon'>▶</span> : null}
  </span>;
}


// const handlers = useSwipeable({ onSwiped: (eventData) => eventHandler, ...config })
// return (<div {...handlers}> You can swipe here </div>)

const Asset = ({asset, formats, close}) => {
  // Asset being viewed at the moment.
  const [viewAsset, setViewAsset] = useState(asset)
      , ext = formats[viewAsset.medium]['medium'].ext
      , src = `/asset/medium/${viewAsset.slug.slice(0, 1)}/${viewAsset.slug}.${ext}`;

  // Loader for duplicate asset data.
  const [dupes, setDupes] = useState({assets: [], loading: false});
  useEffect(() => {
    setDupes({assets: [], loading: true});
    axios(`/rest/asset/${asset.slug}/similar/content/?alg=dhash-8&max=0.03`).then(
      res => { setDupes({assets: res.data, loading: false}); });
  }, [asset]);

  const dupeThumbs =
    dupes.loading ? <div><h2>Duplicates</h2><Spinner /></div> :
    dupes.assets.length > 0 ? <div>
      <h2>Duplicates</h2>
      <div className='thumbs dupes'>{
        dupes.assets.map(a => <Thumb key={a.id}
                                     asset={a}
                                     formats={formats}
                                     handleClick={() => setViewAsset(a)} />)
      }</div>
    </div> : null;

  // Loader for similar asset data.
  const [similar, setSimilar] = useState({assets: [], loading: false});
  useEffect(() => {
    setSimilar({assets: [], loading: true});
    axios(`/rest/asset/${asset.slug}/similar/tag/?lim=20&min=0.5`).then(res => {
      const slugs = {}, assets = []
      if (dupes.assets.forEach) {
        dupes.assets.forEach(a => { slugs[a.slug] = true; });
      }
      res.data.forEach(a => { if (!slugs[a.slug]) assets.push(a); });
      setSimilar({assets: assets, loading: false}); });
  }, [asset, dupes.loading]);

  const similarThumbs =
    similar.loading ? <div><h2>Similar</h2><Spinner /></div> :
    similar.assets.length > 0 ? <div>
      <h2>Similar</h2>
      <div className='thumbs similar'>{
        similar.assets.map(a => <Thumb key={a.id}
                                       asset={a}
                                       formats={formats}
                                       handleClick={() => setViewAsset(a)} />)
      }</div>
  </div> : null;

  return <div className='asset'>
    <Tags assets={[asset]} startVisible={true} href={hrefForTag} />
    <div className='view'>{
      viewAsset.medium === 'video' ?
      <video title={viewAsset.slug} autoPlay controls><source src={src} /></video> :
      viewAsset.medium === 'audio' ?
      <audio title={viewAsset.slug} autoPlay controls><source src={src} /></audio> :
      <img title={viewAsset.slug} src={src} />}
    </div>
    <div className='thumbs self'>
      <Thumb asset={asset} formats={formats} handleClick={() => setViewAsset(asset)} />
      <p>{asset.path}</p>
      <p>{asset.slug}</p>
      <p>{asset.stamp}</p>
      <p>{asset.width}x{asset.height}</p>
      {asset.duration ? <p>{`${asset.duration} sec`}</p> : null}
    </div>
    {similarThumbs}
    {dupeThumbs}
    <div className='icon-buttons'>
      <span className='icon-button' onClick={close}><span className='icon' style={{fontSize:'200%'}}>×</span></span>
    </div>
  </div>;
}

/*
      <span className='icon-button'><span className='icon'>🖉</span></span>
      <span className='icon-button'><span className='icon'>⚠</span></span>
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
*/


const Spinner = () => {
  const bladeStyle = {
    position: 'absolute',
    left: '0.4629em',
    bottom: '0',
    width: '0.074em',
    height: '0.2777em',
    borderRadius: '0.0555em',
    backgroundColor: 'transparent',
    transformOrigin: 'center -0.2222em',
    animation: 'spinner 1s infinite linear',
  };
  return <div style={{
    fontSize: '34px', position: 'relative', display: 'inline-block', width: '1em', height: '1em'}}>
    <div style={{...bladeStyle, animationDelay: '0.00000s', transform: 'rotate(  0deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.08333s', transform: 'rotate( 30deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.16666s', transform: 'rotate( 60deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.25000s', transform: 'rotate( 90deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.33333s', transform: 'rotate(120deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.41666s', transform: 'rotate(150deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.50000s', transform: 'rotate(180deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.58333s', transform: 'rotate(210deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.66666s', transform: 'rotate(240deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.75000s', transform: 'rotate(270deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.83333s', transform: 'rotate(300deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.91666s', transform: 'rotate(330deg)'}}></div>
  </div>;
}
