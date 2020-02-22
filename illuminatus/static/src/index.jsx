import React from "react"
import {BrowserRouter as Router, Route, Link, Redirect, Switch} from "react-router-dom"
import ReactDOM from "react-dom"
import moment from "moment"

import DB from "./db"
import Browse from "./browse"
import View from "./view"
import Edit from "./edit"
import Label from "./label"
import Cluster from "./cluster"


const KEYS = {
  tab: 9, enter: 13, escape: 27, space: 32,
  insert: 45, delete: 46, backspace: 8,
  pageup: 33, pagedown: 34, end: 35, home: 36,
  left: 37, up: 38, right: 39, down: 40,
  "0": 48, "1": 49, "2": 50, "3": 51, "4": 52,
  "5": 53, "6": 54, "7": 55, "8": 56, "9": 57,
  a: 65, b: 66, c: 67, d: 68, e: 69, f: 70, g: 71, h: 72, i: 73,
  j: 74, k: 75, l: 76, m: 77, n: 78, o: 79, p: 80, q: 81, r: 82,
  s: 83, t: 84, u: 85, v: 86, w: 87, x: 88, y: 89, z: 90,
  "=": 187, "-": 189, "`": 192, "[": 219, "]": 221,
}

const Nav = () => <nav></nav>
const Index = () => <div className="index">INDEX</div>

ReactDOM.render(
<Router>
  <Nav />
  <Switch>
    <Route path="/browse/:query"><Browse /></Route>
    <Route path="/cluster/:id"><Cluster /></Route>
    <Route path="/label/:id"><Label /></Route>
    <Route path="/edit/:id"><Edit /></Route>
    <Route path="/view/:id"><View /></Route>
    <Route path="/"><Index /></Route>
  </Switch>
</Router>, document.getElementById("root"))
