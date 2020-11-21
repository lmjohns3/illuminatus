import axios from 'axios'
import React, {useEffect, useState} from 'react'
import ReactDOM from 'react-dom'
import {BrowserRouter, Route, Switch, useHistory} from 'react-router-dom'

import Edit from './edit'
import View from './view'
import Browse from './browse'
import Label from './label'

import {TagsContext, TagGroups} from './tags'
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
      , [tags, setTags] = useState(null);

  useEffect(() => {
    axios('/tags/').then(res => setTags(res.data.tags));
  }, [version]);

  const refresh = () => setVersion(n => n + 1);

  return !tags ? <Spinner /> :
  <BrowserRouter>
    <TagsContext.Provider value={tags || []}>
      <Switch>
        <Route path='/label/:query([^?#]+)'><Label refresh={refresh} /></Route>
        <Route path='/browse/:query([^?#]+)'><Browse /></Route>
        <Route path='/edit/:slug'><Edit refresh={refresh} /></Route>
        <Route path='/view/:slug'><View /></Route>
        <Route path='/'><Index /></Route>
      </Switch>
    </TagsContext.Provider>
  </BrowserRouter>
}

ReactDOM.render(<App />, document.getElementById('root'))
