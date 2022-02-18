import React, {useEffect, useState} from 'react'
import {useHistory, useParams} from 'react-router-dom'

import {TagGroups} from './tags'
import {Breadcrumbs, Related, Spinner, Thumb, useAssets} from './utils'

import './view.styl'


const Full = ({asset}) => {
  const src = `/asset/${asset.slug}/read/full/`;
  return <div className='view asset'>{
    asset.medium === 'video' ?
    <video key={asset.id} autoPlay controls><source src={src} /></video> :
    asset.medium === 'audio' ?
    <audio key={asset.id} autoPlay controls><source src={src} /></audio> :
    asset.medium === 'photo' ?
    <img key={asset.id} src={src} /> :
    null
  }</div>;
}


const View = () => {
  const hist = useHistory()
      , slug = useParams().slug
      , defaultAsset = {medium: 'photo', tags: [], slug}
      , [startEditing, setStartEditing] = useState(null)
      , [asset, setAsset] = useState(defaultAsset);

  useEffect(() => {
    window.scrollTo(0, 0);

    setAsset(defaultAsset);
    fetch(`/asset/${slug}/`).then(res => res.json()).then(setAsset);

    const edit = () => hist.replace(`/edit/${slug}/`);
    setStartEditing(() => edit);

    const handler = ev => {
      if (ev.code === 'KeyE') {
        ev.preventDefault();
        return edit();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [slug]);

  return <>
    <Breadcrumbs className='view'>{slug.slice(0, 12)}</Breadcrumbs>
    <Full asset={asset} />
    <dl className='view info'>
      <dt>Path</dt><dd id='path' onClick={
        () => window.getSelection().selectAllChildren(document.getElementById('path'))
      }>{asset.path}</dd>
      {asset.width ? <><dt>Size</dt><dd>{asset.width} x {asset.height}</dd></> : null}
      {asset.duration ? <><dt>Length</dt><dd>{`${Math.round(asset.duration)} sec`}</dd></> : null}
    </dl>
    <Related asset={asset} how='tag' title='Related' className='view' />
    <Related asset={asset} how='content' title='Duplicates' className='view' />
    <TagGroups assets={[asset]}
               className='view'
               clickHandler={tag => () => hist.push(`/browse/${tag.name}/`)} />
    <div className='view tools'>
      <span className='button' onClick={startEditing}><span className='icon'>✏️</span></span>
    </div>
  </>;
}


export default View
