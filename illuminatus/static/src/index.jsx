import {BrowserRouter as Router, Route, Link} from "react-router-dom"
import ReactDOM from "react-dom"
import Dexie from "dexie"
import moment from "moment"

import Browse from "./browse"
import View from "./view"
import Edit from "./edit"
import Label from "./label"
import Cluster from "./cluster"

const Index = () => <div className="index">INDEX</div>


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

const DB = new Dexie("illuminatus")

DB.version(1).stores({
    state: "++id",
})

/*
class App extends Component {
    constructor() {
        super();
        this.state = {
            query: [],
            current: -1,
        };
    }

    setCurrent(idx) {
        this.setState(state => {
            if (state.editor && idx !== state.current) {
                DB.history.add({
                    item: state.playlist[state.current],
                    when: new Date().toISOString(),
                    action: "skip",
                });
            }
            this.audio.pause();
            if (0 <= idx && idx < state.playlist.length) {
                this.audio.src = `/item/${state.playlist[idx].id}/file`;
                this.audio.play();
                return {current: idx};
            } else {
                this.audio.src = "";
                return {current: -1};
            }
        });
    }

    render() {
        return (<>
            <ThumbsContainer />
            <Tagging />
            <Editing current={this.state.current}
                     setCurrent={this.setCurrent} /></>);
    }
}
*/
class Tagging extends Component {
    render() {
        return <div>Tagging</div>;
    }
}

const EditTools = () => (
  <ul>
    <li><a id="magic"><span className="dingbat">☘</span> Magic</a></li>
    <li className="sep"></li>
    <li><a id="brightness"><span className="dingbat">☀</span> Brightness</a></li>
    <li><a id="contrast"><span className="dingbat">◑</span> Contrast</a></li>
    <li><a id="saturation"><span className="dingbat">▧</span> Saturation</a></li>
    <li><a id="hue"><span className="dingbat">🖌</span> Hue</a></li>
    <li className="sep"></li>
    <li><a id="rotate"><span className="dingbat">↻</span> Rotate</a></li>
    <li><a id="cw-90"><span className="dingbat">⤵</span> Clockwise 90&deg;</a></li>
    <li><a id="ccw-90"><span className="dingbat">⤴</span> Counter-clockwise 90&deg;</a></li>
    <li><a id="hflip"><span className="dingbat">↔</span> Flip Horizontal</a></li>
    <li><a id="vflip"><span className="dingbat">↕</span> Flip Vertical</a></li>
    <li className="sep"></li>
    <li><a id="crop"><span className="dingbat">✂</span> Crop</a></li>
  </ul>)

const TagTools = ({tags}) => (
  <ul>
    {tags.map(tag => <li className="tag group-{tag.group}">{tag.name}</li>)}
    <li><input id="tag-input" type="text"/></li>
  </ul>)

const FilterTools = ({filters}) => (
    <ul>{filters.map(filter => (
      <li><a data-filter="{filter}" data-index="{index}">
        <span className="dingbat">✘</span> {filter}</a></li>
    ))}</ul>)

const StampTools = ({stamp}) => (
  <ul>
    <li><a id="">Y: {stamp.year}</a></li>
    <li><a id="">M: {stamp.month}</a></li>
    <li><a id="">D: {stamp.day}</a></li>
    <li><a id="">H: {stamp.hour}</a></li>
  </ul>)

class Editing extends Component {
    constructor(props) {
        super(props);

        this.state = {
            asset: {
                tags: [],
                filters: [],
                stamp: {},
            },
            format: {},
            uniq: 1,
            isRanging: false,
            isCropping: false,
            crop: {unit: "%"},
        };

        this.setCurrent = this.setCurrent.bind(this);
    }

    setCurrent() {
    }

    setCrop() {
    }

