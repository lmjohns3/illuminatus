import axios from 'axios'
import React, {useEffect, useState} from 'react'
import ReactDOM from 'react-dom'
import {BrowserRouter, Route, Switch, useHistory} from 'react-router-dom'

import Edit from './edit'
import View from './view'
import Browse from './browse'
import Label from './label'

import {countAssetTags, Tags} from './tags'
import {Spinner, ConfigContext} from './utils'

import './base.styl'
import './index.styl'

const Index = () => {
  const hist = useHistory();
  return <>
    <ConfigContext.Consumer>{config => (
      countAssetTags(config.tags.map(t => ({tags: [t.name]}))).map(
        group => <Tags key={group.icon}
                       icon={group.icon}
                       tags={group.tags}
                       className='index'
                       clickHandler={tag => () => hist.push(`/browse/${tag.name}/`)} />
    ))}</ConfigContext.Consumer>
  </>;
}


const App = () => {
  const [config, setConfig] = useState({});

  useEffect(() => { axios('/rest/config/').then(res => setConfig(res.data)); }, []);

  return !config.formats ? <Spinner /> :
  <ConfigContext.Provider value={config}>
    <BrowserRouter>
      <Switch>
        <Route path='/label/:query([^?#]+)'><Label /></Route>
        <Route path='/browse/:query([^?#]+)'><Browse /></Route>
        <Route path='/view/:slug'><View /></Route>
        <Route path='/edit/:slug'><Edit /></Route>
        <Route path='/'><Index /></Route>
      </Switch>
    </BrowserRouter>
  </ConfigContext.Provider>;
}

ReactDOM.render(<App />, document.getElementById('root'))
