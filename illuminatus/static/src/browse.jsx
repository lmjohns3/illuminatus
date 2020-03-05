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
      if (fmt.path === size && fmt.medium === medium) match = fmt;
    });
    return match;
  };

  return <div>
    <Tags assets={assets} />
    <Thumbs assets={assets} getFormat={getFormat} />
  </div>;
}


const Thumbs = ({assets, getFormat}) => {
  return <div className="browse" style={{
  }}>{assets.map(asset => <Asset key={asset.id} asset={asset} getFormat={getFormat} />)}</div>;
}


const Asset = ({asset, getFormat}) => {
  const imageStyle = {
    maxHeight: "100px",
    maxWidth: "100px",
  };
  const ph = asset.path_hash
      , isVideo = asset.medium === "video"
      , fmt = getFormat("small", asset.medium)
      , source = ext => `/asset/small/${ph.slice(0, 2)}/${ph}.${ext}`
      , initialSrc = source(isVideo ? "png" : fmt.format.ext);
  return <div className="asset"><Link to={`/view/${asset.id}/`}>
    <img className={asset.medium}
         src={initialSrc}
         onMouseEnter={e => { console.log("enter", e.target); if (isVideo) e.target.src = source("gif"); }}
         onMouseLeave={e => { console.log("leave", e.target); if (isVideo) e.target.src = initialSrc; }}
         style={imageStyle} />
    {isVideo ? <span className="video-icon">▶</span> : null}
  </Link></div>;
}
