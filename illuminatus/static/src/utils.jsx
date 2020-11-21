import axios from 'axios'
import React, {useEffect, useState} from 'react'
import {Link, useHistory, useLocation} from 'react-router-dom'


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


const Related = ({asset, how, title, className}) => {
  const hist = useHistory()
      , path = useLocation().pathname
      , args = {content: 'alg=dhash-8', tag: 'min=0.3'}
      , {assets, loading} = useAssets(
        `/asset/${asset.slug}/similar/${how}/?${args[how]}`);

  return <div className={`related ${how} thumbs ${className || ''}`}>
    {(title && (loading || assets.length > 0)) ? <h2>{title}</h2> : null}
    {loading ? <Spinner /> : assets.map(
      asset => <Thumb key={asset.id}
                      asset={asset}
                      handleClick={() => hist.push(`/${path.split(/\//)[1]}/${asset.slug}/`)} />)}
  </div>;
}


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
  const classes = [
    'thumb',
    asset.medium,
    cursored ? 'cursored' : '',
    selected ? 'selected' : '',
  ], src = m => `/asset/${asset.slug}/read/thumb/?m=${m ? '1' : '0'}`;
  return !asset.id ? <Spinner /> : <div className={classes.join(' ')}>
    <img src={src()}
         title={asset.tags.join(' ')}
         onClick={handleClick}
         onMouseEnter={({target}) => { target.src = src(true); }}
         onMouseLeave={({target}) => { target.src = src(); }}/>
    {asset.medium === 'video' ? <span className='video-icon'>▶</span> : null}
  </div>;
}


const useAssets = url => {
  const [state, setState] = useState({assets: [], loading: false});

  useEffect(() => {
    setState({assets: [], loading: true});
    axios(url).then(res => setState({assets: res.data, loading: false}));
  }, [url]);

  return state;
}


export {Breadcrumbs, Button, Related, Spinner, Thumb, useAssets}
