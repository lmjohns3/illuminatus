import React, {useEffect, useState} from 'react'
import ReactDOM from 'react-dom'
import {BrowserRouter, Route, Switch, useHistory} from 'react-router-dom'

import Edit from './edit'
import View from './view'
import Browse from './browse'
import Label from './label'

import {ConfigContext} from './config'
import {TagGroups} from './tags'
import {Spinner} from './utils'

import './base.styl'
import './index.styl'

const Index = () => {
  const hist = useHistory()
      , clickHandler = t => () => hist.push(`/browse/${t.name}/`);
  return <TagGroups className='index' clickHandler={clickHandler} />;
}


const App = () => {
  const [version, setVersion] = useState(0)
      , [config, setConfig] = useState({});

  useEffect(() => {
    fetch('/config/').then(res => res.json()).then(setConfig);
  }, [version]);

  const refresh = () => setVersion(n => n + 1);

  return (config && config.tags) ?
  <ConfigContext.Provider value={config}>
    <BrowserRouter>
      <Switch>
        <Route path='/label/:query([^?#]+)'><Label refresh={refresh} /></Route>
        <Route path='/browse/:query([^?#]+)'><Browse /></Route>
        <Route path='/edit/:slug'><Edit refresh={refresh} /></Route>
        <Route path='/view/:slug'><View /></Route>
        <Route path='/'><Index /></Route>
      </Switch>
    </BrowserRouter>
  </ConfigContext.Provider>
  : <Spinner />;
}

ReactDOM.render(<App />, document.getElementById('root'))
