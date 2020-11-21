import axios from 'axios'
import React, {useEffect, useState} from 'react'
import {useHistory, useLocation, useParams} from 'react-router-dom'
import CreatableSelect from 'react-select/creatable'

import {TagGroups} from './tags'
import {Breadcrumbs, Button, Spinner, Thumb, useAssets} from './utils'

import './browse.styl'


const Browse = () => {
  const hist = useHistory()
      , path = useLocation().pathname
      , query = useParams().query
      , [thumbSize, setThumbSize] = useState(160)
      , {assets, loading} = useAssets(`/query/${query}`);

  useEffect(() => {
    const handler = ev => {
      console.log(ev.code);
      if (ev.code === 'KeyE') hist.replace(`/label/${query}`);
      if (ev.code === 'Equal') setThumbSize(s => Math.max(80, Math.min(s + 20, 320)));
      if (ev.code === 'Minus') setThumbSize(s => Math.max(80, Math.min(s - 20, 320)));
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return <>
    <Breadcrumbs className='browse'>
      {query.replace(/\/$/, '').replace(/\//g, ' and ')}
    </Breadcrumbs>

    <div className='tools'>
      <Button name='select' icon='✏' onClick={() => hist.replace(`/label/${query}`)} />
    </div>

    {loading ? <Spinner /> : <>
      <TagGroups assets={assets}
                 className='browse'
                 clickHandler={tag => {
                   const key = `/${tag.name}/`, active = path.indexOf(key) >= 0;
                   return () => hist.push(active ? path.replace(key, '/') : `${tag.name}/`);
                 }} />
      <div className='browse thumbs' style={{
        gridTemplateColumns: `repeat(auto-fit, minmax(${thumbSize}px, 1fr))`,
        gridAutoRows: `${thumbSize}px`
      }}>{assets.map(
        (asset, idx) => <Thumb key={asset.id}
                               asset={asset}
                               handleClick={() => hist.push(`/view/${asset.slug}/`)} />
      )}</div>
    </>}
  </>;
}


export default Browse
