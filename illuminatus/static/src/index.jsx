import React, {useEffect} from 'react'
import {BrowserRouter, Route, useLocation} from 'react-router-dom'
import ReactDOM from 'react-dom'

import View from './view'
import Edit from './edit'
import Label from './label'
import Cluster from './cluster'

const Index = () => <div className='index'>INDEX</div>

const ScrollToTop = () => {
  useEffect(() => window.scrollTo(0, 0), [useLocation().pathname]);
  return null;
}

ReactDOM.render(
<BrowserRouter>
  <Route path='/view/:query([^?]*)'><View /></Route>
  <Route path='/cluster/:slug'><Cluster /></Route>
  <Route path='/label/:slug'><Label /></Route>
  <Route path='/edit/:slug'><Edit /></Route>
  <Route exact path='/'><Index /></Route>
</BrowserRouter>, document.getElementById('root'))
