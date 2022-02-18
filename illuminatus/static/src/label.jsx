import {hsluvToHex} from 'hsluv'
import React, {useEffect, useState} from 'react'
import {useHistory, useLocation, useParams} from 'react-router-dom'

import {TagGroups, TagSelect} from './tags'
import {Breadcrumbs, Button, Spinner, Thumb, useAssets} from './utils'

import './label.styl'


const Tools = ({active, onBrowse, onDelete, onClear}) => (
  <div className='tools'>
    <Button name='exit' icon='✕' onClick={onBrowse} />
    <span className='spacer' />
    <Button name='delete' icon='🗑' disabled={active.length === 0} onClick={onDelete} />
    <span className='spacer' />
    <Button name='clear' icon='⛶' disabled={active.length === 0} onClick={onClear} />
  </div>)


const Label = ({refresh}) => {
  const hist = useHistory()
      , path = useLocation().pathname
      , query = useParams().query
      , {assets, loading} = useAssets(`/query/${query}`)
      , [thumbSize, setThumbSize] = useState(160)
      , [cursor, setCursor] = useState(-1)
      , [selected, setSelected] = useState({})
      , [activeAssets, setActiveAssets] = useState([])
      , [clickHandler, setClickHandler] = useState(() => null);

  const moveCursor = inc => setCursor(cur => {
    const colsPerRow = Math.floor(window.innerWidth / thumbSize)
        , nxt = Math.max(0, Math.min(cur + inc, assets.length - 1));
    if (Math.floor(cur / colsPerRow) !== Math.floor(nxt / colsPerRow))
      window.scrollBy(0, (inc > 0 ? 1 : -1) * thumbSize);
    return nxt;
  });

  const toggleSelected = idx => setSelected(sel => {
    if (sel[idx]) { delete sel[idx]; }
    else { sel[idx] = true; }
    return {...sel};
  });

  const deleteAssets = active => {
    if (window.confirm('Really delete?')) {
      Promise.all(
        active.map(({slug}) => fetch(`/asset/${slug}/`, {method: 'delete'}))
      ).then(() => hist.go(0));
    }
  };

  // When the cursor changes, update our click handler factory to use the
  // updated cursor value.
  useEffect(() => {
    // To use a function as a state variable, we have to wrap it in an empty
    // function. The actual thing we're setting is idx => {...}.
    setClickHandler(() => idx => ev => {
      if (ev.shiftKey) {
        const add = {};
        if (cursor < idx) {
          for (let i = cursor; i <= idx; i++) add[i] = true;
        } else {
          for (let i = cursor; i >= idx; i--) add[i] = true;
        }
        setSelected(sel => ({...sel, ...add}));
        setCursor(idx);
      } else {
        toggleSelected(idx);
        setCursor(idx);
      }
    });
  }, [cursor]);

  // When the selected set changes, update our "active" assets accordingly.
  useEffect(() => {
    const idxs = Object.keys(selected);
    setActiveAssets(idxs.length ? idxs.map(idx => assets[idx]) : []);
  }, [selected]);

  // When the state of the view changes, update our key-down handler. We use the
  // size of the thumbnails to move the cursor up/down, and the current cursor
  // value to toggle its selected state.
  useEffect(() => {
    const colsPerRow = Math.floor(window.innerWidth / thumbSize);
    const handler = ev => {
      if (ev.code === 'Escape') { setCursor(-1); hist.replace(`/browse/${query}`); }
      const input = document.querySelector('.tag-select input');
      if (input && input.matches(':focus')) return;
      if (ev.code === 'KeyN') setSelected({});
      if (ev.code === 'KeyT') { ev.preventDefault(); input.focus(); }
      if (ev.code === 'KeyX') toggleSelected(cursor);
      if ({ArrowLeft: 1, KeyH: 1}[ev.code]) moveCursor(-1);
      if ({ArrowRight: 1, KeyL: 1}[ev.code]) moveCursor(1);
      if ({ArrowUp: 1, KeyK: 1}[ev.code]) moveCursor(-colsPerRow);
      if ({ArrowDown: 1, KeyJ: 1}[ev.code]) moveCursor(colsPerRow);
      if (ev.code === 'Equal') setThumbSize(s => Math.max(80, Math.min(s + 20, 320)));
      if (ev.code === 'Minus') setThumbSize(s => Math.max(80, Math.min(s - 20, 320)));
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [cursor, query, thumbSize]);

  return <>
    <Breadcrumbs className='label'>
      {query.replace(/\/$/, '').replace(/\//g, ' & ')}
      <span className='divider'>»</span>
      Edit
    </Breadcrumbs>

    <Tools onBrowse={() => hist.replace(`/browse/${query}`)}
           onDelete={() => deleteAssets(activeAssets)}
           onClear={() => setSelected({})}
           active={activeAssets} />

    <TagSelect className='label'
               key={assets.map(a => a.slug).join('-')}
               assets={activeAssets.length ? activeAssets : assets}
               refresh={refresh} />

    {loading ? <Spinner /> : <>
      <TagGroups className='label'
                 assets={activeAssets.length ? activeAssets : assets}
                 hideEditable={true} />
      <div className={`label thumbs ${activeAssets.length ? 'selective' : ''}`}
           style={{
             gridTemplateColumns: `repeat(auto-fit, minmax(${thumbSize}px, 1fr))`,
             gridAutoRows: `${thumbSize}px`,
           }}>{assets.map(
          (asset, idx) => <Thumb key={asset.id}
                                 asset={asset}
                                 cursored={cursor === idx}
                                 selected={selected[idx]}
                                 handleClick={clickHandler(idx)} />)}</div>
    </>}
  </>;
}


export default Label
