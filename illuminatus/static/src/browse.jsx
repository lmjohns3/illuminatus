import React from "react"
import {useParams} from "react-router-dom"
import Select from "react-select"
import axios from "axios"

const Browse = () => <Browser query={useParams().query} />

export default Browse

class Browser extends React.Component {
  constructor(props) {
    super(props);
    this.state = {value: props.query};
    this.handleChange = this.handleChange.bind(this);
    this.handleSubmit = this.handleSubmit.bind(this);
  }

  handleChange(e) {
      this.setState({value: e.target.value});
  }

  handleSubmit(e) {
    e.preventDefault();
    if (this.state.value !== "") {
      window.location = `/browse/${this.state.value}/`;
    }
  }

  render() {
    return <div className="browse">
      <form onSubmit={this.handleSubmit}>
        <input type="text" value={this.state.value} onChange={this.handleChange} />
      </form>
      <Container query={this.props.query} />
    </div>;
  }
}

class Container extends React.Component {
  constructor(props) {
    super(props);
    this.state = {assets: []};
  }

  componentDidMount() {
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
      <Thumbs assets={this.state.assets} />
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
    background: "#999",
  };
  return <div className="tags" style={collectionStyle}>{tags.map(
      tag => <span className="tag" key={tag.id} style={itemStyle}>{tag.name}</span>
  )}</div>;
}

const Thumbs = ({assets}) => {
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
    borderRadius: "0.3rem",
    border: "solid 0.3rem #111",
  };
  return <div className="thumbs" style={collectionStyle}>{assets.map(
      asset => <div className="asset" key={asset.id} style={itemStyle}>
        <span className="cursor star" style={cursorStyle}>*</span>
        <img className={asset.medium}
             src={`/asset/thumb/${asset.id}/`}
             style={imageStyle}/>
      </div>
  )}</div>;
}
