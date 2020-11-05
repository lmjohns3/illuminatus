import axios from 'axios'
import React, {useEffect, useState} from 'react'
import {useHistory, useParams} from 'react-router-dom'

import {countAssetTags, Tags} from './tags'
import {Breadcrumbs, ConfigContext, Spinner, Thumb, useAssets} from './utils'

import './view.styl'


const Related = ({asset, how, title}) => {
  const hist = useHistory()
      , args = {content: 'alg=dhash-8', tag: 'min=0.5'}
      , {assets, loading} = useAssets(
        `/rest/asset/${asset.slug}/similar/${how}/?${args[how]}`);

  return <div className={`related ${how} thumbs view`}>
    {(title && (loading || assets.length > 0)) ? <h2>{title}</h2> : null}
    {loading ? <Spinner /> : assets.map(
      asset => <Thumb key={asset.id}
                      asset={asset}
                      handleClick={() => hist.push(`/view/${asset.slug}/`)} />)}
  </div>;
}


const Full = ({asset}) => <ConfigContext.Consumer>{config => {
  const ext = config.formats[asset.medium]['full'].ext
      , src = `/asset/full/${asset.slug.slice(0, 1)}/${asset.slug}.${ext}`;
  return <div className='view asset'>{
    asset.medium === 'video' ?
    <video key={asset.id} autoPlay controls><source src={src} /></video> :
    asset.medium === 'audio' ?
    <audio key={asset.id} autoPlay controls><source src={src} /></audio> :
    asset.medium === 'photo' ?
    <img key={asset.id} src={src} /> :
    null
  }</div>;
}}</ConfigContext.Consumer>;


const View = () => {
  const hist = useHistory()
      , slug = useParams().slug
      , defaultAsset = {medium: 'photo', tags: [], slug}
      , [startEditing, setStartEditing] = useState(null)
      , [asset, setAsset] = useState(defaultAsset);

  useEffect(() => {
    setAsset(defaultAsset);
    axios(`/rest/asset/${slug}/`).then(res => setAsset(res.data));

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
      <dt>Path</dt><dd>{asset.path}</dd>
      {asset.width ? <><dt>Size</dt><dd>{asset.width} x {asset.height}</dd></> : null}
      {asset.duration ? <><dt>Length</dt><dd>{`${Math.round(asset.duration)} sec`}</dd></> : null}
    </dl>
    <Related asset={asset} how='tag' title='Related' />
    <Related asset={asset} how='content' title='Duplicates' />
    {countAssetTags([asset]).map(
      group => group.tags.length === 0 ? null :
        <Tags key={group.icon}
              icon={group.icon}
              tags={group.tags}
              className='view'
              clickHandler={tag => () => hist.push(`/browse/${tag.name}/`)} />
    )}
    <div className='view tools'>
      <span className='button' onClick={startEditing}><span className='icon'>✏️</span></span>
    </div>
  </>;
}


export default View
