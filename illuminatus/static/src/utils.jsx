const Spinner = () => {
  const bladeStyle = {
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
    <div style={{...bladeStyle, animationDelay: '0.00000s', transform: 'rotate(  0deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.08333s', transform: 'rotate( 30deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.16666s', transform: 'rotate( 60deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.25000s', transform: 'rotate( 90deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.33333s', transform: 'rotate(120deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.41666s', transform: 'rotate(150deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.50000s', transform: 'rotate(180deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.58333s', transform: 'rotate(210deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.66666s', transform: 'rotate(240deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.75000s', transform: 'rotate(270deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.83333s', transform: 'rotate(300deg)'}}></div>
    <div style={{...bladeStyle, animationDelay: '0.91666s', transform: 'rotate(330deg)'}}></div>
  </div>;
}


export {Spinner}