    render() {
        const {asset, format, uniq} = this.state;
        return (
<div id="editing">
  <div id="tools">
    <ul className="toolbar" id="basic-tools">
      <li><span className="dingbat">⚒</span> Edit <EditTools /></li>
      <li><span className="dingbat">🏷</span> Tags <TagTools tags={asset.tags} /></li>
      <li><span className="dingbat">☞</span> Filters <FilterTools filters={asset.filters} /></li>
      <li><span className="dingbat">⏰</span> {asset.stamp.title} <StampTools stamp={asset.stamp} /></li>
      <li><span id="path">{asset.path}</span></li>
    </ul>
    <ul className="toolbar" id="ephemeral-tools">
      <li id="cancel"><span className="dingbat">✘</span> Cancel</li>
      <li id="commit"><span className="dingbat">✔</span> Save</li>
      <li id="range"><input type="range" min="0" max="200" defaultValue="100" step="1"/><span id="range-value"></span></li>
    </ul>
  </div>
  <div id="workspace">
    <div id="grid"></div>
    { (asset.is_video) ? <video controls src="/thumb/{format.path}/{asset.thumb}.{format.ext}?{uniq}"/>
    : (asset.is_audio) ? <audio controls src="/thumb/{format.path}/{asset.thumb}.{format.ext}?{uniq}"/>
    : (asset.is_photo) ? <img src="/thumb/{format.path}/{asset.thumb}.{format.ext}?{this.state.uniq}"/>
    : ""}
    <ReactCrop src={this.state.asset.src} crop={this.state.crop} onChange={newCrop => this.setCrop(newCrop)} />
  </div>
</div>);
    }
}

class ThumbsContainer extends Component {
    constructor(props) {
        super(props);
    }

    render() {
        return <Thumbs assets={[{id: 1, medium: "photo", path: "foo", thumb: "thumb"}]}/>;
    }
}

const Tag = ({name, group}) => <li className="tag group-{group}">{name}</li>

const Thumbs = ({assets}) => (
    <ul id="thumbs">{assets.map(asset => (
        <li className="asset" key={asset.id}>
        <span className="cursor star">*</span>
        <img className={asset.medium} src={`/thumb/${asset.path}/${asset.thumb}.jpg`}/>
        </li>
    ))}</ul>)

const TagSelections = (props) => (
    <Select
    clearButton
    defaultSelected={options.slice(0, 5)}
    labelKey="name"
    multiple
    options={options}
    placeholder="Tags..." />)

/*
const Playlist = ({playlist, current, player, toggle, remove, clear, setCurrent}) => (
    <ul id="playlist">{playlist.map((item, i) => (
        <li key={i}>
        <PlaylistItem item={item}
                      active={current === i}
                      playPause={current === i ? toggle :  () => setCurrent(i)}
                      remove={() => remove(i)}
                      player={player} />
        </li>
    ))}{(playlist.length > 0) && <li id="clear" onClick={clear}>&times;</li>}</ul>
)

const Album = ({album, tracks, add}) => (
  <div className="album">
    <div onClick={tracks.length > 0 ? () => add(tracks) : null}
         className="art" style={{backgroundImage: `url(/album/${album.id}/art)`}}></div>
    <div onClick={tracks.length > 0 ? () => add(tracks) : null}
         className="title">{album.album}</div>
    <div onClick={tracks.length > 0 ? () => add(tracks) : null}
         className="artist">{album.albumartist}</div>
    <ul className="tracks">{tracks.map(track => {
        const title = <div className="title">{track.title}</div>;
        const artist = track.artist === track.albumartist ?
                       "" : <div className="artist">{track.artist}</div>;
        return <li className="track"
                   onClick={() => add([track])}
                   key={track.id}>{title}{artist}</li>;
    })}</ul>
  </div>)

const Song = ({song, add}) => (
  <div className="song" onClick={() => add([song])}>
    <div className="title">{song.title}</div>
    <div className="artist">{song.artist === song.albumartist ? "" : song.artist}</div>
  </div>)
*/

ReactDOM.render(
  <Router>
    <Route path="/view/:id"><View /></Route>
    <Route path="/edit/:id"><Edit /></Route>
    <Route path="/label/:id"><Label /></Route>
    <Route path="/cluster/:id"><Cluster /></Route>
    <Route path="/browse/:query"><Browse /></Route>
    <Route exact path="/"><Index /></Route>
  </Router>,
  document.getElementById("root"))
