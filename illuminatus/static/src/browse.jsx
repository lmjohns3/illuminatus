import React from "react"
import {useParams} from "react-router-dom"
import Select from "react-select"
import axios from "axios"
import {hsluvToHex} from "hsluv"

export default Browse = () => <Container query={useParams().query} />

class Container extends React.Component {
  constructor(props) {
    super(props);
    this.state = {assets: [], formats: {}};
    this.computeAssetPath = this.computeAssetPath.bind(this);
  }

  computeAssetPath(size, asset) {
    const ph2 = asset.path_hash.slice(0, 2)
        , ph4 = asset.path_hash.slice(0, 4)
        , ph = asset.path_hash
        , fmt = this.state.formats[`${size}_${asset.medium}_format`]
    ;
    return `${fmt.path}/${ph2}/${ph4}/${ph}.${fmt.ext}`;
  }

  componentDidMount() {
    axios(`/rest/formats/`).then(
      res => this.setState({formats: res.data}));
    axios(`/rest/query/${this.props.query}`).then(
      res => this.setState({assets: res.data.assets}));
  }

  render() {
    const counts = {}, tags = [];
    this.state.assets.forEach(asset => {
      asset.tags.forEach(tag => {
        if (!counts[tag.name]) {
          tags.push(tag);
          counts[tag.name] = 0;
        }
        counts[tag.name]++;
      });
    });
    tags.sort((a, b) => (
      a.group[0] < b.group[0] ? -1 :
      a.group[0] > b.group[0] ? 1 :
      a.name < b.name ? -1 :
      a.name > b.name ? 1 :
      counts[a.name] < counts[b.name] ? -1 :
      counts[a.name] > counts[b.name] ? 1 :
      0));
    console.log(tags);
    return <div>
      <Tags tags={tags} counts={counts} />
      <Thumbs assets={this.state.assets}
              computeAssetPath={this.computeAssetPath} />
    </div>;
  }
}

const Tags = ({tags, counts}) => {
  const collectionStyle = {
    margin: "0",
    padding: "0.3rem",
  };
  const itemStyle = {
    display: "inline-block",
    padding: "0.2rem 0.4rem",
    margin: "0 0.2rem 0.2rem 0",
    borderRadius: "0.3rem",
    whiteSpace: "nowrap",
    cursor: "pointer",
    fontSize: "0.9rem",
  };
  const colorForGroup = g => (g <=  0 ? hsluvToHex([100, 100, 90]) :
                              g <= 12 ? hsluvToHex([130, 100, 90]) :
                              g <= 14 ? hsluvToHex([150, 100, 90]) :
                              g <= 21 ? hsluvToHex([180, 100, 90]) :
                              g <= 25 ? hsluvToHex([210, 100, 90]) :
                              g <= 32 ? hsluvToHex([240, 100, 90]) :
                              g <= 33 ? hsluvToHex([270, 100, 90]) :
                              g <= 34 ? hsluvToHex([300, 100, 90]) :
                                        hsluvToHex([0, 100, 90]));
  return <div className="tags" style={collectionStyle}>{tags.map(
      tag => <span className={`tag`} key={tag.id} style={{...itemStyle,
                   backgroundColor: colorForGroup(tag.group[0])}}
             >{tag.name}</span>
  )}</div>;
}

const Thumbs = ({assets, computeAssetPath}) => {
  const collectionStyle = {
    padding: "0 1rem 1rem 0",
    display: "flex",
    flexFlow: "row wrap",
    alignItems: "center",
  };
  const itemStyle = {
    flex: "0 0 100px",
    maxHeight: "100px",
    maxWidth: "100px",
    margin: "1rem 0 0 1rem",
    cursor: "pointer",
    position: "relative",
    textAlign: "center",
  };
  const cursorStyle = {
    position: "absolute",
    textShadow: "#111 0px 0px 2px, #111 0px 0px 2px, #111 0px 0px 2px",
    display: "none",
    fontSize: "2em",
    fontWeight: "bold",
  };
  const imageStyle = {
    maxHeight: "100px",
    maxWidth: "100px",
  };
  return <div className="thumbs" style={collectionStyle}>{assets.map(
      asset => <div className="asset" key={asset.id} style={itemStyle}>
        <span className="cursor star" style={cursorStyle}>*</span>
        <img className={asset.medium}
             src={`/asset/${computeAssetPath("small", asset)}`}
             style={imageStyle}/>
      </div>
  )}</div>;
}
