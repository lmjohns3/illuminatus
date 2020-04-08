import React, {useEffect} from 'react'
import {BrowserRouter, Route, useLocation} from 'react-router-dom'
import ReactDOM from 'react-dom'

import View from './view'

ReactDOM.render(
<BrowserRouter>
  <Route path='/:query([^?#]*)'><View /></Route>
</BrowserRouter>, document.getElementById('root'))
