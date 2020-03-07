import React, {useEffect, useState} from "react"
import {Link, useParams} from "react-router-dom"
import axios from "axios"

import Tags from "./tags"


export default function Browse() {
  const [formats, setFormats] = useState([]);
  useEffect(() => {
    axios("/rest/formats/").then(res => setFormats(res.data));
  }, []);

  const query = useParams().query, [assets, setAssets] = useState([]);
  useEffect(() => {
    axios(`/rest/query/${query}`).then(res => setAssets(res.data.assets));
  }, [query]);

  const getFormat = (size, medium) => {
    let match = null;
    formats.forEach(fmt => {
      if ((fmt.path === size) && (fmt.medium === medium)) {
        match = fmt;
      }
    });
    return match;
  };

  if ((assets.length === 0) || (formats.length === 0)) return null;

  return <div className="browse">
    <Tags assets={assets} />
    <div class="thumbs">{
      assets.map(asset => <Thumb key={asset.id}
                                 asset={asset}
                                 format={getFormat("small", asset.medium).format} />)
    }</div>
  </div>;
}


const Thumb = ({asset, format}) => {
  const ph = asset.path_hash
      , isVideo = asset.medium === "video"
      , source = ext => `/asset/small/${ph.slice(0, 2)}/${ph}.${ext}`
      , initialSrc = source(isVideo ? "png" : format.ext);
  return <Link className="thumb" to={`/view/${asset.id}/`}>
    <img className={asset.medium}
         src={initialSrc}
         onMouseEnter={e => { if (isVideo) e.target.src = source("gif"); }}
         onMouseLeave={e => { if (isVideo) e.target.src = initialSrc; }}/>
    {isVideo ? <span className="video-icon">▶</span> : null}
  </Link>;
}
