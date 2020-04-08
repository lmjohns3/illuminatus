import axios from 'axios'
import React, {useEffect, useState} from 'react'

import {Spinner} from './utils'


const useAssets = (query, makeUrl) => {
  const limit = 64
      , [load, setLoad] = useState(() => () => {})
      , [assets, setAssets] = useState([])
      , [hasMore, setHasMore] = useState(true);

  // Redefine the load function whenever the number of loaded assets changes.
  useEffect(() => {
    const offset = assets.length
        , url = makeUrl(query, offset, limit)
        , func = () => axios(url).then(res => {
          setHasMore(res.data.length >= limit);
          setAssets(prevAssets => [...prevAssets, ...res.data]);
        });
    setLoad(() => func);
    if (offset === 0) func();
  }, [assets.length]);

  // Clear assets whenever the query changes.
  useEffect(() => { setAssets([]); }, [query]);

  return [assets, hasMore, load];
}


const useCurrent = (history, assets, hasMoreAssets, loadMoreAssets) => {
  const [current, setCurrent] = useState(null)
      , update = idx => {
        setCurrent(idx);
        history.replace(idx ? `#${idx}` : '#');
        if (hasMoreAssets && idx && idx > assets.length - 32) {
          loadMoreAssets();
        }
      };
  useEffect(() => { if (assets.length === 0) update(null); }, [assets.length]);
  useEffect(() => {
    const onKeyDown = ({key}) => {
      if (key === 'Escape') update(null);
      if (key === 'ArrowLeft' && current > 0) update(current - 1);
      if (key === 'ArrowRight' && current < assets.length - 1) update(current + 1);
    };
    if (current) {
      window.addEventListener('keydown', onKeyDown);
      return () => window.removeEventListener('keydown', onKeyDown);
    }
  }, [assets.length, current]);
  return [current, update];
}


export {useAssets, useCurrent}
