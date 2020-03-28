import React, {useEffect, useState} from "react"
import {Link, useParams} from "react-router-dom"
import Select from "react-select"
import axios from "axios"

import Tags from "./tags"


const hrefForTag = (tag, path) => (tag.active
    ? path.replace(new RegExp(`/${tag.name}/`), "/")
    : `${tag.name}/`);


export default function View() {
  // Get format info for the app.
  const [formats, setFormats] = useState([]);
  useEffect(() => {
    axios("/rest/formats/").then(res => setFormats(res.data));
  }, []);

  // Get assets matching our view query.
  const query = useParams().query, [assets, setAssets] = useState([]);
  useEffect(() => {
    axios(`/rest/query/${query}`).then(res => setAssets(res.data));
  }, [query]);

  // Keep track if there is a single asset being viewed.
  const [viewIndex, setViewIndex] = useState(-1);
  let viewAsset = null;
  if ((0 <= viewIndex) && (viewIndex < assets.length)) {
    const asset = assets[viewIndex];
    viewAsset = <Asset asset={asset} formats={formats} />;
  }

  return <div className={`view ${viewAsset ? 'viewing' : 'browsing'}`}>
    <Tags assets={assets} href={hrefForTag} />
    <div className="thumbs">{assets.map(
        (asset, idx) => <Thumb key={asset.id}
                               asset={asset}
                               formats={formats}
                               handleClick={() => setViewIndex(idx)} />
    )}</div>
    {viewAsset}
  </div>;
}


const Thumb = ({asset, formats, handleClick}) => {
  const s = asset.slug
      , ext = formats[asset.medium]["small"].ext
      , isVideo = asset.medium === "video"
      , source = e => `/asset/small/${s.slice(0, 1)}/${s}.${e}`
      , initialSrc = source(isVideo ? "png" : ext);
  return <span className="thumb" onClick={handleClick}>
    <img className={asset.medium}
         src={initialSrc}
         onMouseEnter={e => { if (isVideo) e.target.src = source(ext); }}
         onMouseLeave={e => { if (isVideo) e.target.src = initialSrc; }}/>
    {isVideo ? <span className="video-icon">▶</span> : null}
  </span>;
}


const Asset = ({asset, formats}) => {
  const s = asset.slug
      , ext = formats[asset.medium]["medium"].ext
      , src = `/asset/medium/${s.slice(0, 1)}/${s}.${ext}`;
  const [similar, setSimilar] = useState([]);
  useEffect(() => {
    axios(`/rest/asset/${s}/similar/?hash=DIFF_6&max-diff=0.1`).then(res => setSimilar(res.data));
  }, [asset]);
  return <div className="asset">
    <Tags assets={[asset]} startVisible={true} href={null} />
    {
      asset.medium === "video" ? <video autoPlay controls><source src={src} /></video> :
      asset.medium === "audio" ? <audio autoPlay controls><source src={src} /></audio> :
                                 <img src={src} />
    }
    <div className="similar">{
      similar.map(a => <Thumb key={a.id} asset={a} formats={formats} handleClick={null} />)
    }</div>
  </div>;
}

// ✏🗑 ⛔
