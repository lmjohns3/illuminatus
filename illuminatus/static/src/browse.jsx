import axios from 'axios'
import React, {useEffect, useState} from 'react'
import {useHistory, useLocation, useParams} from 'react-router-dom'
import CreatableSelect from 'react-select/creatable'

import {countAssetTags, Tags} from './tags'
import {Breadcrumbs, Button, ConfigContext, Spinner, Thumb, useAssets} from './utils'

import './browse.styl'


const Browse = () => {
  const hist = useHistory()
      , path = useLocation().pathname
      , query = useParams().query
      , {assets, loading} = useAssets(`/rest/query/${query}`);

  useEffect(() => {
    const handler = ev => {
      if (ev.code === 'KeyE') {
        ev.preventDefault();
        hist.replace(`/label/${query}`);
      }
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
      {countAssetTags(assets).map(
        group => group.tags.length === 0 ? null :
          <Tags key={group.icon}
                className='browse'
                icon={group.icon}
                tags={group.tags.filter(t => path.indexOf(`/${t.name}/`) < 0)}
                clickHandler={tag => {
                  const key = `/${tag.name}/`, active = path.indexOf(key) >= 0;
                  return () => hist.push(active ? path.replace(key, '/') : `${tag.name}/`);
                }} />)}
      <div className='browse thumbs'>{assets.map(
        (asset, idx) => <Thumb key={asset.id}
                               asset={asset}
                               handleClick={() => hist.push(`/view/${asset.slug}/`)} />
      )}</div>
    </>}
  </>;
}


export default Browse
