import axios from 'axios'
import moment from 'moment'
import React, {useEffect, useState} from 'react'
import {BrowserView, MobileView, isBrowser, isMobile} from 'react-device-detect';
import InfiniteScroll from 'react-infinite-scroll-component'
import {useHistory, useParams} from 'react-router-dom'
import Select from 'react-select'
import {useSwipeable} from 'react-swipeable'

import DB from './db'
import Tags from './tags'
import Controls from './edit'
import {useAssets, useCurrent} from './hooks'


export default function View() {
  const [formats, setFormats] = useState([]);
  useEffect(() => { axios('/rest/formats/').then(res => setFormats(res.data)); }, []);

  const query = useParams().query
      , hist = useHistory()
      , assetsUrl = (q, o, l) => `/rest/query/${q}?lim=${o === 0 ? 128 : l}&off=${o}`
      , [assets, hasMoreAssets, loadMoreAssets] = useAssets(query, assetsUrl)
      , [current, setCurrent] = useCurrent(hist, assets, hasMoreAssets, loadMoreAssets);

  const [thumbsScroll, setThumbsScroll] = useState(0);
  useEffect(() => { window.scrollTo(0, current ? 0 : thumbsScroll); }, [current]);

  const [isEditing, setIsEditing] = useState(false);

  // Show either the asset being viewed or thumbnails of all the assets.
  if (current && 0 <= current && current < assets.length) {
    return <>
      <Controls asset={assets[current]}
                close={() => setCurrent(null)}
                isEditing={isEditing}
                setIsEditing={setIsEditing} />
      <Tags assets={[assets[current]]} startVisible={true} href={tag => `/${tag}/`} />
      <Asset asset={assets[current]} formats={formats} />
    </>;
  } else {
    return <>
      <Tags assets={assets} startVisible={false} href={(tag, path) =>
        path.indexOf(`/${tag}/`) < 0 ? `${tag}/` : path.replace(`/${tag}/`, '/')} />
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
  return <div className='thumb'>
    <img className={asset.medium}
         src={initialSrc}
         onClick={handleClick}
         onMouseEnter={({target}) => { if (isVideo) target.src = source(ext); }}
         onMouseLeave={({target}) => { if (isVideo) target.src = initialSrc; }}/>
    {isVideo ? <span className='video-icon'>▶</span> : null}
  </div>;
}


const useThumbs = (url, title, formats, handleClick) => {
  const [thumbs, setThumbs] = useState({assets: [], loading: false});

  useEffect(() => {
    setThumbs({assets: [], loading: true});
    axios(url).then(res => { setThumbs({assets: res.data, loading: false}); });
  }, [url]);

  return thumbs.loading ? <Spinner /> :
         thumbs.assets.length > 0 ?
           <div className={`thumbs ${title.toLowerCase()}`}>{
             thumbs.assets.map(a => <Thumb key={a.id} asset={a} formats={formats}
                                           handleClick={handleClick(a)} />)
           }</div> : null;
}


const Asset = ({asset, formats, close, canEdit}) => {
  const [viewAsset, setViewAsset] = useState(asset)
      , [isEditing, setEditing] = useState(false)
      , ext = formats[viewAsset.medium]['medium'].ext
      , stamp = moment(asset.stamp.slice(0, 19))
      , src = `/asset/medium/${viewAsset.slug.slice(0, 1)}/${viewAsset.slug}.${ext}`;

  useEffect(() => setViewAsset(asset), [asset]);

  return <>
    <div className='asset'>{
      viewAsset.medium === 'video' ?
          <video key={viewAsset.id} autoPlay controls><source src={src} /></video> :
      viewAsset.medium === 'audio' ?
          <audio key={viewAsset.id} autoPlay controls><source src={src} /></audio> :
      viewAsset.medium === 'photo' ?
          <img key={viewAsset.id} src={src} /> : null}
      <table className='info'><tbody>
        <tr><td rowSpan='999'>
          <Thumb asset={asset} formats={formats} handleClick={() => setViewAsset(asset)} />
        </td><th>ID</th><td>{asset.slug.slice(0, 8)}</td></tr>
        <tr><th>Date</th><td>{stamp.format('MMMM Do YYYY')}</td></tr>
        <tr><th>Time</th><td>{stamp.format('h:mm a')}</td></tr>
        <tr>{asset.width ? <><th>Size</th><td>{asset.width} x {asset.height}</td></> : null}</tr>
        <tr>{asset.duration ? <><th>Length</th><td>{Math.round(asset.duration)}</td></> : null}</tr>
      </tbody></table>
    </div>
    {useThumbs(`/rest/asset/${asset.slug}/similar/tag/?lim=20&min=0.5`,
               'Similar', formats, a => () => setViewAsset(a))}
    {useThumbs(`/rest/asset/${asset.slug}/similar/content/?alg=dhash-8&max=0.06`,
               'Duplicates', formats, a => () => setViewAsset(a))}
  </>;
}


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
