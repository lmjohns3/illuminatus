import axios from 'axios'
import React, {useEffect, useState} from 'react'
import {Link} from 'react-router-dom'


const ConfigContext = React.createContext('config')


const Breadcrumbs = ({className, children}) => (
  <h1 className={`breadcrumbs ${className || ''}`}>
    <Link to='/'>🏠</Link>
    <span className='divider'>»</span>
    {children}
  </h1>)


const Button = ({name, icon, disabled, onClick}) => (
  <span className={`button ${disabled ? 'disabled' : ''}`}
        title={name}
        onClick={disabled ? null : onClick}>
    <span className='icon'>{icon}</span>
  </span>)


const Spinner = () => {
  const style = {
    position: 'absolute',
    left: '0.4629em',
    bottom: '0',
    width: '0.074em',
    height: '0.2777em',
    borderRadius: '0.0555em',
    backgroundColor: 'transparent',
    transformOrigin: 'center -0.2222em',
    animation: 'spinner 1s infinite linear',
  };
  return <div style={{
    fontSize: '34px', position: 'relative', display: 'inline-block', width: '1em', height: '1em'}}>
    <div style={{...style, animationDelay: '0.00000s', transform: 'rotate(  0deg)'}}></div>
    <div style={{...style, animationDelay: '0.08333s', transform: 'rotate( 30deg)'}}></div>
    <div style={{...style, animationDelay: '0.16666s', transform: 'rotate( 60deg)'}}></div>
    <div style={{...style, animationDelay: '0.25000s', transform: 'rotate( 90deg)'}}></div>
    <div style={{...style, animationDelay: '0.33333s', transform: 'rotate(120deg)'}}></div>
    <div style={{...style, animationDelay: '0.41666s', transform: 'rotate(150deg)'}}></div>
    <div style={{...style, animationDelay: '0.50000s', transform: 'rotate(180deg)'}}></div>
    <div style={{...style, animationDelay: '0.58333s', transform: 'rotate(210deg)'}}></div>
    <div style={{...style, animationDelay: '0.66666s', transform: 'rotate(240deg)'}}></div>
    <div style={{...style, animationDelay: '0.75000s', transform: 'rotate(270deg)'}}></div>
    <div style={{...style, animationDelay: '0.83333s', transform: 'rotate(300deg)'}}></div>
    <div style={{...style, animationDelay: '0.91666s', transform: 'rotate(330deg)'}}></div>
  </div>;
}


const Thumb = ({asset, handleClick, cursored, selected}) => {
  const isVideo = asset.medium === 'video'
      , source = ext => `/asset/thumb/${asset.slug.slice(0, 1)}/${asset.slug}.${ext}`;
  return <div className={`thumb ${asset.medium} ${cursored ? 'cursored' : ''} ${selected ? 'selected' : ''}`}><ConfigContext.Consumer>{
    config => {
      const ext = config.formats[asset.medium]['thumb'].ext;
      return !asset.id ? <Spinner /> : <>
      <img src={source(isVideo ? 'png' : ext)}
           title={asset.tags.join(' ')}
           onClick={handleClick}
           onMouseEnter={({target}) => { if (isVideo) target.src = source(ext); }}
           onMouseLeave={({target}) => { if (isVideo) target.src = source('png'); }}/>
        {isVideo ? <span className='video-icon'>▶</span> : null}
      </>;
    }
  }</ConfigContext.Consumer></div>;
}


const useAssets = url => {
  const [state, setState] = useState({assets: [], loading: false});

  useEffect(() => {
    setState({assets: [], loading: true});
    axios(url).then(res => setState({assets: res.data, loading: false}));
  }, [url]);

  return state;
}


export {Breadcrumbs, Button, ConfigContext, Spinner, Thumb, useAssets}
