import React, {useEffect, useState} from "react"
import {Link, useParams} from "react-router-dom"
import Select from "react-select"
import axios from "axios"

import Tags from "./tags"


export default function View() {
  const [formats, setFormats] = useState([]);
  useEffect(() => {
    axios("/rest/formats/").then(res => setFormats(res.data));
  }, []);

  const query = useParams().query, [assets, setAssets] = useState([]);
  useEffect(() => {
    axios(`/rest/query/${query}`).then(res => setAssets(res.data.assets));
  }, [query]);

  if ((assets.length === 0) || (formats.length === 0)) return null;

  const getFormat = (size, medium) => {
    let match = null;
    formats.forEach(fmt => {
      if ((fmt.path === size) && (fmt.medium === medium)) {
        match = fmt;
      }
    });
    return match;
  };

  const tagHref = tag => {
    let href = `${tag.name}/`;
    if (tag.active)
      href = useLocation().pathname.replace(new RegExp(`/${tag.name}/`), "/");
    return href;
  };

  return <div className="view">
    <Tags assets={assets} tagHref={tagHref} />
    <div className="thumbs">{
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
  return <Link className="thumb" to={`/view/${ph.slice(0, 8)}/`}>
    <img className={asset.medium}
         src={initialSrc}
         onMouseEnter={e => { if (isVideo) e.target.src = source("webp"); }}
         onMouseLeave={e => { if (isVideo) e.target.src = initialSrc; }}/>
    {isVideo ? <span className="video-icon">▶</span> : null}
  </Link>;
}


const View = ({format, asset}) => {
  const ph = asset.path_hash
      , src = `/asset/medium/${ph.slice(0, 2)}/${ph}.${format.ext}`;
  return <div className="view">
    <Tags assets={[asset]} startVisible={true} tagHref={tag => `/browse/${tag.name}/`} />
    <div className="asset">{
      asset.medium === "video" ? <video autoPlay controls><source src={src} /></video> :
      asset.medium === "audio" ? <audio autoPlay controls><source src={src} /></audio> :
                                 <img src={src} />
    }</div>
    <div className="similar">
    </div>
  </div>;
}
