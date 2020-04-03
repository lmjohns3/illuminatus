import axios from 'axios'
import moment from 'moment'
import React, {useEffect, useReducer, useState} from 'react'
import {BrowserView, MobileView, isBrowser, isMobile} from 'react-device-detect';
import InfiniteScroll from 'react-infinite-scroll-component'
import {useHistory, useParams} from 'react-router-dom'
import Select from 'react-select'
import { useSwipeable } from 'react-swipeable'

import DB from './db'
import Tags from './tags'


const hrefForTag = (tag, path) => {
  const part = `/${tag}/`;
  return path.indexOf(part) < 0 ? tag : path.replace(part, '/');
}


const useAssets = (query, limit = 20) => {
  const makeUrl = (off, lim = limit) => `/rest/query/${query}?lim=${lim}&off=${off}`
      , [url, setUrl] = useState(makeUrl(0, 100))
      , [assets, setAssets] = useState([])
      , [hasMoreAssets, setHasMoreAssets] = useState(true)
      , loadMoreAssets = () => {axios(url).then(res => {
        setUrl(makeUrl(assets.length + res.data.length));
        setHasMoreAssets(res.data.length >= limit);
        setAssets(prevAssets => [...prevAssets, ...res.data]);
      })};
  useEffect(loadMoreAssets, [query]);
  return [assets, hasMoreAssets, loadMoreAssets];
}


const useCurrent = (history, assets) => {
  const h = window.location.hash
      , hashCurrent = /#\d+/.test(h) ? parseInt(h.replace('#', '')) : null
      , [current, setCurrent] = useState(hashCurrent);
  const update = idx => { setCurrent(idx); history.replace(idx ? `#${idx}` : '#'); };
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
  return [current, update];
}


export default function View() {
  const [formats, setFormats] = useState([]);
  useEffect(() => {
    axios('/rest/formats/').then(res => setFormats(res.data));
  }, []);

  const [assets, hasMoreAssets, loadMoreAssets] = useAssets(useParams().query);
  const [current, setCurrent] = useCurrent(useHistory(), assets);
  const [thumbsScroll, setThumbsScroll] = useState(0);
  useEffect(() => { if (!current) window.scrollTo(0, thumbsScroll); }, [current]);

  // Show either the asset being viewed or thumbnails of all the assets.
  if (current && 0 <= current && current < assets.length) {
    return <Asset asset={assets[current]}
                  formats={formats}
                  close={() => setCurrent(null)} />;
  } else {
    return <>
      <Tags assets={assets} href={hrefForTag} />
      <InfiniteScroll className='thumbs'
                      dataLength={assets.length}
                      next={loadMoreAssets}
                      hasMore={hasMoreAssets}
                      loader={<Spinner/>}>
        {assets.map((asset, idx) => <Thumb key={asset.id}
                                           asset={asset}
                                           formats={formats}
                                           handleClick={() => {
                                             setThumbsScroll(window.scrollY);
                                             setCurrent(idx);
                                           }} />)}
      </InfiniteScroll>
    </>;
  }
}


const Thumb = ({asset, formats, handleClick}) => {
  const ext = formats[asset.medium]['small'].ext
      , isVideo = asset.medium === 'video'
      , source = e => `/asset/small/${asset.slug.slice(0, 1)}/${asset.slug}.${e}`
      , initialSrc = source(isVideo ? 'png' : ext);
  return <div className='thumb' style={{
    gridRow: 'span 3',
    gridColumn: `span ${asset.width > asset.height ? 4 : 3}`,
  }}>
    <img className={asset.medium}
         src={initialSrc}
         onClick={handleClick}
         onMouseEnter={({target}) => { if (isVideo) target.src = source(ext); }}
         onMouseLeave={({target}) => { if (isVideo) target.src = initialSrc; }}/>
    {isVideo ? <span className='video-icon'>▶</span> : null}
  </div>;
}


// const handlers = useSwipeable({ onSwiped: (eventData) => eventHandler, ...config })
// return (<div {...handlers}> You can swipe here </div>)

const useThumbs = (url, title, formats, handleClick) => {
  const [thumbs, setThumbs] = useState({assets: [], loading: false});

  useEffect(() => {
    setThumbs({assets: [], loading: true});
    axios(url).then(res => { setThumbs({assets: res.data, loading: false}); });
  }, [url]);

  return thumbs.loading ? <div><h2>{title}</h2><Spinner /></div> :
         thumbs.assets.length > 0 ? <div>
           <h2>{title}</h2>
           <div className={`thumbs ${title.toLowerCase()}`}>{
             thumbs.assets.map(a => <Thumb key={a.id} asset={a} formats={formats}
                                           handleClick={handleClick(a)} />)
           }</div>
         </div> : null;
}


const Asset = ({asset, formats, close}) => {
  const [viewAsset, setViewAsset] = useState(asset)
      , ext = formats[viewAsset.medium]['medium'].ext
      , src = `/asset/medium/${viewAsset.slug.slice(0, 1)}/${viewAsset.slug}.${ext}`;
  useEffect(() => setViewAsset(asset), [asset]);
  return <>
    <div className='icon-buttons'>
      <span className='icon-button' onClick={close}><span className='icon' style={{fontSize:'200%'}}>×</span></span>
      <span className='icon-button'><span className='icon'>🖉</span></span>
    </div>
    <Tags assets={[asset]} startVisible={true} href={hrefForTag} />
    <div className='asset'>
      <div className='view'>{
        viewAsset.medium === 'video' ?
        <video title={viewAsset.slug} autoPlay controls><source src={src} /></video> :
        viewAsset.medium === 'audio' ?
        <audio title={viewAsset.slug} autoPlay controls><source src={src} /></audio> :
        <img title={viewAsset.slug} src={src} />}
      </div>
      <div className='self'>
        <Thumb asset={asset} formats={formats} handleClick={() => setViewAsset(asset)} />
        <dl>
          <dt>ID</dt><dd>{asset.slug.slice(0, 8)}</dd>
          <dt>Path</dt><dd>{asset.path}</dd>
          <dt>Date</dt><dd>{moment(asset.stamp).format('MMMM Do YYYY')}</dd>
          <dt>Time</dt><dd>{moment(asset.stamp).format('h:mm:ss a')}</dd>
          {asset.width ? <><dt>Size</dt><dd>{asset.width} x {asset.height}</dd></> : null}
          {asset.duration ? <><dt>Duration</dt><dd>{asset.duration}</dd></> : null}
        </dl>
      </div>
      <div className='others'>
        {useThumbs(`/rest/asset/${asset.slug}/similar/tag/?lim=20&min=0.5`,
                   'Similar', formats, a => () => setViewAsset(a))}
        {useThumbs(`/rest/asset/${asset.slug}/similar/content/?alg=dhash-8&max=0.03`,
                   'Duplicates', formats, a => () => setViewAsset(a))}
      </div>
    </div>
  </>;
}

/*
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
