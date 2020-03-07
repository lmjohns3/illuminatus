import React, {useEffect, useState} from "react"
import {Link, useParams} from "react-router-dom"
import Select from "react-select"
import axios from "axios"

import Tags from "./tags"


export default function View() {
  const [{format, asset}, setState] = useState({format: null, asset: null});
  const id = useParams().id;

  useEffect(() => {
    axios(`/rest/asset/${id}/`).then(res => {
      console.log("asset", res);
      const asset = res.data;
      axios("/rest/formats/").then(res => {
        console.log("formats", res);
        res.data.some(f => {
          if (f.path === "medium" && f.medium === asset.medium) {
            setState({asset: asset, format: f.format});
            return true;
          }
          return false;
        });
      });
    });
  }, [id]);

  if (!!!format || !!!asset) return null;

  const ph = asset.path_hash
      , src = `/asset/medium/${ph.slice(0, 2)}/${ph}.${format.ext}`;

  return <div className="view">
    <Tags assets={[asset]} startVisible={true} />
    <div className="asset">{
      asset.medium === "video" ? <video autoPlay controls><source src={src} /></video> :
      asset.medium === "audio" ? <audio autoPlay controls><source src={src} /></audio> :
                                 <img src={src} />
    }</div>
  </div>;
}
