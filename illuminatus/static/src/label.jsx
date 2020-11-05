import axios from 'axios'
import {hsluvToHex} from 'hsluv'
import React, {useEffect, useState} from 'react'
import {useHistory, useLocation, useParams} from 'react-router-dom'
import {useSwipeable} from 'react-swipeable'

import {countAssetTags, patternForTag, Tags, TagSelect} from './tags'
import {Breadcrumbs, Button, ConfigContext, Spinner, Thumb, useAssets} from './utils'

import './label.styl'

const GRID_SIZE = 160


const Label = () => {
  const hist = useHistory()
      , path = useLocation().pathname
      , query = useParams().query
      , {assets, loading} = useAssets(`/rest/query/${query}`)
      , [cursor, setCursor] = useState(-1)
      , [selected, setSelected] = useState({})
      , [activeAssets, setActiveAssets] = useState([]);

  const moveCursor = inc => setCursor(cur => {
    const colsPerRow = Math.floor(window.innerWidth / GRID_SIZE)
        , nxt = Math.max(0, Math.min(cur + inc, assets.length - 1));
    if (Math.floor(cur / colsPerRow) !== Math.floor(nxt / colsPerRow))
      window.scrollBy(0, (inc > 0 ? 1 : -1) * GRID_SIZE);
    return nxt;
  });

  const toggleSelected = idx => setSelected(sel => {
    if (sel[idx]) { delete sel[idx]; }
    else { sel[idx] = true; }
    return {...sel};
  });

  useEffect(() => {
    const idxs = Object.keys(selected);
    if (idxs.length > 0) setActiveAssets(idxs.map(idx => assets[idx]));
    else if (cursor >= 0) setActiveAssets([assets[cursor]]);
    else setActiveAssets([]);
  }, [cursor, selected]);

  useEffect(() => {
    const colsPerRow = Math.floor(window.innerWidth / GRID_SIZE);
    const handler = ev => {
      const input = document.querySelector('.tag-select input');
      if (input && input.matches(':focus')) return;
      if (ev.code === 'Escape') hist.replace(`/browse/${query}`);
      if (ev.code === 'KeyX') toggleSelected(cursor);
      if (ev.code === 'KeyT') { ev.preventDefault(); input.focus(); }
      if ({ArrowLeft: true, KeyH: true}[ev.code]) moveCursor(-1);
      if ({ArrowRight: true, KeyL: true}[ev.code]) moveCursor(1);
      if ({ArrowUp: true, KeyK: true}[ev.code]) moveCursor(-colsPerRow);
      if ({ArrowDown: true, KeyJ: true}[ev.code]) moveCursor(colsPerRow);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [cursor]);

  const deleteAssets = active => {
    if (window.confirm('Really delete?')) {
      active.forEach(({slug}) => axios.delete(`/rest/asset/${slug}/`));
      hist.go(0);
    }
  };

  return <>
    <Breadcrumbs className='label'>
      {query.replace(/\/$/, '').replace(/\//g, ' & ')}
      <span className='divider'>»</span>
      Edit
    </Breadcrumbs>
    <div className='tools'>
      <Button name='exit' icon='⨉' onClick={() => hist.replace(`/browse/${query}`)} />
      <span className='spacer' />
      <Button name='delete'
              icon='🗑'
              disabled={activeAssets.length === 0}
              onClick={() => deleteAssets(activeAssets)} />
    </div>
    <TagSelect className='label' assets={assets} activeAssets={activeAssets} />
    {loading ? <Spinner /> : <>
      {countAssetTags(assets).map(
        group => (group.tags.length === 0 || group.index > 2) ? null :
          <Tags key={group.icon}
                className='label'
                icon={group.icon}
                tags={group.tags.filter(t => path.indexOf(`/${t.name}/`) < 0)} />)}
      <div className={`label thumbs ${activeAssets.length ? 'selective' : ''}`}>{assets.map(
          (asset, idx) => <Thumb key={asset.id}
                                 asset={asset}
                                 cursored={cursor === idx}
                                 selected={selected[idx]}
                                 handleClick={() => toggleSelected(idx)} />
      )}</div>
    </>}
  </>;
}


export default Label
